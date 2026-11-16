"""Instructor contracts: what an instructor should be paid for one event (Holger, 12 + 16 Nov 2026).

An event's lines are the bookings with that event name in the Event column - no events.csv
with dates any more (Holger, 16 Nov 2026: "drop it").
Profit = income MINUS venue, catering, transport and flights. Fees are NOT subtracted.
Income = every sales line of the event, also tickets paid at the door by Zettle or MobilePay
and booked as e.g. Entrance fee sales (Holger, 16 Nov 2026)."""

from review import CATEGORIES

INCOME = {c for c in CATEGORIES if c.endswith(" sales")}
CONTRACT_COSTS = {"Venue costs", "Miscellaneous catering costs",
                  "Transportation costs", "Airline tickets"}
INSTRUCTOR = "Dance teacher costs"


def parse_number(text):
    """'' -> None, '80' -> 80.0, '6000' -> 6000.0, '80,5' -> 80.5. Raises ValueError if not a number."""
    text = str(text).strip().replace(",", ".")
    return float(text) if text else None


def check_contract(contract):
    """Rule errors for one contract {"percent": "...", "fixed": "..."} (empty list = OK)."""
    try:
        percent = parse_number(contract.get("percent", ""))
        fixed = parse_number(contract.get("fixed", ""))
    except ValueError:
        return ["contract % and fixed amount must be numbers"]
    errors = []
    if percent is None and fixed is None:
        errors.append("fill in the contract % or the fixed amount")
    if percent is not None and fixed is not None:
        errors.append("fill in the contract % OR the fixed amount, not both")
    if percent is not None and not 0 < percent <= 100:
        errors.append("contract % must be above 0 and at most 100")
    if fixed is not None and fixed <= 0:
        errors.append("the fixed amount must be above 0")
    return errors


def expected_instructor_payment(contract, lines):
    """What the instructor should be paid for one event, from its contract and the event's lines."""
    fixed = parse_number(contract.get("fixed", ""))
    if fixed is not None:
        return fixed
    percent = parse_number(contract["percent"])
    return round(profit(lines) / 100 * percent, 2)


def profit(lines):
    income = sum(l["amount"] for l in lines if l["category"] in INCOME)
    costs = sum(l["amount"] for l in lines if l["category"] in CONTRACT_COSTS)
    return round(income + costs, 2)
