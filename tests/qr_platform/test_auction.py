"""E1's close-to-open instrument and the auction-fade family. Hand-built fixtures."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qr.data.auction import NASDAQ31, auction_frame
from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.auction import AuctionFade


def _daily(sessions, opens, closes, volume=1e6):
    idx = pd.DatetimeIndex(pd.to_datetime(sessions)).tz_localize("UTC")
    idx.name = "open_time"
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes), "low": np.minimum(opens, closes), "close": closes, "volume": volume}, index=idx)


def _snaps(rows):
    return pd.DataFrame(rows, columns=["symbol", "session", "snapshot", "imbalance_ratio", "paired_qty", "ref_price", "published_at", "age_seconds"])


def test_the_instruments_bar_return_is_the_overnight_return_and_a_split_is_not_a_bar():
    """Close 100 -> open 101 is +1%; close 102 -> open 102.51 is +0.5%. A
    10:1 split (close 1200 -> open 120) is not a return and its bar is empty."""
    bars = _daily(["2024-06-05", "2024-06-06", "2024-06-07", "2024-06-10", "2024-06-11", "2024-06-12"],
                  opens=[99.0, 101.0, 102.51, 120.0, 121.0, 123.0], closes=[100.0, 102.0, 1200.0, 119.0, 122.0, 124.0])
    frame = auction_frame(bars, _snaps([]))
    r = frame["close"].pct_change(fill_method=None)
    assert r.iloc[1] == pytest.approx(0.01)
    assert r.iloc[2] == pytest.approx(0.005)
    assert np.isnan(frame["close"].iloc[3])  # the split night: open 120 against close 1200 is not a return
    assert np.isnan(r.iloc[4])  # and the bar after it has no previous price to return from
    assert r.iloc[5] == pytest.approx(123.0 / 122.0 - 1.0)  # then it resumes
    assert frame["quote_volume"].iloc[1] == pytest.approx(1e6 * 102.0)
    assert frame["volume"].iloc[1] * frame["close"].iloc[1] == pytest.approx(frame["quote_volume"].iloc[1])
    from qr.data.qa import check_klines
    assert not [c.name for c in check_klines(frame.dropna(subset=["close"]), "X", "1d", calendar="continuous").checks if c.verdict == "FAIL"]
    assert frame["session_close"].iloc[1] == 102.0 and frame["session_open"].iloc[1] == 101.0


def test_snapshot_features_land_on_the_decision_bar_only_when_published_by_the_cutoff():
    bars = _daily(["2024-06-05", "2024-06-06", "2024-06-07"], opens=[99.0, 101.0, 100.0], closes=[100.0, 102.0, 101.0])
    ny = "America/New_York"
    snaps = _snaps([
        ["X", pd.Timestamp("2024-06-05").date(), "15:55", -0.30, 100_000, 100.0, pd.Timestamp("2024-06-05 15:55:00.9", tz=ny), 0.9],
        ["X", pd.Timestamp("2024-06-06").date(), "15:55", -0.20, 100_000, 102.0, pd.Timestamp("2024-06-06 15:55:20", tz=ny), 20.0],  # stale
        ["X", pd.Timestamp("2024-06-07").date(), "15:55", 0.40, 100_000, 101.0, pd.Timestamp("2024-06-07 15:55:00.5", tz=ny), 0.5],
    ])
    frame = auction_frame(bars, snaps)
    assert frame["imb_1555"].iloc[0] == pytest.approx(-0.30)
    assert np.isnan(frame["imb_1555"].iloc[1])  # 20 s stale at the cutoff: not a feature
    assert frame["imb_1555"].iloc[2] == pytest.approx(0.40)
    assert frame["paired_usd_1555"].iloc[0] == pytest.approx(100_000 * 100.0)
    assert frame["imb_age_1555"].iloc[0] == pytest.approx(0.9) and np.isnan(frame["imb_age_1555"].iloc[1])


def test_auction_fade_buys_sell_imbalances_at_the_close_and_is_flat_by_the_next_close():
    """Two names. On day 1 A shows a -30% sell imbalance and B +10%; only A is
    bought (weight 1/n_max = 0.5), held over the night into day 2 and gone."""
    ny = "America/New_York"
    sessions = ["2024-06-05", "2024-06-06", "2024-06-07"]
    frames = {}
    for sym, imb in (("A", -0.30), ("B", 0.10)):
        bars = _daily(sessions, opens=[100.0, 101.0, 100.5], closes=[100.0, 100.0, 100.0])
        snaps = _snaps([[sym, pd.Timestamp(s).date(), "15:55", imb, 200_000, 100.0, pd.Timestamp(f"{s} 15:55:00.5", tz=ny), 0.5] for s in sessions[:1]])
        frames[sym] = auction_frame(bars, snaps)
    panel = Panel.from_frames(frames, fields=list(frames["A"].columns))
    strat = AuctionFade(k=0.20, snapshot="15:55", n_max=2)
    result = run_backtest(panel, strat, CostModel(fee_bps=0.0, half_spread_bps=0.0))
    held = result.held
    assert held["A"].iloc[1] == pytest.approx(0.5) and held["B"].iloc[1] == 0.0
    assert held.iloc[2].abs().sum() == 0.0
    assert float(result.gross.iloc[1]) == pytest.approx(0.5 * 0.01)  # A's overnight: close 100 -> open 101
    # the overnight bar is the whole round trip: bought at the close (0.5),
    # sold at the open after growing 1% (0.505); nothing is carried into day 2
    # (review 22, §1.4 — until 17 September 2026 the exit was charged a bar late)
    assert result.turnover.iloc[1] == pytest.approx(0.5 + 0.5 * 1.01)
    assert result.turnover.iloc[2] == pytest.approx(0.0)


def test_the_basket_is_the_thirty_one_nasdaq_names():
    assert len(NASDAQ31) == 31 and "QQQ" in NASDAQ31 and "SPY" not in NASDAQ31


def test_a_ticker_that_belonged_to_another_security_starts_when_the_name_took_it(tmp_path):
    from qr.config import Paths
    from qr.data.auction import SYMBOL_START, build_auction_lake
    from qr.data.lake import Lake

    assert SYMBOL_START["META"] == "2022-06-09"  # the Metaverse ETF before, Facebook after
    lake = Lake(Paths(tmp_path))
    bars = _daily(["2022-06-07", "2022-06-08", "2022-06-09", "2022-06-10"], opens=[12.0, 12.1, 196.0, 190.0], closes=[12.2, 12.29, 184.85, 188.0])
    summary = build_auction_lake(lake, {"META": bars}, _snaps([]))
    assert summary.iloc[0]["sessions"] == 2 and summary.iloc[0]["split_nights"] == 0


def test_the_mirror_control_buys_the_buy_imbalance_instead():
    ny = "America/New_York"
    sessions = ["2024-06-05", "2024-06-06"]
    frames = {}
    for sym, imb in (("A", -0.30), ("B", 0.30)):
        bars = _daily(sessions, opens=[100.0, 101.0], closes=[100.0, 100.0])
        snaps = _snaps([[sym, pd.Timestamp(sessions[0]).date(), "15:55", imb, 200_000, 100.0, pd.Timestamp(f"{sessions[0]} 15:55:00.5", tz=ny), 0.5]])
        frames[sym] = auction_frame(bars, snaps)
    panel = Panel.from_frames(frames, fields=list(frames["A"].columns))
    family = AuctionFade(k=0.20, n_max=1).target_weights(panel)
    mirror = AuctionFade(k=0.20, n_max=1, side="buy").target_weights(panel)
    assert family["A"].iloc[0] == 1.0 and family["B"].iloc[0] == 0.0
    assert mirror["B"].iloc[0] == 1.0 and mirror["A"].iloc[0] == 0.0
