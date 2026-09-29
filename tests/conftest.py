import datetime as dt

import numpy as np
import pandas as pd
import pytest

from centaur.config import AccountConfig
from centaur.screens.regime import RegimeAssessment, Regime, Component


def make_ohlcv(n: int = 400, seed: int = 1, start: float = 100.0, drift: float = 0.0003, vol: float = 0.015) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-09-10", periods=n)
    rets = rng.normal(drift, vol, n)
    close = start * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0.008, 0.003, n)))
    low = close * (1 - np.abs(rng.normal(0.008, 0.003, n)))
    opn = np.r_[close[0], close[:-1]]
    volume = rng.lognormal(14, 0.3, n)
    return pd.DataFrame({"Open": opn, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)


def inject_setup(df: pd.DataFrame, at: int, days: int = 3, drop: float = 0.05, vol_mult: float = 2.5) -> pd.DataFrame:
    """Force `days` consecutive down closes on heavy volume ending at index `at` and crush RSI."""
    df = df.copy()
    # a long slide before the streak so RSI is deep
    for i in range(at - 12, at - days + 1):
        df.iloc[i, df.columns.get_loc("Close")] = df["Close"].iloc[i - 1] * (1 - 0.012)
    for i in range(at - days + 1, at + 1):
        df.iloc[i, df.columns.get_loc("Close")] = df["Close"].iloc[i - 1] * (1 - drop)
        df.iloc[i, df.columns.get_loc("Volume")] = df["Volume"].iloc[i - 25:i - 1].mean() * vol_mult
    df["High"] = np.maximum(df["High"], df["Close"])
    df["Low"] = np.minimum(df["Low"], df["Close"])
    return df


@pytest.fixture
def cfg() -> AccountConfig:
    return AccountConfig(equity=10_000.0, risk_pct=0.01)


@pytest.fixture
def risk_on() -> RegimeAssessment:
    return RegimeAssessment(Regime.RISK_ON, 0.5, 0.8, [Component("trend_spy", 1.0, 0.2, "up")], "2026-09-10")


@pytest.fixture
def risk_off() -> RegimeAssessment:
    return RegimeAssessment(Regime.RISK_OFF, -0.5, 0.8, [Component("trend_spy", -1.0, 0.2, "down")], "2026-09-10")


@pytest.fixture
def today() -> dt.date:
    return dt.date(2026, 9, 10)


# ---------------------------------------------------------------------------
# `qr` platform fixtures. They live here rather than in tests/qr_platform/ because
# a second conftest.py on sys.path shadows this one for the centaur tests, which
# import `make_ohlcv` from it by module name.
# ---------------------------------------------------------------------------
from qr.data.binance import BinanceBucket  # noqa: E402
from qr.data.fixtures import SyntheticPair, build_mirror  # noqa: E402


@pytest.fixture()
def pairs():
    """A universe with a delisted pair, a late lister and a volume ladder."""
    return [
        SyntheticPair("BTCUSDT", "2023-01-01", "2024-06-30", price=30_000, quote_volume=9e8, seed=1),
        SyntheticPair("ETHUSDT", "2023-01-01", "2024-06-30", price=2_000, quote_volume=5e8, seed=2),
        SyntheticPair("SOLUSDT", "2023-01-01", "2024-06-30", price=20, quote_volume=2e8, seed=3),
        SyntheticPair("DEADUSDT", "2023-01-01", "2023-08-15", price=1.0, quote_volume=6e8, seed=4),
        SyntheticPair("LATEUSDT", "2024-01-10", "2024-06-30", price=5.0, quote_volume=7e8, seed=5),
    ]


@pytest.fixture()
def mirror(tmp_path, pairs):
    return build_mirror(tmp_path / "mirror", pairs)


@pytest.fixture()
def bucket(mirror):
    return BinanceBucket(mirror)


@pytest.fixture()
def frames(bucket):
    return {s: bucket.load_klines(s) for s in bucket.symbols()}
