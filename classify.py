import re
from datetime import datetime
from event_types import AUTO_EVENTS
from match import match_mobilepay

MOBILEPAY_LIKE = re.compile(r"^\d{15,}$")   # the bank text is only a long transfer reference
ZETTLE_MAX_DAYS = 3  # the bank line comes 0-3 days after Zettle's payout date

# MobilePay's own categories -> Forró's accounts. "Other" is left for the treasurer.
MOBILEPAY_CATEGORIES = {"Classes": "Classes sales", "Globen": "Entrance fee sales"}


def bank_date(text):
    return datetime.strptime(text, "%d.%m.%Y").date()


def match_zettle(bank_line, payouts):
    """Return the ONE Zettle payout that fits a bank line, or None."""
    if bank_line["text"] != "OVERFØRSEL" or bank_line["amount"] <= 0:
        return None
    d = bank_date(bank_line["date"])
    candidates = [p for p in payouts
                  if p["to_bank"] == bank_line["amount"]
                  and 0 <= (d - p["date"]).days <= ZETTLE_MAX_DAYS]
    return candidates[0] if len(candidates) == 1 else None


def booking(line, category, amount, reason):
    """One line in the accounts. category "" = the treasurer decides.
    event: filled in for Globen entrance and classes, otherwise "" (the treasurer may add one)."""
    return {"date": line["date"], "text": line["text"], "amount": round(amount, 2),
            "category": category, "event": AUTO_EVENTS.get(category, ""), "reason": reason}


def bookings_for(line, mobilepay_transfers, zettle_payouts):
    """Turn one bank line into one or more bookings. Unknown -> category ""."""
    text, amount = line["text"], line["amount"]

    if text.startswith("Globen") and amount < 0:
        return [booking(line, "Globen vouchers", amount, "Rule: text starts with 'Globen'")]

    ref = match_mobilepay(line, mobilepay_transfers)
    if ref:
        t = mobilepay_transfers[ref]
        reason = f"Match: MobilePay transfer {ref}"
        result = []
        for mp_cat, total in t["by_category"].items():
            cat = MOBILEPAY_CATEGORIES.get(mp_cat, "")  # "Other" -> treasurer
            result.append(booking(line, cat, total, f"{reason}, MobilePay category '{mp_cat}'"))
        result.append(booking(line, "Mobilepay fee", t["fees"], reason))
        return result

    payout = match_zettle(line, zettle_payouts)
    if payout:
        reason = f"Match: Zettle payout {payout['date']:%d.%m.%Y}"
        by_cat = {}
        for p in payout["payments"]:
            by_cat[p["category"]] = by_cat.get(p["category"], 0) + p["amount"]
        result = [booking(line, "", total, f"{reason}, {cat[len('CHECK: '):]}") if cat.startswith("CHECK")
                  else booking(line, cat, total, f"{reason}, by payment time")
                  for cat, total in by_cat.items()]
        result.append(booking(line, "Zettle fee", payout["fees"], reason))
        return result

    if MOBILEPAY_LIKE.match(text):
        return [booking(line, "", amount, "Looks like a MobilePay transfer reference, but it isn't in the "
                                          "MobilePay file – check that the MobilePay report covers this date")]
    return [booking(line, "", amount, "No rule or document matched")]