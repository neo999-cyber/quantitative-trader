"""C3's event definition and measurement on synthetic liquidations and a synthetic tape. No network."""
from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qr.research import liq_events as le

T0 = pd.Timestamp("2026-09-20 12:00", tz="UTC")


def _liq(t, base, side, usd, venue="bybit"):
    return {"t_ms": int(t.timestamp() * 1000), "base": base, "dir": side, "usd": usd, "t": t, "venue": venue}


def test_burst_needs_dollars_and_sigma_and_merges_consecutive_bins():
    rows = []
    # a day of background: $2k every minute on SOL sell
    for i in range(24 * 60):
        rows.append(_liq(T0 - pd.Timedelta(days=1) + pd.Timedelta(minutes=i), "SOL", "sell", 2_000 + (i % 7) * 10))
    # the burst: two consecutive minutes of $60k, then a $30k minute (below the dollar floor)
    rows += [_liq(T0, "SOL", "sell", 60_000), _liq(T0 + pd.Timedelta(seconds=70), "SOL", "sell", 60_000), _liq(T0 + pd.Timedelta(seconds=130), "SOL", "sell", 30_000)]
    df = pd.DataFrame(rows)
    q = le.bursts(df)
    assert len(q) == 2 and (q.z >= 5).all()
    q["venue"] = "bybit"
    ev = le.merge(q)
    assert len(ev) == 1
    assert ev.iloc[0].bins == 2 and ev.iloc[0].t0 == T0 + pd.Timedelta(seconds=120) and ev.iloc[0].usd == 120_000


def test_both_venues_within_60s_are_one_event():
    rows = []
    for v in ("okx", "bybit"):
        for i in range(24 * 60):
            rows.append(_liq(T0 - pd.Timedelta(days=1) + pd.Timedelta(minutes=i), "XRP", "buy", 3_000, v))
        rows.append(_liq(T0 + pd.Timedelta(seconds=(5 if v == "okx" else 50)), "XRP", "buy", 80_000, v))
    df = pd.DataFrame(rows)
    per = []
    for v, g in df.groupby("venue"):
        q = le.bursts(g)
        q["venue"] = v
        per.append(q)
    ev = le.merge(pd.concat(per))
    assert len(ev) == 1 and ev.iloc[0].venues == "bybit,okx"


def test_base_mapping():
    assert le.base("1000PEPEUSDT") == "PEPE" and le.base("PEPE-USDT-SWAP") == "PEPE" and le.base("SOL-USDT-SWAP") == "SOL"


def _module():
    spec = importlib.util.spec_from_file_location("c3", Path(__file__).resolve().parents[2] / "scripts" / "c3_liquidation_fade.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_measure_signs_and_placebo(tmp_path):
    c3 = _module()
    # a tape: SOL mid falls from 100 to 99 into the burst, bounces to 99.5 after 15 min
    day = T0.strftime("%Y-%m-%d")
    f = tmp_path / "binance" / "book" / f"{day}.jsonl.gz"
    f.parent.mkdir(parents=True)
    with gzip.open(f, "wt") as fh:
        for sec in range(-600, 3700, 10):
            t = int((T0 + pd.Timedelta(seconds=sec)).timestamp() * 1000)
            mid = 100.0 if sec <= -120 else (99.0 if sec <= 0 else (99.0 + 0.5 * min(sec, 900) / 900))
            fh.write(json.dumps({"t": t, "s": "SOLUSDT", "T": t, "b": f"{mid-0.01:.4f}", "B": "1", "a": f"{mid+0.01:.4f}", "A": "1"}) + "\n")
    ev = pd.DataFrame([{"base": "SOL", "dir": "sell", "start": T0 - pd.Timedelta(seconds=120), "t0": T0, "usd": 120_000.0, "z": 9.0, "bins": 2, "venues": "bybit", "control": False, "placebo": False}])
    mids = c3.load_mids(tmp_path, [day], {"SOLUSDT"})
    m = c3.measure(ev, mids)
    r = m.iloc[0]
    assert r.into_bps < -90 and r.pre5_bps < -90          # fell ~1% into the burst, in the reversion's sign: negative
    assert 45 < r.rev_15m_bps < 55 and r.rev_1m_bps > 0   # bounced ~50 bps by 15 minutes
    pl = c3.placebo_stamps(ev)
    assert len(pl) == 1 and pl.iloc[0].t0.floor("h") == T0.floor("h") and abs((pl.iloc[0].t0 - T0).total_seconds()) >= 900


def test_clustered_and_verdict():
    c3 = _module()
    x = pd.Series([10.0, 12.0, 9.0, 11.0, 10.5, 9.5]); cl = pd.Series(["a", "a", "b", "b", "c", "c"])
    s = c3.clustered(x, cl)
    assert s["clusters"] == 3 and s["mean"] == pytest.approx(10.333, abs=1e-3) and np.isfinite(s["t"])
    good = {"mean": 10.0, "t": 4.0}; flat = {"mean": 0.5, "t": 0.3}; neg = {"mean": -50.0, "t": -5}
    stats = {"events": {"rev_15m_bps": good, "rev_1m_bps": good, "pre5_bps": neg}, "placebo": {"rev_15m_bps": flat}, "control": {"rev_15m_bps": flat}}
    assert c3.verdict(stats)["PASS"]
    stats["placebo"]["rev_15m_bps"] = {"mean": 9.0, "t": 3.0}
    assert not c3.verdict(stats)["PASS"]
