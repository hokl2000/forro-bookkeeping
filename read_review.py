import sys
import warnings
from datetime import date, datetime

from openpyxl import load_workbook

from review import CATEGORIES

# Excel stores the dropdown rules in a format openpyxl can't read. We only read
# the values, so this warning is harmless – hide it so the treasurer doesn't see it.
warnings.filterwarnings("ignore", message="Data Validation extension is not supported")


def to_date(value):
    """Bank dates are text 'DD.MM.YYYY'. Also accept a date Excel may have converted."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%d.%m.%Y").date()


def read_review(path):
    """Read the filled-in review.xlsx. Returns (final bookings, corrections).
    Stops with an error listing every row that has no category or an unknown one."""
    wb = load_workbook(path)
    bookings, corrections, problems = [], [], []

    rows = wb["To decide"].iter_rows(min_row=2, values_only=True)
    for n, row in enumerate(rows, start=2):
        if not any(row):
            continue  # empty row
        day, text, amount, category, comment = row[:5]
        if not category:
            problems.append(f"To decide, row {n}: no category ({day} | {text} | {amount})")
        elif category not in CATEGORIES:
            problems.append(f"To decide, row {n}: unknown category '{category}'")
        else:
            bookings.append({"date": to_date(day), "text": text, "amount": amount,
                             "category": category, "comment": comment or ""})

    rows = wb["Booked automatically"].iter_rows(min_row=2, values_only=True)
    for n, row in enumerate(rows, start=2):
        if not any(row):
            continue
        day, text, amount, code_category, reason, correct = row[:6]
        if correct and correct not in CATEGORIES:
            problems.append(f"Booked automatically, row {n}: unknown category '{correct}'")
            continue
        if correct and correct != code_category:
            corrections.append({"date": to_date(day), "text": text, "amount": amount,
                                "from": code_category, "to": correct, "reason": reason})
        bookings.append({"date": to_date(day), "text": text, "amount": amount,
                         "category": correct or code_category, "comment": ""})

    if problems:
        raise ValueError("review.xlsx is not finished:\n" + "\n".join(problems))
    return bookings, corrections


if __name__ == "__main__":
    try:
        bookings, corrections = read_review("review.xlsx")
    except ValueError as error:
        print(error)
        sys.exit(1)
    print("FINAL BOOKINGS")
    for b in bookings:
        print(b["date"], "|", b["text"], "|", b["amount"], "|", b["category"])
    print("CORRECTIONS (rule to check)")
    for c in corrections:
        print(c["date"], "|", c["text"], "|", c["amount"], "|", c["from"], "->", c["to"], "|", c["reason"])