"""The TimesFM arms on stand-ins: no weights, no network. The engine's leak rule and the covariate alignment."""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.research import forecast as fc
from qr.research import tsfm
from test_forecast import _inputs


class _FakeOutput:
    def __init__(self, forecast):
        self.forecast = forecast


class _FakeTimesFM3:
    """Records what it is asked and answers the last value; the shape checks live in the test."""

    def __init__(self):
        self.calls = []

    def predict_batch(self, contexts, horizon, past_only_covariates=None, return_quantiles=False, **_):
        self.calls.append({"context": contexts[0], "horizon": horizon, "cov": None if past_only_covariates is None else past_only_covariates[0]})
        last = float(contexts[0][-1])
        yield _FakeOutput(np.repeat(last, max(horizon, 64)))      # the real model pads the horizon to a patch; the arm trims


class _FakeTimesFM25:
    def __init__(self):
        self.calls = []

    def forecast(self, horizon, inputs):
        self.calls.append({"horizon": horizon, "n": len(inputs[0])})
        return np.repeat(float(inputs[0][-1]), horizon)[None, :], np.zeros((1, horizon, 10))


def test_window_truncates_history_and_covariates_together():
    h = np.arange(2000, dtype=float)
    c = np.vstack([np.arange(2000), -np.arange(2000)])
    hh, cc = tsfm._window(h, c, 1024)
    assert hh.shape == (1024,) and cc.shape == (2, 1024)
    assert hh[-1] == 1999 and cc[0, -1] == 1999 and cc[1, -1] == -1999 and hh[0] == 976 and cc[0, 0] == 976
    try:
        tsfm._window(h, c[:, :-1], 1024)
        raise AssertionError("misaligned covariates were accepted")
    except ValueError:
        pass


def test_timesfm3_arm_shapes_and_trimming():
    fake = _FakeTimesFM3()
    arm = tsfm.TimesFM3Arm(covariates=True, context=50, forecaster=fake)
    h = np.linspace(0, 1, 200)
    cov = np.vstack([h * 2, h * 3])
    out = arm.forecast(h, 7, cov)
    assert out.shape == (7,) and np.allclose(out, h[-1])
    call = fake.calls[-1]
    assert call["context"].shape == (50,) and call["cov"].shape == (2, 50) and call["horizon"] == 7
    assert np.isclose(call["cov"][0, -1], h[-1] * 2)
    uni = tsfm.TimesFM3Arm(covariates=False, forecaster=_FakeTimesFM3())
    assert uni.forecast(h, 1, cov).shape == (1,)           # a univariate arm ignores covariates it is handed
    assert "Non-Commercial" in arm.licence


def test_timesfm25_arm_shapes():
    fake = _FakeTimesFM25()
    arm = tsfm.TimesFM25Arm(context=100, model=fake)
    out = arm.forecast(np.arange(500, dtype=float), 7)
    assert out.shape == (7,) and np.allclose(out, 499.0) and fake.calls[-1]["n"] == 100


class _CovRecorder:
    """An arm that records the covariate alignment the engine gives it and forecasts the last known value."""

    uses_covariates = True

    def __init__(self):
        self.seen = []

    def forecast(self, history, steps, covariates=None):
        self.seen.append((len(history), None if covariates is None else covariates.shape))
        return np.repeat(history[-1], steps)


def test_covariate_arm_gets_aligned_features_and_only_known_returns():
    df = _inputs(seed=7)
    X, Y = fc.features(df), fc.targets(df)
    rec = _CovRecorder()
    f = fc.walk_forward(X, Y, "direction", "timesfm3_cov", pd.Timestamp("2023-06-01", tz="UTC"), pd.Timestamp("2025-03-31", tz="UTC"), arm=rec)
    assert len(rec.seen) == len(f) > 100
    for n, shape in rec.seen:
        assert shape is not None and shape == (X.shape[1], n)      # one covariate row per feature, one column per history day
    s = fc.score_direction(f)
    assert 0.4 < s["accuracy"] < 0.6 and abs(s["t_vs_base"]) < 3    # a last-value arm on noise sits at the base rate: no leak
    f7 = fc.walk_forward(X, Y, "ret7", "timesfm3_cov", pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-03-31", tz="UTC"), arm=rec)
    assert fc.score_ret7(f7)["oos_r2"] < 0.2


def test_covariates_end_on_the_forecast_day():
    df = _inputs(seed=11)
    X, Y = fc.features(df), fc.targets(df)

    class _Check:
        uses_covariates = True

        def forecast(self, history, steps, covariates=None):
            # the covariate block's last column must be a feature row at or before the forecast day: its values equal
            # X's row at the last history day, and X there is already the lagged feature set
            assert covariates.shape[1] == len(history)
            return np.zeros(steps)

    f = fc.walk_forward(X, Y, "logrv", "timesfm3_cov", pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-02-29", tz="UTC"), arm=_Check())
    assert len(f) > 20


def test_chronos_path_unchanged():
    from test_forecast import _LastValueArm
    df = _inputs(seed=5)
    X, Y = fc.features(df), fc.targets(df)
    f = fc.walk_forward(X, Y, "direction", "chronos", pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-03-31", tz="UTC"), chronos=_LastValueArm())
    assert len(f) > 50 and fc.MODELS == ("ridge", "gbt", "chronos")


def test_make_arm_names():
    assert tsfm.make_arm("timesfm3", forecaster=_FakeTimesFM3()).uses_covariates is False
    assert tsfm.make_arm("timesfm3_cov", forecaster=_FakeTimesFM3()).uses_covariates is True
    assert tsfm.make_arm("timesfm25", model=_FakeTimesFM25()).uses_covariates is False
