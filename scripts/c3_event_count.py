#!/usr/bin/env python3
"""Count C3's liquidation-burst events under the frozen definition (`qr/research/liq_events.py`); touches no price.

    QR_ROOT=~/qr/lake python scripts/c3_event_count.py
"""
from __future__ import annotations

import json
import sys

from qr.config import paths
from qr.research.liq_events import events


def main() -> int:
    p = paths().ensure()
    ev, liq = events(p.root / "mirror")
    for venue, g in liq.groupby("venue"):
        print(f"{venue}: {len(g):,} liquidations on the twenty names since the tape start, ${g.usd.sum()/1e6:,.0f}M")
    names = ev[~ev.control]
    first, last = liq.t.min(), liq.t.max()
    days = (last - first).total_seconds() / 86400
    print(f"\nwindow {first:%Y-%m-%d %H:%M} → {last:%Y-%m-%d %H:%M} UTC ({days:.1f} days)")
    print(f"merged events on the eighteen names: {len(names)}  ({len(names)/days:.1f} a day)   control BTC/ETH: {int(ev.control.sum())}")
    print(f"minimum for the study: 300 → {'REACHED' if len(names) >= 300 else 'not yet'}")
    print("by name:", names.groupby("base").size().sort_values(ascending=False).to_dict())
    print("by direction:", names.groupby("dir").size().to_dict(), " median burst $%.0fk, median z %.1f" % (names.usd.median() / 1e3, names.z.median()))
    (p.root / "reports").mkdir(exist_ok=True)
    (p.root / "reports" / "c3_event_count.json").write_text(json.dumps({"window": [str(first), str(last)], "events_18": int(len(names)), "events_control": int(ev.control.sum()), "by_name": names.groupby("base").size().to_dict(), "per_day": len(names) / days}, indent=1, default=str))
    ev.to_parquet(p.root / "reports" / "c3_events.parquet", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
