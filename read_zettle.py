from datetime import time
from openpyxl import load_workbook

ZETTLE_FILE = "data/zettle.xlsx"
CLASS_ENDS = time(19, 30)    # class payments until 19:30
SOCIAL_STARTS = time(20, 0)  # social payments from 20:00


def friday_event(d):
    """Globen on the first Friday of the month, Volver on the third, None otherwise."""
    if d.weekday() != 4:
        return None
    if 1 <= d.day <= 7:
        return "Globen"
    if 15 <= d.day <= 21:
        return "Volver"
    return None


def category_for(paid_at):
    """Classes or social, from the payment's date and time. "CHECK: ..." -> the treasurer decides.
    Volver (third Friday) is free - no door payment - so a payment during Volver is not entrance."""
    event = friday_event(paid_at.date())
    if event is None or paid_at.time() <= CLASS_ENDS:
        return "Classes sales"
    if event == "Volver":
        return "CHECK: paid during Volver (free event, no door payment)"
    if paid_at.time() >= SOCIAL_STARTS:
        return "Entrance fee sales"
    return "CHECK: paid between class and social"


def read_zettle(path):
    """Return one dict per payout: date, to_bank, and its payments and fees."""
    wb = load_workbook(path, read_only=True)
    rows = list(wb.active.iter_rows(min_row=2, values_only=True))
    wb.close()  # read-only workbooks keep the file open until closed (Windows locks it)
    rows.sort(key=lambda r: r[0])  # oldest first (by Afregningsdato)
    payouts, payments, fees = [], [], []
    for settled, paid_at, ref, kind, net, balance in rows:
        if kind == "Kortbetaling":
            payments.append({"paid_at": paid_at, "amount": net, "category": category_for(paid_at)})
        elif kind == "Gebyr":
            fees.append(net)
        elif kind == "Udbetaling til bankkonto":
            to_bank = round(-net, 2)
            total = round(sum(p["amount"] for p in payments) + sum(fees), 2)
            if total != to_bank:
                raise ValueError(f"Payout {to_bank} on {settled:%d.%m.%Y} != payments + fees {total}")
            payouts.append({"date": settled.date(), "to_bank": to_bank,
                            "payments": payments, "fees": round(sum(fees), 2)})
            payments, fees = [], []
        else:
            raise ValueError(f"Unknown Zettle line type: {kind}")
    return payouts


if __name__ == "__main__":
    for p in read_zettle(ZETTLE_FILE):
        by_cat = {}
        for pay in p["payments"]:
            by_cat[pay["category"]] = by_cat.get(pay["category"], 0) + pay["amount"]
        print(f"Payout {p['date']:%d.%m.%Y}: to bank {p['to_bank']}, fees {p['fees']}, income {by_cat}")