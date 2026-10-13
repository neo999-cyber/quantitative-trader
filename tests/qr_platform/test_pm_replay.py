"""The v2 intraday replay on a synthetic recording: state, hourly decisions, price-through fills, TTL crosses, settlement."""
from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from qr.execution.pm_replay import Market, WedgeSession, iter_events, model_prob

T0 = int(pd.Timestamp("2026-10-01 00:00", tz="UTC").timestamp())
YES = "111"


def _write(rec: Path, venue: str, lines: list[tuple[float, dict]]) -> None:
    by_hour: dict[str, list] = {}
    for t, msg in lines:
        h = pd.Timestamp(t, unit="s", tz="UTC").strftime("%Y-%m-%d/%H")
        by_hour.setdefault(h, []).append(json.dumps({"venue": venue, "recorded_at": t, "raw": json.dumps(msg)}))
    for h, ls in by_hour.items():
        f = rec / venue / f"{h}.jsonl.gz"
        f.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(f, "at", encoding="utf-8") as fh:
            fh.write("\n".join(ls) + "\n")


def _pm(t, bid, ask):
    return (t, {"market": "0xm", "price_changes": [{"asset_id": YES, "price": str(bid), "size": "10", "side": "BUY", "best_bid": str(bid), "best_ask": str(ask)}], "timestamp": str(int(t * 1000)), "event_type": "price_change"})


def _trade(t, price, side="BUY"):
    return (t, {"market": "0xm", "asset_id": YES, "price": str(price), "size": "100", "side": side, "timestamp": str(int(t * 1000)), "event_type": "last_trade_price"})


def _dvol(t, ccy, v):
    return (t, {"jsonrpc": "2.0", "method": "subscription", "params": {"channel": f"deribit_volatility_index.{ccy}_usd", "data": {"timestamp": int(t * 1000), "volatility": v}}})


def _idx(t, ccy, p):
    return (t, {"jsonrpc": "2.0", "method": "subscription", "params": {"channel": f"deribit_price_index.{ccy}_usd", "data": {"timestamp": int(t * 1000), "price": p}}})


@pytest.fixture
def recording(tmp_path):
    rec = tmp_path / "rec"
    # BTC at 100k, DVOL 50, a "reach $120k by +30d" market whose model probability is ~0.19; the book quotes 0.35/0.37
    pmlines = [_pm(T0 + 60, 0.35, 0.37), _pm(T0 + 3600 * 5, 0.35, 0.37), _trade(T0 + 3600 * 1 + 600, 0.37), _pm(T0 + 3600 * 30, 0.18, 0.20), _trade(T0 + 3600 * 31 + 100, 0.18, "SELL")]
    _write(rec, "polymarket", pmlines)
    _write(rec, "deribit", [_dvol(T0 + 30, "btc", 50.0), _idx(T0 + 31, "btc", 100_000.0), _dvol(T0 + 3600 * 40, "btc", 50.0)])
    return rec


def _market():
    return {YES: Market(YES, "m", "BTC", "reach", 120_000.0, pd.Timestamp("2026-10-31", tz="UTC"), resolved_yes=0.0)}


def test_events_are_time_ordered(recording):
    ts = [t for t, _, _ in iter_events(recording)]
    assert ts == sorted(ts) and len(ts) == 8


def test_family_sells_on_wedge_fills_on_print_through_and_exits_on_close(recording):
    mk = _market()
    p = model_prob("reach", 100_000.0, 120_000.0, 0.5, 30 / 365)
    assert 0.1 < p < 0.3
    sess = WedgeSession(mk, k=0.05, T="resolution", side="sell")
    sess.run(iter_events(recording))
    tr = sess.trade_table()
    assert len(tr) == 1
    t = tr.iloc[0]
    assert t.fill == pytest.approx(0.37)                      # posted at the ask at 01:00, the 01:10 print at 0.37 fills it
    assert t.reason == "exit" and t.exit == pytest.approx(0.18)  # wedge closed at the 31h decision, the print at 0.18 fills the buy
    assert t.edge == pytest.approx(0.19) and t.fee == 0.0


def test_unfilled_entry_expires_and_is_counted(recording):
    mk = _market()
    sess = WedgeSession(mk, k=0.05, T="resolution", side="sell")
    # remove the print: no fill within the 4h TTL
    events = [e for e in iter_events(recording) if e[2].get("event_type") != "last_trade_price"]
    sess.run(events)
    tr = sess.trade_table()
    assert list(tr.reason) == ["entry_unfilled"]


def test_max_hold_crosses_with_taker_fee(recording):
    mk = _market()
    sess = WedgeSession(mk, k=0.05, T=1, side="sell")   # max hold one day: exit posted at ~25h, no print → crossed at the ask after TTL
    events = [e for e in iter_events(recording) if not (e[2].get("event_type") == "last_trade_price" and e[0] > T0 + 3600 * 2)]
    sess.run(events)
    t = sess.trade_table().iloc[0]
    assert t.reason == "crossed_max_hold" and t.fee > 0 and t.exit in (0.37, 0.20)


def test_settlement_when_no_exit(recording):
    mk = _market()
    sess = WedgeSession(mk, k=0.05, T="resolution", side="sell")
    events = [e for e in iter_events(recording) if e[0] < T0 + 3600 * 20]   # stop before the wedge closes
    sess.run(events)
    t = sess.trade_table().iloc[0]
    assert t.reason == "resolution" and t.exit == 0.0 and t.edge == pytest.approx(0.37)


def test_one_market_per_ladder(recording):
    mk = _market()
    mk["222"] = Market("222", "m2", "BTC", "reach", 110_000.0, pd.Timestamp("2026-10-31", tz="UTC"), resolved_yes=0.0)
    _write(recording, "polymarket", [(T0 + 61, {"market": "0xm2", "price_changes": [{"asset_id": "222", "price": "0.60", "size": "1", "side": "BUY", "best_bid": "0.60", "best_ask": "0.62"}], "timestamp": "0", "event_type": "price_change"})])
    sess = WedgeSession(mk, k=0.05, T="resolution", side="sell")
    sess.run(iter_events(recording))
    assert len(sess.taken_groups) == 1 and len(sess.trades) == 1


def test_script_runs_on_fixture(recording, tmp_path, monkeypatch):
    (recording / "polymarket").mkdir(exist_ok=True)
    cat = {"at": T0, "markets": [{"market_id": "m", "question": "Will Bitcoin reach $120,000 by October 31?", "end": "2026-10-31T00:00:00Z", "start": "2026-09-20", "yes_token": YES, "no_token": "999"}]}
    (recording / "polymarket" / "catalogue.jsonl").write_text(json.dumps(cat) + "\n")
    (tmp_path / "res.json").write_text(json.dumps({"m": 0.0}))
    monkeypatch.setenv("QR_ROOT", str(tmp_path / "lake"))
    spec = importlib.util.spec_from_file_location("v2", Path(__file__).resolve().parents[2] / "scripts" / "p3a_wedge_v2.py")
    v2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v2)
    assert v2.main(["--start", "2026-10-01", "--end", "2026-10-03", "--mirror", str(recording), "--resolutions", str(tmp_path / "res.json"), "--no-log"]) == 0
    summ = json.loads((tmp_path / "lake" / "reports" / "p3" / "p3_threshold_wedge_v2_intraday_2026-10-01_2026-10-03_summary.json").read_text())
    assert summ["results"]["k5_T3"]["n_trades"] == 1 and "DEFERRED" in summ["verdict"]


def test_run_many_is_run_on_each_session_from_one_pass(recording):
    from qr.execution.pm_replay import run_many

    def fresh():
        return {"family": WedgeSession(_market(), k=0.05, T="resolution", side="sell"),
                "mirror": WedgeSession(_market(), k=0.05, T="resolution", side="buy"),
                "naive": WedgeSession(_market(), k=0.0, T="resolution", side="sell", naive=True)}

    one_by_one = fresh()
    for s in one_by_one.values():
        s.run(iter_events(recording))
    together = fresh()
    run_many(together, iter_events(recording))      # the recording read once for all three
    for name in one_by_one:
        a, b = one_by_one[name].trade_table(), together[name].trade_table()
        assert len(a) == len(b)
        if len(a):
            pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))
    assert len(together["family"].trade_table()) == 1
