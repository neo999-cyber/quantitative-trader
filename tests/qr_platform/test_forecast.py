"""P3-C machinery on synthetic data: no look-ahead in the features, the purge in the walk-forward, metrics on a planted signal vs noise."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qr.research import forecast as fc


def _inputs(n=1600, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    lr = rng.normal(0, 0.03, n)
    close = 30000 * np.exp(np.cumsum(lr))
    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["high"] = close * 1.01
    df["low"] = close * 0.99
    df["volume"] = 1e9
    df["funding"] = rng.normal(1e-4, 5e-5, n)
    df["oi"] = 1e10 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    df["rv"] = (rng.normal(0, 0.03, (n, 24)) ** 2).sum(axis=1)
    df["dvol"] = 50 + rng.normal(0, 5, n)
    df["fng"] = rng.integers(10, 90, n).astype(float)
    df["stable_supply"] = 1e11 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    for c in ("hash_rate", "n_unique_addresses", "n_transactions"):
        df[c] = 1e6 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    df["dxy"] = 100 + np.cumsum(rng.normal(0, 0.2, n))
    df["us10y"] = 3 + np.cumsum(rng.normal(0, 0.02, n))
    df["tbill"] = 4.0
    return df


def test_features_use_only_the_past():
    df = _inputs()
    X = fc.features(df)
    X2 = fc.features(df.iloc[:1000])
    common = X2.index
    pd.testing.assert_frame_equal(X.loc[common].iloc[:-1], X2.iloc[:-1], check_dtype=False)   # truncating the future changes nothing in the past


def test_targets_look_forward_only():
    df = _inputs()
    Y = fc.targets(df)
    lr = np.log(df["close"]).diff()
    assert Y["ret1"].iloc[10] == pytest.approx(lr.iloc[11])
    assert Y["ret7"].iloc[10] == pytest.approx(lr.iloc[11:18].sum())
    assert np.isnan(Y["ret1"].iloc[-1]) and np.isnan(Y["ret7"].iloc[-3])


def test_walk_forward_purges_and_is_out_of_sample():
    df = _inputs()
    X, Y = fc.features(df), fc.targets(df)
    f = fc.walk_forward(X, Y, "ret7", "ridge", pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-03-31", tz="UTC"))
    assert f.index.min() >= pd.Timestamp("2024-01-01", tz="UTC") and f.index.max() <= pd.Timestamp("2024-03-31", tz="UTC")
    assert len(f) > 80 and (f["base"] == 0.0).all()


def test_planted_signal_scores_and_noise_does_not():
    df = _inputs(seed=1)
    X, Y = fc.features(df), fc.targets(df)
    noise = fc.score_direction(fc.walk_forward(X, Y, "direction", "ridge", pd.Timestamp("2023-06-01", tz="UTC"), pd.Timestamp("2025-03-31", tz="UTC")))
    assert abs(noise["t_vs_base"]) < 3
    Xp = X.copy()
    Xp["leak"] = Y["ret1"] + np.random.default_rng(2).normal(0, 0.01, len(Y))    # a planted, nearly perfect signal
    planted = fc.score_direction(fc.walk_forward(Xp, Y, "direction", "ridge", pd.Timestamp("2023-06-01", tz="UTC"), pd.Timestamp("2025-03-31", tz="UTC")))
    assert planted["accuracy"] > 0.8 and planted["t_vs_base"] > 5


def test_vol_scoring_and_garch_run():
    df = _inputs(seed=3)
    X, Y = fc.features(df), fc.targets(df)
    t0, t1 = pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-02-29", tz="UTC")
    f = fc.walk_forward(X, Y, "logrv", "gbt", t0, t1)
    g = fc.garch_forecasts(Y["ret1"], pd.date_range(t0, t1, freq="D", tz="UTC"))
    s = fc.score_vol(f, Y["rv_next"], df["dvol"], g)
    assert s["n"] > 40 and np.isfinite(s["dm_t_vs_dvol"]) and np.isfinite(s["dm_t_vs_garch"])


class _LastValueArm:
    """A stand-in for Chronos: forecasts the last value of the history it is given."""

    def forecast(self, history, steps):
        return np.repeat(history[-1], steps)


def test_chronos_arm_sees_only_known_returns():
    # with a leak (tomorrow's return in the history) a last-value arm would be ~100% right; without it, ~50% on noise
    df = _inputs(seed=5)
    X, Y = fc.features(df), fc.targets(df)
    f = fc.walk_forward(X, Y, "direction", "chronos", pd.Timestamp("2023-06-01", tz="UTC"), pd.Timestamp("2025-03-31", tz="UTC"), chronos=_LastValueArm())
    s = fc.score_direction(f)
    assert 0.4 < s["accuracy"] < 0.6 and abs(s["t_vs_base"]) < 3
    f7 = fc.walk_forward(X, Y, "ret7", "chronos", pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-03-31", tz="UTC"), chronos=_LastValueArm())
    assert fc.score_ret7(f7)["oos_r2"] < 0.2
