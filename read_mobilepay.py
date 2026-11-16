import csv
from collections import defaultdict
from read_bank import parse_amount

MOBILEPAY_FILE = "data/mobilepay.csv"

# Data minimisation: only these columns are kept. Names, phone numbers
# and messages are dropped as soon as the file is read.
KEEP = {
    "Type": "type",
    "Beløb": "amount",
    "Dato": "date",
    "Tid": "time",
    "Kategori": "category",
    "Overførsels Reference": "transfer_ref",
}


def read_mobilepay(path):
    """Return MobilePay lines with only the columns in KEEP."""
    lines = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            line = {new: row[old] for old, new in KEEP.items()}
            line["amount"] = parse_amount(line["amount"])
            lines.append(line)
    return lines


def transfers(lines):
    """Group lines by transfer reference: what each bank line should contain."""
    groups = defaultdict(lambda: {"payments": 0.0, "fees": 0.0, "by_category": defaultdict(float)})
    for line in lines:
        key = "payments" if line["type"] == "Betaling" else "fees"
        groups[line["transfer_ref"]][key] += line["amount"]
        if key == "payments":
            groups[line["transfer_ref"]]["by_category"][line["category"]] += line["amount"]
    for g in groups.values():
        g["payments"], g["fees"] = round(g["payments"], 2), round(g["fees"], 2)
        g["to_bank"] = round(g["payments"] + g["fees"], 2)
    return dict(groups)


if __name__ == "__main__":
    for ref, g in transfers(read_mobilepay(MOBILEPAY_FILE)).items():
        print(ref, g)