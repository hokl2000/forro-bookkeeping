"""Glue between the web page and our Python code.

Every function returns JSON text, so the page never sees a Python traceback:
a wrong file gives a plain message the treasurer can act on.
"""
import csv
import json
import warnings
from datetime import datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from classify import bookings_for
from read_bank import read_bank
from read_mobilepay import KEEP, read_mobilepay, transfers
from read_zettle import read_zettle
from event_types import EVENT_TYPES, NO_EVENT
from events import INSTRUCTOR, check_contract, expected_instructor_payment, parse_number, profit
from post_types import POST_TYPES
from review import CATEGORIES
from year_end import financial_year

warnings.filterwarnings("ignore", message="Workbook contains no default style")

BANK_HEADER = ["Dato", "Tekst", "Rente fra", "Beløb", "Saldo"]
ZETTLE_HEADER = ["Afregningsdato", "Betalingsdato", "Reference", "Type", "Netto", "Saldo"]
ZETTLE_TYPES = {"Kortbetaling", "Gebyr", "Udbetaling til bankkonto"}


def result(ok, message, preview=None):
    return json.dumps({"ok": ok, "message": message, "preview": preview or []})


def check_bank(path):
    """The bank's 'Eksporter til CSV' file."""
    try:
        with open(path, encoding="cp1252", newline="") as f:
            header = next(csv.reader(f, delimiter=";"), [])
    except (UnicodeDecodeError, OSError):
        return result(False, "This is not a CSV file. In the bank, choose 'Eksporter til CSV'.")
    if header[:5] != BANK_HEADER:
        return result(False, "This doesn't look like the bank file: the first line should be "
                             "Dato;Tekst;Rente fra;Beløb;Saldo. In the bank, choose 'Eksporter til CSV'.")
    try:
        lines = read_bank(path)
    except ValueError:
        return result(False, "The bank file has an amount that can't be read. Was it opened "
                             "and saved in Excel? Download it again from the bank.")
    if not lines:
        return result(False, "The bank file has no lines.")
    years = sorted({financial_year(datetime.strptime(l["date"], "%d.%m.%Y").date()) for l in lines})
    if len(years) > 1:
        return result(False, f"The bank file covers more than one financial year ({', '.join(years)}). "
                             "In the bank, choose 1 August – 31 July and export again.")
    for newer, older in zip(lines, lines[1:]):          # newest first
        if round(older["balance"] + newer["amount"], 2) != round(newer["balance"], 2):
            return result(False, f"The bank balance doesn't add up at {newer['date']} – a line seems "
                                 "to be missing from the bank file. Download it again from the bank.")
    preview = [[l["date"], l["text"], f"{l['amount']:.2f}"] for l in lines[:3]]
    return result(True, f"Bank file OK: {len(lines)} lines, "
                        f"{lines[-1]['date']} – {lines[0]['date']}.", preview)


def check_mobilepay(path):
    """MobilePay's transactions report (CSV). Names are never shown."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            header = next(csv.reader(f, delimiter=";"), [])
    except (UnicodeDecodeError, OSError):
        return result(False, "This doesn't look like MobilePay's transactions report (CSV). "
                             "In MobilePay, download the transactions report.")
    missing = [col for col in KEEP if col not in header]
    if missing:
        return result(False, "This doesn't look like MobilePay's transactions report: "
                             f"column(s) missing: {', '.join(missing)}.")
    lines = read_mobilepay(path)
    if not lines:
        return result(False, "The MobilePay file has no payments.")
    payments = [l for l in lines if l["type"] == "Betaling"]
    preview = [[l["date"], l["time"], f"{l['amount']:.2f}", l["category"]] for l in payments[:3]]
    return result(True, f"MobilePay file OK: {len(payments)} payments, "
                        f"{len(transfers(lines))} transfers to the bank.", preview)


def check_zettle(path):
    """Zettle's statement (xlsx) - not the 'PayPal POS Sales Report'."""
    try:
        wb = load_workbook(path, read_only=True)
        rows = list(wb.active.iter_rows(values_only=True))
        wb.close()  # read-only workbooks keep the file open until closed (Windows locks it)
    except Exception:
        return result(False, "This is not an Excel file. In Zettle, download the statement (xlsx).")
    if not rows or list(rows[0][:6]) != ZETTLE_HEADER:
        return result(False, "This doesn't look like the Zettle statement. Choose the statement "
                             "with one line per card payment, fee and payout – not the "
                             "'PayPal POS Sales Report', which only has totals.")
    for n, row in enumerate(rows[1:], start=2):
        kind = row[3] if len(row) > 3 else None
        if (kind not in ZETTLE_TYPES or not isinstance(row[0], datetime)
                or (kind == "Kortbetaling" and not isinstance(row[1], datetime))):
            return result(False, f"Line {n} of the Zettle statement can't be read. "
                                 "Download the statement again from Zettle.")
    try:
        payouts = read_zettle(path)
    except ValueError as error:
        return result(False, f"The Zettle statement doesn't add up: {error}")
    if not payouts:
        return result(False, "The Zettle statement has no payouts to the bank.")
    preview = [[f"{p['date']:%d.%m.%Y}", f"{p['to_bank']:.2f}", f"{len(p['payments'])} payments"]
               for p in payouts[:3]]
    return result(True, f"Zettle statement OK: {len(payouts)} payout(s) to the bank.", preview)


def make_bookings(bank_path, mobilepay_path, zettle_path):
    """All bookings, as run.py makes them. category "" = the treasurer decides.
    "line" = the bank line's position in the bank file (0 = newest), shared by its split rows."""
    mp = transfers(read_mobilepay(mobilepay_path))
    payouts = read_zettle(zettle_path)
    bookings = []
    for n, line in enumerate(read_bank(bank_path)):
        for b in bookings_for(line, mp, payouts):
            b["line"] = n
            bookings.append(b)
    return json.dumps(bookings)


def categories():
    """The category list for the page's dropdown, alphabetical."""
    return json.dumps(sorted(CATEGORIES))


def events():
    """Event suggestions (alphabetical) and the categories that never get an event."""
    return json.dumps({"events": sorted(EVENT_TYPES), "no_event": sorted(NO_EVENT)})


def event_of(b):
    """The event written for a booking: none for fees and running costs."""
    return "" if b["category"] in NO_EVENT else str(b.get("event", "")).strip()


def new_events(bookings_json):
    """Event names the treasurer typed that are not in the 'event types' tab yet."""
    names = {event_of(b) for b in json.loads(bookings_json)} - {""}
    return json.dumps(sorted(names - set(EVENT_TYPES)))


def check_review(bookings_json):
    """The same rules as read_review.py: every line needs a category from the list.
    Returns ok + a plain message + one problem per line (row numbers as on the page)."""
    problems = []
    for n, b in enumerate(json.loads(bookings_json), start=1):
        if not b["category"]:
            problems.append(f"Line {n} ({b['date']}, {b['amount']:.2f}): no category yet.")
        elif b["category"] not in CATEGORIES:
            problems.append(f"Line {n}: '{b['category']}' is not a category – pick one from the list.")
    if problems:
        return result(False, f"{len(problems)} line(s) still need a category.", problems)
    return result(True, "Every line has a category.")


def instructor_check(bookings_json, contracts_json):
    """For every event with a Dance teacher costs line: paid vs what the contract says.
    A warning only - there can be good reasons (paid in two parts, or in another year)."""
    bookings, contracts = json.loads(bookings_json), json.loads(contracts_json)
    rows, untagged = [], 0
    names = sorted({event_of(b) for b in bookings if b["category"] == INSTRUCTOR} - {""})
    untagged = sum(1 for b in bookings if b["category"] == INSTRUCTOR and not event_of(b))
    for name in names:
        lines = [b for b in bookings if event_of(b) == name]
        paid = round(-sum(b["amount"] for b in lines if b["category"] == INSTRUCTOR), 2)
        contract = contracts.get(name, {"percent": "", "fixed": ""})
        errors = check_contract(contract)
        row = {"event": name, "paid": paid, "percent": contract.get("percent", ""),
               "fixed": contract.get("fixed", "")}
        if errors:
            row.update(status="todo", message=errors[0].capitalize() + ".")
        else:
            expected = expected_instructor_payment(contract, lines)
            how = (f"fixed amount" if parse_number(contract.get("fixed", "")) is not None
                   else f"{parse_number(contract['percent']):g} % of profit {profit(lines):.2f}")
            if expected == paid:
                row.update(status="ok", message=f"✓ Paid {paid:.2f} – matches the contract ({how}).")
            else:
                row.update(status="warn", message=f"Paid {paid:.2f} – the contract says {expected:.2f} "
                                                  f"({how}). Check before you download.")
        rows.append(row)
    note = (f"{untagged} Dance teacher costs line(s) have no event – add the event so the "
            "payment can be checked." if untagged else "")
    return json.dumps({"rows": rows, "note": note})


def check_statements(bookings_json, opening, closing):
    """The checks before the Statements file is made (Holger, 16 Nov 2026). Every line needs a
    category: the Overview tab adds up column H per post type (SUMIF), so a row without one
    is left out of every total."""
    bookings = json.loads(bookings_json)
    review = json.loads(check_review(bookings_json))
    if not review["ok"]:
        missing = [str(n) for n, b in enumerate(bookings, start=1) if b["category"] not in CATEGORIES]
        return result(False, f"{len(missing)} line(s) still need a category: line "
                             f"{', '.join(missing)}. Not finished? Use Save progress.")
    years = sorted({financial_year(datetime.strptime(b["date"], "%d.%m.%Y").date()) for b in bookings})
    if len(years) > 1:
        return result(False, f"The lines cover more than one financial year ({', '.join(years)}).")
    booked = round(opening + sum(b["amount"] for b in bookings), 2)
    if booked != round(closing, 2):
        return result(False, f"The bookings end at {booked:.2f}, but the bank ends at {closing:.2f}. "
                             "Please tell Holger.")
    return result(True, f"Checks OK: every line has a category, one financial year ({years[0]}), "
                        f"and the bookings end at the bank's balance {closing:.2f}.")


STATEMENTS_HEADER = ["Receipt number", "From Account", "To Account", "Dato", "Status",
                     "Beløb", "Saldo", "Post typer", "Event", "Tekst"]


def balances(bank_path):
    """Opening balance (before the oldest bank line) and closing balance (after the newest)."""
    bank = read_bank(bank_path)                       # newest first
    oldest = bank[-1]
    return json.dumps({"opening": round(oldest["balance"] - oldest["amount"], 2),
                       "closing": round(bank[0]["balance"], 2)})


def write_statements(bookings_json, opening, out_path):
    """The year's rows in the layout of the Statements tab: oldest first, G1 = opening balance,
    Saldo as numbers (running balance - Holger's decision A: pasting into Google Sheets keeps
    numbers, not formulas), Danish post types, split rows without receipt number and date."""
    bookings = json.loads(bookings_json)

    wb = Workbook()
    ws = wb.active
    ws.title = "Statements"
    ws["G1"] = opening
    ws.append(STATEMENTS_HEADER)
    for cell in ws[2]:
        cell.font = Font(bold=True)

    row, previous_line, saldo = 3, None, opening
    for b in sorted(bookings, key=lambda b: -b["line"]):   # oldest bank line first, split order kept
        first = b["line"] != previous_line
        previous_line = b["line"]
        ws.cell(row, 1, int(b["receipt"]) if first and str(b.get("receipt", "")).isdigit()
                else (b.get("receipt") or None) if first else None)
        if first:
            day = datetime.strptime(b["date"], "%d.%m.%Y")
            ws.cell(row, 4, day).number_format = "dd/mm/yyyy"
        ws.cell(row, 6, b["amount"])
        saldo = round(saldo + b["amount"], 2)
        ws.cell(row, 7, saldo)
        ws.cell(row, 8, POST_TYPES.get(b["category"], "") or None)
        ws.cell(row, 9, event_of(b) or None)
        ws.cell(row, 10, b.get("comment") or None)
        row += 1
    for col, width in zip("ABCDEFGHIJ", (15, 14, 14, 12, 8, 11, 11, 30, 18, 30)):
        ws.column_dimensions[col].width = width
    wb.save(out_path)
    return json.dumps({"rows": row - 3, "opening": opening})


# The progress file: the treasurer's work so far, so she can continue on any computer
# without uploading the bank, MobilePay and Zettle files again (Holger's decision 16 Nov).
PROGRESS_MARK = "Forró Copenhague – bookkeeping progress"
PROGRESS_HEADER = ["Bank line", "Receipt", "Date", "Text", "Amount", "Category", "Event", "Comment",
                   "Automatic category", "Why (automatic)"]
PROGRESS_KEYS = ["line", "receipt", "date", "text", "amount", "category", "event", "comment",
                 "code_category", "reason"]
PROGRESS_VERSION = 2   # 2 = with Event (16 Nov 2026)
NOT_PROGRESS = ("This is not a progress file from this page. Choose the file called "
                "'Forro progress <date>.xlsx' that you saved with the 'Save progress' button.")


def write_progress(bookings_json, opening, closing, saved, out_path, contracts_json="{}"):
    """Sheet 'Info' says what the file is and holds the bank balances; sheet 'Lines' holds the
    review table. saved = the time on the treasurer's computer, given by the page. Plain cells, so the file can be opened and read - but not edited (see read_progress)."""
    wb = Workbook()
    info = wb.active
    info.title = "Info"
    for row in ([PROGRESS_MARK], ["Version", PROGRESS_VERSION], ["Saved", saved],
                ["Opening balance", opening], ["Closing balance", closing],
                ["Note", "Make changes on the page, not in this file."]):
        info.append(row)
    lines = wb.create_sheet("Lines")
    lines.append(PROGRESS_HEADER)
    for b in json.loads(bookings_json):
        lines.append([b.get(k) if b.get(k) != "" else None for k in PROGRESS_KEYS])
    for col, width in zip("ABCDEFGHIJ", (10, 10, 12, 30, 11, 30, 20, 30, 30, 40)):
        lines.column_dimensions[col].width = width
    info.column_dimensions["A"].width = 40
    sheet = wb.create_sheet("Contracts")
    sheet.append(["Event", "Contract %", "Fixed amount"])
    for name, c in sorted(json.loads(contracts_json).items()):
        sheet.append([name, c.get("percent") or None, c.get("fixed") or None])
    sheet.column_dimensions["A"].width = 30
    wb.save(out_path)
    return json.dumps({"lines": len(json.loads(bookings_json))})


def read_progress(path):
    """Back to the page's bookings. Refuses anything that isn't an unchanged progress file:
    the amounts must still lead from the opening to the closing balance."""
    try:
        wb = load_workbook(path, read_only=True)
    except Exception:
        return result(False, NOT_PROGRESS)
    try:
        info = {r[0]: r[1] if len(r) > 1 else None
                for r in wb["Info"].iter_rows(values_only=True) if r and r[0]}
        rows = list(wb["Lines"].iter_rows(values_only=True))
        contracts = {}
        if "Contracts" in wb.sheetnames:
            for r in list(wb["Contracts"].iter_rows(values_only=True))[1:]:
                if r and r[0]:
                    contracts[str(r[0])] = {"percent": "" if r[1] is None else f"{r[1]:g}" if isinstance(r[1], (int, float)) else str(r[1]),
                                            "fixed": "" if r[2] is None else f"{r[2]:g}" if isinstance(r[2], (int, float)) else str(r[2])}
    except Exception:
        return result(False, NOT_PROGRESS)
    finally:
        wb.close()  # always close: Windows locks a file that is still open
    if PROGRESS_MARK in info and info.get("Version") == 1:
        return result(False, "This progress file was saved before the Event column was added "
                             "(16 Nov 2026), so it can't be read. Start again from the bank file.")
    if PROGRESS_MARK not in info or info.get("Version") != PROGRESS_VERSION or not rows \
            or list(rows[0][:len(PROGRESS_HEADER)]) != PROGRESS_HEADER:
        return result(False, NOT_PROGRESS)
    opening, closing = info.get("Opening balance"), info.get("Closing balance")
    bookings = []
    for n, row in enumerate(rows[1:], start=2):
        if not any(row):
            continue
        b = {k: ("" if v is None else v) for k, v in zip(PROGRESS_KEYS, row)}
        if not isinstance(b["line"], int) or not isinstance(b["amount"], (int, float)) \
                or isinstance(b["amount"], bool):
            return result(False, f"Row {n} of the progress file has been changed and can't be read. "
                                 "Use an earlier progress file, or start again from the bank file.")
        b["amount"] = float(b["amount"])
        for k in ("receipt", "date", "text", "category", "event", "comment", "code_category", "reason"):
            b[k] = str(b[k])
        bookings.append(b)
    if not isinstance(opening, (int, float)) or not isinstance(closing, (int, float)) or not bookings:
        return result(False, NOT_PROGRESS)
    if round(opening + sum(b["amount"] for b in bookings), 2) != round(closing, 2):
        return result(False, "The amounts in this progress file no longer add up to the bank "
                             "balance, so it has been changed. Use an earlier progress file, "
                             "or start again from the bank file.")
    done = sum(1 for b in bookings if b["category"] in CATEGORIES)
    return json.dumps({"ok": True, "message": f"Progress file OK (saved {info.get('Saved')}): "
                                              f"{done} of {len(bookings)} lines have a category.",
                       "bookings": bookings, "opening": opening, "closing": closing,
                       "contracts": contracts})
