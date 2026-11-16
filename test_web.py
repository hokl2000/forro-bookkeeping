import json
import os
import tempfile
from datetime import datetime

from openpyxl import Workbook, load_workbook

import web

# Made-up files - no real data.
BANK = "Dato;Tekst;Rente fra;Beløb;Saldo\n02.11.2026;11112222333344447777;02.11.2026;59,41;59,41\n"
MOBILEPAY = ("Type;Beløb;Dato;Tid;Kategori;Overførsels Reference;Kundenavn\n"
             "Betaling;60,00;30-10-2026;19:15;Classes;11112222333344447777;xxx\n"
             "Gebyr;-0,59;30-10-2026;19:15;;11112222333344447777;xxx\n")


def write(folder, name, text, encoding):
    path = os.path.join(folder, name)
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)
    return path


def zettle_file(folder, rows, header=("Afregningsdato", "Betalingsdato", "Reference", "Type", "Netto", "Saldo")):
    path = os.path.join(folder, "zettle.xlsx")
    wb = Workbook()
    wb.active.append(header)
    for row in rows:
        wb.active.append(row)
    wb.save(path)
    return path


def check(function, path):
    return json.loads(function(path))


def test_bank_file_ok_and_wrong():
    with tempfile.TemporaryDirectory() as folder:
        good = check(web.check_bank, write(folder, "bank.csv", BANK, "cp1252"))
        assert good["ok"] and good["preview"][0][1] == "11112222333344447777"
        wrong = check(web.check_bank, write(folder, "mp.csv", MOBILEPAY, "utf-8-sig"))
        assert not wrong["ok"] and "doesn't look like the bank file" in wrong["message"]


def test_mobilepay_file_ok_and_names_never_shown():
    with tempfile.TemporaryDirectory() as folder:
        good = check(web.check_mobilepay, write(folder, "mp.csv", MOBILEPAY, "utf-8-sig"))
        assert good["ok"] and "xxx" not in json.dumps(good)
        wrong = check(web.check_mobilepay, write(folder, "bank.csv", BANK, "cp1252"))
        assert not wrong["ok"]


def test_zettle_statement_ok_and_sales_report_rejected():
    s = datetime(2026, 11, 9, 6, 0)
    with tempfile.TemporaryDirectory() as folder:
        good = check(web.check_zettle, zettle_file(folder, [
            (s, datetime(2026, 11, 6, 20, 15), "r1", "Kortbetaling", 100.0, 100.0),
            (s, datetime(2026, 11, 6, 20, 15), "r1", "Gebyr", -2.0, 98.0),
            (s, None, None, "Udbetaling til bankkonto", -98.0, 0.0)]))  # like the real file
        assert good["ok"] and good["preview"][0][1] == "98.00"
        # The sales report starts with a title, not the statement's column names.
        report = check(web.check_zettle, zettle_file(folder, [
            (None, None, None, None), ("Virksomhedsnavn", "Forró Copenhague", None, None)],
            header=("Salgsrapporter", None, None, None)))
        assert not report["ok"] and "Sales Report" in report["message"]


def test_review_rules():
    lines = [{"date": "02.11.2026", "amount": 59.41, "category": "Classes sales"},
             {"date": "28.10.2026", "amount": -100.0, "category": ""},
             {"date": "22.10.2026", "amount": 50.0, "category": "Beer"}]
    res = json.loads(web.check_review(json.dumps(lines)))
    assert not res["ok"] and len(res["preview"]) == 2
    assert "Line 2" in res["preview"][0] and "'Beer' is not a category" in res["preview"][1]
    lines[1]["category"], lines[2]["category"] = "Venue costs", "Loan (liability)"
    assert json.loads(web.check_review(json.dumps(lines)))["ok"]
    assert json.loads(web.categories())[0] == "Advertisements and advertising"


def test_statements_file():
    bank = ("Dato;Tekst;Rente fra;Beløb;Saldo\n"
            "10.11.2026;OVERFØRSEL;10.11.2026;98,00;198,00\n"
            "02.11.2026;Loan from xxx;02.11.2026;100,00;100,00\n")
    bookings = [  # as the page sends them: newest bank line first, split rows share "line"
        {"line": 0, "date": "10.11.2026", "amount": 100.0, "category": "Entrance fee sales",
         "event": "Globen", "comment": "", "receipt": "990"},
        {"line": 0, "date": "10.11.2026", "amount": -2.0, "category": "Zettle fee", "event": "Globen",
         "comment": "", "receipt": ""},
        {"line": 1, "date": "02.11.2026", "amount": 100.0, "category": "Loan (liability)",
         "comment": "Loan from xxx", "receipt": ""},
    ]
    with tempfile.TemporaryDirectory() as folder:
        bank_path = write(folder, "bank.csv", bank, "cp1252")
        assert json.loads(web.balances(bank_path)) == {"opening": 0.0, "closing": 198.0}
        out = os.path.join(folder, "statements.xlsx")
        info = json.loads(web.write_statements(json.dumps(bookings), 0.0, out))
        assert info == {"rows": 3, "opening": 0.0}
        wb = load_workbook(out)
        rows = list(wb.active.iter_rows(values_only=True))
        wb.close()
    assert rows[1][:8] == ("Receipt number", "From Account", "To Account", "Dato", "Status",
                           "Beløb", "Saldo", "Post typer")
    assert rows[2][5:8] == (100, 100, "Lån")                       # oldest first, Danish name
    assert rows[3][0] == 990 and rows[3][7:9] == ("Salg entre", "Globen")   # receipt on the bank line
    assert rows[4][8] is None                                      # a fee never gets an event
    assert rows[4][0] is None and rows[4][3] is None and rows[4][6] == 198   # split row; = bank balance


PROGRESS = [  # as the page holds them after "Make bookings" and some typing
    {"line": 0, "date": "10.11.2026", "text": "OVERFØRSEL", "amount": 100.0, "category": "Entrance fee sales", "event": "Globen",
     "code_category": "Entrance fee sales", "reason": "Zettle payout", "comment": "", "receipt": "990"},
    {"line": 0, "date": "10.11.2026", "text": "OVERFØRSEL", "amount": -2.0, "category": "Zettle fee", "event": "",
     "code_category": "Zettle fee", "reason": "Zettle payout", "comment": "", "receipt": ""},
    {"line": 1, "date": "02.11.2026", "text": "Loan from xxx", "amount": 100.0, "category": "", "event": "Festival 26",
     "code_category": "", "reason": "", "comment": "ask the board", "receipt": ""},
]


def test_progress_file_round_trip():
    with tempfile.TemporaryDirectory() as folder:
        out = os.path.join(folder, "progress.xlsx")
        web.write_progress(json.dumps(PROGRESS), 0.0, 198.0, "16.11.2026 10:20", out)
        back = json.loads(web.read_progress(out))
    assert back["ok"] and back["bookings"] == PROGRESS
    assert (back["opening"], back["closing"]) == (0.0, 198.0)
    assert back["message"] == "Progress file OK (saved 16.11.2026 10:20): 2 of 3 lines have a category."


def test_progress_file_refused():
    with tempfile.TemporaryDirectory() as folder:
        # another Excel file, e.g. the Statements file
        statements = os.path.join(folder, "statements.xlsx")
        web.write_statements(json.dumps(PROGRESS), 0.0, statements)
        res = json.loads(web.read_progress(statements))
        assert not res["ok"] and "not a progress file" in res["message"]
        # a CSV file
        res = json.loads(web.read_progress(write(folder, "bank.csv", BANK, "cp1252")))
        assert not res["ok"] and "not a progress file" in res["message"]
        # an amount changed in Excel
        out = os.path.join(folder, "progress.xlsx")
        web.write_progress(json.dumps(PROGRESS), 0.0, 198.0, "16.11.2026 10:20", out)
        wb = load_workbook(out)
        wb["Lines"]["E2"] = 10.0
        wb.save(out)
        wb.close()
        res = json.loads(web.read_progress(out))
        assert not res["ok"] and "no longer add up" in res["message"]
        # a progress file from before the Event column
        wb = load_workbook(out)
        wb["Info"]["B2"] = 1
        wb.save(out)
        wb.close()
        res = json.loads(web.read_progress(out))
        assert not res["ok"] and "before the Event column" in res["message"]


def test_events():
    from classify import booking
    from event_types import AUTO_EVENTS, EVENT_TYPES, NO_EVENT
    from review import CATEGORIES
    assert NO_EVENT <= set(CATEGORIES) and set(AUTO_EVENTS) <= set(CATEGORIES)
    assert set(AUTO_EVENTS.values()) <= set(EVENT_TYPES)
    line = {"date": "06.11.2026", "text": "OVERFØRSEL"}
    assert booking(line, "Entrance fee sales", 100, "")["event"] == "Globen"
    assert booking(line, "Classes sales", 100, "")["event"] == "Beginner classes"
    assert booking(line, "Globen vouchers", -1280, "")["event"] == "Globen"
    assert booking(line, "Zettle fee", -2, "")["event"] == ""
    assert booking(line, "", 100, "")["event"] == ""
    lines = [{"category": "Workshop sales", "event": "Workshop Joao"},
             {"category": "Venue costs", "event": "Volver"},
             {"category": "Bank fee", "event": "Festival 26"}]   # ignored: a bank fee has no event
    assert json.loads(web.new_events(json.dumps(lines))) == ["Volver"]


def test_bank_file_checks():
    two_years = ("Dato;Tekst;Rente fra;Beløb;Saldo\n"
                 "01.08.2026;A;01.08.2026;10,00;110,00\n"
                 "31.07.2026;B;31.07.2026;100,00;100,00\n")
    gap = ("Dato;Tekst;Rente fra;Beløb;Saldo\n"
           "10.11.2026;A;10.11.2026;10,00;130,00\n"      # 100 + 10 = 110, not 130: a line is missing
           "02.11.2026;B;02.11.2026;100,00;100,00\n")
    with tempfile.TemporaryDirectory() as folder:
        res = check(web.check_bank, write(folder, "a.csv", two_years, "cp1252"))
        assert not res["ok"] and "2025-2026, 2026-2027" in res["message"]
        res = check(web.check_bank, write(folder, "b.csv", gap, "cp1252"))
        assert not res["ok"] and "missing" in res["message"] and "10.11.2026" in res["message"]


def test_checks_before_statements():
    done = [dict(b, category=b["category"] or "Loan (liability)") for b in PROGRESS]
    res = json.loads(web.check_statements(json.dumps(PROGRESS), 0.0, 198.0))
    assert not res["ok"] and res["message"].startswith("1 line(s) still need a category: line 3.")
    res = json.loads(web.check_statements(json.dumps(done), 0.0, 198.0))
    assert res["ok"] and "2026-2027" in res["message"]
    res = json.loads(web.check_statements(json.dumps(done), 0.0, 200.0))
    assert not res["ok"] and "end at 198.00, but the bank ends at 200.00" in res["message"]
    done[2]["date"] = "31.07.2026"
    res = json.loads(web.check_statements(json.dumps(done), 0.0, 198.0))
    assert not res["ok"] and "more than one financial year" in res["message"]


def test_instructor_check():
    lines = [{"category": "Workshop sales", "event": "Workshop Joao", "amount": 10000.0},
             {"category": "Venue costs", "event": "Workshop Joao", "amount": -2000.0},
             {"category": "Dance teacher costs", "event": "Workshop Joao", "amount": -5000.0},
             {"category": "Dance teacher costs", "event": "Workshop Thamyra", "amount": -6000.0},
             {"category": "Dance teacher costs", "event": "", "amount": -100.0}]
    contracts = {"Workshop Joao": {"percent": "80", "fixed": ""}}
    res = json.loads(web.instructor_check(json.dumps(lines), json.dumps(contracts)))
    joao, thamyra = res["rows"]
    assert joao["status"] == "warn" and "contract says 6400.00 (80 % of profit 8000.00)" in joao["message"]
    assert thamyra["status"] == "todo"
    assert res["note"].startswith("1 Dance teacher costs line(s) have no event")
    contracts["Workshop Thamyra"] = {"percent": "", "fixed": "6000"}
    res = json.loads(web.instructor_check(json.dumps(lines), json.dumps(contracts)))
    assert res["rows"][1]["status"] == "ok"
    with tempfile.TemporaryDirectory() as folder:          # contracts are kept in the progress file
        out = os.path.join(folder, "progress.xlsx")
        web.write_progress(json.dumps(PROGRESS), 0.0, 198.0, "16.11.2026 19:00", out, json.dumps(contracts))
        assert json.loads(web.read_progress(out))["contracts"] == contracts


if __name__ == "__main__":
    test_bank_file_ok_and_wrong()
    test_mobilepay_file_ok_and_names_never_shown()
    test_zettle_statement_ok_and_sales_report_rejected()
    test_review_rules()
    test_statements_file()
    test_progress_file_round_trip()
    test_progress_file_refused()
    test_events()
    test_bank_file_checks()
    test_checks_before_statements()
    test_instructor_check()
    print("OK - 11 web tests passed")
