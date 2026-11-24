"""Forró bookkeeping - LLM test, version 2: the model gets the club's knowledge.

New in version 2 (compared with llm_eval.py):
  1. A one-line description of every post type (written with Holger 22 Nov 2026).
  2. Real examples from the OTHER years (testing a 23/24 line: examples from 22/23 and 24/25 only),
     so the model never sees the answer for the line it is tested on.
Rule fixed BEFORE the run: one run per model, the result is reported as it is.

Uses Ollama on THIS PC (http://127.0.0.1:11434) - nothing is sent anywhere else.
Prints numbers and post types only - never any Tekst.

Needs train_eval.py and the Statements CSV files in the same folder. Run:
    py llm_eval_v2.py                      tests qwen3:1.7b and qwen3:4b
    py llm_eval_v2.py qwen3:4b             tests only that model
"""
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

from train_eval import Baseline, load_years

OLLAMA = "http://127.0.0.1:11434"
MODELS = sys.argv[1:] or ["qwen3:1.7b", "qwen3:4b"]
TEXT_YEARS = ["22_23", "23_24", "24_25"]

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
    "Renter": "interest charged by the bank",
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
}

INTRO = """You help the volunteer treasurer of Forró Copenhague, a Danish dance association \
(classes, Friday dance nights at Café Globen, workshops with dance teachers, concerts with bands, a festival).
You get ONE line from the association's bank statement: the bank text, the amount in DKK \
(negative = money out, positive = money in) and the date.
Choose the ONE post type (Danish bookkeeping category) that fits the line best.
Answer only with JSON: {"post_type": "<one post type from the list>"}"""


def system_prompt(examples):
    types = "\n".join(f"- {name}: {desc}" for name, desc in DESCRIPTIONS.items())
    ex = "\n".join(f"Bank text: {t} | Amount: {a:.2f} DKK -> {p}" for _, a, p, t in examples)
    return (f"{INTRO}\n\nPost types:\n{types}\n\n"
            f"Real lines from earlier years, with the post type the treasurer chose:\n{ex}")


def ollama(path, body=None):
    req = urllib.request.Request(OLLAMA + path,
                                 data=json.dumps(body).encode("utf-8") if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def check_ollama():
    try:
        installed = {m["name"] for m in ollama("/api/tags")["models"]}
    except (urllib.error.URLError, ConnectionError):
        sys.exit("Ollama is not running. Start the Ollama app and try again.")
    missing = [m for m in MODELS if m not in installed]
    if missing:
        sys.exit("Model(s) not downloaded yet. Run:  " + "   ".join(f"ollama pull {m}" for m in missing))


def ask(model, system, line):
    d, amount, _, text = line
    reply = ollama("/api/chat", {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": f"Bank text: {text}\nAmount: {amount:.2f} DKK\nDate: {d.isoformat()}"}],
        "stream": False,
        "think": False,
        "format": {"type": "object",
                   "properties": {"post_type": {"type": "string", "enum": list(DESCRIPTIONS)}},
                   "required": ["post_type"]},
        "options": {"temperature": 0, "seed": 42, "num_ctx": 8192},
    })
    try:
        return json.loads(reply["message"]["content"])["post_type"]
    except (KeyError, ValueError, TypeError):
        return "(no valid answer)"


def main():
    check_ollama()
    by_year = load_years()
    unknown = {l[2] for lines in by_year.values() for l in lines} - set(DESCRIPTIONS)
    if unknown:
        sys.exit(f"Post types without a description: {', '.join(sorted(unknown))}")

    test = [(y, l) for y in TEXT_YEARS for l in by_year[y] if l[3]]
    truth = [l[2] for _, l in test]
    # Examples for each test year: all lines WITH Tekst from the OTHER years
    examples = {y: [l for yy in TEXT_YEARS if yy != y for l in by_year[yy] if l[3]] for y in TEXT_YEARS}

    pred_base = []
    for y, line in test:
        base = Baseline()
        base.fit([l for yy, lines in by_year.items() if yy != y for l in lines])
        pred_base.extend(base.predict([line]))

    n = len(test)
    print(f"Test lines (single-row, with Tekst, {', '.join(TEXT_YEARS)}): {n}")
    print(f"Post types with a description: {len(DESCRIPTIONS)}")
    print("Examples in the prompt per test year: " +
          ", ".join(f"{y}: {len(examples[y])}" for y in TEXT_YEARS))
    ok_base = sum(p == t for p, t in zip(pred_base, truth))
    print(f"Baseline: {ok_base} / {n} right = {100 * ok_base / n:.0f} %")

    for model in MODELS:
        print()
        print("=" * 60)
        print("Model:", model)
        start = time.perf_counter()
        preds = []
        for i, (y, line) in enumerate(test, 1):
            preds.append(ask(model, system_prompt(examples[y]), line))
            print(f"  {i}/{n}", end="\r", flush=True)
        seconds = time.perf_counter() - start
        ok = sum(p == t for p, t in zip(preds, truth))
        print(f"{model}: {ok} / {n} right = {100 * ok / n:.0f} %   "
              f"({seconds:.0f} s in all, {seconds / n:.1f} s per line)")
        for y in TEXT_YEARS:
            idx = [i for i, (yy, _) in enumerate(test) if yy == y]
            m = sum(preds[i] == truth[i] for i in idx)
            b = sum(pred_base[i] == truth[i] for i in idx)
            print(f"  {y}: model {m} / {len(idx)}   baseline {b} / {len(idx)}")
        print("  Per post type:  lines | model right | baseline right")
        for post, count in Counter(truth).most_common():
            m = sum(1 for p, t in zip(preds, truth) if t == post and p == post)
            b = sum(1 for p, t in zip(pred_base, truth) if t == post and p == post)
            print(f"    {count:>3} | {m:>3} | {b:>3}   {post}")
        print("  Mistakes (right answer -> model's suggestion):")
        for (t, p), c in Counter((t, p) for p, t in zip(preds, truth) if p != t).most_common():
            print(f"    {c} x  {t}  ->  {p}")


if __name__ == "__main__":
    main()