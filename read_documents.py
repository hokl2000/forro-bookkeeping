import re
from datetime import datetime
from pypdf import PdfReader
from read_bank import parse_amount


def pdf_text(path):
    """Return all text in a PDF as one string."""
    reader = PdfReader(path)
    return "\n".join(page.extract_text() for page in reader.pages)


def find_amount(pattern, text, what):
    """Find one amount with a regex. Stop with an error if it isn't there."""
    match = re.search(pattern, text)
    if match is None:
        raise ValueError(f"Could not find {what} - has the layout changed?")
    return parse_amount(match.group(1))


def parse_billetfix(text):
    """Return sales, fee and payout from the text of a BilletFix statement."""
    sales = find_amount(r"Salg total: \d+ ([\d.,-]+) kr", text, "sales")
    fee = find_amount(r"MobilePay gebyr: ([\d.,-]+) kr", text, "fee")
    payout = find_amount(r"Total udbetaling: ([\d.,-]+) kr", text, "payout")
    if round(sales + fee, 2) != payout:
        raise ValueError(f"Sales {sales} + fee {fee} does not equal payout {payout}")
    return {"sales": sales, "fee": fee, "payout": payout}


def parse_zettle(text):
    """Return payout amount and email date from the text of a Zettle payout email."""
    amount = find_amount(r"Vi har indsat ([\d.,-]+) kr", text, "Zettle payout")
    match = re.search(r"(\d{1,2} \w+ \d{4}) at \d{2}:\d{2}", text)
    if match is None:
        raise ValueError("Could not find the email date - has the layout changed?")
    date = datetime.strptime(match.group(1), "%d %B %Y").date()
    return {"payout": amount, "date": date}


def read_billetfix(path):
    return parse_billetfix(pdf_text(path))


def read_zettle(path):
    return parse_zettle(pdf_text(path))


if __name__ == "__main__":
    print(read_billetfix("data/billetifx.pdf"))
    print(read_zettle("data/Zettle.pdf"))