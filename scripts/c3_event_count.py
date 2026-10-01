#!/usr/bin/env python3
"""Count C3's liquidation-burst events under the frozen definition (`docs/prereg/p2_liquidation_fade_v1.md`, seq 799).

Reads only the mirrored OKX/Bybit recordings; touches no price. Per venue,
symbol and direction: 60-second bins of liquidation notional; a burst is a
bin ≥ $50,000 and ≥ 5 σ above the trailing 24-hour median of that
series' non-empty bins (past only, σ from the same trailing window);
consecutive qualifying bins are one event stamped at the end of the last
one; an event on both venues within 60 s is one event. Counted on the
tape's eighteen names (the twenty less BTC/ETH), from the tape's start.

    QR_ROOT=~/qr/lake python scripts/c3_event_count.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from qr.config import paths

TAPE_START = pd.Timestamp("2026-09-17 07:31", tz="UTC")
NAMES = ["SOL", "XRP", "HYPE", "ZEC", "DOGE", "ADA", "ENA", "BEAT", "NEAR", "LINK", "PEPE", "CL", "XAUT", "WLD", "SUI", "UNI", "ONDO", "BNB"]
CONTROL = ["BTC", "ETH"]
MIN_USD, Z_MIN, WINDOW_H = 50_000.0, 5.0, 24
OKX_INSTR = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"


def okx_ctval(mirror: Path) -> dict[str, float]:
    f = mirror / "liquidations" / "okx_instruments.json"
    if not f.exists():
        with urllib.request.urlopen(urllib.request.Request(OKX_INSTR, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
            f.write_text(r.read().decode())
    data = json.loads(f.read_text())["data"]
    return {d["instId"]: float(d["ctVal"]) for d in data}


def base(symbol: str, venue: str) -> str:
    s = symbol.replace("-USDT-SWAP", "").replace("USDT", "")
    for k in ("1000000", "100000", "10000", "1000"):
        if s.startswith(k) and len(s) > len(k):
            s = s[len(k):]
            break
    return s


def load(mirror: Path, venue: str, ctval: dict[str, float]) -> pd.DataFrame:
    rows = []
    for f in sorted((mirror / "liquidations" / venue).glob("*.jsonl")):
        with f.open() as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                b = base(d["symbol"], venue)
                if b not in NAMES and b not in CONTROL:
                    continue
                px, qty = float(d["price"]), float(d["qty"])
                notional = qty * px * (ctval.get(d["symbol"], np.nan) if venue == "okx" else 1.0)
                # a sell liquidation closes a long on both venues
                direction = "sell" if d["side"].lower() == "sell" else "buy"
                rows.append((int(d["event_time_ms"]), b, direction, notional))
    df = pd.DataFrame(rows, columns=["t_ms", "base", "dir", "usd"])
    df["t"] = pd.to_datetime(df["t_ms"], unit="ms", utc=True)
    return df[df.t >= TAPE_START].dropna(subset=["usd"])


def bursts(df: pd.DataFrame) -> pd.DataFrame:
    """Qualifying 60 s bins per (base, dir) with the past-only trailing statistics."""
    out = []
    for (b, d), g in df.groupby(["base", "dir"]):
        s = g.set_index("t")["usd"].resample("60s").sum()
        ne = s[s > 0]
        med = ne.rolling(f"{WINDOW_H}h", closed="left").median()
        sd = ne.rolling(f"{WINDOW_H}h", closed="left").std()
        z = (ne - med) / sd
        q = ne[(ne >= MIN_USD) & (z >= Z_MIN)]
        for t, v in q.items():
            out.append({"base": b, "dir": d, "bin_end": t + pd.Timedelta(seconds=60), "usd": v, "z": float(z[t])})
    return pd.DataFrame(out)


def merge(q: pd.DataFrame) -> pd.DataFrame:
    """Consecutive qualifying bins → one event at the end of the last; both venues within 60 s → one event."""
    if q.empty:
        return q
    q = q.sort_values(["base", "dir", "bin_end"]).reset_index(drop=True)
    events = []
    for (b, d), g in q.groupby(["base", "dir"]):
        cur = None
        for _, r in g.iterrows():
            if cur is not None and (r.bin_end - cur["bin_end"]) <= pd.Timedelta(seconds=60):
                cur["bin_end"], cur["usd"], cur["z"], cur["bins"] = r.bin_end, cur["usd"] + r.usd, max(cur["z"], r.z), cur["bins"] + 1
            else:
                if cur is not None:
                    events.append(cur)
                cur = {"base": b, "dir": d, "bin_end": r.bin_end, "usd": r.usd, "z": r.z, "bins": 1, "venues": set([r.venue]) if "venue" in r else set()}
            if "venue" in r:
                cur["venues"].add(r.venue)
        if cur is not None:
            events.append(cur)
    return pd.DataFrame(events)


def main() -> int:
    p = paths().ensure()
    mirror = p.root / "mirror"
    ctval = okx_ctval(mirror)
    frames = []
    for venue in ("okx", "bybit"):
        df = load(mirror, venue, ctval)
        df["venue"] = venue
        frames.append(df)
        print(f"{venue}: {len(df):,} liquidations on the twenty names since the tape start, ${df.usd.sum()/1e6:,.0f}M", flush=True)
    all_ = pd.concat(frames)
    # bursts per venue first (the trailing statistics are per venue-symbol-direction, as frozen), then merged across venues
    per_venue = []
    for venue, g in all_.groupby("venue"):
        q = bursts(g)
        q["venue"] = venue
        per_venue.append(q)
    q = pd.concat(per_venue)
    ev = merge(q)
    ev["control"] = ev.base.isin(CONTROL)
    names = ev[~ev.control]
    first, last = all_.t.min(), all_.t.max()
    days = (last - first).total_seconds() / 86400
    print(f"\nwindow {first:%Y-%m-%d %H:%M} → {last:%Y-%m-%d %H:%M} UTC ({days:.1f} days)")
    print(f"merged events on the eighteen names: {len(names)}  ({len(names)/days:.1f} a day)   control BTC/ETH: {int(ev.control.sum())}")
    print(f"minimum for the study: 300 → {'REACHED' if len(names) >= 300 else f'not yet; at this rate about {(300-len(names))/max(len(names)/days,1e-9):.0f} more days'}")
    print("\nby name:", names.groupby("base").size().sort_values(ascending=False).to_dict())
    print("by direction:", names.groupby("dir").size().to_dict(), " median burst $%.0fk, median z %.1f" % (names.usd.median()/1e3, names.z.median()))
    out = p.root / "reports" / "c3_event_count.json"
    out.write_text(json.dumps({"window": [str(first), str(last)], "events_18": int(len(names)), "events_control": int(ev.control.sum()), "by_name": names.groupby("base").size().to_dict(), "per_day": len(names) / days}, indent=1, default=str))
    ev.drop(columns=["venues"]).to_parquet(p.root / "reports" / "c3_events.parquet", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
