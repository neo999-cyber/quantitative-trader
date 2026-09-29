import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.data.universe import UniverseSpec, rank_asof
from qr.strategies.oi import OIReversal


def test_a_rank_band_skips_the_largest_names():
    idx = pd.date_range("2024-01-01", periods=40, freq="D", tz="UTC")
    qv = pd.DataFrame({f"S{i}": [100.0 - i] * 40 for i in range(10)}, index=idx)
    spec = UniverseSpec(n=6, rank_min=3, lookback=30, min_history=1, min_annual_vol=0.0)
    assert rank_asof(qv, idx[-1], spec) == ["S2", "S3", "S4", "S5"]  # ranks 3..6


def test_oi_reversal_longs_the_losers_and_shorts_the_winners_among_crowded_names():
    idx = pd.date_range("2024-01-01", periods=30, freq="D", tz="UTC")
    n = len(idx)
    closes = {"UP": np.linspace(100, 130, n), "DN": np.linspace(100, 80, n), "FLAT": np.full(n, 100.0), "QUIET": np.linspace(100, 70, n)}
    oi = {"UP": np.linspace(1e6, 2e6, n), "DN": np.linspace(1e6, 2e6, n), "FLAT": np.linspace(1e6, 2e6, n), "QUIET": np.full(n, 1e6)}  # QUIET: no OI rise -> excluded
    frames = {}
    for s in closes:
        c = closes[s]
        frames[s] = pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1e6 / c, "quote_volume": 1e6, "open_interest": oi[s]}, index=idx)
    panel = Panel.from_frames(frames, fields=["open", "high", "low", "close", "volume", "quote_volume", "open_interest"])
    w = OIReversal(lookback=7, oi_lookback=7, oi_min=0.05, n_side=1, rebalance_on=None).target_weights(panel)
    last = w.iloc[-1]
    assert last["DN"] == pytest.approx(0.5) and last["UP"] == pytest.approx(-0.5)  # loser long, winner short, gross 1
    assert last["QUIET"] == 0.0 and last["FLAT"] == 0.0
    with pytest.raises(ValueError):
        OIReversal().target_weights(Panel.from_frames({k: v.drop(columns="open_interest") for k, v in frames.items()}))
