#!/usr/bin/env python3
"""The numbers for the carry-holding decision (`docs/34`): what the funding has paid, by year, against the T-bill.

A descriptive read of the lake's carry units (`raw/binance/carry-um`, daily bars; `perp_funding_rate` is the
day's funding as a fraction of notional, the sum of the day's settlements) and FRED's DTB3. No rule, no
signal, no backtest: a table of what an always-held short perp against spot collected, so the owner can put
the yield next to the T-bill and the exchange risk and decide. Disclosed in the trial log as a note.

    QR_ROOT=~/qr/lake python scripts/carry_decision_pack.py --date 2026-10-27
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
ROUND_TRIP_BPS = 21.5          # spot 7.5 a side (VIP 0 with BNB) + perp 3.23 a side (stage 1, measured), both legs, in and out
COL = "perp_funding_rate"


def load_funding(lake: Path, symbol: str) -> pd.Series:
    path = lake / "raw" / "binance" / "carry-um" / "klines" / "interval=1d" / f"symbol={symbol}" / "data.parquet"
    df = pd.read_parquet(path).set_index("open_time").sort_index()
    return df[COL].dropna()


def tbill_by_year(lake: Path) -> pd.Series:
    rf = pd.read_parquet(lake / "reference" / "risk_free_dtb3.parquet")
    years = pd.to_datetime(rf["date"]).dt.year
    return rf.groupby(years)["rate"].mean()


def yearly_table(funding: dict[str, pd.Series], tbill: pd.Series) -> pd.DataFrame:
    rows = {}
    for sym, s in funding.items():
        g = s.groupby(s.index.year).agg(["sum", "count"])
        rows[sym] = 100 * g["sum"] * 365 / g["count"]
    tab = pd.DataFrame(rows)
    tab["T-bill"] = 100 * tbill.reindex(tab.index)
    for sym in funding:
        tab[f"{sym} − T-bill"] = tab[sym] - tab["T-bill"]
    return tab.round(1)


def symbol_stats(s: pd.Series) -> dict:
    monthly = s.resample("ME").sum()
    r90 = s.rolling(90).sum()
    return {
        "from": str(s.index.min().date()), "to": str(s.index.max().date()), "days": int(len(s)),
        "months": int(len(monthly)), "negative_months": int((monthly < 0).sum()), "share_days_funding_le_0": round(float((s <= 0).mean()), 3),
        "median_annualised_pct": round(float(100 * s.median() * 365), 1),
        "worst_90d_pct": round(float(100 * r90.min()), 2), "worst_90d_ends": str(r90.idxmin().date()),
        "best_90d_pct": round(float(100 * r90.max()), 2),
        "last_365d_pct": round(float(100 * s.iloc[-365:].sum() * 365 / min(365, len(s))), 1),
    }


def capital_views(gross_pct: float) -> dict:
    """What a gross funding yield becomes on the capital that has to be parked: at 1× both legs hold the full
    notional (spot in coin, perp margin in USDT earning nothing); at 2.5× the perp leg needs 40% of it."""
    net = gross_pct - ROUND_TRIP_BPS / 100
    return {"gross_pct": round(gross_pct, 2), "net_of_one_round_trip_pct": round(net, 2),
            "on_capital_at_1x_pct": round(net / 2, 2), "on_capital_at_2_5x_pct": round(net / 1.4, 2)}


def build(lake: Path) -> dict:
    funding = {sym: load_funding(lake, sym) for sym in SYMBOLS}
    tab = yearly_table(funding, tbill_by_year(lake))
    stats = {sym: symbol_stats(s) for sym, s in funding.items()}
    views = {sym: capital_views(stats[sym]["last_365d_pct"]) for sym in SYMBOLS}
    return {"yearly": tab, "stats": stats, "last_365d_on_capital": views, "round_trip_bps": ROUND_TRIP_BPS}


def render(out: dict, date: str) -> str:
    tab = out["yearly"]
    lines = [f"# Carry holding — what the funding paid, by year, against the T-bill ({date})", "",
             "Annualised funding collected by a short USDⓈ-M perp held every day of the year (sum of the day's settlements,",
             "fraction of notional), from the lake's carry units; the T-bill is the year's mean DTB3. Gross of costs and",
             "of basis; a descriptive read, no rule. Percent a year.", "",
             "| year | " + " | ".join(tab.columns) + " |", "|---|" + "---|" * len(tab.columns)]
    for yr, r in tab.iterrows():
        lines.append(f"| {yr} | " + " | ".join("" if pd.isna(v) else f"{v:.1f}" for v in r) + " |")
    lines += ["", "## Per symbol", "", "| symbol | from | months | negative months | days with funding ≤ 0 | median annualised | worst 90 days (ends) | best 90 days | last 365 days |",
              "|---|---|---|---|---|---|---|---|---|"]
    for sym, s in out["stats"].items():
        lines.append(f"| {sym} | {s['from']} | {s['months']} | {s['negative_months']} | {100*s['share_days_funding_le_0']:.0f}% | {s['median_annualised_pct']}% | "
                     f"{s['worst_90d_pct']}% ({s['worst_90d_ends']}) | {s['best_90d_pct']}% | {s['last_365d_pct']}% |")
    lines += ["", f"## The last 365 days on the capital it ties up (round trip {out['round_trip_bps']} bps, both legs in and out)", "",
              "| symbol | gross | net of one round trip | on capital at 1× | on capital at 2.5× |", "|---|---|---|---|---|"]
    for sym, v in out["last_365d_on_capital"].items():
        lines.append(f"| {sym} | {v['gross_pct']}% | {v['net_of_one_round_trip_pct']}% | {v['on_capital_at_1x_pct']}% | {v['on_capital_at_2_5x_pct']}% |")
    lines += ["", "At 1× the perp margin is the full notional in USDT earning nothing, so the yield on the money parked is half the",
              "funding; at 2.5× (the rehearsal's setting) the perp leg needs 40% of its notional and a basis spike can liquidate it.",
              "The exchange is the counterparty for the whole holding either way (`docs/31` §13 B for the stress tiers)."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", type=Path, default=Path(os.environ.get("QR_ROOT", Path.home() / "qr" / "lake")))
    ap.add_argument("--date", default=str(pd.Timestamp.now("UTC").date()))
    ap.add_argument("--out", type=Path, default=Path("reports") / "carry")
    a = ap.parse_args(argv)
    out = build(a.lake)
    a.out.mkdir(parents=True, exist_ok=True)
    md = render(out, a.date)
    (a.out / f"funding_history_{a.date}.md").write_text(md)
    payload = {"date": a.date, "yearly": {str(k): {c: (None if pd.isna(v) else float(v)) for c, v in r.items()} for k, r in out["yearly"].iterrows()},
               "stats": out["stats"], "last_365d_on_capital": out["last_365d_on_capital"], "round_trip_bps": out["round_trip_bps"]}
    (a.out / f"funding_history_{a.date}.json").write_text(json.dumps(payload, indent=1))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
