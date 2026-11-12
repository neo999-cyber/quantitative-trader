#!/usr/bin/env python3
"""Counts only, before registration, for `p6_trend_reset_v1` (`docs/prereg/p6_trend_reset_v1.md`).

What it reads: the two trend instruments' prices and the rule's own inputs. What it prints: how many positions each
variant would open in the in-sample window, on how many names, and the share of the book they fill — and two checks
of the instrument (the closing print on dates whose close is public knowledge; the early-close list against where the
closing auction's volume actually sits). **No return is computed and no position is valued.**

    QR_ROOT=~/qr/lake python scripts/p6_trend_counts.py            # prints, and writes reports/p6/p6_counts_<date>.md
"""
from __future__ import annotations

import itertools
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qr.config import paths  # noqa: E402
from qr.data.auction import NASDAQ31  # noqa: E402
from qr.data.lake import Lake  # noqa: E402
from qr.data.trendbars import EARLY_CLOSES, ETF12, NY  # noqa: E402
from qr.data.universe import fixed_basket  # noqa: E402
from qr.strategies.trend import TrendReset  # noqa: E402

ARMS = {"nasdaq31": ("databento", "trend-xnas", NASDAQ31, "2019-07-01", "2025-08-31"),
        "etf12": ("tiingo", "trend-etf", ETF12, "2007-01-01", "2022-12-31")}
GRID = list(itertools.product((21, 63), (1.0, 1.5), (0.25, 0.5)))
MINIMUM = 60


def counts(lake: Lake, arm: str) -> pd.DataFrame:
    source, market, symbols, start, end = ARMS[arm]
    panel = lake.load_panel(list(symbols), "1d", start, end, source=source, market=market)
    universe = fixed_basket(panel, symbols)
    rows = []
    for control in ("none", "trend", "mirror", "placebo"):
        for roc, high, zero in GRID if control != "trend" else GRID[:1]:
            weights, opened = TrendReset(roc=roc, was_high=high, near_zero=zero, control=control).positions(panel, universe)
            per_name = opened.sum()
            rows.append({"arm": arm, "control": control, "roc": roc, "was_high": high, "near_zero": zero, "opened": int(per_name.sum()),
                         "names": int((per_name > 0).sum()), "exposure": round(float(weights.sum(axis=1).mean()), 3),
                         "bars": len(panel), "ok": "yes" if per_name.sum() >= MINIMUM else "below"})
    return pd.DataFrame(rows)


def instrument_checks(lake: Lake) -> list[str]:
    out = []
    aapl = lake.read_klines("AAPL", "1d", source="databento", market="trend-xnas")
    for day, known in (("2020-08-28", 499.23), ("2020-08-31", 129.04), ("2024-06-12", 213.07)):
        row = aapl.loc[pd.Timestamp(day, tz="UTC")]
        out.append(f"- AAPL {day}: closing print {row['close_unadjusted']:.2f} (the published close: {known}); adjusted {row['close']:.4f}")
    for symbol in ("AAPL", "MSFT"):
        m = lake.read_klines(symbol, "1m", source="databento", market="xnas")
        local = pd.DatetimeIndex(m.index).tz_convert(NY)
        minute = local.hour * 60 + local.minute
        day = pd.Series(local.tz_localize(None).normalize(), index=m.index)
        v13 = m["volume"][minute == 13 * 60].groupby(day[minute == 13 * 60]).first()
        v16 = m["volume"][minute == 16 * 60].groupby(day[minute == 16 * 60]).first()
        both = pd.concat([v13, v16], axis=1, keys=["v13", "v16"]).fillna(0.0)
        looks_early = set(both.index[both["v13"] > both["v16"]].date)
        listed = {d for d in EARLY_CLOSES if both.index[0].date() <= d <= both.index[-1].date()}
        out.append(f"- {symbol}: sessions whose 13:00 minute outweighs their 16:00 minute: {len(looks_early)}; early closes listed in the data's span: "
                   f"{len(listed)}; in one and not the other: {sorted(str(d) for d in looks_early ^ listed) or 'none'}")
    return out


def main() -> int:
    lake = Lake(paths(None))
    tables = {arm: counts(lake, arm) for arm in ARMS}
    lines = [f"# `p6_trend_reset_v1` — counts only, {date.today().isoformat()} (no return computed, nothing registered by this file)", ""]
    for arm, t in tables.items():
        _, market, symbols, start, end = ARMS[arm]
        lines += [f"## {arm}: market `{market}`, {len(symbols)} names, in-sample {start} → {end}, {int(t['bars'].iloc[0])} bars; minimum {MINIMUM} positions a variant", "",
                  "| control | roc | was_high | near_zero | positions opened | names | mean share of the book held | against the minimum |", "|---|---|---|---|---|---|---|---|"]
        lines += [f"| {r.control} | {r.roc} | {r.was_high} | {r.near_zero} | {r.opened} | {r.names} | {r.exposure:.1%} | {r.ok} |" for r in t.itertuples()]
        lines += [""]
    lines += ["## The instrument", ""] + instrument_checks(lake) + [""]
    text = "\n".join(lines)
    print(text)
    out = Path(__file__).resolve().parents[1] / "reports" / "p6" / f"p6_counts_{date.today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
