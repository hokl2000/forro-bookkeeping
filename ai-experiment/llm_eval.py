"""Forró bookkeeping - can a local open-source LLM suggest the post type from the bank text?

Uses Ollama on THIS PC (http://127.0.0.1:11434) - nothing is sent anywhere else.
Test set: every single-row bank line WITH Tekst in 22/23, 23/24 and 24/25.
Compares each model with the baseline (same amount seen in the other years -> that post type).
Prints numbers and post types only - never any Tekst.

Needs train_eval.py and the Statements CSV files in the same folder. Run:
    py llm_eval.py                      tests qwen3:1.7b and qwen3:4b
    py llm_eval.py qwen3:1.7b           tests only that model
"""
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

from train_eval import Baseline, MERGE, load_years

OLLAMA = "http://127.0.0.1:11434"
MODELS = sys.argv[1:] or ["qwen3:1.7b", "qwen3:4b"]
TEXT_YEARS = ["22_23", "23_24", "24_25"]

SYSTEM_PROMPT = """You help the volunteer treasurer of Forró Copenhague, a Danish dance association \
(classes, Friday dance nights at Café Globen, workshops with dance teachers, concerts with bands, a festival).
You get ONE line from the association's bank statement: the bank text, the amount in DKK \
(negative = money out, positive = money in) and the date.
Choose the ONE post type (Danish bookkeeping category) from the list that fits the line best.
Answer only with JSON: {"post_type": "<one post type from the list>"}"""


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


def ask(model, post_types, line):
    d, amount, _, text = line
    user = (f"Post types: {json.dumps(post_types, ensure_ascii=False)}\n\n"
            f"Bank text: {text}\nAmount: {amount:.2f} DKK\nDate: {d.isoformat()}")
    reply = ollama("/api/chat", {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user}],
        "stream": False,
        "think": False,
        "format": {"type": "object",
                   "properties": {"post_type": {"type": "string", "enum": post_types}},
                   "required": ["post_type"]},
        "options": {"temperature": 0, "seed": 42},
    })
    try:
        return json.loads(reply["message"]["content"])["post_type"]
    except (KeyError, ValueError, TypeError):
        return "(no valid answer)"


def main():
    check_ollama()
    by_year = load_years()
    test = [(y, l) for y in TEXT_YEARS for l in by_year[y] if l[3]]
    truth = [l[2] for _, l in test]
    # The list the model chooses from: every post type used in the files (spellings merged)
    post_types = sorted({l[2] for lines in by_year.values() for l in lines} | set(MERGE.values()))

    # Baseline: for each test year, learn amounts from all OTHER years
    pred_base = []
    for y, line in test:
        base = Baseline()
        base.fit([l for yy, lines in by_year.items() if yy != y for l in lines])
        pred_base.extend(base.predict([line]))

    n = len(test)
    print(f"Test lines (single-row, with Tekst, {', '.join(TEXT_YEARS)}): {n}")
    print(f"Post types the model can choose from: {len(post_types)}")
    ok_base = sum(p == t for p, t in zip(pred_base, truth))
    print(f"Baseline: {ok_base} / {n} right = {100 * ok_base / n:.0f} %")

    for model in MODELS:
        print()
        print("=" * 60)
        print("Model:", model)
        start = time.perf_counter()
        preds = []
        for i, (_, line) in enumerate(test, 1):
            preds.append(ask(model, post_types, line))
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