"""P3-C forecastability test — inputs, features, targets, walk-forward, metrics (`docs/prereg/p3_forecastability_v1.md`, seq 935).

Everything at day *t* is computable at the close of day *t*; macro and
on-chain series are lagged one extra day for publication. The walk-forward
is expanding, refit monthly, with a 7-day purge before each test month.
Three model families: `ridge` (the floor), `gbt` (gradient-boosted trees)
and `chronos` (a zero-shot time-series foundation model on the target's
own history). The benchmarks are the base rate (direction), zero (the
7-day return) and DVOL / GARCH (variance).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261001
PURGE_DAYS = 7
TARGETS = ("direction", "ret7", "logrv")
MODELS = ("ridge", "gbt", "chronos")
IN_SAMPLE_START = pd.Timestamp("2021-03-24", tz="UTC")
TEST_START = pd.Timestamp("2023-01-01", tz="UTC")
IN_SAMPLE_END = pd.Timestamp("2026-05-31", tz="UTC")
HOLDOUT = (pd.Timestamp("2026-06-01", tz="UTC"), pd.Timestamp("2026-09-30", tz="UTC"))


# ------------------------------------------------------------------ inputs
def load_inputs(lake, mirror: Path) -> pd.DataFrame:
    """One row per UTC day: price, funding, OI, realised variance (from hourly spot), DVOL, sentiment, stablecoins, on-chain, macro."""
    ref = lake.paths.reference
    perp = lake.read_klines("BTCUSDT", "1d", market="futures/um")          # the perpetual's bars
    deriv = lake.read_klines("BTCUSDT", "1d", market="futures-um")        # its funding and open interest
    df = pd.DataFrame({"close": perp["close"], "high": perp["high"], "low": perp["low"], "volume": perp["quote_volume"]})
    df.index = df.index.normalize()
    deriv.index = deriv.index.normalize()
    df["funding"] = deriv["funding_rate"].reindex(df.index)
    df["oi"] = deriv["open_interest_usd"].reindex(df.index)
    h = lake.read_klines("BTCUSDT", "1h", market="spot")["close"]
    tail = mirror / "p3" / "btc_1h_tail_2026-09.parquet"
    if tail.exists():
        h = pd.concat([h, pd.read_parquet(tail)["close"]]).sort_index()
        h = h[~h.index.duplicated(keep="last")]
    r2 = np.log(h).diff() ** 2
    df["rv"] = r2.groupby(r2.index.normalize()).sum().reindex(df.index)
    df["dvol"] = pd.read_parquet(ref / "dvol_BTC.parquet").set_index("date")["close"].reindex(df.index)
    fg = pd.read_parquet(ref / "fear_greed.parquet")
    fg_idx = pd.to_datetime(fg.iloc[:, 0], utc=True).dt.normalize()
    df["fng"] = pd.Series(fg["fng_value"].to_numpy(), index=fg_idx).reindex(df.index)
    sc = pd.read_parquet(ref / "stablecoin_supply.parquet").set_index("date")["supply_usd"]
    df["stable_supply"] = sc.reindex(df.index)
    oc = pd.read_parquet(ref / "onchain_btc.parquet").set_index("date")
    for c in ("hash_rate", "n_unique_addresses", "n_transactions"):
        df[c] = oc[c].reindex(df.index).shift(1)          # final after the day closes: use yesterday's
    for series, name in (("DTWEXBGS", "dxy"), ("DGS10", "us10y")):
        s = pd.read_parquet(ref / f"fred_{series}.parquet").set_index("date")["value"]
        df[name] = s.reindex(df.index).ffill().shift(1)      # published next day
    rf = pd.read_parquet(ref / "risk_free_dtb3.parquet")
    rf_idx = pd.to_datetime(rf.iloc[:, 0], utc=True).dt.normalize()
    df["tbill"] = pd.Series(rf.iloc[:, 1].to_numpy(), index=rf_idx).reindex(df.index).ffill().shift(1)
    return df


# ---------------------------------------------------------------- features
def features(df: pd.DataFrame) -> pd.DataFrame:
    """The frozen feature table; every value is known at the close of its day."""
    lr = np.log(df["close"]).diff()
    X = pd.DataFrame(index=df.index)
    for k in (1, 2, 3, 5, 10, 21, 63):
        X[f"ret_{k}"] = lr.rolling(k).sum()
    for k in (5, 21, 63):
        X[f"rvol_{k}"] = lr.rolling(k).std() * math.sqrt(365)
    for k in (21, 63, 252):
        X[f"dd_{k}"] = df["close"] / df["close"].rolling(k).max() - 1
    X["dow"] = df.index.dayofweek
    X["funding"] = df["funding"]
    X["funding_3"] = df["funding"].rolling(3).mean()
    X["funding_7"] = df["funding"].rolling(7).mean()
    X["oi_level"] = np.log(df["oi"])
    X["oi_chg_1"] = np.log(df["oi"]).diff()
    X["oi_chg_7"] = np.log(df["oi"]).diff(7)
    X["dvol"] = df["dvol"]
    X["dvol_chg_1"] = df["dvol"].diff()
    X["dvol_chg_7"] = df["dvol"].diff(7)
    X["dvol_minus_rv21"] = df["dvol"] - X["rvol_21"] * 100
    X["fng"] = df["fng"]
    X["fng_chg_7"] = df["fng"].diff(7)
    X["stable_chg_7"] = np.log(df["stable_supply"]).diff(7)
    X["stable_chg_30"] = np.log(df["stable_supply"]).diff(30)
    for c in ("hash_rate", "n_unique_addresses", "n_transactions"):
        X[f"{c}_chg_7"] = np.log(df[c]).diff(7)
        X[f"{c}_chg_30"] = np.log(df[c]).diff(30)
    for c in ("dxy", "us10y", "tbill"):
        X[c] = df[c]
        X[f"{c}_chg_5"] = df[c].diff(5)
    X["logrv_1"] = np.log(df["rv"].clip(lower=1e-10))
    X["logrv_5"] = np.log(df["rv"].rolling(5).mean().clip(lower=1e-10))
    X["logrv_21"] = np.log(df["rv"].rolling(21).mean().clip(lower=1e-10))
    return X.replace([np.inf, -np.inf], np.nan)   # a log of a zero print (open interest, on-chain gaps) is a missing value, not a number


def targets(df: pd.DataFrame) -> pd.DataFrame:
    lr = np.log(df["close"]).diff()
    y = pd.DataFrame(index=df.index)
    y["ret1"] = lr.shift(-1)
    y["direction"] = (y["ret1"] > 0).astype(float).where(y["ret1"].notna())
    y["ret7"] = lr.rolling(7).sum().shift(-7)
    y["logrv"] = np.log(df["rv"].clip(lower=1e-10)).shift(-1)
    y["rv_next"] = df["rv"].shift(-1)
    return y


# ------------------------------------------------------------------ models
def _fit_predict(model: str, kind: str, Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray, seed: int) -> np.ndarray:
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    from sklearn.linear_model import LogisticRegressionCV, RidgeCV
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if model == "ridge":
        if kind == "direction":
            m = make_pipeline(StandardScaler(), LogisticRegressionCV(Cs=8, cv=5, max_iter=2000, scoring="neg_log_loss"))
            m.fit(Xtr, ytr)
            return m.predict_proba(Xte)[:, 1]
        m = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 4, 13)))
        m.fit(Xtr, ytr)
        return m.predict(Xte)
    if model == "gbt":
        kw = dict(max_depth=4, max_iter=300, learning_rate=0.05, early_stopping=True, validation_fraction=0.15, n_iter_no_change=20, random_state=seed)
        if kind == "direction":
            m = HistGradientBoostingClassifier(**kw)
            m.fit(Xtr, ytr)
            return m.predict_proba(Xte)[:, 1]
        m = HistGradientBoostingRegressor(**kw)
        m.fit(Xtr, ytr)
        return m.predict(Xte)
    raise ValueError(model)


class ChronosArm:
    """Zero-shot Chronos-Bolt on the target's own history (context 512), one forecast per test day."""

    def __init__(self, name: str = "amazon/chronos-bolt-small", context: int = 512):
        import torch
        from chronos import BaseChronosPipeline
        self.pipe = BaseChronosPipeline.from_pretrained(name, device_map="cpu", torch_dtype=torch.float32)
        self.context = context
        self.torch = torch

    def forecast(self, history: np.ndarray, steps: int) -> np.ndarray:
        ctx = self.torch.tensor(history[-self.context:], dtype=self.torch.float32)
        q, mean = self.pipe.predict_quantiles([ctx], prediction_length=steps, quantile_levels=[0.5])
        return mean[0].numpy()


def walk_forward(X: pd.DataFrame, y: pd.DataFrame, target: str, model: str, test_start=TEST_START, test_end=IN_SAMPLE_END,
                 seed: int = SEED, chronos: "ChronosArm | None" = None, lag_extra: int = 0) -> pd.DataFrame:
    """Out-of-sample forecasts for one (target, model) pair: columns `pred`, `y`, `base` (the no-information benchmark)."""
    kind = target
    Xs = X.shift(lag_extra) if lag_extra else X
    data = pd.concat([Xs, y[[target]]], axis=1).dropna()
    data = data[data.index >= IN_SAMPLE_START]
    out = []
    months = pd.date_range(test_start, test_end, freq="MS", tz="UTC")
    for m0 in months:
        m1 = min(m0 + pd.offsets.MonthEnd(1), test_end)
        train = data[data.index <= m0 - pd.Timedelta(days=PURGE_DAYS + 1)]
        test = data[(data.index >= m0) & (data.index <= m1)]
        if len(train) < 250 or test.empty:
            continue
        ytr = train[target].to_numpy()
        base = float(ytr.mean()) if kind == "direction" else (0.0 if kind == "ret7" else float(np.mean(ytr[-21:])))
        if model == "chronos":
            if chronos is None:
                raise RuntimeError("the chronos arm needs a ChronosArm")
            # the target's own history as known at the close of each test day: `ret1[t]` is TOMORROW's return (the
            # target), so the known return series is ret1 shifted by one; logrv likewise. Run 936 (1 Oct 2026) fed the
            # unshifted series and "forecast" direction at Sharpe 5 — caught by the memo's leak rule, fixed here.
            known_ret = y["ret1"].shift(1 + lag_extra)
            known_logrv = y["logrv"].shift(1 + lag_extra)
            preds = []
            for t in test.index:
                if kind == "ret7":
                    preds.append(float(chronos.forecast(known_ret[known_ret.index <= t].dropna().to_numpy(), 7).sum()))
                elif kind == "direction":
                    preds.append(float(chronos.forecast(known_ret[known_ret.index <= t].dropna().to_numpy(), 1)[0]))
                else:
                    preds.append(float(chronos.forecast(known_logrv[known_logrv.index <= t].dropna().to_numpy(), 1)[0]))
            pred = np.array(preds)
            if kind == "direction":
                pred = 1 / (1 + np.exp(-pred / max(np.std(y["ret1"].dropna()), 1e-6) * 2))   # a forecast return into a probability, monotone
        else:
            pred = _fit_predict(model, kind, train.drop(columns=[target]).to_numpy(), ytr, test.drop(columns=[target]).to_numpy(), seed)
        out.append(pd.DataFrame({"pred": pred, "y": test[target].to_numpy(), "base": base}, index=test.index))
    return pd.concat(out) if out else pd.DataFrame(columns=["pred", "y", "base"])


# ----------------------------------------------------------------- metrics
def hac_t(x: np.ndarray, lags: int) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 10:
        return float("nan")
    m = x.mean()
    e = x - m
    s = (e * e).sum()
    for k in range(1, lags + 1):
        w = 1 - k / (lags + 1)
        s += 2 * w * (e[k:] * e[:-k]).sum()
    se = math.sqrt(max(s, 1e-18)) / n
    return float(m / se) if se > 0 else float("nan")


def score_direction(f: pd.DataFrame) -> dict:
    hit = ((f["pred"] > 0.5).astype(float) == f["y"]).astype(float)
    base_hit = ((f["base"] > 0.5).astype(float) == f["y"]).astype(float)
    brier = (f["pred"] - f["y"]) ** 2
    brier_base = (f["base"] - f["y"]) ** 2
    return {"n": int(len(f)), "accuracy": float(hit.mean()), "base_rate_accuracy": float(base_hit.mean()),
            "t_vs_base": hac_t((hit - base_hit).to_numpy(), 5), "brier_skill": float(1 - brier.mean() / brier_base.mean()),
            "t_brier": hac_t((brier_base - brier).to_numpy(), 5)}


def score_ret7(f: pd.DataFrame) -> dict:
    e2 = (f["y"] - f["pred"]) ** 2
    b2 = f["y"] ** 2
    return {"n": int(len(f)), "oos_r2": float(1 - e2.sum() / b2.sum()), "dm_t_vs_zero": hac_t((b2 - e2).to_numpy(), 7)}


def qlike(rv: np.ndarray, var_hat: np.ndarray) -> np.ndarray:
    r = rv / var_hat
    return r - np.log(r) - 1


def score_vol(f: pd.DataFrame, rv_next: pd.Series, dvol: pd.Series, garch_var: pd.Series) -> dict:
    idx = f.index
    rv = rv_next.reindex(idx).to_numpy()
    var_model = np.exp(f["pred"].to_numpy())
    var_dvol = ((dvol.reindex(idx).to_numpy() / 100) ** 2) / 365
    var_garch = garch_var.reindex(idx).to_numpy()
    ok = np.isfinite(rv) & np.isfinite(var_model) & np.isfinite(var_dvol) & np.isfinite(var_garch) & (rv > 0)
    lm, ld, lg = qlike(rv[ok], var_model[ok]), qlike(rv[ok], var_dvol[ok]), qlike(rv[ok], var_garch[ok])
    return {"n": int(ok.sum()), "qlike_model": float(lm.mean()), "qlike_dvol": float(ld.mean()), "qlike_garch": float(lg.mean()),
            "dm_t_vs_dvol": hac_t(ld - lm, 5), "dm_t_vs_garch": hac_t(lg - lm, 5)}


def garch_forecasts(ret1_known: pd.Series, test_index: pd.DatetimeIndex) -> pd.Series:
    """GARCH(1,1) one-step variance, refit monthly on the past only (returns in %, variance back in decimal)."""
    from arch import arch_model
    out = {}
    months = pd.date_range(test_index.min().replace(day=1), test_index.max(), freq="MS", tz="UTC")
    for m0 in months:
        m1 = m0 + pd.offsets.MonthEnd(1)
        hist = ret1_known[ret1_known.index < m0].dropna() * 100
        if len(hist) < 250:
            continue
        am = arch_model(hist.to_numpy(), vol="Garch", p=1, q=1, mean="Zero", rescale=False)
        res = am.fit(disp="off")
        params = res.params
        omega, alpha, beta = params["omega"], params["alpha[1]"], params["beta[1]"]
        # roll the recursion through the test month using realised returns as they arrive
        r_all = ret1_known.dropna() * 100
        r_hist = r_all[r_all.index < m0]
        h = float(res.conditional_volatility[-1] ** 2)
        last_r = float(r_hist.iloc[-1])
        for t in test_index[(test_index >= m0) & (test_index <= m1)]:
            h = omega + alpha * last_r**2 + beta * h
            out[t] = h / 1e4
            if t in r_all.index:
                last_r = float(r_all.loc[t])
    return pd.Series(out)
