#!/usr/bin/env python3
"""Per-variant reading of `p4_cot_crowding_v1` and its control sweeps, from the saved returns only.

Reads each sweep's `<lake>/reports/<hypothesis>_variant_returns.parquet` (the per-variant net return matrix
`qr gates` writes beside its report) and gives, per variant, what the memo's own falsifier asks: the net yield
over the sample against the holding with no rule, the share of days in the unit, the net Sharpe, and the
yield by calendar year (the walk-forward the memo names). Nothing is re-run and nothing is written to the
trial log: a sensitivity read of counted runs.

    QR_ROOT=~/qr/lake python scripts/p4_cot_rule_table.py --date 2026-10-27
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SWEEPS = (
    ("p4_cot_crowding_v1", "the timer: out while crowded"),
    ("p4_cot_crowding_v1_always_in", "the holding, no rule"),
    ("p4_cot_crowding_v1_mirror", "mirror: in only while crowded"),
    ("p4_cot_crowding_v1_placebo", "placebo: the crowded flags in permuted 13-week blocks"),
    ("p4_cot_crowding_v1_eth", "the ETH arm"),
)
PPY = 365.0


def variant_stats(net: pd.Series) -> dict:
    """Total and annualised net return, net Sharpe, share of days in the unit, net by calendar year."""
    s = net.astype(float)
    years = s.groupby(s.index.year).sum() * 100.0
    sd = s.std()
    return {
        "total_net_pct": round(float(s.sum() * 100.0), 2),
        "ann_net_pct": round(float(s.mean() * PPY * 100.0), 2),
        "net_sharpe": round(float(s.mean() / sd * np.sqrt(PPY)), 2) if sd > 0 else np.nan,
        "days_in_share": round(float((s != 0).mean()), 3),
        "worst_year_pct": round(float(years.min()), 2),
        "best_year_pct": round(float(years.max()), 2),
        "years": {str(y): round(float(v), 2) for y, v in years.items()},
    }


def sweep_table(returns: pd.DataFrame, reference: pd.Series | None = None) -> pd.DataFrame:
    rows = []
    for col in returns.columns:
        st = variant_stats(returns[col])
        row = {"variant": col.replace("carry_crowding_timer_", ""), **{k: v for k, v in st.items() if k != "years"}}
        if reference is not None:
            ref = variant_stats(reference)
            row["vs_holding_ann_pct"] = round(st["ann_net_pct"] - ref["ann_net_pct"], 2)
            row["years_ahead_of_holding"] = int(sum(st["years"][y] > ref["years"].get(y, np.nan) for y in st["years"]))
        row["years"] = " ".join(f"{y}:{v:+.1f}" for y, v in st["years"].items())
        rows.append(row)
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", type=Path, default=Path(os.environ.get("QR_ROOT", Path.home() / "qr" / "lake")))
    ap.add_argument("--date", default=str(pd.Timestamp.now("UTC").date()))
    ap.add_argument("--out", type=Path, default=Path("reports") / "p4")
    a = ap.parse_args(argv)
    ref_path = a.lake / "reports" / "p4_cot_crowding_v1_always_in_variant_returns.parquet"
    reference = None
    if ref_path.exists():
        r = pd.read_parquet(ref_path)
        r.index = pd.to_datetime(r.index, utc=True)
        reference = r.iloc[:, 0]
    lines = [f"# `p4_cot_crowding_v1` — per-variant reading of the counted runs ({a.date})", "",
             "In-sample 2020-01-01 → 2024-12-31 on the BTCUSDT carry unit at the memo's cost (21.5 bps a round trip), from the saved",
             "per-variant net returns; no re-run. `ann_net_pct` is the mean daily net return annualised; `vs_holding_ann_pct` the same",
             "less the always-in holding's; `days_in_share` the share of days the unit was held; the years are net percent each.", ""]
    payload = {}
    for hyp, label in SWEEPS:
        path = a.lake / "reports" / f"{hyp}_variant_returns.parquet"
        if not path.exists():
            lines += [f"## `{hyp}` — {label}", "", f"_no saved returns at {path}_", ""]
            continue
        r = pd.read_parquet(path)
        r.index = pd.to_datetime(r.index, utc=True)
        tab = sweep_table(r, None if hyp.endswith("_eth") else reference)
        payload[hyp] = tab.to_dict(orient="records")
        lines += [f"## `{hyp}` — {label}", "", "| " + " | ".join(tab.columns) + " |", "|" + "---|" * len(tab.columns)]
        for _, row in tab.iterrows():
            lines.append("| " + " | ".join("" if (isinstance(v, float) and pd.isna(v)) else (f"{v:g}" if isinstance(v, float) else str(v)) for v in row) + " |")
        lines.append("")
    a.out.mkdir(parents=True, exist_ok=True)
    md = "\n".join(lines) + "\n"
    (a.out / f"p4_cot_crowding_v1_rules_{a.date}.md").write_text(md)
    (a.out / f"p4_cot_crowding_v1_rules_{a.date}.json").write_text(json.dumps(payload, indent=1, default=str))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
