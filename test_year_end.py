from datetime import date

from year_end import year_end

# Made-up data - no real data. The bank file is newest first.
BANK = [
    {"date": "05.09.2026", "text": "Venue", "amount": -500.0, "balance": 1560.0},
    {"date": "02.09.2026", "text": "Classes", "amount": 60.0, "balance": 2060.0},
    {"date": "01.09.2026", "text": "Loan", "amount": 2000.0, "balance": 2000.0},
]
BOOKINGS = [
    {"date": date(2026, 9, 5), "amount": -500.0, "category": "Venue costs"},
    {"date": date(2026, 9, 2), "amount": 60.0, "category": "Classes sales"},
    {"date": date(2026, 9, 1), "amount": 2000.0, "category": "Loan (liability)"},
]


def test_good_year():
    figures, problems = year_end(BOOKINGS, BANK)
    assert problems == []
    assert figures["year"] == "2026-2027"
    assert figures["total"] == -440.0        # loan kept out of the result
    assert figures["loans"] == 2000.0
    assert figures["opening"] == 0.0
    assert figures["closing"] == 1560.0
    assert figures["opening"] + figures["total"] + figures["loans"] == figures["closing"]


def test_missing_bank_line_stops():
    figures, problems = year_end(BOOKINGS, [BANK[0], BANK[2]])  # the 02.09 line is gone
    assert any("is a line missing" in p for p in problems)


def test_two_financial_years_stops():
    bookings = BOOKINGS + [{"date": date(2026, 7, 31), "amount": 0.0, "category": "Bank fee"}]
    figures, problems = year_end(bookings, BANK)
    assert any("more than one financial year" in p for p in problems)


def test_unbooked_bank_line_stops():
    figures, problems = year_end(BOOKINGS[:2], BANK)  # the loan was never booked
    assert any("Bookings add up to" in p for p in problems)


if __name__ == "__main__":
    test_good_year()
    test_missing_bank_line_stops()
    test_two_financial_years_stops()
    test_unbooked_bank_line_stops()
    print("OK - 4 year_end tests passed")