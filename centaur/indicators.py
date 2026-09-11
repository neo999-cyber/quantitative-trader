"""Technical indicators used by the screens and the rulebook.

All functions are pure and operate on pandas Series/DataFrames with a
DatetimeIndex and the standard OHLCV columns: Open, High, Low, Close, Volume.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index.

    Seeded the way Wilder defined it: the first average gain/loss is a simple
    mean of the first `period` changes, then smoothed recursively with
    alpha = 1/period.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    def _wilder(x: pd.Series) -> pd.Series:
        if len(x) <= period:
            return pd.Series(np.nan, index=x.index)
        seeded = x.copy()
        seed = x.iloc[1 : period + 1].mean()          # x.iloc[0] is the NaN from diff()
        seeded.iloc[: period + 1] = np.nan
        seeded.iloc[period] = seed
        return seeded.ewm(alpha=1.0 / period, adjust=False, ignore_na=True).mean()

    avg_gain = _wilder(gain)
    avg_loss = _wilder(loss)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(avg_loss != 0.0, 100.0)          # no losses at all -> RSI 100
    out[avg_gain.isna() | avg_loss.isna()] = np.nan
    return out.rename("rsi")


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder smoothing)."""
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean().rename("atr")


def consecutive_down_days(close: pd.Series) -> pd.Series:
    """Number of consecutive down closes ending at each bar (0 if the bar closed up/flat)."""
    down = (close.diff() < 0).astype(int)
    # cumulative count that resets whenever `down` is 0
    groups = (down == 0).cumsum()
    return down.groupby(groups).cumsum().rename("consecutive_down")


def consecutive_up_days(close: pd.Series) -> pd.Series:
    up = (close.diff() > 0).astype(int)
    groups = (up == 0).cumsum()
    return up.groupby(groups).cumsum().rename("consecutive_up")


def avg_dollar_volume(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Rolling average of Close * Volume (a liquidity proxy)."""
    return (df["Close"] * df["Volume"]).rolling(window, min_periods=window).mean().rename("adv")


def relative_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    """Today's volume divided by the average of the *previous* `window` days."""
    baseline = volume.shift(1).rolling(window, min_periods=window).mean()
    return (volume / baseline).rename("rvol")


def swing_levels(df: pd.DataFrame, window: int = 10, lookback: int = 250) -> tuple[list[float], list[float]]:
    """Return (resistance_levels, support_levels) from local swing highs/lows.

    A swing high is a High that is the maximum within +/- `window` bars; a
    swing low is the mirror.  Only the last `lookback` bars are considered.
    Levels are sorted ascending and de-duplicated within 0.5%.
    """
    sub = df.tail(lookback)
    highs = sub["High"]
    lows = sub["Low"]
    roll_max = highs.rolling(2 * window + 1, center=True).max()
    roll_min = lows.rolling(2 * window + 1, center=True).min()
    res = sorted(float(v) for v in highs[highs == roll_max].dropna().unique())
    sup = sorted(float(v) for v in lows[lows == roll_min].dropna().unique())
    return _dedupe(res), _dedupe(sup)


def _dedupe(levels: list[float], tol: float = 0.005) -> list[float]:
    out: list[float] = []
    for lv in levels:
        if not out or abs(lv - out[-1]) / max(out[-1], 1e-9) > tol:
            out.append(lv)
    return out


def trend_state(close: pd.Series, fast: int = 50, slow: int = 200) -> dict:
    """Simple trend classification for an index: above/below moving averages,
    and whether recent swing structure is making lower lows / higher highs."""
    fast_ma = sma(close, fast)
    slow_ma = sma(close, slow)
    last = float(close.iloc[-1])
    above_fast = bool(last > fast_ma.iloc[-1]) if not np.isnan(fast_ma.iloc[-1]) else None
    above_slow = bool(last > slow_ma.iloc[-1]) if not np.isnan(slow_ma.iloc[-1]) else None

    # Compare the last 20-day window to the prior 20-day window.
    recent = close.tail(20)
    prior = close.iloc[-40:-20] if len(close) >= 40 else close.head(0)
    lower_lows = bool(len(prior) and recent.min() < prior.min())
    lower_highs = bool(len(prior) and recent.max() < prior.max())
    higher_highs = bool(len(prior) and recent.max() > prior.max())
    higher_lows = bool(len(prior) and recent.min() > prior.min())

    ret_20 = float(close.iloc[-1] / close.iloc[-21] - 1.0) if len(close) > 21 else float("nan")
    return {
        "last": last,
        "sma_fast": float(fast_ma.iloc[-1]),
        "sma_slow": float(slow_ma.iloc[-1]),
        "above_fast": above_fast,
        "above_slow": above_slow,
        "lower_lows": lower_lows,
        "lower_highs": lower_highs,
        "higher_highs": higher_highs,
        "higher_lows": higher_lows,
        "downtrend": bool(lower_lows and lower_highs),
        "uptrend": bool(higher_highs and higher_lows),
        "return_20d": ret_20,
    }
