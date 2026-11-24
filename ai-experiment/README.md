# AI experiment: suggesting post types for bank lines

The bookkeeping page books the bank lines it can recognise with fixed rules (MobilePay, Zettle, Café Globen). The lines that are left – the "yellow lines" – the volunteer treasurer has to categorise by hand into one of the club's post types (Danish bookkeeping categories such as *Omkostning til bands* or *Gebyr bank*).

This folder is the experiment behind one question: **can an AI suggest the right post type for those lines, so the treasurer only has to accept or correct it?**

Everything here runs locally and for free. The club's real data is **not** in this repo (see `.gitignore`).

## Data

The club's own bookkeeping, financial years 2022/23 – 2025/26 (1 Aug – 31 Jul), exported from the Google Sheet as CSV. Only bank lines that are one row in the sheet are used (a split line's total is not in the sheet as one number).

| Year | Bank lines (single-row) | …with bank text |
|---|---|---|
| 2022/23 | 54 | 40 |
| 2023/24 | 46 | 30 |
| 2024/25 | 49 | 17 |
| 2025/26 | 39 | 0 |

The bank text contains names, so every script runs on the owner's own PC and prints numbers and post types only – never any bank text.

Every result is compared with a **baseline**, a simple rule: *if the same amount has been seen before, choose the post type it had; otherwise the most common post type.* If an AI cannot beat that rule, it is not worth calling AI.

## Results

### 1. Classic machine learning (scikit-learn) – about as good as the rule
`train_eval.py`: logistic regression on character n-grams of the bank text plus date/amount features. Trained on 2022/23–2024/25 (149 lines), tested on 2025/26 (39 lines).

| | right |
|---|---|
| Model | 20 / 39 (51 %) |
| Baseline | 18 / 39 (46 %) |

Two lines apart on 39 is not a real difference. Without the text (`--no-text`, run on a copy with names removed) the result was exactly the same, and a small change in the input data moved it by 4 lines. Too little data for this approach.

### 2. A local open-source language model (Qwen3 via Ollama)
Test set: the 87 lines that have bank text. The model gets the bank text, amount and date and must choose one of the 21 post types used in the files.

| | right | 22/23 (40) | 23/24 (30) | 24/25 (17) | time per line* |
|---|---|---|---|---|---|
| Baseline | 28 (32 %) | 11 | 11 | 6 | – |
| Qwen3 1.7B, no club knowledge (`llm_eval.py`) | 14 (16 %) | 0 | 6 | 8 | 2.8 s |
| Qwen3 4B, no club knowledge | 17 (20 %) | 1 | 8 | 8 | 7.5 s |
| **Qwen3 1.7B, with club knowledge (`llm_eval_v2.py`)** | **42 (48 %)** | 13 | 15 | 14 | 7.3 s |
| Qwen3 4B, with club knowledge | 49 (56 %) | 15 | 20 | 14 | 23.3 s |

\* on one Windows PC.

"Club knowledge" = a one-line description of every post type, plus real lines from the **other** years as examples (when a 2023/24 line is tested, the examples come only from 2022/23 and 2024/25, so the model never sees the answer). Without it, the model guessed things like "drinks" for the club's Café Globen voucher payments.

The rule for choosing a model was fixed before the run: **the smallest model that clearly beats the baseline** – Qwen3 1.7B.

**Honest caveats**
- The post-type descriptions were written *after* seeing the first run's mistakes, and they mention bank-text patterns from the same lines. So 48 % is somewhat optimistic. A clean test needs new lines (the 2026/27 year).
- 87 lines and 21 of the club's 44 post types.
- The weak spot is *Voucher Globen*: the model got 6 of 18, the amount rule 18 of 18. Combining the rule and the model is the obvious next step – and must also be tested on new lines.

### 3. Can it run in the treasurer's browser? Yes – on a modern PC
The bookkeeping page runs in the browser, so the model should too: WebLLM + WebGPU, nothing installed, nothing uploaded (`browser_test.html`).

**Speed** (`speed_test.html`, dummy prompts):

| Prompt | Older PC, integrated Intel GPU | Newer PC, integrated Intel Xe2 GPU |
|---|---|---|
| 500 characters | 34 s | 2.4 s |
| 2,000 characters | 109 s | 5.9 s |
| 4,000 characters | 238 s | 11.6 s |
| 8,000 characters | crashed | 25 s (3,637 tokens) |

**Accuracy in the browser** (newer PC, the same 87 lines and prompts as `llm_eval_v2.py`):

| | right | 22/23 (40) | 23/24 (30) | 24/25 (17) | time per line |
|---|---|---|---|---|---|
| Baseline | 28 (32 %) | 11 | 11 | 6 | – |
| Qwen3 1.7B, Ollama | 42 (48 %) | 13 | 15 | 14 | 7.3 s |
| **Qwen3 1.7B, browser** | **38 (44 %)** | 11 | 13 | 14 | 11.3 s |

0 of 87 answers were outside the post-type list. The browser version is 4 lines below Ollama – it uses a different quantised build of the model and no forced answer format – and identical on 2024/25, the year whose bank text is most like today's.

On the older PC the real prompts did not run at all. Two problems were met on the way: WebLLM 0.2.83+ fails on low-end integrated GPUs ([web-llm issue #844](https://github.com/mlc-ai/web-llm/issues/844); pinned to 0.2.82), and with a forced JSON schema the first answer failed with a `GrammarMatcher` error on the newest WebLLM version (cause not confirmed). The forced format was removed; the answer is now checked against the post-type list instead.

**Try your own computer:** [speed_test.html](https://hokl2000.github.io/forro-bookkeeping/ai-experiment/speed_test.html) runs the length test with dummy text – no data, nothing uploaded.

### 4. Can the model's confidence decide which lines to book automatically? No
`llm_eval_v3.py` asks the same 87 lines again (Ollama, Qwen3 1.7B, no forced answer format – like the browser) and reads the model's log probabilities: how sure it is of the post type it chose. If lines above a threshold were booked without the treasurer:

| Book automatically when the model is at least … sure | Lines booked automatically | Of those, wrong |
|---|---|---|
| 99 % | 36 of 87 | 12 |
| 95 % | 59 of 87 | 25 |
| 90 % | 69 of 87 | 32 |

Even at 99 % it was wrong one time in three – the small model is overconfident. So **the treasurer confirms every suggestion**; nothing is booked by the AI alone. (When the model and the amount rule agreed: 15 lines, 2 wrong.)

Qwen3 4B could not be tested this way: without a forced format it writes its reasoning first, even with thinking switched off, so no answer came within the token limit. Letting it finish would make it far too slow for the browser.

### 5. In the live page
The model now runs in the bookkeeping page itself (`../ai_suggest.py`, `../index.html`): purple lines with a suggestion, Confirm or Confirm all, and the download is blocked until every suggestion is confirmed or changed. First real test (a newer PC, the current year's files): 3 suggestions, 1 right. The 2 misses were fixed before publishing: *Loan* was not on the model's list of post types (added, with *Transfer between own accounts*), and one bank text was only a transfer reference number – such lines now get a rule-based hint ("looks like a MobilePay payout missing from the MobilePay file") instead of an AI guess.

The page's set-up is built on the one measured above, with two differences: 22 post types instead of 21 (*Loan* and *Transfer between own accounts* added, *Renter* dropped because it is no longer a post type), and the examples come from the Statements files the treasurer adds (newest first, up to 8,600 characters). That version has so far only had the 3-line test above – the 38/87 and 42/87 results are from the experiment.

## What's next
1. Run the speed test on the treasurer's computer.
2. Measure the page on new 2026/27 lines as they come in – the first clean test, since the descriptions were written after seeing the old lines.
3. Rule + model combined (e.g. Café Globen vouchers by amount) – tested on new lines only.

## Files
| File | What it does |
|---|---|
| `count_data.py` | Counts bank lines, lines with text and post types per year (numbers only). |
| `train_eval.py` | Experiment 1: scikit-learn model vs baseline. `--no-text` = date and amount only. |
| `llm_eval.py` | Experiment 2, version 1: Qwen3 via Ollama, no club knowledge. |
| `llm_eval_v2.py` | Experiment 2, version 2: with post-type descriptions and other-year examples. |
| `llm_eval_v3.py` | Experiment 4: the model's confidence (log probabilities) – how many lines could be booked automatically, and how many of those would be wrong. |
| `export_browser_test.py` | Writes the same prompts as `llm_eval_v2.py` to a local JSON file for the browser test. |
| `browser_test.html` | Experiment 3: the real test in the browser (reads the local JSON file; nothing is uploaded). |
| `speed_test.html` | Length test with dummy text – open it on any computer. |

## Run it yourself
Needs Python 3, `pip install scikit-learn`, and for experiment 2 [Ollama](https://ollama.com) with `ollama pull qwen3:1.7b` (local only). Put the Statements CSV files (columns Dato, Beløb, Post typer, Tekst) in this folder and run e.g. `py llm_eval_v2.py`. For the browser test: `py export_browser_test.py`, then `py -m http.server 8000 --bind 127.0.0.1` and open `http://127.0.0.1:8000/browser_test.html` in Chrome.
