import warnings

from classify import bookings_for
from read_bank import read_bank
from read_mobilepay import read_mobilepay, transfers
from read_zettle import read_zettle
from review import write_review

# The Zettle statement has no default style; openpyxl warns about it.
# We only read the numbers, so the warning is harmless – hide it.
warnings.filterwarnings("ignore", message="Workbook contains no default style")

BANK_FILE = "data/Eksporter_posteringer_til_CSV.csv"
MOBILEPAY_FILE = "data/mobilepay.csv"
ZETTLE_FILE = "data/zettle.xlsx"
REVIEW_FILE = "review.xlsx"


def main(bank_file=BANK_FILE):
    bank = read_bank(bank_file)
    mp = transfers(read_mobilepay(MOBILEPAY_FILE))
    zettle = read_zettle(ZETTLE_FILE)

    bookings = []
    for line in bank:
        bookings += bookings_for(line, mp, zettle)
    for b in bookings:
        print(f"{b['date']}  {b['text']:<24} {b['amount']:>10.2f}  {b['category'] or 'TREASURER':<20} {b['reason']}")

    write_review(bookings, REVIEW_FILE)
    todo = sum(1 for b in bookings if not b["category"])
    print(f"\n{len(bookings) - todo} bookings made automatically, {todo} for the treasurer -> {REVIEW_FILE}")


if __name__ == "__main__":
    main()