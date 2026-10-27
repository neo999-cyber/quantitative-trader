#!/usr/bin/env python3
"""The sort test of `p4_cot_crowding_v1`: the next four weeks' funding in crowded weeks against the rest.

For each released report (the week's row, usable from its availability stamp — `qr.data.cot.release_time`)
the BTC carry unit's funding over the following 28 days is summed and annualised, and the weeks are sorted
by whether the leveraged-fund net short's trailing percentile is at or above `p`. The registered statistic
is the difference of means on **non-overlapping** four-week blocks: every fourth report, starting from the
first (phase 0); the other three phases are reported beside it so a reader can see whether the phase chose
the answer. Welch's t. Six (window, p) cells, one counted run.

    QR_ROOT=~/qr/lake python scripts/p4_cot_sort.py --start 2020-01-01 --end 2024-12-31 --date 2026-10-27

`--dry-run` computes nothing against the funding and only prints the week counts; without it the read is a
counted run of the hypothesis in the trial log.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qr.data.cot import GRID_P, MARKET, TFF_MARKETS, WINDOWS, crowd_features, read_tff_zips  # noqa: E402

HYP = "p4_cot_crowding_v1"
DAYS = 28


def next_funding(funding: pd.Series, stamps: pd.DatetimeIndex, days: int = DAYS) -> np.ndarray:
    """Funding over the `days` bars from each stamp, annualised in percent; NaN where the bars run out."""
    f = funding.sort_index()
    out = np.full(len(stamps), np.nan)
    for i, a in enumerate(stamps):
        window = f[(f.index >= a) & (f.index < a + pd.Timedelta(days=days))]
        if len(window) >= days:
            out[i] = float(window.sum() * 365.0 / days * 100.0)
    return out


def welch_t(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    return float((a.mean() - b.mean()) / np.sqrt(va + vb)) if va + vb > 0 else float("nan")


def sort_table(weekly: pd.DataFrame, funding: pd.Series, start, end, windows=WINDOWS, grid_p=GRID_P, days: int = DAYS) -> pd.DataFrame:
    """One row per (window, p, phase): counts, means and the t of crowded minus the rest."""
    w = weekly[(weekly["available"] >= pd.Timestamp(start, tz="UTC")) & (weekly["available"] <= pd.Timestamp(end, tz="UTC"))].sort_values("available").reset_index(drop=True)
    w = w.assign(next_funding=next_funding(funding, pd.DatetimeIndex(w["available"]), days))
    rows = []
    for n in windows:
        for p in grid_p:
            for phase in range(4):
                part = w.iloc[phase::4]
                crowded = part[part[f"cot_pct_{n}"] >= p]["next_funding"].to_numpy()
                rest = part[part[f"cot_pct_{n}"] < p]["next_funding"].to_numpy()
                rows.append({
                    "window": n, "p": p, "phase": phase, "weeks": int(len(part)),
                    "crowded": int(np.isfinite(crowded).sum()), "rest": int(np.isfinite(rest).sum()),
                    "mean_crowded_pct": round(float(np.nanmean(crowded)), 2) if np.isfinite(crowded).any() else np.nan,
                    "mean_rest_pct": round(float(np.nanmean(rest)), 2) if np.isfinite(rest).any() else np.nan,
                    "diff_pct": round(float(np.nanmean(crowded) - np.nanmean(rest)), 2) if np.isfinite(crowded).any() and np.isfinite(rest).any() else np.nan,
                    "t": round(welch_t(crowded, rest), 2),
                })
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", type=Path, default=Path(os.environ.get("QR_ROOT", Path.home() / "qr" / "lake")))
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--date", default=str(pd.Timestamp.now("UTC").date()))
    ap.add_argument("--out", type=Path, default=Path("reports") / "p4")
    ap.add_argument("--hypothesis", default=HYP)
    ap.add_argument("--dry-run", action="store_true", dest="dry_run", help="week counts only; nothing read against the funding, nothing logged")
    a = ap.parse_args(argv)
    from qr.config import paths
    from qr.data.lake import Lake
    from qr.validate.trial_log import TrialLog

    p = paths(a.lake)
    lake = Lake(p)
    tff = read_tff_zips(p.root / "mirror" / "cftc")
    weekly = crowd_features(tff[tff["market"] == TFF_MARKETS[a.symbol]])
    inside = weekly[(weekly["available"] >= pd.Timestamp(a.start, tz="UTC")) & (weekly["available"] <= pd.Timestamp(a.end, tz="UTC"))]
    counts = {f"w{n}_p{q}": int((inside[f"cot_pct_{n}"] >= q).sum()) for n in WINDOWS for q in GRID_P}
    print(f"{len(inside)} reports released inside {a.start} → {a.end}; crowded weeks: {counts}")
    if a.dry_run:
        return 0
    funding = lake.read_klines(a.symbol, "1d", market=MARKET)["perp_funding_rate"]
    log = TrialLog(p.ensure().trial_log)
    rec = log.run(a.hypothesis, "cot_sort", {"windows": list(WINDOWS), "p": list(GRID_P), "days": DAYS, "window": [a.start, a.end], "engine": "scripts/p4_cot_sort.py"},
                  f"{MARKET} {a.symbol}", variants=len(WINDOWS) * len(GRID_P), manifest_hash=lake.manifest_hash())
    tab = sort_table(weekly, funding, a.start, a.end)
    a.out.mkdir(parents=True, exist_ok=True)
    lines = [f"# `{a.hypothesis}` — the sort: next-four-week funding, crowded weeks against the rest ({a.date})", "",
             f"{a.symbol} carry unit, reports released {a.start} → {a.end}; funding over the 28 days from each release, annualised, percent.",
             f"Phase 0 (every fourth report from the first) is the registered non-overlapping statistic; phases 1–3 are the same test",
             f"on the other offsets. Trial-log run seq {rec.seq}.", "",
             "| " + " | ".join(tab.columns) + " |", "|" + "---|" * len(tab.columns)]
    for _, r in tab.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else (f"{v:g}" if isinstance(v, float) else str(v)) for v in r) + " |")
    md = "\n".join(lines) + "\n"
    (a.out / f"p4_cot_sort_{a.date}.md").write_text(md)
    (a.out / f"p4_cot_sort_{a.date}.json").write_text(json.dumps({"seq": rec.seq, "counts": counts, "rows": tab.to_dict(orient="records")}, indent=1, default=str))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
