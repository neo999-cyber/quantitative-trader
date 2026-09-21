"""The P3-A engine on synthetic fixtures: the model probabilities and the rule's bookkeeping. No lake, no network."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("p3a", Path(__file__).resolve().parents[2] / "scripts" / "p3a_wedge.py")
p3a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p3a)


def test_model_prob_sanity():
    S = np.array([100.0]); sig = np.array([0.5]); tau = np.array([30 / 365])
    at_money = p3a.model_prob("above", S, 100.0, sig, tau)[0]
    assert 0.45 < at_money < 0.5  # Φ(d₂) just under a half with the −σ²/2 drift
    assert p3a.model_prob("reach", S, 90.0, sig, tau)[0] == 1.0  # already touched
    assert p3a.model_prob("dip", S, 110.0, sig, tau)[0] == 1.0
    touch = p3a.model_prob("reach", S, 120.0, sig, tau)[0]
    terminal = p3a.model_prob("above", S, 120.0, sig, tau)[0]
    assert 1.9 * terminal < touch < 2.2 * terminal  # reflection principle: touch ≈ 2 × terminal, a little over with the −σ²/2 drift
    assert p3a.model_prob("dip", S, 80.0, sig, tau)[0] > p3a.model_prob("dip", S, 60.0, sig, tau)[0]


def _cat(rows):
    df = pd.DataFrame(rows)
    df["end"] = pd.to_datetime(df["end"], utc=True)
    return df.set_index("market_id")


def _panel(days, prices, p_model):
    idx = pd.to_datetime(days, utc=True)
    f = pd.DataFrame({"price": prices, "p_model": p_model}, index=idx)
    f["wedge"] = f["price"] - f["p_model"]
    return f


def test_simulate_sell_fills_next_day_and_settles():
    cat = _cat([{"market_id": "m1", "asset": "BTC", "kind": "reach", "end": "2026-01-10", "resolved_yes": 0.0, "strike": 1.0, "yes_token": "a"}])
    days = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    panels = {"m1": _panel(days, [0.30, 0.28, 0.27, 0.26], [0.20, 0.20, 0.20, 0.20])}
    tr, ret = p3a.simulate(panels, cat, k=0.05, T="resolution", side="sell")
    assert len(tr) == 1
    t = tr.iloc[0]
    assert str(t.decision.date()) == "2026-01-01" and str(t.fill_day.date()) == "2026-01-02"
    assert t.fill == pytest.approx(0.27)  # next-day print less the haircut
    assert t.reason == "resolution" and t.exit == 0.0 and t.edge == pytest.approx(0.27)
    assert t.in_book and ret.sum() == pytest.approx(25 / 0.73 * 0.27 / 200)


def test_simulate_exit_on_wedge_close_and_one_per_group():
    cat = _cat([
        {"market_id": "m1", "asset": "BTC", "kind": "reach", "end": "2026-01-10", "resolved_yes": 1.0, "strike": 1.0, "yes_token": "a"},
        {"market_id": "m2", "asset": "BTC", "kind": "reach", "end": "2026-01-10", "resolved_yes": 1.0, "strike": 2.0, "yes_token": "b"},
    ])
    days = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
    panels = {
        "m1": _panel(days, [0.30, 0.28, 0.21, 0.19, 0.18], [0.20] * 5),   # wedge 10 → closes on day 3, exit at day 4's print
        "m2": _panel(days, [0.26, 0.25, 0.25, 0.25, 0.25], [0.20] * 5),   # same asset × end date, smaller wedge: skipped
    }
    tr, _ = p3a.simulate(panels, cat, k=0.05, T="resolution", side="sell")
    assert list(tr.market_id) == ["m1"]
    t = tr.iloc[0]
    assert t.reason == "wedge_closed" and t.exit == pytest.approx(0.20) and t.edge == pytest.approx(0.27 - 0.20)


def test_mirror_buys_and_naive_shorts_cheap():
    cat = _cat([{"market_id": "m1", "asset": "ETH", "kind": "dip", "end": "2026-01-10", "resolved_yes": 1.0, "strike": 1.0, "yes_token": "a"}])
    days = ["2026-01-01", "2026-01-02", "2026-01-03"]
    panels = {"m1": _panel(days, [0.10, 0.12, 0.30], [0.20, 0.20, 0.20])}
    tr, _ = p3a.simulate(panels, cat, k=0.05, T="resolution", side="buy")
    assert tr.iloc[0].fill == pytest.approx(0.13) and tr.iloc[0].edge == pytest.approx(1.0 - 0.13)
    tr, _ = p3a.simulate(panels, cat, k=0.0, T="resolution", side="sell", naive=True)
    assert tr.iloc[0].fill == pytest.approx(0.11) and tr.iloc[0].edge == pytest.approx(0.11 - 1.0)


def test_clustered_t_uses_groups():
    tr = pd.DataFrame({"edge": [0.1, 0.1, 0.1, -0.05], "asset": ["BTC"] * 4, "end": ["a", "a", "b", "c"], "hold_days": [1] * 4})
    c = p3a.clustered(tr)
    assert c["n_clusters"] == 3 and c["mean_edge"] == pytest.approx(0.0625)
    assert np.isfinite(c["t"])
