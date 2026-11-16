import csv

BANK_FILE = "data/Eksporter_posteringer_til_CSV.csv"


def parse_amount(text):
    # "-1.280,00" -> -1280.0
    return float(text.replace(".", "").replace(",", "."))


def read_bank(path):
    """Return the bank lines as a list of dicts: date, text, amount, balance."""
    lines = []
    with open(path, encoding="cp1252", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)  # skip the header row: Dato;Tekst;Rente fra;Beløb;Saldo
        for row in reader:
            if len(row) < 5:  # skip empty lines at the end of the file
                continue
            lines.append({
                "date": row[0],
                "text": row[1],
                "amount": parse_amount(row[3]),
                "balance": parse_amount(row[4]),
            })
    return lines


if __name__ == "__main__":
    lines = read_bank(BANK_FILE)
    for line in lines:
        print(line["date"], line["text"], line["amount"], line["balance"])
    print("Sum of all amounts:", round(sum(l["amount"] for l in lines), 2))