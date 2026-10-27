#!/usr/bin/env python3
"""Per-trade reading of `p4_etf_flow_pressure_v1` and its control sweeps, from the saved returns only.

Reads each sweep's `<lake>/reports/<hypothesis>_variant_returns.parquet` (the per-variant net return matrix
`qr gates` writes beside its report) and the instrument's `etf_flow_z_*` column, and sums each variant's net
return over the bars after every entry it took. Nothing is re-run through the engine and nothing is written
to the trial log: a sensitivity read of a counted run. The placebo's entries are its own — the flows permuted
within each month with the family's seed — so its trades are counted on the days it actually traded.

    QR_ROOT=~/qr/lake python scripts/p4_etf_trade_table.py --date 2026-10-27
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qr.data.etfflow import MARKET  # noqa: E402
from qr.strategies.etfflow import HOLD_BARS, PLACEBO_SEED, shuffle_within_month  # noqa: E402

SWEEPS = (
    ("p4_etf_flow_pressure_v1", "the family (T + 2)"),
    ("p4_etf_flow_pressure_v1_t1", "the diagnostic arm (T + 1)"),
    ("p4_etf_flow_pressure_v1_mirror", "mirror (sides reversed)"),
    ("p4_etf_flow_pressure_v1_placebo", "placebo (flows permuted within month)"),
    ("p4_etf_flow_pressure_v1_always_long", "base rate (long every eligible session)"),
)


def parse_variant(name: str) -> dict:
    """`etf_flow_pressure_controlnone_gross1_hold24h_k1p5_timingt2` -> its parameters.

    Matched on the known tokens rather than split on underscores: `always_long` carries one of its own.
    """
    out = {}
    for key, pattern in (("control", r"control(none|mirror|placebo|always_long)"), ("hold", r"hold(session|24h)"), ("timing", r"timing(t[12])")):
        m = re.search(pattern, name)
        if m:
            out[key] = m.group(1)
    m = re.search(r"_k(\d+(?:p\d+)?)(?:_|$)", name)
    if m:
        out["k"] = float(m.group(1).replace("p", "."))
    return out


def per_trade(net: np.ndarray, decisions: np.ndarray, n: int) -> np.ndarray:
    """Each entry's net return: the sum of the `n` bars after its decision bar (an entry cut by the sample's end is dropped)."""
    return np.array([net[i + 1:i + 1 + n].sum() for i in decisions if i + 1 + n <= len(net)])


def sweep_table(returns: pd.DataFrame, z_by_timing: dict[str, pd.Series], periods_per_year: float) -> pd.DataFrame:
    rows = []
    for col in returns.columns:
        p = parse_variant(col)
        z = z_by_timing[p["timing"]].reindex(returns.index)
        if p.get("control") == "placebo":
            z = shuffle_within_month(z.to_frame("x"), PLACEBO_SEED)["x"]
        if p.get("control") == "always_long":
            decisions = np.flatnonzero(z.notna().to_numpy())
            sides = np.ones(len(decisions))
        else:
            decisions = np.flatnonzero((z.abs() >= p["k"]).to_numpy())
            sides = np.sign(z.to_numpy()[decisions])
            if p.get("control") == "mirror":
                sides = -sides
        net = returns[col].to_numpy(dtype=float)
        trades = per_trade(net, decisions, HOLD_BARS[p["hold"]])
        sd = trades.std(ddof=1) if len(trades) > 1 else np.nan
        rows.append({
            "variant": col.replace("etf_flow_pressure_", ""), "k": p.get("k"), "hold": p["hold"],
            "entries": int(len(trades)), "long": int((sides > 0).sum()), "short": int((sides < 0).sum()),
            "mean_net_bps": round(float(trades.mean() * 1e4), 2) if len(trades) else np.nan,
            "t_per_trade": round(float(trades.mean() / sd * np.sqrt(len(trades))), 2) if sd and sd > 0 else np.nan,
            "hit_rate": round(float((trades > 0).mean()), 3) if len(trades) else np.nan,
            "total_net_pct": round(float(net.sum() * 100), 2),
            "net_sharpe": round(float(returns[col].mean() / returns[col].std() * np.sqrt(periods_per_year)), 2) if returns[col].std() > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", type=Path, default=Path(os.environ.get("QR_ROOT", Path.home() / "qr" / "lake")))
    ap.add_argument("--start", default="2024-01-11")
    ap.add_argument("--end", default="2026-06-30")
    ap.add_argument("--date", default=str(pd.Timestamp.now("UTC").date()))
    ap.add_argument("--out", type=Path, default=Path("reports") / "p4")
    a = ap.parse_args(argv)
    from qr.config import paths
    from qr.data.lake import Lake

    panel = Lake(paths(a.lake)).load_panel(interval="1h", start=a.start, end=a.end, market=MARKET)
    z_by_timing = {t: panel[f"etf_flow_z_{t}"].iloc[:, 0] for t in ("t2", "t1")}
    ppy = panel.periods_per_year
    lines = [f"# `p4_etf_flow_pressure_v1` — per-trade reading of the counted runs ({a.date})", "",
             f"In-sample {a.start} → {a.end}, net of the weekday measured maker cost, from the saved per-variant returns; no re-run.",
             "`mean_net_bps` is the mean net return per entry over its hold; `t_per_trade` its t across entries; `net_sharpe` the", "hourly series annualised.", ""]
    payload = {}
    for hyp, label in SWEEPS:
        path = a.lake / "reports" / f"{hyp}_variant_returns.parquet"
        if not path.exists():
            lines += [f"## {hyp} — {label}", "", f"_no saved returns at {path}_", ""]
            continue
        r = pd.read_parquet(path)
        r.index = pd.to_datetime(r.index, utc=True)
        tab = sweep_table(r, z_by_timing, ppy)
        payload[hyp] = tab.to_dict(orient="records")
        lines += [f"## `{hyp}` — {label}", "", "| " + " | ".join(tab.columns) + " |", "|" + "---|" * len(tab.columns)]
        for _, row in tab.iterrows():
            lines.append("| " + " | ".join("" if pd.isna(v) else (f"{v:g}" if isinstance(v, float) else str(v)) for v in row) + " |")
        lines.append("")
    a.out.mkdir(parents=True, exist_ok=True)
    md = "\n".join(lines) + "\n"
    (a.out / f"p4_etf_flow_pressure_v1_trades_{a.date}.md").write_text(md)
    (a.out / f"p4_etf_flow_pressure_v1_trades_{a.date}.json").write_text(json.dumps(payload, indent=1, default=str))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
