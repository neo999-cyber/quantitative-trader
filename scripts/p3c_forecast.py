#!/usr/bin/env python3
"""P3-C: the forecastability kill test, run once (`docs/prereg/p3_forecastability_v1.md`, seq 935).

    QR_ROOT=~/qr/lake python scripts/p3c_forecast.py                 # in-sample: test months 2023-01 → 2026-05
    QR_ROOT=~/qr/lake python scripts/p3c_forecast.py --holdout       # 2026-06 → 2026-09, once, only after an in-sample pass
    QR_ROOT=~/qr/lake python scripts/p3c_forecast.py --no-chronos    # six variants (if the arm is unavailable)

Nine (target, model) pairs, each scored against its no-information
benchmark; the permuted-target control and the extra-lag leak check on
every pair; the money test through the ledger engine (perp costs, cash
benchmark, DSR over the nine) for every pair; one trial-log record with
`variants=9`. Writes `reports/p3/p3c_<sample>_{summary.json,forecasts.parquet,report.md}`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from qr.config import paths
from qr.data.lake import Lake
from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research import forecast as fc
from qr.research.runner import run_backtest
from qr.strategies.base import Strategy
from qr.validate import stats as st
from qr.validate.cscv import cscv
from qr.validate.spa import cash_benchmark
from qr.validate.trial_log import TrialLog

HYP = "p3_forecastability_v1"
TARGET_VOL = 0.20


class FixedWeights(Strategy):
    """A precomputed weight series on one symbol — the forecast's position, already lagged by the runner."""
    family = "forecast_money_test"

    def __init__(self, weights: pd.Series, symbol: str = "BTCUSDT") -> None:
        super().__init__(symbol=symbol)
        self._w = weights

    def target_weights(self, panel: Panel, universe=None) -> pd.DataFrame:
        w = pd.DataFrame(0.0, index=panel.close.index, columns=panel.close.columns)
        w[self.params["symbol"]] = self._w.reindex(panel.close.index).fillna(0.0).clip(-1, 1)
        return w


def money_test(lake, f: pd.DataFrame, target: str, vol_pred: pd.Series | None, rf: pd.Series, panel: Panel) -> tuple[dict, pd.Series]:
    """Trade the forecast: direction/7-day sign, sized to a 20% vol target by the vol forecast (the pair's own family, else realised 21-d)."""
    if target == "logrv":
        return {"skipped": "a variance forecast has no direction to trade"}, pd.Series(dtype=float)
    sign = np.sign(f["pred"] - (0.5 if target == "direction" else 0.0))
    if vol_pred is not None and len(vol_pred):
        sigma = np.sqrt(np.exp(vol_pred.reindex(f.index)) * 365)
    else:
        lr = np.log(panel.close["BTCUSDT"]).diff()
        sigma = (lr.rolling(21).std() * np.sqrt(365)).reindex(f.index)
    w = (sign * (TARGET_VOL / sigma.replace(0, np.nan))).clip(-1, 1).fillna(0.0)
    if target == "ret7":
        w = w.rolling(7, min_periods=1).mean()   # a 7-day forecast is held across its horizon: overlapping positions averaged
    res = run_backtest(panel, FixedWeights(w), costs=CostModel.binance_perp(), engine="ledger", risk_free=rf)
    net = res.net.reindex(f.index).dropna()
    bench = cash_benchmark(net.index, 365.0, rf)
    excess = net - bench.reindex(net.index).fillna(0.0)
    t, p, lags = st.hac_tstat(excess)
    return {"net_sharpe": st.annualised_sharpe(net, 365.0), "alpha_t_vs_cash": float(t), "ann_net": float(net.mean() * 365), "turnover_ann": float(res.turnover.reindex(net.index).mean() * 365)}, net


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--no-chronos", action="store_true")
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args(argv)
    p = paths().ensure()
    lake = Lake(p)
    mirror = p.root / "mirror"
    df = fc.load_inputs(lake, mirror)
    X, Y = fc.features(df), fc.targets(df)
    t0, t1 = (fc.HOLDOUT if a.holdout else (fc.TEST_START, fc.IN_SAMPLE_END))
    tag = "holdout" if a.holdout else "insample"
    models = [m for m in fc.MODELS if not (a.no_chronos and m == "chronos")]
    chronos = fc.ChronosArm() if "chronos" in models else None
    rf = pd.Series(df["tbill"].to_numpy() / 100, index=df.index).ffill()
    panel = lake.load_panel(["BTCUSDT"], "1d", start="2020-09-01", market="futures/um")
    garch = fc.garch_forecasts(Y["ret1"], pd.date_range(t0, t1, freq="D", tz="UTC"))
    results, forecasts, nets, vol_preds = {}, [], {}, {}
    started = time.time()
    for target in fc.TARGETS:
        for model in models:
            name = f"{target}:{model}"
            f = fc.walk_forward(X, Y, target, model, t0, t1, chronos=chronos)
            if f.empty:
                results[name] = {"error": "no forecasts"}
                continue
            if target == "direction":
                sc = fc.score_direction(f)
            elif target == "ret7":
                sc = fc.score_ret7(f)
            else:
                sc = fc.score_vol(f, Y["rv_next"], df["dvol"], garch)
                vol_preds[model] = f["pred"]
            # controls: the target permuted within years (same pipeline), and one extra day of lag on every input
            rng = np.random.default_rng(fc.SEED)
            Yp = Y.copy()
            for yr, g in Y.groupby(Y.index.year):
                Yp.loc[g.index, target] = rng.permutation(g[target].to_numpy())
            fp = fc.walk_forward(X, Yp, target, model, t0, t1, chronos=chronos) if model != "chronos" else pd.DataFrame()
            fl = fc.walk_forward(X, Y, target, model, t0, t1, chronos=chronos, lag_extra=1) if model != "chronos" else pd.DataFrame()
            ctl = {}
            if len(fp):
                ctl["permuted"] = fc.score_direction(fp) if target == "direction" else (fc.score_ret7(fp) if target == "ret7" else fc.score_vol(fp, Yp["rv_next"], df["dvol"], garch))
            if len(fl):
                ctl["extra_lag"] = fc.score_direction(fl) if target == "direction" else (fc.score_ret7(fl) if target == "ret7" else fc.score_vol(fl, Y["rv_next"], df["dvol"], garch))
            results[name] = {"score": sc, "controls": ctl}
            f = f.copy()
            f.insert(0, "pair", name)
            forecasts.append(f)
            print(f"{name:20s} {json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in sc.items()})}  [{time.time()-started:.0f}s]", flush=True)
    # the money test on every directional pair, with the pair's own family's vol forecast
    for target in ("direction", "ret7"):
        for model in models:
            name = f"{target}:{model}"
            f = next((x for x in forecasts if x["pair"].iloc[0] == name), None)
            if f is None:
                continue
            mt, net = money_test(lake, f, target, vol_preds.get(model), rf, panel)
            results[name]["money"] = mt
            if len(net):
                nets[name] = net
            print(f"money {name:14s} {json.dumps({k: round(v, 3) for k, v in mt.items() if isinstance(v, float)})}", flush=True)
    gates = {}
    if len(nets) >= 2:
        N = pd.DataFrame(nets).fillna(0.0)
        sharpes = {n: st.annualised_sharpe(N[n], 365.0) for n in N}
        best = max(sharpes, key=sharpes.get)
        per_period = np.array([st.moments(N[n]).sharpe for n in N])
        dsr, bench = st.deflated_sharpe(N[best], n_trials=len(fc.TARGETS) * len(models), trial_sharpes=per_period)
        res = cscv(N, n_blocks=16) if len(N) >= 32 else None
        gates = {"best": best, "net_sharpe": sharpes, "dsr": float(dsr), "dsr_benchmark_per_period": float(bench), "pbo": (res.pbo if res else None), "n_trials": len(fc.TARGETS) * len(models)}
        print("gates:", json.dumps(gates, default=str))
    # verdict against the registered bars
    passes = {}
    for name, r in results.items():
        sc = r.get("score", {})
        tgt = name.split(":")[0]
        if tgt == "direction":
            passes[name] = bool(sc.get("accuracy", 0) > sc.get("base_rate_accuracy", 1) and sc.get("t_vs_base", 0) >= 3)
        elif tgt == "ret7":
            passes[name] = bool(sc.get("oos_r2", 0) > 0 and sc.get("dm_t_vs_zero", 0) >= 3)
        else:
            passes[name] = bool(sc.get("dm_t_vs_dvol", 0) >= 3)
    money_pass = {n: bool(r.get("money", {}).get("net_sharpe", 0) >= 1.0 and r.get("money", {}).get("alpha_t_vs_cash", 0) >= 2 and gates.get("dsr", 0) >= 0.9) for n, r in results.items() if "money" in r}
    verdict = {"statistical_passes": [n for n, v in passes.items() if v], "money_passes": [n for n, v in money_pass.items() if v]}
    verdict["PASS"] = bool(verdict["statistical_passes"] and verdict["money_passes"])
    print("verdict:", json.dumps(verdict))
    out = p.root / "reports" / "p3"
    out.mkdir(parents=True, exist_ok=True)
    if forecasts:
        pd.concat(forecasts).to_parquet(out / f"p3c_{tag}_forecasts.parquet")
    (out / f"p3c_{tag}_summary.json").write_text(json.dumps({"hypothesis": HYP, "sample": tag, "window": [str(t0.date()), str(t1.date())], "models": models, "results": results, "gates": gates, "verdict": verdict}, indent=1, default=str))
    if not a.no_log:
        rec = TrialLog(p.trial_log).run(HYP, "forecastability", {"engine": "scripts/p3c_forecast.py", "sample": tag, "models": models, "targets": list(fc.TARGETS)}, "btcusdt_perp_daily_with_free_inputs",
                                         metrics={"scores": {n: r.get("score") for n, r in results.items()}, "gates": gates, "verdict": verdict}, variants=len(fc.TARGETS) * len(models))
        print("trial log seq", rec.seq)
    return 0


if __name__ == "__main__":
    sys.exit(main())
