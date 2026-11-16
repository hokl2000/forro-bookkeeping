from match import match_mobilepay

# Made-up data - no real data.
TRANSFERS = {
    "11112222333344445555": {"payments": 60.0, "fees": -0.59, "to_bank": 59.41,
                             "by_category": {"Classes": 60.0}},
}


def line(text, amount):
    return {"date": "26.10.2026", "text": text, "amount": amount, "balance": 0.0}


def test_full_reference_matches():
    assert match_mobilepay(line("11112222333344445555", 59.41), TRANSFERS) == "11112222333344445555"


def test_wrong_amount_does_not_match():
    assert match_mobilepay(line("11112222333344445555", 60.00), TRANSFERS) is None


def test_unknown_reference_does_not_match():
    assert match_mobilepay(line("11112222333344446666", 59.41), TRANSFERS) is None


def test_text_that_is_not_a_reference_does_not_match():
    assert match_mobilepay(line("Globen September", 59.41), TRANSFERS) is None


def test_excel_damaged_reference_goes_to_treasurer():
    # Excel turns the reference into a rounded number - never guess, leave it to the treasurer.
    assert match_mobilepay(line("11112222333344400000.00", 59.41), TRANSFERS) is None


if __name__ == "__main__":
    test_full_reference_matches()
    test_wrong_amount_does_not_match()
    test_unknown_reference_does_not_match()
    test_text_that_is_not_a_reference_does_not_match()
    test_excel_damaged_reference_goes_to_treasurer()
    print("OK - 5 match tests passed")