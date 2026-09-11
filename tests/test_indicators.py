import numpy as np
import pandas as pd

from centaur.indicators import rsi, consecutive_down_days, relative_volume, swing_levels, trend_state, atr
from conftest import make_ohlcv


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.linspace(100, 200, 60))
    down = pd.Series(np.linspace(200, 100, 60))
    assert rsi(up).iloc[-1] > 99
    assert rsi(down).iloc[-1] < 1
    r = rsi(make_ohlcv()["Close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_rsi_matches_reference_calculation():
    close = pd.Series([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
                       45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64])
    # classic Wilder worked example: RSI(14) on bar 15 is ~70.5
    assert abs(rsi(close).iloc[14] - 70.46) < 0.6


def test_consecutive_down_days():
    close = pd.Series([10, 9, 8, 7, 8, 7, 7, 6])
    assert consecutive_down_days(close).tolist() == [0, 1, 2, 3, 0, 1, 0, 1]


def test_relative_volume_uses_prior_window():
    vol = pd.Series([100.0] * 20 + [300.0])
    rv = relative_volume(vol, 20)
    assert rv.iloc[-1] == 3.0
    assert np.isnan(rv.iloc[0])


def test_swing_levels_finds_obvious_peak():
    df = make_ohlcv(120, seed=3)
    df.loc[df.index[60], "High"] = df["High"].max() * 1.2
    res, sup = swing_levels(df, window=5, lookback=120)
    assert max(res) == df["High"].max()
    assert all(a < b for a, b in zip(res, res[1:]))


def test_trend_state_flags_uptrend():
    df = make_ohlcv(300, seed=5, drift=0.003, vol=0.005)
    st = trend_state(df["Close"])
    assert st["above_fast"] and st["above_slow"]
    assert st["uptrend"] and not st["downtrend"]


def test_atr_positive():
    a = atr(make_ohlcv()).dropna()
    assert (a > 0).all()
