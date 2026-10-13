"""The Polymarket recorder's compaction (`scripts/record_polymarket.py`), on fixtures; no network."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("record_polymarket", Path(__file__).resolve().parents[2] / "scripts" / "record_polymarket.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


def _book(n_levels: int) -> str:
    bids = [{"price": f"{0.01 * i:.3f}", "size": "10"} for i in range(1, n_levels + 1)]           # ascending: best bid last
    asks = [{"price": f"{1 - 0.01 * i:.3f}", "size": "10"} for i in range(1, n_levels + 1)]      # descending: best ask last
    return json.dumps({"event_type": "book", "asset_id": "T", "market": "m", "bids": bids, "asks": asks, "hash": "h", "timestamp": "1"})


def test_book_depth_keeps_the_best_levels_each_side():
    out = json.loads(rp.compact(_book(80), {"T"}, {}, book_depth=50))
    assert len(out["bids"]) == 50 and len(out["asks"]) == 50 and out["book_depth"] == 50 and "hash" not in out
    assert max(float(b["price"]) for b in out["bids"]) == 0.80 and min(float(b["price"]) for b in out["bids"]) == 0.31   # the 50 highest bids
    assert min(float(a["price"]) for a in out["asks"]) == 0.20 and max(float(a["price"]) for a in out["asks"]) == 0.69   # the 50 lowest asks


def test_book_depth_leaves_small_books_and_other_messages_alone():
    small = json.loads(rp.compact(_book(10), {"T"}, {}, book_depth=50))
    assert len(small["bids"]) == 10 and "book_depth" not in small
    whole = json.loads(rp.compact(_book(80), {"T"}, {}, book_depth=None))
    assert len(whole["bids"]) == 80
    pc = json.dumps({"event_type": "price_change", "market": "m", "price_changes": [{"asset_id": "T", "price": "0.5", "best_bid": "0.49", "best_ask": "0.51", "size": "1", "side": "BUY"}], "timestamp": "1"})
    kept = json.loads(rp.compact(pc, {"T"}, {}, book_depth=50))
    assert kept["price_changes"][0]["best_bid"] == "0.49"
