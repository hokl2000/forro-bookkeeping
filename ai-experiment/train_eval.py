"""Forró bookkeeping - AI suggestion for post types: training and test.

Learns post types from the club's own Statements (Tekst + amount + date),
trains on 22/23-24/25 and tests on 25/26, and compares with a simple baseline.
Prints numbers and post types only - never any Tekst.

Put this file in the same folder as the Statements CSV files and run:
    py train_eval.py             version A: Tekst + date + amount
    py train_eval.py --no-text   version B: date + amount only
"""
import csv
import glob
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date

try:
    from scipy.sparse import hstack
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
except ImportError:
    sys.exit("scikit-learn is missing. Run:  py -m pip install scikit-learn   and try again.")

TRAIN_YEARS = ["22_23", "23_24", "24_25"]
TEST_YEARS = ["25_26"]

# Spelling variants of the same post type (agreed with Holger 22 Nov 2026)
MERGE = {
    "Udgifter til e-conomic": "Udgifter til E-conomic",
    "Voucher Cafe Globen": "Voucher Globen",
    "Omkostninger til bands": "Omkostning til bands",
    "Salg af Workshops": "Salg af workshops",
    "Salg af undervisning": "Salg undervisning",
}


# ---------- reading the files ----------

def find_header(rows):
    """Return (row number, {column name: column index}) for the header row."""
    for i, row in enumerate(rows):
        names = [c.strip() for c in row]
        if "Dato" in names and "Post typer" in names:
            return i, {n: names.index(n) for n in ["Dato", "Beløb", "Post typer", "Tekst"] if n in names}
    return None, {}


def parse_amount(s):
    s = s.replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def date_order(date_strings):
    """Decide per file if dates are day-first (05/09/2023) or month-first (9/15/2022)."""
    parts = [re.split(r"[/.\-]", d) for d in date_strings]
    if any(int(p[1]) > 12 for p in parts):
        return "month_first"
    return "day_first"


def parse_date(s, order):
    a, b, y = [int(x) for x in re.split(r"[/.\-]", s)]
    return date(y, a, b) if order == "month_first" else date(y, b, a)


def single_row_lines(path):
    """Bank lines that are ONE row in the sheet: (date, amount, post type, tekst)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    h, col = find_header(rows)
    if h is None:
        sys.exit(f"No header row with 'Dato' and 'Post typer' in {path}")
    lines = []
    for row in rows[h + 1:]:
        row = row + [""] * 20
        get = lambda name: row[col[name]].strip() if name in col else ""
        d, a, p, t = get("Dato"), get("Beløb"), get("Post typer"), get("Tekst")
        if not a and not p:
            continue
        if d:
            lines.append([])
        if lines:
            lines[-1].append((d, a, p, t))
    single = [l[0] for l in lines if len(l) == 1 and l[0][1] and l[0][2]]
    order = date_order([s[0] for s in single])
    return [(parse_date(d, order), parse_amount(a), MERGE.get(p, p), t) for d, a, p, t in single]


def load_years():
    by_year = {}
    for path in sorted(glob.glob("*.csv")):
        m = re.search(r"Statements_(\d\d)_(\d\d)", path)
        if not m:
            continue
        year = f"{m.group(1)}_{m.group(2)}"
        if year not in TRAIN_YEARS + TEST_YEARS:
            continue
        if year in by_year:
            sys.exit(f"Two files for {year} in the folder - keep only one.")
        by_year[year] = single_row_lines(path)
    missing = [y for y in TRAIN_YEARS + TEST_YEARS if y not in by_year]
    if missing:
        sys.exit(f"Missing Statements file(s) for: {', '.join(missing)}")
    return by_year


# ---------- features: what the model gets to see ----------

def structured_features(d, amount):
    """Date and amount turned into named features."""
    size = abs(amount)
    first_friday = d.weekday() == 4 and d.day <= 7
    third_friday = d.weekday() == 4 and 15 <= d.day <= 21
    return {
        "direction=" + ("in" if amount > 0 else "out"): 1,
        "size_bucket=" + str(int(math.log10(size + 1) * 4)): 1,   # 4 buckets per factor 10
        "exact_amount=" + f"{amount:.2f}": 1,                     # repeated fixed amounts
        "whole_hundred": 1 if size % 100 == 0 else 0,
        "has_øre": 1 if round(size % 1, 2) != 0 else 0,
        "weekday=" + str(d.weekday()): 1,
        "month=" + str(d.month): 1,
        "first_days_of_month": 1 if d.day <= 3 else 0,
        "last_days_of_month": 1 if d.day >= 28 else 0,
        "quarter_start": 1 if d.month in (1, 4, 7, 10) and d.day <= 3 else 0,
        "first_friday": 1 if first_friday else 0,
        "third_friday": 1 if third_friday else 0,
    }


class Model:
    def __init__(self, use_text=True):
        self.use_text = use_text
        self.text = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), lowercase=True)
        self.struct = DictVectorizer()
        self.clf = LogisticRegression(max_iter=5000)

    def _x(self, lines, fit):
        texts = [t for _, _, _, t in lines]
        dicts = [structured_features(d, a) for d, a, _, _ in lines]
        if not self.use_text:
            return self.struct.fit_transform(dicts) if fit else self.struct.transform(dicts)
        if fit:
            return hstack([self.text.fit_transform(texts), self.struct.fit_transform(dicts)])
        return hstack([self.text.transform(texts), self.struct.transform(dicts)])

    def fit(self, lines):
        self.clf.fit(self._x(lines, fit=True), [p for _, _, p, _ in lines])

    def predict(self, lines):
        return list(self.clf.predict(self._x(lines, fit=False)))


# ---------- baseline: a rule written by us ----------

class Baseline:
    """Same amount seen before -> its most common post type; otherwise the most common post type."""

    def fit(self, lines):
        per_amount = defaultdict(Counter)
        for _, a, p, _ in lines:
            per_amount[round(a, 2)][p] += 1
        self.per_amount = {a: c.most_common(1)[0][0] for a, c in per_amount.items()}
        self.most_common = Counter(p for _, _, p, _ in lines).most_common(1)[0][0]

    def predict(self, lines):
        return [self.per_amount.get(round(a, 2), self.most_common) for _, a, _, _ in lines]


# ---------- run ----------

def main():
    by_year = load_years()
    train = [l for y in TRAIN_YEARS for l in by_year[y]]
    test = [l for y in TEST_YEARS for l in by_year[y]]
    truth = [p for _, _, p, _ in test]

    print("Training years:", ", ".join(TRAIN_YEARS), f"-> {len(train)} single-row bank lines,",
          sum(1 for l in train if l[3]), "with Tekst")
    print("Test year:     ", ", ".join(TEST_YEARS), f"-> {len(test)} single-row bank lines,",
          sum(1 for l in test if l[3]), "with Tekst")
    print("Post types in training:", len({p for _, _, p, _ in train}))

    start = time.perf_counter()
    use_text = "--no-text" not in sys.argv
    print("Version:", "A - Tekst + date + amount" if use_text else "B - date + amount only (--no-text)")
    model = Model(use_text)
    model.fit(train)
    pred_model = model.predict(test)
    seconds = time.perf_counter() - start

    base = Baseline()
    base.fit(train)
    pred_base = base.predict(test)

    n = len(test)
    ok_model = sum(p == t for p, t in zip(pred_model, truth))
    ok_base = sum(p == t for p, t in zip(pred_base, truth))
    print()
    print(f"AI model: {ok_model} / {n} right = {100 * ok_model / n:.0f} %   (trained and tested in {seconds:.1f} s)")
    print(f"Baseline: {ok_base} / {n} right = {100 * ok_base / n:.0f} %")

    seen = {p for _, _, p, _ in train}
    print()
    print("Per post type in the test year:  lines | model right | baseline right")
    for post, count in Counter(truth).most_common():
        m = sum(1 for p, t in zip(pred_model, truth) if t == post and p == post)
        b = sum(1 for p, t in zip(pred_base, truth) if t == post and p == post)
        note = "" if post in seen else "   <- not in training data"
        print(f"  {count:>3} | {m:>3} | {b:>3}   {post}{note}")

    print()
    print("AI model mistakes (right answer -> model's suggestion):")
    wrong = Counter((t, p) for p, t in zip(pred_model, truth) if p != t)
    for (t, p), c in wrong.most_common():
        print(f"  {c} x  {t}  ->  {p}")


if __name__ == "__main__":
    main()
