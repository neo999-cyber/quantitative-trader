import numpy as np
import pandas as pd

from centaur.screens.regime import RegimeInputs, assess_regime, Regime
from conftest import make_ohlcv


def _series(n, start, drift, vol, seed):
    return make_ohlcv(n, seed=seed, start=start, drift=drift, vol=vol)["Close"]


def test_risk_on_environment():
    n = 300
    idx = pd.bdate_range(end="2026-09-10", periods=n)
    inputs = RegimeInputs(
        spy=_series(n, 400, 0.002, 0.004, 1),
        qqq=_series(n, 350, 0.002, 0.004, 2),
        vix=pd.Series(np.full(n, 13.0), index=idx),
        vix3m=pd.Series(np.full(n, 16.0), index=idx),
        us10y=pd.Series(np.full(n, 4.3), index=idx),
        us3m=pd.Series(np.full(n, 3.5), index=idx),
        dxy=pd.Series(np.linspace(105, 101, n), index=idx),
    )
    a = assess_regime(inputs)
    assert a.regime == Regime.RISK_ON
    assert a.confidence > 0.6
    assert {c.name for c in a.components} >= {"trend_spy", "trend_qqq", "vix_level", "vix_term_structure", "yield_curve", "dollar_dxy"}


def test_risk_off_environment():
    n = 300
    idx = pd.bdate_range(end="2026-09-10", periods=n)
    inputs = RegimeInputs(
        spy=_series(n, 500, -0.003, 0.004, 3),
        qqq=_series(n, 450, -0.003, 0.004, 4),
        vix=pd.Series(np.r_[np.full(n - 5, 22.0), np.full(5, 34.0)], index=idx),
        vix3m=pd.Series(np.full(n, 28.0), index=idx),
        us10y=pd.Series(np.full(n, 3.8), index=idx),
        us3m=pd.Series(np.full(n, 4.6), index=idx),
        dxy=pd.Series(np.linspace(100, 105, n), index=idx),
    )
    a = assess_regime(inputs)
    assert a.regime == Regime.RISK_OFF
    assert a.bearish
    assert a.confidence > 0.6


def test_missing_components_are_reported_not_fatal():
    n = 300
    idx = pd.bdate_range(end="2026-09-10", periods=n)
    inputs = RegimeInputs(spy=_series(n, 400, 0.0, 0.01, 5), qqq=_series(n, 350, 0.0, 0.01, 6),
                          vix=pd.Series(np.full(n, 18.0), index=idx))
    a = assess_regime(inputs)
    assert len(a.components) == 3
    assert any("yield curve" in w for w in a.warnings)
    assert 0 <= a.confidence <= 1
    d = a.to_dict()
    assert d["regime"] in {"RISK_ON", "RISK_OFF", "NEUTRAL"}
