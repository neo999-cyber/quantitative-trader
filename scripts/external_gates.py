"""E5 (`p2_insider_cluster_v1`): the gate statistics on results run outside the engine.

QuantConnect's free tier runs the family; its results come home as JSON
(`qr/data/quantconnect.py`). This script records the sweep in the trial log
(counted, like every backtest), then computes what the engine's own gate
functions can compute from return series alone:

  gate 2  cost survival   — net = gross minus the alpaca_zero round-trip cost
                             charged per order (2 x 3 bps of the slice)
  gate 3  significance    — HAC t-statistic, PSR (qr.validate.stats)
  gate 4  deflation       — DSR over the 8 pre-registered variants
  gate 5  selection       — PBO (CSCV) and SPA against the exposure-matched
                             benchmark (the QC equal-weight eligible universe,
                             scaled to the best variant's mean exposure)
  gate 7  cross-validated — CPCV paths on the best variant

Gates 1, 6 and 8 need the panel and cannot run on an external engine; the
random-entry control (one QC draw) stands beside gate 6 as evidence, not as a
p-value. This is written in the report and the log.

    export QR_ROOT=~/qr/lake
    .venv/bin/python scripts/external_gates.py --family e5
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from qr.config import paths
from qr.data.quantconnect import daily_equity, load_result, statistics
from qr.execution.costs import CostModel
from qr.validate import stats as st
from qr.validate.cscv import cscv
from qr.validate.spa import cash_benchmark, superior_predictive_ability
from qr.validate.trial_log import TrialLog

import argparse

ap = argparse.ArgumentParser()
ap.add_argument("--family", default="e5", help="e5, e4 or e7: which mirror folder and hypothesis")
ap.add_argument("--no-log", action="store_true", help="recompute without recording the sweep again")
args = ap.parse_args()
HYP = {"e5": "p2_insider_cluster_v1", "e4": "p2_pead_v1", "e7": "p2_short_squeeze_v1"}[args.family]
FAMILY_NAME = {"e5": "insider_cluster", "e4": "pead", "e7": "short_squeeze"}[args.family]
root = Path(paths().root)
files = sorted(glob.glob(str(root / "mirror" / "quantconnect" / args.family / f"qc_{args.family}_*.json")))
variants, gross, net, meta, controls = {}, {}, {}, {}, {}
costs = CostModel.alpaca_zero()
for f in files:
    r = load_result(f)
    v = r.get("variant") or {"hold_sessions": 60, "min_combined_usd": 100000, "min_insiders": 2, "max_positions": 4, "equity": 1000}
    if args.family == "e5":
        name = f"e5_hold{v['hold_sessions']}_usd{int(v['min_combined_usd'])}_ins{v['min_insiders']}"
    else:
        name = v.get("impl", args.family).replace(".py", "")
        v.setdefault("max_positions", v.get("n", 4))
    if v.get("mode") in ("bottom", "random"):
        controls[name] = (r, v)
        continue
    eq = daily_equity(r)
    g = eq.pct_change().dropna()
    orders = int(statistics(r).get("Total Orders", "0"))
    # each order trades one slice (1 / max_positions of equity) at linear_bps a side
    per_order = (1.0 / v["max_positions"]) * costs.linear_bps * 1e-4
    drag = orders * per_order / len(g)  # spread evenly: the only honest option without fills
    gross[name], net[name] = g, g - drag
    variants[name] = v
    meta[name] = {"orders": orders, "backtest_id": r["backtestId"], "cost_drag_ann": drag * 252, **{k: statistics(r).get(k) for k in ("Drawdown", "Compounding Annual Return")}}

G, N = pd.DataFrame(gross).dropna(), pd.DataFrame(net).dropna()
ppy = 252.0
sharpes = {n: st.annualised_sharpe(N[n], ppy) for n in N}
best = max(sharpes, key=sharpes.get)
print(f"{N.shape[1]} variants x {N.shape[0]} sessions; best {best} net Sharpe {sharpes[best]:.2f}")

# benchmark: QC equal-weight eligible universe, if downloaded
bench_files = sorted(glob.glob(str(root / "mirror" / "quantconnect" / "e5_benchmark" / "*.json")))
bench = None
if bench_files:
    b = daily_equity(load_result(bench_files[-1])).pct_change().dropna()
    exposure = float(np.clip((N[best] != 0).mean(), 0, 1))  # share of sessions with a move: a proxy for time invested
    rf = cash_benchmark(N.index, ppy, 0.02)
    bench = (exposure * b.reindex(N.index).fillna(0.0) + (1 - exposure) * rf).rename("exposure_matched")
    print(f"benchmark: equal-weight eligible universe scaled to exposure {exposure:.2f}")

out = {"hypothesis": HYP, "variants": variants, "meta": meta, "net_sharpe": sharpes}
nb = N[best]
t, p, lags = st.hac_tstat(nb)
out["gate2"] = {"gross_sharpe": st.annualised_sharpe(G[best], ppy), "net_sharpe": sharpes[best], "net_over_gross": float(N[best].mean() / G[best].mean()) if G[best].mean() else float("nan"), "cost_drag_ann": meta[best]["cost_drag_ann"], "sharpe_at_2x_costs": st.annualised_sharpe(G[best] - 2 * (G[best] - N[best]), ppy)}
out["gate3"] = {"hac_t": t, "p": p, "lags": lags, "psr": st.probabilistic_sharpe(nb)}
per_period = np.array([st.moments(N[n]).sharpe for n in N])
dsr, dsr_bench = st.deflated_sharpe(nb, n_trials=N.shape[1], trial_sharpes=per_period)
out["gate4"] = {"dsr": dsr, "n_trials": N.shape[1], "benchmark_per_period": dsr_bench}
res = cscv(N, n_blocks=16)
out["gate5"] = {**res.summary()}
if bench is not None:
    try:
        spa = superior_predictive_ability(N, bench, ppy, reps=500, seed=0)
        out["gate5"].update(spa.summary())
    except Exception as exc:  # noqa: BLE001
        out["gate5"]["spa_error"] = str(exc)
print(json.dumps({k: out[k] for k in ("gate2", "gate3", "gate4", "gate5")}, indent=1, default=str))

log = TrialLog(paths().ensure().trial_log)
if not args.no_log:
  rec = log.run(HYP, FAMILY_NAME, {"grid": "the pre-registered variants (see prereg)", "engine": "quantconnect-free", "backtests": [m["backtest_id"] for m in meta.values()]}, "qc_us_equities_eligible", metrics={"best": best, "net_sharpe": sharpes[best], "hac_t": t, "dsr": dsr, "pbo": res.pbo}, variants=N.shape[1])
  print("trial log seq", rec.seq)
for name, (r, v) in controls.items():
    eq = daily_equity(r); g = eq.pct_change().dropna()
    print(f"control {name}: ann {g.mean()*252:.3f} sharpe {st.annualised_sharpe(g, ppy):.2f} DD {statistics(r).get('Drawdown')}")
(root / "reports").mkdir(exist_ok=True)
(root / "reports" / f"{HYP}_external.json").write_text(json.dumps(out, indent=1, default=str))
N.to_parquet(root / "reports" / f"{HYP}_variant_returns.parquet")
