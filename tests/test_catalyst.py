import datetime as dt

import pandas as pd

from centaur.screens.catalyst import summarize_insider_activity, cross_reference, CatalystSummary

TODAY = dt.date(2026, 9, 10)


def _frame(rows):
    return pd.DataFrame(rows, columns=["Shares", "Value", "Text", "Insider", "Position", "Transaction", "Start Date"])


def test_insider_summary_counts_open_market_only():
    df = _frame([
        [1000, 150_000, "Purchase at price 150.00 per share.", "Jane CEO", "CEO", "Buy", TODAY - dt.timedelta(days=3)],
        [5000, 760_000, "Sale at price 152.00 per share.", "Bob CFO", "CFO", "Sale", TODAY - dt.timedelta(days=10)],
        [5000, 0, "Stock Award(Grant) at price 0.00 per share.", "Bob CFO", "CFO", "Award", TODAY - dt.timedelta(days=10)],
        [2000, 300_000, "Purchase at price 150.00 per share.", "Old Guy", "Director", "Buy", TODAY - dt.timedelta(days=90)],
    ])
    s = summarize_insider_activity("XYZ", df, days=30, as_of=TODAY)
    assert (s.buys, s.sells) == (1, 1)
    assert s.buy_value == 150_000 and s.sell_value == 760_000
    assert s.bias == "selling"


def test_cross_reference_contradiction():
    summary = CatalystSummary("XYZ", [{"point": "a", "evidence": "b", "category": "guidance"}] * 3,
                              [{"point": "c", "evidence": "d", "category": "margins"}] * 3, tone=0.6,
                              key_catalysts_ahead=[], one_line_thesis="guide up")
    df = _frame([[5000, 760_000, "Sale at price 152.00 per share.", "Bob CFO", "CFO", "Sale", TODAY - dt.timedelta(days=2)]])
    insiders = summarize_insider_activity("XYZ", df, as_of=TODAY)
    x = cross_reference(summary, insiders)
    assert x["verdict"] == "contradicts"
    assert any(s.startswith("fundamental:") for s in x["signals"])
    assert any(s.startswith("sentiment_flow:") for s in x["signals"])


def test_cross_reference_without_transcript():
    x = cross_reference(None, summarize_insider_activity("XYZ", pd.DataFrame(), as_of=TODAY))
    assert x["verdict"] == "unknown" and x["signals"] == []
