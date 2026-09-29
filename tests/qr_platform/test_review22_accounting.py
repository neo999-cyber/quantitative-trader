"""Review 22 (17 September 2026) counterexamples that must hold in this engine."""
import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.base import Strategy


def _panel(closes, quote_volume=1e6):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D", tz="UTC")
    idx.name = "open_time"
    c = np.asarray(closes, dtype=float)
    frame = pd.DataFrame(
        {"open": c, "high": c * 1.001, "low": c * 0.999, "close": c, "volume": quote_volume / c, "quote_volume": quote_volume},
        index=idx,
    )
    return frame, idx


class _Hold(Strategy):
    family = "test"

    def __init__(self, weights):
        super().__init__()
        self._w = weights

    def target_weights(self, panel, universe=None):
        return self._w.copy()


def test_a_corrupt_volume_field_on_a_crash_bar_does_not_erase_the_loss_on_a_held_position():
    frame, idx = _panel([100, 100, 100, 50, 50])
    w = pd.DataFrame({"X": [1.0] * 5}, index=idx)
    clean = Panel.from_frames({"X": frame})
    r_clean = run_backtest(clean, _Hold(w), CostModel(fee_bps=0, half_spread_bps=0, name="free", verified_on="unverified")).gross
    bad = frame.copy()
    bad.loc[idx[3], "quote_volume"] = bad.loc[idx[3], "volume"] * bad.loc[idx[3], "high"] * 1.5  # VWAP outside the bar
    broken = Panel.from_frames({"X": bad})
    assert not broken.tradable().loc[idx[3], "X"]
    r_bad = run_backtest(broken, _Hold(w), CostModel(fee_bps=0, half_spread_bps=0, name="free", verified_on="unverified")).gross
    assert r_clean.loc[idx[3]] == pytest.approx(-0.5)
    assert r_bad.loc[idx[3]] == pytest.approx(-0.5)


def test_a_new_position_is_refused_when_the_decision_bar_was_not_tradable():
    frame, idx = _panel([100, 100, 100, 120, 120])
    bad = frame.copy()
    bad.loc[idx[2], "quote_volume"] = bad.loc[idx[2], "volume"] * bad.loc[idx[2], "high"] * 1.5
    w = pd.DataFrame({"X": [0.0, 0.0, 1.0, 1.0, 1.0]}, index=idx)  # decided at idx[2], held over idx[3]
    res = run_backtest(Panel.from_frames({"X": bad}), _Hold(w), CostModel(fee_bps=0, half_spread_bps=0, name="free", verified_on="unverified"))
    assert res.gross.loc[idx[3]] == pytest.approx(0.0)  # the order at the corrupt bar's close is refused


def test_three_consecutive_overnight_signals_are_three_round_trips():
    from qr.strategies.auction import AuctionFade

    frame, idx = _panel([100.0] * 6)
    assert AuctionFade.round_trip_each_bar
    w = pd.DataFrame({"X": [0.0, 1.0, 1.0, 1.0, 0.0, 0.0]}, index=idx)

    class _Overnight(_Hold):
        round_trip_each_bar = True

    res = run_backtest(Panel.from_frames({"X": frame}), _Overnight(w), CostModel(fee_bps=10, half_spread_bps=0, name="t", verified_on="unverified"))
    assert res.turnover.sum() == pytest.approx(6.0)
    assert res.costs.sum() == pytest.approx(6 * 10e-4)
