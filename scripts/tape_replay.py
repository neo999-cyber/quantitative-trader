"""Maker-fill study stage 0: replay every recorded day per venue and write the report.

    .venv/bin/python scripts/tape_replay.py --tape ~/qr/lake/mirror/tape --out ~/qr/lake/reports/maker_stage0

Writes `<out>/<venue>_<day>_orders.parquet` (every virtual order), then
`<out>/stage0_summary.md` with, per venue: fill probability at 1/5/15
minutes overall, by symbol and side, by UTC hour; the median and mean
adverse-selection mark on fills; wait-time quantiles; and the registered
rule read against them (`docs/24`: ≥ 70% at 15 minutes for the units C2
would hold, median mark < 2 bps). Reads nothing but the tape; writes no
trial-log record — this is a measurement of execution, not a backtest.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from qr.execution.tape import merge_streams, read_tape, replay, summarise


def replay_day(tape: Path, venue: str, day: str, slot_s: int, ttl_s: int) -> pd.DataFrame:
    book = read_tape(tape / venue / "book" / f"{day}.jsonl.gz")
    trades = read_tape(tape / venue / "trade" / f"{day}.jsonl.gz")
    orders = replay(merge_streams(book, trades), slot_s=slot_s, ttl_s=ttl_s)
    orders.insert(0, "venue", venue)
    orders.insert(1, "day", day)
    return orders


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tape", default="~/qr/lake/mirror/tape")
    ap.add_argument("--out", default="~/qr/lake/reports/maker_stage0")
    ap.add_argument("--venues", nargs="*", default=["binance", "bybit"])
    ap.add_argument("--slot", type=int, default=900, help="seconds between virtual order pairs")
    ap.add_argument("--ttl", type=int, default=900, help="seconds a virtual order rests before cancel")
    ap.add_argument("--redo", action="store_true", help="replay days that already have a parquet")
    args = ap.parse_args()
    tape, out = Path(args.tape).expanduser(), Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    frames = []
    for venue in args.venues:
        days = sorted(p.stem for p in (tape / venue / "book").glob("*.jsonl.gz")) if (tape / venue / "book").exists() else []
        for day in days:
            target = out / f"{venue}_{day}_orders.parquet"
            if target.exists() and not args.redo:
                frames.append(pd.read_parquet(target))
                continue
            orders = replay_day(tape, venue, day, args.slot, args.ttl)
            orders.to_parquet(target, index=False)
            frames.append(orders)
            print(f"{venue} {day}: {len(orders)} virtual orders, {orders['filled'].mean():.1%} filled within {args.ttl}s")
    if not frames:
        print("no tape found under", tape)
        return 2
    all_orders = pd.concat(frames, ignore_index=True)

    lines = ["# Maker-fill study — stage 0 replay", "",
             f"Tape: `{tape}`; slot {args.slot}s, TTL {args.ttl}s, mark 60s after the fill. "
             f"{len(all_orders)} virtual orders over {all_orders['day'].nunique()} day(s). "
             "Queue model: behind the whole displayed size at placement, consumed by prints only (a floor).", ""]
    for venue, group in all_orders.groupby("venue"):
        s = summarise(group)
        lines += [f"## {venue}", "",
                  f"Orders {s['orders']}; fill probability at 60/300/900 s: "
                  + " / ".join(f"{s['overall'][f'fill_{h}s']:.1%}" for h in (60, 300, 900)) + ".",
                  f"Adverse-selection mark on fills: median **{s['median_mark_bps']:.2f} bps**, mean {s['mean_mark_bps']:.2f} bps.",
                  "Wait to fill (s), quantiles 25/50/75/90: " + " / ".join(f"{v:.0f}" for v in s["wait_quantiles_s"].to_numpy()) + ".",
                  "", "### By symbol and side", "", "```", s["by_symbol"].round(3).to_string(), "```",
                  "", "### By UTC hour", "", "```", s["by_hour"].round(3).to_string(), "```", ""]
        rule_fill = s["overall"]["fill_900s"] >= 0.70
        rule_mark = s["median_mark_bps"] < 2.0
        lines += [f"**Registered rule (docs/24):** 15-minute fill ≥ 70% → {'met' if rule_fill else 'not met'} "
                  f"({s['overall']['fill_900s']:.1%}); median mark < 2 bps → {'met' if rule_mark else 'not met'} "
                  f"({s['median_mark_bps']:.2f}). Read on the full 14-day tape on or after 1 October; "
                  "a partial tape is a preview, not the decision.", ""]
    (out / "stage0_summary.md").write_text("\n".join(lines))
    print("\n".join(lines[:12]))
    print(f"\nwrote {out / 'stage0_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
