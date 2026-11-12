#!/usr/bin/env python3
"""The comparisons between the rule and its controls that `docs/prereg/p6_trend_reset_v1.md` registers ("What a pass is").

It runs nothing and reads no price: only the per-variant daily net returns `qr gates` wrote for the six sweeps
(`<lake>/reports/<id>_variant_returns.parquet`). For each sweep it lists every variant's net Sharpe and names the
**median variant** — rank ⌈n/2⌉ by net Sharpe — so that no side of a comparison is a best-of-n (the rehearsal on
drifting noise showed a best-of-eight 0.44 of Sharpe above a one-variant control). For the rule against a control
it gives the annualised mean of the daily difference in net return between the two median variants, its Newey–West
t (21 lags) and the difference in Sharpe.

    QR_ROOT=~/qr/lake python scripts/p6_trend_compare.py            # after the six registered sweeps have run
"""
from __future__ import annotations

import argparse
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qr.config import paths  # noqa: E402

HYP = "p6_trend_reset_v1"
SWEEPS = {"rule": HYP, "trend": f"{HYP}_trend", "mirror": f"{HYP}_mirror", "placebo": f"{HYP}_placebo", "etf": f"{HYP}_etf", "etf_trend": f"{HYP}_etf_trend"}
PERIODS, LAGS, T_BAR = 252, 21, 2.0


def sharpe(r: pd.Series) -> float:
    r = r.dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * math.sqrt(PERIODS)) if sd > 0 else float("nan")


def median_variant(frame: pd.DataFrame) -> str:
    """The variant at rank ⌈n/2⌉ by net Sharpe (the single one when there is one)."""
    ranked = sorted(frame.columns, key=lambda c: (-sharpe(frame[c]), c))
    return ranked[math.ceil(len(ranked) / 2) - 1]


def newey_west_t(d: pd.Series, lags: int = LAGS) -> float:
    x = d.dropna().to_numpy(dtype=float)
    n = len(x)
    if n < lags + 2:
        return float("nan")
    e = x - x.mean()
    var = float(e @ e) / n
    for k in range(1, lags + 1):
        var += 2.0 * (1.0 - k / (lags + 1.0)) * float(e[k:] @ e[:-k]) / n
    return float(x.mean() / math.sqrt(var / n)) if var > 0 else float("nan")


def compare(rule: pd.Series, control: pd.Series) -> dict:
    both = pd.concat([rule, control], axis=1, keys=["rule", "control"]).dropna()
    d = both["rule"] - both["control"]
    return {"bars": len(d), "mean_diff_pct_yr": float(d.mean() * PERIODS * 100), "t": newey_west_t(d),
            "sharpe_rule": sharpe(both["rule"]), "sharpe_control": sharpe(both["control"]), "sharpe_diff": sharpe(both["rule"]) - sharpe(both["control"])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="lake root (default $QR_ROOT)")
    ap.add_argument("--ids", default=None, help="rehearsals only: rule=<id>,trend=<id>,... to read other hypothesis ids")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    ids = dict(SWEEPS)
    if a.ids:
        ids.update(dict(pair.split("=", 1) for pair in a.ids.split(",")))
    reports = paths(a.root).root / "reports"
    frames, missing = {}, []
    for key, hyp in ids.items():
        f = reports / f"{hyp}_variant_returns.parquet"
        if f.exists():
            frames[key] = pd.read_parquet(f)
        else:
            missing.append(hyp)
    lines = [f"# `{HYP}` — the rule against its controls, {date.today().isoformat()} (reads the sweeps' returns; runs nothing)", ""]
    if missing:
        lines += [f"Not found, so not compared: {', '.join(f'`{m}`' for m in missing)}.", ""]
    med = {}
    lines += ["| sweep | id | variants | net Sharpe, each | the median variant |", "|---|---|---|---|---|"]
    for key, frame in frames.items():
        med[key] = median_variant(frame)
        each = ", ".join(f"{sharpe(frame[c]):.2f}" for c in sorted(frame.columns, key=lambda c: -sharpe(frame[c])))
        lines += [f"| {key} | `{ids[key]}` | {frame.shape[1]} | {each} | `{med[key]}` ({sharpe(frame[med[key]]):.2f}) |"]
    lines += ["", "| the rule against | bars | mean difference, points a year | Newey–West t | Sharpe, rule − control | the memo's bar | met |", "|---|---|---|---|---|---|---|"]
    verdicts = {}
    for label, rule_key, control_key, bar in (("its trend filter alone", "rule", "trend", "t"), ("its placebo", "rule", "placebo", "t"), ("its mirror", "rule", "mirror", "sign"),
                                              ("ETF arm: its trend filter alone", "etf", "etf_trend", "report")):
        if rule_key not in frames or control_key not in frames:
            continue
        c = compare(frames[rule_key][med[rule_key]], frames[control_key][med[control_key]])
        if bar == "t":
            met, text = c["t"] >= T_BAR, f"t ≥ {T_BAR:.0f}"
        elif bar == "sign":
            met, text = c["mean_diff_pct_yr"] >= 0, "difference ≥ 0"
        else:
            met, text = None, "reported"
        verdicts[control_key] = met
        lines += [f"| {label} | {c['bars']} | {c['mean_diff_pct_yr']:+.1f} | {c['t']:+.2f} | {c['sharpe_rule']:.2f} − {c['sharpe_control']:.2f} = {c['sharpe_diff']:+.2f} | {text} | "
                  f"{'—' if met is None else 'yes' if met else '**no**'} |"]
    core = [verdicts.get(k) for k in ("trend", "placebo", "mirror")]
    if all(v is not None for v in core):
        lines += ["", f"Conditions (2)–(4) of the memo: **{'all met' if all(core) else 'not met'}**. Condition (1) is the candidate's own gate report; (5) is the ETF arm's."]
    text = "\n".join(lines) + "\n"
    print(text)
    if not a.no_write:
        out = Path(__file__).resolve().parents[1] / "reports" / "p6" / f"p6_compare_{date.today().isoformat()}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
