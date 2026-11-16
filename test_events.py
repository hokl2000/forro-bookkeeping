from events import INCOME, check_contract, expected_instructor_payment

LINES = [
    {"category": "Workshop sales", "amount": 11000.0},
    {"category": "Entrance fee sales", "amount": 1000.0},   # tickets paid at the door count too
    {"category": "Venue costs", "amount": -1000.0},
    {"category": "Miscellaneous catering costs", "amount": -800.0},
    {"category": "Transportation costs", "amount": -600.0},
    {"category": "Airline tickets", "amount": -2000.0},
    {"category": "Billetfix fee", "amount": -200.0},         # fees are not subtracted
    {"category": "Dance teacher costs", "amount": -6080.0},  # the payment itself is not a cost here
]

assert "Workshop sales" in INCOME and "Entrance fee sales" in INCOME and "Billetfix fee" not in INCOME
assert expected_instructor_payment({"percent": "80", "fixed": ""}, LINES) == 6080.0
assert expected_instructor_payment({"percent": "", "fixed": "6000"}, LINES) == 6000.0
assert check_contract({"percent": "80", "fixed": ""}) == []
assert check_contract({"percent": "80", "fixed": "6000"}) == ["fill in the contract % OR the fixed amount, not both"]
assert check_contract({"percent": "120", "fixed": ""}) == ["contract % must be above 0 and at most 100"]
assert check_contract({"percent": "", "fixed": ""}) == ["fill in the contract % or the fixed amount"]
assert check_contract({"percent": "abc", "fixed": ""}) == ["contract % and fixed amount must be numbers"]

print("OK - instructor payment tests passed")
