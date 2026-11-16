# Forró Copenhague – bookkeeping

A web page that does the year-end bookkeeping for the dance association Forró Copenhague.
The treasurer adds the year's bank, MobilePay and Zettle files, checks the bookings on the page
and downloads the year's rows ready to paste into the association's Google Sheet.

**Your files never leave your computer.** The page runs Python inside the browser
([Pyodide](https://pyodide.org)); nothing is uploaded.

## Why

The treasurer is a volunteer. Booking a year of bank lines by hand – splitting every MobilePay
and Zettle payout into classes, entrance and fees – is the part of the job nobody wants to do.
This page books what it can recognise and leaves only the rest to the treasurer. 

## What it does

1. **Reads three files** and checks that each is the right one, with a plain message if not:
   - bank statement (CSV, "Eksporter til CSV"),
   - MobilePay transactions report (CSV),
   - Zettle account statement (xlsx, "Udbetalinger → Eksporter til Excel").
2. **Books automatically** where a rule or document fits:
   - a MobilePay payout is matched to the MobilePay report by its full transfer reference and split by MobilePay's categories, plus the fee,
   - a Zettle payout is matched by amount and date and split by payment time (class time, the Globen social on the first Friday) plus the fee,
   - the event (Globen, Beginner classes) is filled in where it is known.
3. **Leaves the rest to the treasurer** in a review table: yellow lines need a category, every automatic line shows *why* it was booked and can be changed.
4. **Checks before the file is made:** every line has a category, one financial year (1 August – 31 July), and the bookings end at the bank's own balance. A bank file with a missing line is refused when it is added.
5. **Instructor contracts:** for each workshop with an instructor payment, it compares what was paid with the contract (a % of the profit, or a fixed amount) and warns if they differ.
6. **Save progress** to a file and continue later, on any computer.
7. **Download Statements:** the year's rows in the exact layout of the Google Sheet's Statements tab (Danish post types, events, running balance).

## Use it

Open the page, wait until it says *Ready*, and follow the steps on the page.

## Run it locally

```
python -m http.server 8000 --bind 127.0.0.1
```
Then open http://127.0.0.1:8000.

## Tests

The tests use made-up data only.
```
python test_web.py
python test_match.py
python test_friday.py
python test_events.py
python test_read_review.py
python test_year_end.py
python test_read_bank.py
python test_read_documents.py
```

## Files

| File | What it does |
|---|---|
| `index.html` | The page |
| `web.py` | Glue between the page and the Python code: file checks, bookings, checks, Statements and progress files |
| `read_bank.py`, `read_mobilepay.py`, `read_zettle.py` | Read the three files |
| `match.py`, `classify.py` | Match bank lines to MobilePay/Zettle and book them |
| `review.py`, `post_types.py`, `event_types.py` | Categories, Danish post types and events (copied from the Google Sheet) |
| `events.py` | Instructor contract check |
| `year_end.py`, `read_review.py`, `run.py` | The command-line version the page grew out of |
| `read_documents.py` | Reads BilletFix statements (not used by the page yet) |

## Status

Built in November 2026.
