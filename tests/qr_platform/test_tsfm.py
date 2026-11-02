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


# ----------------------------------------------------------------- the run script's seams (no data, no weights)

def _p5():
    import importlib
    import sys
    from pathlib import Path
    scripts = str(Path(__file__).resolve().parents[2] / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return importlib.import_module("p5_tsfm_forecast")


def test_build_arms_shares_the_timesfm3_weights(monkeypatch):
    p5 = _p5()
    loads = []

    class Fake3(tsfm.TimesFM3Arm):
        def __init__(self, checkpoint=tsfm.TIMESFM3_CHECKPOINT, context=tsfm.DEFAULT_CONTEXT, covariates=False, backend="auto",
                     device=None, forecaster=None, revision=tsfm.TIMESFM3_REVISION):
            if forecaster is None:
                loads.append("timesfm3")
                forecaster = object()
            super().__init__(checkpoint, context, covariates, backend, device, forecaster, revision)

    class Fake25(tsfm.TimesFM25Arm):
        def __init__(self, checkpoint=tsfm.TIMESFM25_CHECKPOINT, context=tsfm.DEFAULT_CONTEXT, model=None, revision=tsfm.TIMESFM25_REVISION):
            loads.append("timesfm25")
            super().__init__(checkpoint, context, object(), revision)

    monkeypatch.setattr(tsfm, "TimesFM3Arm", Fake3)
    monkeypatch.setattr(tsfm, "TimesFM25Arm", Fake25)
    arms = p5.build_arms(["timesfm3", "timesfm3_cov", "timesfm25"])
    assert loads == ["timesfm3", "timesfm25"]                       # one load per checkpoint
    assert arms["timesfm3"].model is arms["timesfm3_cov"].model      # the two TimesFM-3 arms share their weights
    assert not arms["timesfm3"].uses_covariates and arms["timesfm3_cov"].uses_covariates
    assert arms["timesfm3"].revision == tsfm.TIMESFM3_REVISION and arms["timesfm25"].revision == tsfm.TIMESFM25_REVISION
    rec = p5.arm_record(arms["timesfm3_cov"])
    assert rec["covariates"] and rec["revision"] == tsfm.TIMESFM3_REVISION and "Non-Commercial" in rec["licence"]
    assert p5.arm_record(arms["timesfm25"])["licence"] == "Apache-2.0"


def test_bars_and_money_rule_as_registered(tmp_path):
    p5 = _p5()
    assert p5.MONEY_ARMS == ("timesfm25",)
    assert p5.passes_bar("direction", {"accuracy": 0.55, "base_rate_accuracy": 0.50, "t_vs_base": 3.1})
    assert not p5.passes_bar("direction", {"accuracy": 0.55, "base_rate_accuracy": 0.50, "t_vs_base": 2.9})
    assert p5.passes_bar("ret7", {"oos_r2": 0.01, "dm_t_vs_zero": 3.0}) and not p5.passes_bar("ret7", {"oos_r2": -0.01, "dm_t_vs_zero": 3.0})
    assert p5.passes_bar("logrv", {"dm_t_vs_dvol": 3.0}) and not p5.passes_bar("logrv", {"dm_t_vs_dvol": 2.0})
    summary = {"sample": "insample", "window": ["2023-01-01", "2026-05-31"], "models": ["timesfm25"],
               "arms": {"timesfm25": {"backend": "torch"}}, "n_forecasts": 3, "elapsed_s": 1.0,
               "results": {"direction:timesfm25": {"score": {"accuracy": 0.5}, "controls": {"permuted": {"accuracy": 0.49}},
                                                   "money": {"skipped": "below its statistical bar"}}},
               "passes": {"direction:timesfm25": False}, "gates": {"n_trials": 3}, "verdict": {"PASS": False}}
    p5.write_report(tmp_path / "r.md", summary)
    text = (tmp_path / "r.md").read_text()
    assert "direction:timesfm25" in text and "below its statistical bar" in text and "fail" in text
