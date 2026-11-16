"""Which Zettle payments are booked automatically on a Friday (Holger, 16 Nov 2026):
first Friday = Globen (entrance from 20:00), third Friday = Volver (free - no door payment)."""
from datetime import datetime

from read_zettle import category_for


def test_friday_rules():
    # November 2026: Friday 6 = first Friday (Globen), Friday 20 = third Friday (Volver)
    assert category_for(datetime(2026, 11, 6, 19, 15)) == "Classes sales"
    assert category_for(datetime(2026, 11, 6, 19, 45)) == "CHECK: paid between class and social"
    assert category_for(datetime(2026, 11, 6, 21, 0)) == "Entrance fee sales"
    assert category_for(datetime(2026, 11, 20, 19, 15)) == "Classes sales"
    assert category_for(datetime(2026, 11, 20, 21, 0)) == "CHECK: paid during Volver (free event, no door payment)"
    assert category_for(datetime(2026, 11, 13, 21, 0)) == "Classes sales"   # second Friday
    assert category_for(datetime(2026, 11, 18, 21, 0)) == "Classes sales"   # a Wednesday


if __name__ == "__main__":
    test_friday_rules()
    print("OK - Friday rules test passed")
