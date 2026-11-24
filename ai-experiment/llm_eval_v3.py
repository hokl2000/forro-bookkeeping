"""Forró bookkeeping - LLM test, version 3: how SURE is the model, and can we trust that?

Same prompts as llm_eval_v2.py (descriptions + examples from the OTHER years), but:
  1. No forced answer format - like the browser version (the answer is checked against the list).
  2. The model returns log probabilities; confidence = the probability of the post type it chose.
Prints a table: if lines above a confidence threshold were booked automatically,
how many would that be, and how many of them would be wrong?

Uses Ollama on THIS PC (http://127.0.0.1:11434) - nothing is sent anywhere else.
Prints numbers and post types only - never any Tekst.

Needs train_eval.py, llm_eval_v2.py and the Statements CSV files in the same folder. Run:
    py llm_eval_v3.py                 (qwen3:1.7b)
"""
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request

from llm_eval_v2 import DESCRIPTIONS, TEXT_YEARS, system_prompt
from train_eval import Baseline, load_years

OLLAMA = "http://127.0.0.1:11434"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3:1.7b"
POST_TYPES = list(DESCRIPTIONS)
THRESHOLDS = [0.99, 0.95, 0.90, 0.80, 0.70, 0.60, 0.50]


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
    if MODEL not in installed:
        sys.exit(f"Model not downloaded yet. Run:  ollama pull {MODEL}")


def find_answer(text):
    """The same three checks as the browser page. Returns (post type, (start, end) in text) or (None, None)."""
    try:
        p = json.loads(text).get("post_type")
        if p in POST_TYPES:
            i = text.find('"' + p + '"')
            return p, (i + 1, i + 1 + len(p)) if i >= 0 else None
    except (ValueError, AttributeError):
        pass
    m = re.search(r'"post_type"\s*:\s*"([^"]+)"', text)
    if m and m.group(1) in POST_TYPES:
        return m.group(1), m.span(1)
    named = [p for p in POST_TYPES if p in text]
    if named:
        longest = max(named, key=len)
        if all(p in longest for p in named):
            i = text.find(longest)
            return longest, (i, i + len(longest))
    return None, None


def confidence(tokens, span):
    """Probability of the chosen post type = exp(sum of log probs of the tokens that spell it)."""
    if not tokens or span is None:
        return None
    pos, total = 0, 0.0
    for t in tokens:
        start, end = pos, pos + len(t["token"])
        if end > span[0] and start < span[1]:
            total += t["logprob"]
        pos = end
    return math.exp(total)


def ask(system, line):
    d, amount, _, text = line
    reply = ollama("/api/chat", {
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": f"Bank text: {text}\nAmount: {amount:.2f} DKK\nDate: {d.isoformat()}"}],
        "stream": False,
        "think": False,
        "logprobs": True,
        "options": {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 60},
    })
    content = reply["message"]["content"]
    tokens = reply.get("logprobs")
    if tokens is None:
        sys.exit("Ollama returned no log probabilities. Update Ollama (download the newest version from ollama.com) and try again.")
    if not tokens:
        return find_answer(content)[0], None
    # Work on the text the tokens spell, so positions match the log probs exactly
    joined = "".join(t["token"] for t in tokens)
    post, span = find_answer(joined)
    if post is None:
        post, span = find_answer(content)[0], None
    return post, confidence(tokens, span)


def main():
    check_ollama()
    by_year = load_years()
    test = [(y, l) for y in TEXT_YEARS for l in by_year[y] if l[3]]
    examples = {y: [l for yy in TEXT_YEARS if yy != y for l in by_year[yy] if l[3]] for y in TEXT_YEARS}
    truth = [l[2] for _, l in test]
    base = []
    for y, line in test:
        b = Baseline()
        b.fit([l for yy, lines in by_year.items() if yy != y for l in lines])
        base.extend(b.predict([line]))

    print(f"Model: {MODEL}   test lines: {len(test)}   (no forced format, like the browser)")
    start = time.perf_counter()
    preds, confs = [], []
    for i, (y, line) in enumerate(test, 1):
        p, c = ask(system_prompt(examples[y]), line)
        preds.append(p)
        confs.append(c)
        print(f"  {i}/{len(test)}", end="\r", flush=True)
    secs = time.perf_counter() - start
    n = len(test)
    right = [p == t for p, t in zip(preds, truth)]
    print(f"Model:    {sum(right)} / {n} right = {100 * sum(right) / n:.0f} %   ({secs / n:.1f} s per line)")
    print(f"Baseline: {sum(b == t for b, t in zip(base, truth))} / {n} right")
    print(f"No valid answer: {sum(p is None for p in preds)}   no confidence value: {sum(c is None for c in confs)}")

    print()
    print("If lines at or above the threshold were booked AUTOMATICALLY:")
    print("  threshold | booked automatically | of those WRONG | left for the treasurer |  per year: auto/wrong " + " ".join(TEXT_YEARS))
    for t in THRESHOLDS:
        auto = [i for i in range(n) if confs[i] is not None and confs[i] >= t]
        wrong = [i for i in auto if not right[i]]
        per_year = []
        for y in TEXT_YEARS:
            a = [i for i in auto if test[i][0] == y]
            per_year.append(f"{len(a)}/{sum(not right[i] for i in a)}")
        print(f"  {t:>8.0%}  | {len(auto):>3} of {n} ({100 * len(auto) / n:>3.0f} %)   | {len(wrong):>3}"
              f"            | {n - len(auto):>3}                     |  " + "  ".join(f"{p:>7}" for p in per_year))

    agree = [i for i in range(n) if preds[i] is not None and preds[i] == base[i]]
    print()
    print(f"AI and the amount rule AGREE on {len(agree)} lines; of those {sum(not right[i] for i in agree)} wrong.")
    both = [i for i in agree if confs[i] is not None and confs[i] >= 0.90]
    print(f"Agree AND AI at least 90 % sure: {len(both)} lines; of those {sum(not right[i] for i in both)} wrong.")

    print()
    print("Wrong answers the model was MOST sure of (right answer -> model's answer, confidence):")
    wrong_sorted = sorted([i for i in range(n) if not right[i] and confs[i] is not None], key=lambda i: -confs[i])
    for i in wrong_sorted[:10]:
        print(f"  {truth[i]}  ->  {preds[i]}   {confs[i]:.0%}")


if __name__ == "__main__":
    main()
