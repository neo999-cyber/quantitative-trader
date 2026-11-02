#!/usr/bin/env python3
"""P5: the multivariate foundation-model forecastability test, run once (`docs/prereg/p5_forecastability_tsfm_v1.md`).

    QR_ROOT=~/qr/lake python scripts/p5_tsfm_forecast.py                  # in-sample: test months 2023-01 → 2026-05
    QR_ROOT=~/qr/lake python scripts/p5_tsfm_forecast.py --holdout        # 2026-06 → 2026-09, once, only after an in-sample pass
    QR_ROOT=~/qr/lake python scripts/p5_tsfm_forecast.py --models timesfm25   # a subset (the log records which, and fewer variants)

Nine (target, arm) pairs — P3-C's three targets × the three zero-shot TimesFM arms — each scored with P3-C's scorers
against its no-information benchmark; the permuted-target control and the extra-lag leak check on every pair; the
money test only on a `timesfm25` pair that passes its statistical bar (the licence rule: TimesFM-3's weights are
research-only, so a pass on them is reported as a finding with no money test); one trial-log record with
`variants = 9`. Writes `reports/p5/p5_<sample>_{summary.json,forecasts.parquet,report.md}`. Built 2 November 2026
before registration, on fixtures; it reads the lake only when run.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3c_forecast import money_test  # noqa: E402  — P3-C's money test, unchanged

from qr.config import paths  # noqa: E402
from qr.data.lake import Lake  # noqa: E402
from qr.research import forecast as fc  # noqa: E402
from qr.research import tsfm  # noqa: E402
from qr.validate import stats as st  # noqa: E402
from qr.validate.cscv import cscv  # noqa: E402
from qr.validate.trial_log import TrialLog  # noqa: E402

HYP = "p5_forecastability_tsfm_v1"
MONEY_ARMS = ("timesfm25",)        # the Apache-2.0 weights: the only arm whose forecast could be acted on


def build_arms(names, backend: str = "auto") -> dict:
    """One loaded model per checkpoint: the two TimesFM-3 arms share their weights."""
    arms, shared3 = {}, None
    for n in names:
        if n in ("timesfm3", "timesfm3_cov"):
            if shared3 is None:
                shared3 = tsfm.TimesFM3Arm(covariates=False, backend=backend)
            arms[n] = shared3 if n == "timesfm3" else tsfm.TimesFM3Arm(covariates=True, forecaster=shared3.model, backend=shared3.backend)
        elif n == "timesfm25":
            arms[n] = tsfm.TimesFM25Arm()
        else:
            raise ValueError(n)
    return arms


class Counted:
    """An arm with a heartbeat: counts its forecasts and prints the running speed every `every` calls."""

    def __init__(self, arm, name: str, every: int = 1000):
        self._arm, self.name, self.every, self.n, self.t0 = arm, name, every, 0, time.time()

    def __getattr__(self, k):
        return getattr(self._arm, k)

    def forecast(self, *args, **kw):
        self.n += 1
        if self.n % self.every == 0:
            print(f"  … {self.name}: {self.n} forecasts, {(time.time() - self.t0) / self.n * 1000:.0f} ms each  [{time.strftime('%H:%M:%S')}]", flush=True)
        return self._arm.forecast(*args, **kw)


def arm_record(arm) -> dict:
    return {"checkpoint": arm.checkpoint, "revision": getattr(arm, "revision", None), "context": arm.context,
            "backend": getattr(arm, "backend", "torch"), "covariates": bool(getattr(arm, "uses_covariates", False)),
            "licence": getattr(arm, "licence", "Apache-2.0")}


def score(target: str, f: pd.DataFrame, rv_next: pd.Series, dvol: pd.Series, garch: pd.Series) -> dict:
    if target == "direction":
        return fc.score_direction(f)
    if target == "ret7":
        return fc.score_ret7(f)
    return fc.score_vol(f, rv_next, dvol, garch)


def passes_bar(target: str, sc: dict) -> bool:
    if target == "direction":
        return bool(sc.get("accuracy", 0) > sc.get("base_rate_accuracy", 1) and sc.get("t_vs_base", 0) >= 3)
    if target == "ret7":
        return bool(sc.get("oos_r2", 0) > 0 and sc.get("dm_t_vs_zero", 0) >= 3)
    return bool(sc.get("dm_t_vs_dvol", 0) >= 3)


def write_report(path: Path, summary: dict) -> None:
    lines = [f"# P5 — `{HYP}` — {summary['sample']} {summary['window'][0]} → {summary['window'][1]}", "",
             f"Arms: {', '.join(summary['models'])}; backend {summary['arms'][summary['models'][0]]['backend']}; "
             f"{summary['n_forecasts']} forecasts in {summary['elapsed_s']:.0f} s.", "",
             "| pair | score | permuted control | extra-lag control | bar |", "|---|---|---|---|---|"]
    for name, r in summary["results"].items():
        sc = r.get("score") or {}
        ctl = r.get("controls") or {}
        fmt = lambda d: ", ".join(f"{k} {round(v, 3) if isinstance(v, float) else v}" for k, v in (d or {}).items())  # noqa: E731
        lines.append(f"| `{name}` | {fmt(sc)} | {fmt(ctl.get('permuted'))} | {fmt(ctl.get('extra_lag'))} | "
                     f"{'PASS' if summary['passes'].get(name) else 'fail'} |")
    lines += ["", f"Money test (`{'`, `'.join(MONEY_ARMS)}` pairs above their bar only): "
              f"{json.dumps({n: r.get('money') for n, r in summary['results'].items() if 'money' in r}, default=str)}", "",
              f"Gates: {json.dumps(summary['gates'], default=str)}", "", f"Verdict: {json.dumps(summary['verdict'])}", ""]
    path.write_text("\n".join(lines))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--models", default=",".join(fc.TSFM_MODELS), help="comma-separated subset of " + ",".join(fc.TSFM_MODELS))
    ap.add_argument("--backend", default="auto", choices=("auto", "mlx", "torch"))
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--no-resume", action="store_true", help="recompute every pass even if its checkpoint exists under reports/p5/cache")
    a = ap.parse_args(argv)
    models = [m for m in a.models.split(",") if m]
    for m in models:
        if m not in fc.TSFM_MODELS:
            raise SystemExit(f"unknown arm {m}; choose from {fc.TSFM_MODELS}")
    p = paths().ensure()
    lake = Lake(p)
    mirror = p.root / "mirror"
    df = fc.load_inputs(lake, mirror)
    X, Y = fc.features(df), fc.targets(df)
    t0, t1 = (fc.HOLDOUT if a.holdout else (fc.TEST_START, fc.IN_SAMPLE_END))
    tag = "holdout" if a.holdout else "insample"
    arms = {m: Counted(arm, m) for m, arm in build_arms(models, backend=a.backend).items()}
    out = p.root / "reports" / "p5"
    cache = out / "cache"
    cache.mkdir(parents=True, exist_ok=True)

    def checkpointed(key: str, compute) -> pd.DataFrame:
        """Each walk-forward pass is saved as it completes, so a crash or a sleeping laptop costs nothing already forecast."""
        path = cache / f"{tag}_{key}.parquet"
        if path.exists() and not a.no_resume:
            print(f"  (resumed {path.name})", flush=True)
            return pd.read_parquet(path)
        frame = compute()
        frame.to_parquet(path)
        return frame

    print(f"{HYP} {tag} {t0.date()} → {t1.date()} arms={models} backends={[arms[m].backend for m in models]}  [{time.strftime('%H:%M:%S')}]", flush=True)
    rf = pd.Series(df["tbill"].to_numpy() / 100, index=df.index).ffill()
    panel = lake.load_panel(["BTCUSDT"], "1d", start="2020-09-01", market="futures/um")
    garch = fc.garch_forecasts(Y["ret1"], pd.date_range(t0, t1, freq="D", tz="UTC"))
    results, forecasts, nets, vol_preds, passes = {}, [], {}, {}, {}
    started, n_forecasts = time.time(), 0
    for target in fc.TARGETS:
        for model in models:
            name = f"{target}:{model}"
            arm = arms[model]
            f = checkpointed(f"{target}_{model}_f", lambda: fc.walk_forward(X, Y, target, model, t0, t1, arm=arm))
            n_forecasts += len(f)
            if f.empty:
                results[name] = {"error": "no forecasts"}
                continue
            sc = score(target, f, Y["rv_next"], df["dvol"], garch)
            if target == "logrv":
                vol_preds[model] = f["pred"]
            # controls, as P3-C: the target permuted within years (same pipeline), and one extra day of lag on every input
            rng = np.random.default_rng(fc.SEED)
            Yp = Y.copy()
            for _yr, g in Y.groupby(Y.index.year):
                Yp.loc[g.index, target] = rng.permutation(g[target].to_numpy())
            # only the scored column is permuted; the history the arm sees (`ret1`, `logrv`) stays the real one, as in P3-C
            fp = checkpointed(f"{target}_{model}_fp", lambda: fc.walk_forward(X, Yp, target, model, t0, t1, arm=arm))
            fl = checkpointed(f"{target}_{model}_fl", lambda: fc.walk_forward(X, Y, target, model, t0, t1, arm=arm, lag_extra=1))
            n_forecasts += len(fp) + len(fl)
            ctl = {}
            if len(fp):
                ctl["permuted"] = score(target, fp, Yp["rv_next"], df["dvol"], garch)
            if len(fl):
                ctl["extra_lag"] = score(target, fl, Y["rv_next"], df["dvol"], garch)
            results[name] = {"score": sc, "controls": ctl}
            passes[name] = passes_bar(target, sc)
            f = f.copy()
            f.insert(0, "pair", name)
            forecasts.append(f)
            print(f"{name:22s} {json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in sc.items()})} "
                  f"{'PASS' if passes[name] else 'fail'}  [{time.time()-started:.0f}s]", flush=True)
    # the money test: only an Apache-licensed arm, and only a pair above its statistical bar (the memo's rule)
    for target in ("direction", "ret7"):
        for model in models:
            name = f"{target}:{model}"
            f = next((x for x in forecasts if x["pair"].iloc[0] == name), None)
            if f is None:
                continue
            if model not in MONEY_ARMS:
                results[name]["money"] = {"skipped": "research-only licence: a pass is a finding, not a trade"}
                continue
            if not passes.get(name):
                results[name]["money"] = {"skipped": "below its statistical bar"}
                continue
            mt, net = money_test(lake, f, target, vol_preds.get(model), rf, panel)
            results[name]["money"] = mt
            if len(net):
                nets[name] = net
            print(f"money {name:16s} {json.dumps({k: round(v, 3) for k, v in mt.items() if isinstance(v, float)})}", flush=True)
    n_trials = len(fc.TARGETS) * len(models)
    gates = {"n_trials": n_trials, "money_tested": sorted(nets)}
    if len(nets) >= 1:
        N = pd.DataFrame(nets).fillna(0.0)
        sharpes = {n: st.annualised_sharpe(N[n], 365.0) for n in N}
        best = max(sharpes, key=sharpes.get)
        per_period = np.array([st.moments(N[n]).sharpe for n in N])
        dsr, bench = st.deflated_sharpe(N[best], n_trials=n_trials, trial_sharpes=per_period)
        res = cscv(N, n_blocks=16) if (len(N.columns) >= 2 and len(N) >= 32) else None
        gates.update({"best": best, "net_sharpe": sharpes, "dsr": float(dsr), "dsr_benchmark_per_period": float(bench), "pbo": (res.pbo if res else None)})
        print("gates:", json.dumps(gates, default=str))
    money_pass = {n: bool(r.get("money", {}).get("net_sharpe", 0) >= 1.0 and r.get("money", {}).get("alpha_t_vs_cash", 0) >= 2 and gates.get("dsr", 0) >= 0.9)
                  for n, r in results.items() if isinstance(r.get("money"), dict) and "net_sharpe" in r.get("money", {})}
    statistical = [n for n, v in passes.items() if v]
    verdict = {"statistical_passes": statistical,
               "research_findings_no_money_test": [n for n in statistical if n.split(":")[1] not in MONEY_ARMS],
               "money_passes": [n for n, v in money_pass.items() if v]}
    verdict["covariates_beat_univariate"] = {t: bool(passes.get(f"{t}:timesfm3_cov") and not passes.get(f"{t}:timesfm3")) for t in fc.TARGETS} \
        if {"timesfm3", "timesfm3_cov"} <= set(models) else None
    verdict["PASS"] = bool(verdict["money_passes"])
    print("verdict:", json.dumps(verdict))
    if forecasts:
        pd.concat(forecasts).to_parquet(out / f"p5_{tag}_forecasts.parquet")
    summary = {"hypothesis": HYP, "sample": tag, "window": [str(t0.date()), str(t1.date())], "models": models,
               "arms": {m: arm_record(arms[m]) for m in models}, "n_forecasts": int(n_forecasts), "elapsed_s": time.time() - started,
               "results": results, "passes": passes, "gates": gates, "verdict": verdict}
    (out / f"p5_{tag}_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    write_report(out / f"p5_{tag}_report.md", summary)
    if not a.no_log:
        rec = TrialLog(p.trial_log).run(HYP, "forecastability", {"engine": "scripts/p5_tsfm_forecast.py", "sample": tag, "models": models,
                                                                 "targets": list(fc.TARGETS), "arms": summary["arms"]},
                                         "btcusdt_perp_daily_with_free_inputs",
                                         metrics={"scores": {n: r.get("score") for n, r in results.items()}, "gates": gates, "verdict": verdict},
                                         variants=n_trials)
        print("trial log seq", rec.seq)
    return 0


if __name__ == "__main__":
    sys.exit(main())
