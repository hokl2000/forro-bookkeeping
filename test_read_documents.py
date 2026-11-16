from datetime import date
from read_documents import parse_billetfix, parse_zettle

# Written test texts with made-up amounts - no real data, never changes.
BILLETFIX_TEXT = """Total udbetaling 990,00 kr
Salg total: 5 1.000,00 kr
Heraf moms (25%) 200,00 kr
MobilePay gebyr: -10,00 kr
Total udbetaling: 990,00 kr"""

ZETTLE_TEXT = """Zettle <alert@zettle.paypal.com> 3 October 2026 at 21:15
Vi har indsat 1.234,56 kr. på den bankkonto, du har valgt."""

# 1. BilletFix: the three amounts are read correctly
assert parse_billetfix(BILLETFIX_TEXT) == {"sales": 1000.0, "fee": -10.0, "payout": 990.0}

# 2. BilletFix: a statement that doesn't add up must stop, not be booked
broken = BILLETFIX_TEXT.replace("Total udbetaling: 990,00", "Total udbetaling: 999,00")
try:
    parse_billetfix(broken)
    raise AssertionError("The sum check did not stop a wrong payout")
except ValueError:
    pass

# 3. Zettle: amount and date
zettle = parse_zettle(ZETTLE_TEXT)
assert zettle["payout"] == 1234.56
assert zettle["date"] == date(2026, 10, 3)

print("OK - document tests passed")