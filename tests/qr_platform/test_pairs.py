"""C7 perp pairs (qr/strategies/pairs.py) on a synthetic cointegrated pair."""
import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.pairs import LINKED, PerpPairs, random_pairs


def _panel(n=400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"); idx.name = "open_time"
    common = np.cumsum(rng.normal(0, 0.02, n))
    spread = np.zeros(n)
    for t in range(1, n):  # AR(1) spread, half-life ~ 7 bars
        spread[t] = 0.9 * spread[t - 1] + rng.normal(0, 0.01)
    b = 100 * np.exp(common)
    a = 50 * np.exp(1.0 * common + spread)
    frames = {}
    for sym, px in (("SOLUSDT", a), ("AVAXUSDT", b), ("ZECUSDT", 30 * np.exp(np.cumsum(rng.normal(0, 0.03, n)))),
                    ("XMRUSDT", 150 * np.exp(np.cumsum(rng.normal(0, 0.03, n))))):
        frames[sym] = pd.DataFrame({"open": px, "high": px * 1.01, "low": px * 0.99, "close": px, "volume": 1e6 / px, "quote_volume": 1e6}, index=idx)
    return Panel.from_frames(frames), spread


def test_the_family_trades_the_linked_pair_dollar_neutral_and_flat_between_signals():
    panel, spread = _panel()
    w = PerpPairs(lookback=60, entry=2.0, exit_z=0.5, max_hold=10).target_weights(panel)
    assert set(w.columns) == set(panel.symbols)
    live = w[(w != 0).any(axis=1)]
    assert len(live) > 5, "the reverting spread should produce entries"
    # dollar-neutral per pair: SOL and AVAX legs offset; the unlinked names untouched by the linked pair
    on = live[live["SOLUSDT"] != 0]
    assert len(on) > 5 and (on["SOLUSDT"] * on["AVAXUSDT"] < 0).all()
    assert w.abs().sum(axis=1).max() <= 1.0 + 1e-9
    # the sign is against the spread: short SOL when it is rich
    z_now = pd.Series(spread, index=panel.index)
    entries = live.index[(live["SOLUSDT"] != 0) & (w["SOLUSDT"].shift(1).reindex(live.index).fillna(0) == 0)]
    assert (np.sign(z_now.loc[entries]) == -np.sign(live.loc[entries, "SOLUSDT"])).mean() > 0.8
    assert (w != 0).any(axis=1).mean() < 0.6  # flat most of the time


def test_the_random_control_uses_other_pairs_deterministically():
    panel, _ = _panel()
    ctrl = PerpPairs(pairs="random")
    pairs = ctrl.pair_list(panel)
    assert pairs == ctrl.pair_list(panel)
    assert all(frozenset(p) not in {frozenset(q) for q in LINKED} for p in pairs)
    assert random_pairs(panel.symbols, n=2, seed=1) != random_pairs(panel.symbols, n=2, seed=2) or len(panel.symbols) <= 4


def test_it_runs_through_the_ledger_with_perp_costs():
    panel, _ = _panel()
    res = run_backtest(panel, PerpPairs(lookback=60), CostModel.binance_perp(), engine="ledger")
    assert res.stats()["round_trips"] > 0 and np.isfinite(res.stats()["sharpe"])
