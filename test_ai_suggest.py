import json
import os
import tempfile
from datetime import date

import ai_suggest
import web

# Made-up Statements tab (no real data): two empty top rows like the real export,
# a split bank line (two rows), an old spelling, a post type the AI doesn't know, a line without text.
HISTORY = (",,,,\n,,,,\nDato,Beløb,Post typer,Tekst,\n"
           "05/09/2023,-1200,Voucher Cafe Globen,Drinks Globen 01.09,\n"
           "10/10/2023,2350,Salg entre,OVERFØRSEL,\n"
           ",-88.12,Gebyr zettle,,\n"
           "11/10/2023,-746.25,Udgifter til e-conomic,LS VISMA E-CONOMIC A/S,\n"
           "13/10/2023,-500,Fonde,Something,\n"
           "29/12/2023,-152,Gebyr bank,,\n"
           "02/01/2024,-460,Gebyr bank,Omkostningsbidrag,\n")


def history_file(folder, text=HISTORY, name="history.csv"):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return path


def test_read_history():
    with tempfile.TemporaryDirectory() as folder:
        examples, message = ai_suggest.read_history(history_file(folder))
    assert [(d.isoformat(), a, p) for d, a, p, _ in examples] == [
        ("2023-09-05", -1200.0, "Voucher Globen"),          # old spelling merged
        ("2023-10-11", -746.25, "Udgifter til E-conomic"),
        ("2024-01-02", -460.0, "Gebyr bank")], examples   # split line, unknown type and empty text left out
    assert message == "3 example lines with bank text."


def test_read_history_month_first_and_wrong_file():
    text = "Dato,Beløb,Post typer,Tekst\n9/15/2022,-69.94,Web-hotel og domænenavne,Web hotel\n"
    with tempfile.TemporaryDirectory() as folder:
        examples, _ = ai_suggest.read_history(history_file(folder, text))
        assert examples[0][0] == date(2022, 9, 15)
        none, message = ai_suggest.read_history(history_file(folder, "Dato;Tekst;Rente fra;Beløb;Saldo\n", "bank.csv"))
    assert none == [] and "Statements tab" in message


def test_prompt_keeps_newest_examples_under_the_limit():
    examples = [(date(2020, 1, 1 + i % 28), -100.0 - i, "Gebyr bank", "x" * 200) for i in range(100)]
    prompt, used = ai_suggest.system_prompt(examples)
    assert len(prompt) <= ai_suggest.MAX_PROMPT and 0 < used < 100
    assert prompt.startswith(ai_suggest.INTRO) and "- Voucher Globen:" in prompt


def test_answer_checks():
    a = ai_suggest.answer
    assert a('{"post_type": "Voucher Globen"}') == "Globen vouchers"
    assert a('<think>\n\n</think>\n\n{"post_type": "Gebyr bank"}') == "Bank fee"
    assert a('```json\n{"post_type": "Salg entre"}\n```') == "Entrance fee sales"
    assert a("The answer is Omkostning til bands.") == "Band costs"
    assert a("Salg entre or Gebyr bank") == ""                 # two post types = no answer
    assert a('{"post_type": "Bank fee"}') == ""               # not one of the post types
    assert a("") == ""
    assert a('{"post_type": "Lån"}') == "Loan (liability)"
    assert a('{"post_type": "Overførsel mellem egne konti"}') == "Transfer between own accounts"


def test_which_lines_get_a_suggestion():
    yellow = {"date": "02.11.2026", "text": "Drinks Globen", "amount": -960.0, "category": "",
              "reason": "No rule or document matched"}
    assert ai_suggest.needs_ai(yellow)
    assert not ai_suggest.needs_ai({**yellow, "category": "Band costs"})          # she already chose
    assert not ai_suggest.needs_ai({**yellow, "text": " "})                       # no bank text
    assert not ai_suggest.needs_ai({**yellow, "reason": "Match: Zettle payout 01.11.2026, check"})
    assert ai_suggest.user_message(yellow) == "Bank text: Drinks Globen\nAmount: -960.00 DKK\nDate: 2026-11-02"


def test_reference_number_lines_are_not_sent_to_the_ai():
    from classify import bookings_for
    line = {"date": "09.11.2026", "text": "0200110044001061263", "amount": 346.53, "balance": 0.0}
    b = bookings_for(line, {}, [])[0]
    assert b["category"] == "" and b["reason"].startswith("Looks like a MobilePay transfer reference")
    assert not ai_suggest.needs_ai(b)
    other = bookings_for({**line, "text": "Loan from xxx"}, {}, [])[0]
    assert other["reason"] == "No rule or document matched" and ai_suggest.needs_ai(other)


def test_web_flow():
    with tempfile.TemporaryDirectory() as folder:
        res = json.loads(web.ai_history(json.dumps([[history_file(folder), "Statements_23_24.csv"]])))
    assert res["ok"] and res["message"].startswith("3 example lines read"), res
    bookings = [{"date": "02.11.2026", "text": "Drinks Globen", "amount": -960.0, "category": "",
                 "reason": "No rule or document matched"},
                {"date": "03.11.2026", "text": "OVERFØRSEL", "amount": 500.0, "category": "Classes sales",
                 "reason": "Match: MobilePay transfer 1"}]
    out = json.loads(web.ai_prompts(json.dumps(bookings)))
    assert [it["i"] for it in out["items"]] == [0]
    assert "Drinks Globen 01.09 | Amount: -1200.00 DKK -> Voucher Globen" in out["system"]
    assert web.ai_answer('{"post_type": "Voucher Globen"}') == "Globen vouchers"


if __name__ == "__main__":
    test_read_history()
    test_read_history_month_first_and_wrong_file()
    test_prompt_keeps_newest_examples_under_the_limit()
    test_answer_checks()
    test_which_lines_get_a_suggestion()
    test_reference_number_lines_are_not_sent_to_the_ai()
    test_web_flow()
    print("OK - 7 AI suggestion tests passed")
