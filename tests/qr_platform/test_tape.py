"""Stage 0 of the maker-fill study: the virtual-order replay (qr/execution/tape.py)."""
import gzip
import json

import pandas as pd
import pytest

from qr.execution.tape import merge_streams, read_tape, replay, summarise, taker_sold


def _book(t, s, b, B, a, A):
    return {"t": t, "T": t, "s": s, "b": str(b), "B": str(B), "a": str(a), "A": str(A)}


def _trade(t, s, p, q, sold):
    return {"t": t, "T": t, "s": s, "p": str(p), "q": str(q), "m": sold}


def test_a_resting_bid_fills_when_the_queue_ahead_is_consumed_and_marks_one_minute_later():
    t0 = 1_700_000_000_000
    slot = 900_000
    first = t0 - (t0 % slot) + slot  # the first slot boundary after the opening book
    book = [_book(t0, "X", 100.0, 10.0, 100.1, 5.0), _book(first, "X", 100.0, 10.0, 100.1, 5.0)]
    trades = [
        _trade(first + 1_000, "X", 100.0, 4.0, True),    # taker sells 4 at the bid: queue 10 -> 6
        _trade(first + 2_000, "X", 100.1, 2.0, False),   # taker buys at the ask: irrelevant to the bid
        _trade(first + 3_000, "X", 100.0, 6.0, True),    # queue gone: the buy fills at 100.0
    ]
    book += [_book(first + 63_000, "X", 99.9, 3.0, 100.0, 3.0)]  # a minute later the mid is 99.95
    book += [_book(first + 2 * slot, "X", 99.9, 3.0, 100.0, 3.0)]  # expire the unfilled sell
    orders = replay(merge_streams(book, trades), slot_s=900, ttl_s=900, mark_after_s=60)
    buy = orders[(orders.side == "buy")].iloc[0]
    assert buy.filled and buy.wait_s == pytest.approx(3.0) and buy.fill_price == 100.0
    assert buy.mid_after == pytest.approx(99.95)
    assert buy.mark_bps == pytest.approx((100.0 - 99.95) / 100.0 * 1e4)  # 5 bps against the buyer
    sell = orders[(orders.side == "sell")].iloc[0]
    assert not sell.filled and pd.isna(sell.wait_s)
    s = summarise(orders)
    assert s["orders"] == 2 and s["overall"]["fill_900s"] == 0.5 and s["median_mark_bps"] == pytest.approx(5.0)


def test_a_print_through_the_level_fills_the_whole_queue_and_bybit_side_is_read():
    t0 = 1_700_000_000_000
    slot = 900_000
    first = t0 - (t0 % slot) + slot
    book = [_book(t0, "Y", 50.0, 100.0, 50.1, 100.0), _book(first, "Y", 50.0, 100.0, 50.1, 100.0)]
    trades = [{"t": first + 500, "T": first + 500, "s": "Y", "p": "50.2", "q": "1", "S": "Buy"}]  # a buy through the ask
    assert not taker_sold(trades[0])
    book += [_book(first + 61_000, "Y", 50.0, 100.0, 50.1, 100.0)]
    orders = replay(merge_streams(book, trades), slot_s=900, ttl_s=900)
    sell = orders[orders.side == "sell"].iloc[0]
    assert sell.filled and sell.wait_s == pytest.approx(0.5)
    assert sell.mark_bps == pytest.approx(-1 * (50.1 - 50.05) / 50.1 * 1e4)  # the mid stayed below: in the seller's favour


def test_read_tape_tolerates_a_truncated_last_member(tmp_path):
    path = tmp_path / "d.jsonl.gz"
    with gzip.open(path, "wt") as fh:
        fh.write(json.dumps({"t": 1, "s": "A"}) + "\n")
    with gzip.open(path, "at") as fh:
        fh.write(json.dumps({"t": 2, "s": "A"}) + "\n")
    data = path.read_bytes()
    path.write_bytes(data[:-7])  # chop the second member's trailer
    assert [r["t"] for r in read_tape(path)][:1] == [1]
