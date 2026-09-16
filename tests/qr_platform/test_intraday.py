"""E2's two-bars-a-session instrument and the late-day momentum family."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qr.data.intraday import session_split_frames
from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.intraday import LateDayMomentum

NY = "America/New_York"


def _minutes(day, path):
    """Minute closes from 09:30 with the given prices, one per minute."""
    idx = pd.date_range(f"{day} 09:30", periods=len(path), freq="min", tz=NY).tz_convert("UTC")
    p = np.asarray(path, dtype=float)
    return pd.DataFrame({"open": p, "high": p, "low": p, "close": p, "volume": 100.0, "quote_volume": 100.0 * p}, index=idx)


def _session(day, open_px, at_1530, close_px):
    n = 391  # 09:30 .. 16:00 inclusive
    path = np.linspace(open_px, at_1530, 361).tolist() + np.linspace(at_1530, close_px, 31)[1:].tolist()
    return _minutes(day, path)


def test_the_two_bars_carry_the_signal_and_the_trade():
    """Day 1: 100 -> 101 by 15:30 (+1%), 101 -> 101.505 by the close (+0.5%).
    The first bar's `ret_to_decision` is +1%; the second bar's return is +0.5%."""
    bars = pd.concat([_session("2024-03-05", 100.0, 101.0, 101.505), _session("2024-03-06", 101.0, 100.0, 100.2)])
    frame = session_split_frames(bars, decision="15:30")
    assert len(frame) == 4
    assert frame["is_late"].tolist() == [0.0, 1.0, 0.0, 1.0]
    r = frame["close"].pct_change(fill_method=None)
    assert r.iloc[1] == pytest.approx(0.005, abs=1e-6)  # the late bar of day 1
    assert r.iloc[3] == pytest.approx(0.002, abs=1e-6)
    assert frame["ret_to_decision"].iloc[0] == pytest.approx(0.01, abs=1e-6)
    assert frame["ret_to_decision"].iloc[2] == pytest.approx(-100.0 / 101.0 + 1.0 - 0.0, abs=1e-3) or frame["ret_to_decision"].iloc[2] < 0
    assert np.isnan(frame["ret_to_decision"].iloc[1])  # the late bar carries no signal
    stamps = frame.index.tz_convert(NY)
    assert stamps[0].strftime("%H:%M") == "09:30" and stamps[1].strftime("%H:%M") == "15:30"


def test_late_day_momentum_buys_at_the_decision_when_the_day_is_up_and_is_flat_by_the_close():
    bars = pd.concat([_session("2024-03-05", 100.0, 101.0, 101.505), _session("2024-03-06", 101.0, 100.0, 100.2), _session("2024-03-07", 100.0, 100.1, 100.0)])
    frame = session_split_frames(bars, decision="15:30")
    panel = Panel.from_frames({"QQQ": frame}, fields=list(frame.columns))
    result = run_backtest(panel, LateDayMomentum(k=0.005), CostModel(fee_bps=0.0, half_spread_bps=0.0))
    held = result.held["QQQ"]
    assert held.iloc[1] == 1.0  # day 1: +1% by 15:30 clears k = 0.5%: long over the last half hour
    assert held.iloc[3] == 0.0  # day 2: down day, long-only: flat
    assert held.iloc[5] == 0.0  # day 3: +0.1% below k: flat
    assert held.iloc[0] == 0.0 and held.iloc[2] == 0.0 and held.iloc[4] == 0.0  # never held over the day session
    assert float(result.gross.iloc[1]) == pytest.approx(0.005, abs=1e-6)
    reverse = run_backtest(panel, LateDayMomentum(k=0.005, side="reverse"), CostModel(fee_bps=0.0, half_spread_bps=0.0)).held["QQQ"]
    assert reverse.iloc[1] == 0.0 and reverse.iloc[3] == 1.0  # the control buys the down day


def test_the_two_bar_instrument_passes_qa_under_the_sessions2_calendar():
    from qr.data.qa import check_klines

    bars = pd.concat([_session("2024-03-05", 100.0, 101.0, 101.505), _session("2024-03-06", 101.0, 100.0, 100.2)])
    frame = session_split_frames(bars, decision="15:30")
    assert [c.name for c in check_klines(frame, "QQQ", "1d", calendar="continuous").checks if c.verdict == "FAIL"] == ["bar_spacing"]
    assert not [c.name for c in check_klines(frame, "QQQ", "1d", calendar="sessions2").checks if c.verdict == "FAIL"]
