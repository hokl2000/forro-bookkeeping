import re


def match_mobilepay(bank_line, transfers):
    """Return the MobilePay transfer reference that matches a bank line, or None.

    The bank text of a MobilePay payout is the full transfer reference
    (e.g. "11112222333344445555"), so it must equal the reference in the
    MobilePay file exactly, and the amount must be what reached the bank.
    """
    text = bank_line["text"].strip()
    if not re.fullmatch(r"\d+", text):
        return None
    t = transfers.get(text)
    if t is not None and t["to_bank"] == bank_line["amount"]:
        return text
    return None
