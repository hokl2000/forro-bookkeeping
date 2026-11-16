import os
import tempfile

from openpyxl import load_workbook

from read_review import read_review
from review import write_review

# Made-up bookings - no real data.
BOOKINGS = [
    {"date": "01.09.2026", "text": "Unknown payment", "amount": -100.0,
     "category": "", "reason": "No rule or document matched"},
    {"date": "05.09.2026", "text": "Globen September", "amount": -500.0,
     "category": "Globen vouchers", "reason": "Rule: text starts with 'Globen'"},
    {"date": "06.09.2026", "text": "Ref 123", "amount": 60.0,
     "category": "Classes sales", "reason": "Match: MobilePay"},
]


def make_file(folder):
    """Write a review.xlsx with the made-up bookings in a temporary folder."""
    path = os.path.join(folder, "review.xlsx")
    write_review(BOOKINGS, path)
    return path


def test_unfilled_row_stops():
    with tempfile.TemporaryDirectory() as folder:
        path = make_file(folder)
        try:
            read_review(path)
        except ValueError as error:
            assert "To decide, row 2: no category" in str(error)
        else:
            raise AssertionError("read_review should stop when a row has no category")


def test_filled_file_and_correction():
    with tempfile.TemporaryDirectory() as folder:
        path = make_file(folder)
        wb = load_workbook(path)
        wb["To decide"]["D2"] = "Venue costs"
        wb["Booked automatically"]["F2"] = "Venue costs"  # correct the Globen line
        wb.save(path)

        bookings, corrections = read_review(path)
        assert [b["category"] for b in bookings] == ["Venue costs", "Venue costs", "Classes sales"]
        assert len(corrections) == 1
        assert corrections[0]["from"] == "Globen vouchers"
        assert corrections[0]["to"] == "Venue costs"
        assert str(bookings[0]["date"]) == "2026-09-01"


def test_unknown_category_stops():
    with tempfile.TemporaryDirectory() as folder:
        path = make_file(folder)
        wb = load_workbook(path)
        wb["To decide"]["D2"] = "Beer"
        wb.save(path)
        try:
            read_review(path)
        except ValueError as error:
            assert "unknown category 'Beer'" in str(error)
        else:
            raise AssertionError("read_review should stop on a category not in the list")


if __name__ == "__main__":
    test_unfilled_row_stops()
    test_filled_file_and_correction()
    test_unknown_category_stops()
    print("OK - 3 read_review tests passed")