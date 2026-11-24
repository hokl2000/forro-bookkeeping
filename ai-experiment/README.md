# AI experiment: suggesting post types for bank lines

The bookkeeping page books most bank lines with fixed rules (MobilePay, Zettle, Café Globen). The lines that are left – the "yellow lines" – the volunteer treasurer has to categorise by hand into one of the club's post types (Danish bookkeeping categories such as *Omkostning til bands* or *Gebyr bank*).

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

Two lines apart on 39 is not a real difference. Without the text (`--no-text`) the result was exactly the same, and a small change in the input data moved it by 4 lines. Too little data for this approach.

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

On the older PC the real prompts did not run at all. Two problems were met on the way: WebLLM 0.2.83+ fails on low-end integrated GPUs ([web-llm issue #844](https://github.com/mlc-ai/web-llm/issues/844); pinned to 0.2.82), and with a forced JSON schema the first answer failed with a `GrammarMatcher` error (removed; the answer is now checked against the post-type list instead).

**Try your own computer:** [speed_test.html](https://hokl2000.github.io/forro-bookkeeping/ai-experiment/speed_test.html) runs the length test with dummy text – no data, nothing uploaded.

## What's next
1. Run the speed test on the treasurer's computer.
2. Add the model as an "AI suggestion" for the yellow lines on the bookkeeping page – the treasurer accepts or corrects it.
3. Test on new 2026/27 lines, including rule + model combined.

## Files
| File | What it does |
|---|---|
| `count_data.py` | Counts bank lines, lines with text and post types per year (numbers only). |
| `train_eval.py` | Experiment 1: scikit-learn model vs baseline. `--no-text` = date and amount only. |
| `llm_eval.py` | Experiment 2, version 1: Qwen3 via Ollama, no club knowledge. |
| `llm_eval_v2.py` | Experiment 2, version 2: with post-type descriptions and other-year examples. |
| `export_browser_test.py` | Writes the same prompts as `llm_eval_v2.py` to a local JSON file for the browser test. |
| `browser_test.html` | Experiment 3: the real test in the browser (reads the local JSON file; nothing is uploaded). |
| `speed_test.html` | Length test with dummy text – open it on any computer. |

## Run it yourself
Needs Python 3, `pip install scikit-learn`, and for experiment 2 [Ollama](https://ollama.com) with `ollama pull qwen3:1.7b` (local only). Put the Statements CSV files (columns Dato, Beløb, Post typer, Tekst) in this folder and run e.g. `py llm_eval_v2.py`. For the browser test: `py export_browser_test.py`, then `py -m http.server 8000 --bind 127.0.0.1` and open `http://127.0.0.1:8000/browser_test.html` in Chrome.
