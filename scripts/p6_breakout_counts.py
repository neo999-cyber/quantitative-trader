#!/usr/bin/env python3
"""Counts only, before registration, for `p6_breakout_crypto_v1` (`docs/prereg/p6_breakout_crypto_v1.md`).

Loads the Binance spot panel and the ranked universe exactly as `qr gates` does for the registered invocation, and
prints for every variant of the rule and of each control how many positions it opens in-sample, on how many names,
and the mean share of the book invested. **No return is computed and no position is valued against a benchmark.**

    QR_ROOT=~/qr/lake python scripts/p6_breakout_counts.py      # prints, and writes reports/p6/p6_breakout_counts_<date>.md
"""
from __future__ import annotations

import argparse
import itertools
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qr import cli  # noqa: E402
from qr.strategies.breakout import MomentumBreakout  # noqa: E402

START, END, N = "2018-01-01", "2025-04-30", 100
GRID = list(itertools.product((5, 10), (2.0, 2.5), (10, 20)))
MINIMUM = 60


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    a = ap.parse_args(argv)
    args = cli.build_parser().parse_args((["--root", a.root] if a.root else []) + [
        "gates", "--family", "momentum_breakout", "--market", "spot", "--n", str(N), "--start", START, "--end", END])
    lake = cli._lake(args)
    panel = cli._load_panel(lake, "1d", START, END, source="binance", market="spot")
    spec = cli._universe_spec(args, "spot")
    universe = cli._universe_for(panel, spec, None)
    panel, universe = cli._restrict_to_universe(panel, universe)
    rows = []
    for control in ("none", "leaders", "placebo", "late", "nofilter"):
        grid = [(5, 2.0, t) for t in (10, 20)] if control == "leaders" else GRID
        for base, tight, trail in grid:
            w, opened = MomentumBreakout(base=base, tight=tight, trail=trail, control=control).positions(panel, universe)
            per = opened.sum()
            invested = w.sum(axis=1)
            rows.append({"control": control, "base": base, "tight": tight, "trail": trail, "opened": int(per.sum()),
                         "names": int((per > 0).sum()), "invested": float(invested.mean()),
                         "days_any": float((invested > 0).mean()), "ok": "yes" if per.sum() >= MINIMUM else "below"})
    t = pd.DataFrame(rows)
    members = universe.sum(axis=1)
    lines = [f"# `p6_breakout_crypto_v1` — counts only, {date.today().isoformat()} (no return computed, nothing registered by this file)", "",
             f"Binance spot, universe `{spec.name}` (top {N} by 30-day quote volume, 15% volatility floor, pegs and leveraged tokens out), "
             f"in-sample {START} → {END}: {len(panel)} bars, {panel.close.shape[1]} names ever admitted, {members.median():.0f} members on the median bar "
             f"({members.min():.0f} at the least). Minimum {MINIMUM} positions a variant.", "",
             "| control | base | tight | trail | positions opened | names | mean share invested | bars with a position | against the minimum |",
             "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {r.control} | {r.base} | {r.tight} | {r.trail} | {r.opened} | {r.names} | {r.invested:.1%} | {r.days_any:.1%} | {r.ok} |" for r in t.itertuples()]
    text = "\n".join(lines) + "\n"
    print(text)
    out = Path(__file__).resolve().parents[1] / "reports" / "p6" / f"p6_breakout_counts_{date.today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
