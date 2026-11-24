"""Count what is in the Statements CSV files - prints numbers only, never any Tekst.

Put this file in the same folder as the Statements CSV files and run:  py count_data.py
"""
import csv
import glob
import os
from collections import Counter

WANTED = ["Dato", "Beløb", "Post typer", "Tekst"]


def find_header(rows):
    """Return (row number, {column name: column index}) for the header row."""
    for i, row in enumerate(rows):
        names = [c.strip() for c in row]
        if "Dato" in names and "Post typer" in names:
            return i, {n: names.index(n) for n in WANTED if n in names}
    return None, {}


def bank_lines(path):
    """Group rows into bank lines: a row with a date starts a new bank line,
    rows without a date continue the previous (split) bank line."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    h, col = find_header(rows)
    if h is None:
        return None, {}
    lines = []
    for row in rows[h + 1:]:
        row = row + [""] * 20
        get = lambda name: row[col[name]].strip() if name in col else ""
        date, amount, post, text = get("Dato"), get("Beløb"), get("Post typer"), get("Tekst")
        if not amount and not post:
            continue  # empty row or a note row
        if date:
            lines.append([])
        if lines:
            lines[-1].append((amount, post, text))
    return lines, col


all_posts = Counter()
files = sorted(glob.glob("*.csv"))
if not files:
    print("No .csv files found in this folder.")

for path in files:
    lines, col = bank_lines(path)
    print("=" * 60)
    print(os.path.basename(path))
    if lines is None:
        print("  No header row with 'Dato' and 'Post typer' found.")
        continue
    print("  Columns found:", ", ".join(col))
    single = [l[0] for l in lines if len(l) == 1 and l[0][0]]
    with_text = [s for s in single if s[2]]
    print("  Bank lines:", len(lines))
    print("  Single-row bank lines:", len(single))
    print("  ...with Tekst:", len(with_text), "  without Tekst:", len(single) - len(with_text))
    per_post = Counter(s[1] for s in single)
    per_post_text = Counter(s[1] for s in with_text)
    print("  Single-row lines per post type (with Tekst / total):")
    for post, n in per_post.most_common():
        print(f"    {per_post_text[post]:>3} / {n:<3} {post}")
    all_posts.update(s[1] for l in lines for s in l)

print("=" * 60)
print("All post type spellings in all files (rows):")
for post, n in sorted(all_posts.items()):
    print(f"  {n:>4}  {post}")