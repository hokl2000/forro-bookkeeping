"""Writes browser_test.json: the SAME prompts as llm_eval_v2.py, for the browser test page.

The file contains bank texts (with names) - it stays in this folder and is never uploaded or committed.
Run:  py export_browser_test.py
"""
import json

from llm_eval_v2 import DESCRIPTIONS, TEXT_YEARS, system_prompt
from train_eval import Baseline, load_years


def main():
    by_year = load_years()
    examples = {y: [l for yy in TEXT_YEARS if yy != y for l in by_year[yy] if l[3]] for y in TEXT_YEARS}
    items = []
    for y in TEXT_YEARS:
        base = Baseline()
        base.fit([l for yy, lines in by_year.items() if yy != y for l in lines])
        for line in by_year[y]:
            d, amount, post, text = line
            if not text:
                continue
            items.append({
                "year": y,
                "system": system_prompt(examples[y]),
                "user": f"Bank text: {text}\nAmount: {amount:.2f} DKK\nDate: {d.isoformat()}",
                "truth": post,
                "baseline": base.predict([line])[0],
            })
    with open("browser_test.json", "w", encoding="utf-8") as f:
        json.dump({"post_types": list(DESCRIPTIONS), "items": items}, f, ensure_ascii=False)
    longest = max(len(i["system"]) + len(i["user"]) for i in items)
    print(f"browser_test.json written: {len(items)} lines, longest prompt {longest} characters.")


if __name__ == "__main__":
    main()