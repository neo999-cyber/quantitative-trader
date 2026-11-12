#!/usr/bin/env python3
"""The comparisons between the rule and its controls that `docs/prereg/p6_breakout_crypto_v1.md` registers.

It runs nothing and reads no price: only the per-variant daily net returns `qr gates` wrote for the five sweeps
(`<lake>/reports/<id>_variant_returns.parquet`). For each sweep it names the **median variant** (rank ⌈n/2⌉ by net
Sharpe, so no side of a comparison is a best-of-n). For the rule against a control it scales the control's median
variant to the rule's volatility — the books are invested to different degrees (by the count, the rule 9–16% of the
time-average book, the leaders control 39%, the placebo 7–12%), and a raw difference would mostly measure exposure —
and gives the annualised mean of the daily difference, its Newey–West t (30 lags) and the two Sharpe ratios.

    QR_ROOT=~/qr/lake python scripts/p6_breakout_compare.py           # after the five registered sweeps have run
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

HYP = "p6_breakout_crypto_v1"
SWEEPS = {"rule": HYP, "leaders": f"{HYP}_leaders", "placebo": f"{HYP}_placebo", "late": f"{HYP}_late", "nofilter": f"{HYP}_nofilter"}
PERIODS, LAGS, T_BAR = 365, 30, 2.0


def sharpe(r: pd.Series) -> float:
    r = r.dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * math.sqrt(PERIODS)) if sd > 0 else float("nan")


def median_variant(frame: pd.DataFrame) -> str:
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
    sr, sc = both["rule"].std(ddof=1), both["control"].std(ddof=1)
    scaled = both["control"] * (sr / sc) if sc > 0 else both["control"] * np.nan
    d = both["rule"] - scaled
    return {"bars": len(d), "scale": float(sr / sc) if sc > 0 else float("nan"), "mean_diff_pct_yr": float(d.mean() * PERIODS * 100),
            "t": newey_west_t(d), "sharpe_rule": sharpe(both["rule"]), "sharpe_control": sharpe(both["control"])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--ids", default=None, help="rehearsals only: rule=<id>,leaders=<id>,... to read other hypothesis ids")
    a = ap.parse_args(argv)
    ids = dict(SWEEPS)
    if a.ids:
        ids.update(dict(kv.split("=", 1) for kv in a.ids.split(",")))
    reports = paths(a.root).root / "reports"
    frames, missing = {}, []
    for key, hid in ids.items():
        f = reports / f"{hid}_variant_returns.parquet"
        if f.exists():
            frames[key] = pd.read_parquet(f)
        else:
            missing.append(hid)
    lines = [f"# `{HYP}` — the rule against its controls, {date.today().isoformat()} (reads the sweeps' returns; runs nothing)", ""]
    if missing:
        lines += [f"Missing sweeps: {', '.join(missing)}.", ""]
    med = {}
    for key, fr in frames.items():
        med[key] = median_variant(fr)
        lines += [f"- `{ids[key]}`: {fr.shape[1]} variant(s); median variant `{med[key]}`, net Sharpe {sharpe(fr[med[key]]):.2f}"]
    lines += [""]
    if "rule" in frames:
        r = frames["rule"][med["rule"]]
        lines += ["| condition | control | bars | control scaled by | rule − control, % a year | Newey–West t | Sharpe rule | Sharpe control | met |", "|---|---|---|---|---|---|---|---|---|"]
        for cond, key, test in (("(2) the setup adds to owning leaders", "leaders", lambda c: c["t"] >= T_BAR),
                                ("(3) the day matters, not the name alone", "placebo", lambda c: c["t"] >= T_BAR),
                                ("(4) the breakout day is not worse than the next", "late", lambda c: c["mean_diff_pct_yr"] >= 0),
                                ("(reported) the market filter", "nofilter", None)):
            if key not in frames:
                continue
            c = compare(r, frames[key][med[key]])
            met = "—" if test is None else ("yes" if test(c) else "**no**")
            lines += [f"| {cond} | `{ids[key]}` | {c['bars']} | {c['scale']:.2f} | {c['mean_diff_pct_yr']:+.1f} | {c['t']:.2f} | {c['sharpe_rule']:.2f} | {c['sharpe_control']:.2f} | {met} |"]
    text = "\n".join(lines) + "\n"
    print(text)
    out = paths(a.root).root / "reports" / f"{HYP}_compare_{date.today().isoformat()}.md"
    out.write_text(text)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
