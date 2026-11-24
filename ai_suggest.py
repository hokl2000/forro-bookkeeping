"""AI suggestions for the yellow lines (bank lines no rule or document could book).

The model (Qwen3 1.7B) runs in the treasurer's browser with WebLLM; this file builds its prompts
and checks its answers. Built on the set-up measured in ai-experiment/ (llm_eval_v2.py + browser_test.html):
a one-line description per post type + real lines from earlier years as examples. Differences: 22 post types
(Lån and Overførsel mellem egne konti added, Renter dropped), and the examples come from the treasurer's own
Statements files, newest first up to MAX_PROMPT characters. This version has not been re-measured.

The examples come from the treasurer's own Statements files of earlier years, read in her browser.
They contain names, so they are never part of this repo.
"""
import csv
import json
import re
from datetime import date

from post_types import POST_TYPES

# Danish post type -> one-line description (written with Holger, 22 Nov 2026).
# The post types the AI was tested on (ai-experiment/README.md), plus Lån and Overførsel mellem egne konti
# (added 24 Nov 2026 after the first real test: the bank change in Oct 2026 brought a loan and a transfer).
# The treasurer picks any other post type herself.
DESCRIPTIONS = {
    "Flybilletter": "plane tickets, e.g. for teachers or artists flying in",
    "Forplejning til diverse": "food and snacks for events, volunteers and meetings",
    "Gebyr bank": "the bank's own fees (e.g. 'Omkostningsbidrag', 'Gebyr iflg nota')",
    "Gebyr diverse": "other fees and memberships, e.g. MitID registration, membership of Casa Latina",
    "Gebyr zettle": "fees for card payments through Zettle",
    "Kontorartikler og tryksager": "office supplies and printed items, e.g. wristbands, flyers",
    "Køb af Drikkevarer": "buying drinks for events",
    "Lokaleomkostninger": "venue costs: rent, cleaning, the municipality's facility fees, decoration",
    "Omkostning til bands": "payments to bands and musicians, incl. bonuses and sound technicians",
    "Omkostning til danselærer": "payments to dance teachers, incl. their meals",
    "Omkostning til transport": "travel by train, bus and car, and parking",
    "Retur": "money returned to the association, e.g. a refund of a reservation (usually money in)",
    "Salg Drikkevarer": "drink sales (the association no longer sells drinks)",
    "Salg af kontigent": "membership fees paid in",
    "Salg af workshops": "workshop ticket sales, e.g. payouts from BilletFix",
    "Salg entre": "entrance sales for Globen nights, concerts and parties, "
                  "e.g. payouts from PayPal, Ticketbutler, BilletFix or Zettle",
    "Salg undervisning": "payments for classes, e.g. beginner classes",
    "Udgifter til E-conomic": "the accounting system's subscription (Visma e-conomic)",
    "Voucher Globen": "payment to Café Globen for the drink vouchers guests get with their entrance; "
                      "bank text often 'Drinks Globen'",
    "Web-hotel og domænenavne": "website hosting and domain names",
    "Lån": "a loan to the association, or paying a loan back (e.g. 'Loan from …')",
    "Overførsel mellem egne konti": "moving money between the association's own bank accounts, e.g. when changing bank",
}

# Older spellings in the Statements tabs -> today's post type (agreed with Holger 22 Nov 2026)
MERGE = {
    "Udgifter til e-conomic": "Udgifter til E-conomic",
    "Voucher Cafe Globen": "Voucher Globen",
    "Omkostninger til bands": "Omkostning til bands",
    "Salg af Workshops": "Salg af workshops",
    "Salg af undervisning": "Salg undervisning",
}

TO_CATEGORY = {danish: english for english, danish in POST_TYPES.items()}   # Danish -> the page's category
MAX_PROMPT = 8600   # characters; the longest prompt measured in the browser test (ai-experiment/README.md)

INTRO = """You help the volunteer treasurer of Forró Copenhague, a Danish dance association \
(classes, Friday dance nights at Café Globen, workshops with dance teachers, concerts with bands, a festival).
You get ONE line from the association's bank statement: the bank text, the amount in DKK \
(negative = money out, positive = money in) and the date.
Choose the ONE post type (Danish bookkeeping category) that fits the line best.
Answer only with JSON: {"post_type": "<one post type from the list>"}"""


def _header(rows):
    for i, row in enumerate(rows):
        names = [c.strip() for c in row]
        if "Dato" in names and "Post typer" in names and "Tekst" in names:
            return i, {n: names.index(n) for n in ("Dato", "Beløb", "Post typer", "Tekst") if n in names}
    return None, {}


def _amount(s):
    s = s.replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def _dates(strings):
    """Google Sheets exports dates day-first (05/09/2023) or month-first (9/15/2022) - decide per file."""
    parts = [re.split(r"[/.\-]", s) for s in strings]
    month_first = any(len(p) == 3 and p[1].isdigit() and int(p[1]) > 12 for p in parts)
    out = []
    for p in parts:
        a, b, y = (int(x) for x in p)
        out.append(date(y, a, b) if month_first else date(y, b, a))
    return out


def read_history(path):
    """Examples from one Statements tab saved as CSV: single-row bank lines with bank text and a
    post type the AI knows. Returns (examples, message). examples = [(date, amount, post type, text)]."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    except (UnicodeDecodeError, OSError):
        return [], "This is not a CSV file. In the Google Sheet, open a Statements tab and choose File → Download → CSV."
    h, col = _header(rows)
    if h is None or "Beløb" not in col:
        return [], ("This doesn't look like a Statements tab: it needs the columns Dato, Beløb, "
                    "Post typer and Tekst. In the Google Sheet, open a Statements tab and choose File → Download → CSV.")
    lines = []
    for row in rows[h + 1:]:
        row = row + [""] * 20
        d, a, p, t = (row[col[n]].strip() for n in ("Dato", "Beløb", "Post typer", "Tekst"))
        if not a and not p:
            continue
        if d:
            lines.append([])            # a row with a date starts a bank line
        if lines:
            lines[-1].append((d, a, p, t))
    single = [l[0] for l in lines if len(l) == 1]
    usable = [(d, a, MERGE.get(p, p), t) for d, a, p, t in single if a and t and MERGE.get(p, p) in DESCRIPTIONS]
    try:
        days = _dates([d for d, _, _, _ in usable])
        examples = [(day, _amount(a), p, t) for day, (_, a, p, t) in zip(days, usable)]
    except ValueError:
        return [], "A date or amount in this file can't be read. Download the tab again as CSV."
    return examples, f"{len(examples)} example lines with bank text."


def system_prompt(examples):
    """Descriptions + examples, newest first until MAX_PROMPT characters, then shown oldest first."""
    types = "\n".join(f"- {name}: {desc}" for name, desc in DESCRIPTIONS.items())
    head = (f"{INTRO}\n\nPost types:\n{types}\n\n"
            "Real lines from earlier years, with the post type the treasurer chose:\n")
    chosen, size = [], len(head)
    for d, a, p, t in sorted(examples, key=lambda e: e[0], reverse=True):
        line = f"Bank text: {t} | Amount: {a:.2f} DKK -> {p}\n"
        if size + len(line) > MAX_PROMPT:
            break
        chosen.append((d, line))
        size += len(line)
    return head + "".join(line for _, line in sorted(chosen, key=lambda c: c[0])).rstrip("\n"), len(chosen)


def user_message(booking):
    d = date(*reversed([int(x) for x in booking["date"].split(".")]))   # dd.mm.yyyy
    return f"Bank text: {booking['text']}\nAmount: {booking['amount']:.2f} DKK\nDate: {d.isoformat()}"


def needs_ai(booking):
    """Yellow lines the AI may suggest for: no rule or document matched, the treasurer hasn't chosen yet."""
    return booking.get("reason") == "No rule or document matched" and not booking.get("category") \
        and bool(booking.get("text", "").strip())


def answer(text):
    """The model's answer -> the page's category, or "" if it isn't one post type from the list.
    The same three checks as ai-experiment/browser_test.html."""
    text = re.sub(r"<think>[\s\S]*?</think>", "", text or "").strip()
    post = None
    try:
        p = json.loads(text).get("post_type")
        post = p if p in DESCRIPTIONS else None
    except (ValueError, AttributeError):
        pass
    if post is None:
        m = re.search(r'"post_type"\s*:\s*"([^"]+)"', text)
        if m and m.group(1) in DESCRIPTIONS:
            post = m.group(1)
    if post is None:
        named = [p for p in DESCRIPTIONS if p in text]
        longest = max(named, key=len) if named else None
        if longest and all(p in longest for p in named):
            post = longest
    return TO_CATEGORY.get(post, "") if post else ""
