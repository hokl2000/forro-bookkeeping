import sys
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font

from read_bank import BANK_FILE, read_bank
from read_review import read_review
from review import CATEGORIES

REVIEW_FILE = "review.xlsx"
YEAR_END_FILE = "year_end.xlsx"

LOAN = "Loan (liability)"
TRANSFER = "Transfer between own accounts"

# The Overview sheet's rows 5-47, in its own order. None = its empty row 14.
OVERVIEW_LINES = [
    "Entrance fee sales", "Drinks sales", "Classes sales", "Membership sales",
    "Merchandise sales", "Funds", "Workshop sales", "Marathon sales", "Group trip sales",
    None,
    "Dance teacher costs", "Band costs", "Miscellaneous catering costs",
    "Transportation costs", "DJ costs", "Airline tickets", "Music equipment rental",
    "Purchase of electronics", "Gift cards", "Group trip costs", "Organizer fee costs",
    "Globen vouchers", "Refunds", "Discounts", "Venue costs",
    "Advertisements and advertising", "Stationery and printed matter", "Zettle fee",
    "Billetfix fee", "E-conomic costs", "Repair / maintenance of inventory",
    "Minor purchases", "Webpage and domain", "Bank fee", "Interest income, bank",
    "Interest expense, bank", "Returns", "Miscellaneous fees", "Shortfall",
    "Food sales", "Festival sales", "Purchase of Drinks", "Mobilepay fee",
]


def financial_year(day):
    """1 Aug - 31 Jul. 14 Nov 2026 -> '2026-2027'."""
    start = day.year if day.month >= 8 else day.year - 1
    return f"{start}-{start + 1}"


def year_end(bookings, bank):
    """Sums per Overview line + the balance figures. Returns (figures, problems)."""
    problems = []

    # The category list and the Overview must match (guards against one being changed).
    lines = [c for c in OVERVIEW_LINES if c]
    if set(lines) != set(CATEGORIES) - {LOAN, TRANSFER}:
        problems.append("The Overview lines in year_end.py don't match CATEGORIES in review.py")

    # Check 1: everything inside ONE financial year.
    bank_dates = [datetime.strptime(b["date"], "%d.%m.%Y").date() for b in bank]
    years = {financial_year(d) for d in bank_dates + [b["date"] for b in bookings]}
    if len(years) != 1:
        problems.append(f"Dates from more than one financial year: {', '.join(sorted(years))}")

    # Check 2: the bank file is complete - each balance = the older balance + the amount.
    # The bank file is newest first.
    for newer, older in zip(bank, bank[1:]):
        if round(older["balance"] + newer["amount"], 2) != round(newer["balance"], 2):
            problems.append(f"Bank balance doesn't add up at {newer['date']} {newer['text']} "
                            "- is a line missing from the bank file?")

    # Check 3: every krone in the bank is booked exactly once.
    bank_sum = round(sum(b["amount"] for b in bank), 2)
    booked_sum = round(sum(b["amount"] for b in bookings), 2)
    if bank_sum != booked_sum:
        problems.append(f"Bookings add up to {booked_sum:.2f}, the bank lines to {bank_sum:.2f}")

    sums = {c: 0.0 for c in lines}
    loans = transfers = 0.0
    for b in bookings:
        if b["category"] == LOAN:
            loans += b["amount"]
        elif b["category"] == TRANSFER:
            transfers += b["amount"]
        else:
            sums[b["category"]] += b["amount"]

    oldest, newest = bank[-1], bank[0]
    figures = {
        "year": years.pop() if len(years) == 1 else "?",
        "sums": {c: round(s, 2) for c, s in sums.items()},
        "total": round(sum(sums.values()), 2),
        "loans": round(loans, 2),
        "transfers": round(transfers, 2),
        "opening": round(oldest["balance"] - oldest["amount"], 2),
        "closing": round(newest["balance"], 2),
    }
    return figures, problems


def write_year_end(figures, path):
    """Same row numbers as the Overview sheet: copy B3:B58, paste at row 3 of the new column."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Year end"
    ws["B3"] = "Årsresultat"
    ws["B4"] = figures["year"]
    ws["A4"] = "Kontering"
    for row, category in enumerate(OVERVIEW_LINES, start=5):
        if category:
            ws.cell(row, 1, category)
            ws.cell(row, 2, figures["sums"][category])
    ws["A48"], ws["B48"] = "Total", figures["total"]
    ws["A50"] = "Actives"
    ws["A51"], ws["A52"], ws["A53"] = "T-shirts", "Bags", "Drinks"  # stock: not in the bank
    ws["A54"], ws["B54"] = "Bank balance", figures["closing"]
    ws["A56"] = "Passives"
    ws["A57"], ws["B57"] = "Liabilities", figures["loans"]
    ws["A58"], ws["B58"] = "Balance", round(figures["closing"] - figures["loans"], 2)
    for row in ws.iter_rows(min_row=5, max_row=58, min_col=2, max_col=2):
        row[0].number_format = "#,##0.00"
    for cell in (ws["A4"], ws["A48"], ws["A50"], ws["A56"]):
        cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 14
    wb.save(path)


if __name__ == "__main__":
    try:
        bookings, corrections = read_review(REVIEW_FILE)
    except ValueError as error:
        print(error)
        sys.exit(1)
    figures, problems = year_end(bookings, read_bank(BANK_FILE))
    if problems:
        print("STOPPED - year_end.xlsx was not written:")
        for p in problems:
            print(" -", p)
        sys.exit(1)

    f = figures
    print(f"Financial year {f['year']} (new bank)")
    print(f"  Opening balance               {f['opening']:>12,.2f}")
    print(f"  Result (Total)                {f['total']:>12,.2f}")
    print(f"  Loans                         {f['loans']:>12,.2f}")
    print(f"  Transfers between own accounts{f['transfers']:>12,.2f}")
    print(f"  Closing balance               {f['closing']:>12,.2f}")
    print("All checks passed: one financial year, bank file complete, every bank line booked once.")
    if corrections:
        print(f"{len(corrections)} automatic booking(s) were corrected - see read_review.py")
    write_year_end(figures, YEAR_END_FILE)
    print(f"-> {YEAR_END_FILE}: copy B3:B58 and paste at row 3 of the new year's column in the Overview")