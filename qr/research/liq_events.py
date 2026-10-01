"""Liquidation-burst events under C3's frozen definition (`docs/prereg/p2_liquidation_fade_v1.md`, seq 799).

Per venue, symbol and direction: 60-second bins of liquidation notional; a
**burst** is a bin ≥ $50,000 and ≥ 5 σ above the trailing 24-hour median of
that series' non-empty bins (past only; σ from the same trailing window);
consecutive qualifying bins are one event stamped at the **end** of the last
one; an event on both venues within 60 s is one event. OKX notional uses
the instrument's `ctVal` (contracts → coins); Bybit's `v` is already in
coins. A sell liquidation closes a long on both venues.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

TAPE_START = pd.Timestamp("2026-09-17 07:31", tz="UTC")
NAMES = ["SOL", "XRP", "HYPE", "ZEC", "DOGE", "ADA", "ENA", "BEAT", "NEAR", "LINK", "PEPE", "CL", "XAUT", "WLD", "SUI", "UNI", "ONDO", "BNB"]
CONTROL = ["BTC", "ETH"]
#: the Binance tape's symbol for each base
BINANCE = {b: f"{b}USDT" for b in NAMES + CONTROL} | {"PEPE": "1000PEPEUSDT"}
MIN_USD, Z_MIN, WINDOW_H = 50_000.0, 5.0, 24
OKX_INSTR = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"


def okx_ctval(mirror: Path) -> dict[str, float]:
    """Contract values per OKX swap, mirrored once (`mirror/liquidations/okx_instruments.json`)."""
    f = mirror / "liquidations" / "okx_instruments.json"
    if not f.exists():
        with urllib.request.urlopen(urllib.request.Request(OKX_INSTR, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
            f.write_text(r.read().decode())
    return {d["instId"]: float(d["ctVal"]) for d in json.loads(f.read_text())["data"]}


def base(symbol: str) -> str:
    s = symbol.replace("-USDT-SWAP", "").replace("USDT", "")
    for k in ("1000000", "100000", "10000", "1000"):
        if s.startswith(k) and len(s) > len(k):
            return s[len(k):]
    return s


def load(mirror: Path, venue: str, ctval: dict[str, float], start: pd.Timestamp = TAPE_START) -> pd.DataFrame:
    """Every recorded liquidation on the twenty names from `start`: `t, base, dir, usd, venue`."""
    rows = []
    for f in sorted((mirror / "liquidations" / venue).glob("*.jsonl")):
        with f.open() as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                b = base(d["symbol"])
                if b not in NAMES and b not in CONTROL:
                    continue
                usd = float(d["qty"]) * float(d["price"]) * (ctval.get(d["symbol"], np.nan) if venue == "okx" else 1.0)
                rows.append((int(d["event_time_ms"]), b, "sell" if d["side"].lower() == "sell" else "buy", usd))
    df = pd.DataFrame(rows, columns=["t_ms", "base", "dir", "usd"])
    df["t"] = pd.to_datetime(df["t_ms"], unit="ms", utc=True)
    df["venue"] = venue
    return df[df.t >= start].dropna(subset=["usd"]).reset_index(drop=True)


def bursts(df: pd.DataFrame) -> pd.DataFrame:
    """Qualifying 60 s bins per (base, dir) of one venue, with the past-only trailing statistics."""
    out = []
    for (b, d), g in df.groupby(["base", "dir"]):
        s = g.set_index("t")["usd"].resample("60s").sum()
        ne = s[s > 0]
        med = ne.rolling(f"{WINDOW_H}h", closed="left").median()
        sd = ne.rolling(f"{WINDOW_H}h", closed="left").std()
        z = (ne - med) / sd
        q = ne[(ne >= MIN_USD) & (z >= Z_MIN)]
        for t, v in q.items():
            out.append({"base": b, "dir": d, "bin_start": t, "bin_end": t + pd.Timedelta(seconds=60), "usd": float(v), "z": float(z[t])})
    return pd.DataFrame(out, columns=["base", "dir", "bin_start", "bin_end", "usd", "z"])


def merge(q: pd.DataFrame) -> pd.DataFrame:
    """Consecutive qualifying bins → one event at the end of the last; both venues within 60 s → one event.

    Columns: base, dir, start (first bin's start), t0 (last bin's end), usd, z, bins, venues.
    """
    cols = ["base", "dir", "start", "t0", "usd", "z", "bins", "venues"]
    if q.empty:
        return pd.DataFrame(columns=cols)
    q = q.sort_values(["base", "dir", "bin_end"]).reset_index(drop=True)
    events = []
    for (b, d), g in q.groupby(["base", "dir"]):
        cur = None
        for r in g.itertuples(index=False):
            v = getattr(r, "venue", None)
            if cur is not None and (r.bin_end - cur["t0"]) <= pd.Timedelta(seconds=60):
                cur["t0"] = max(cur["t0"], r.bin_end)
                cur["usd"] += r.usd
                cur["z"] = max(cur["z"], r.z)
                cur["bins"] += 1
                if v:
                    cur["venues"].add(v)
            else:
                if cur is not None:
                    events.append(cur)
                cur = {"base": b, "dir": d, "start": r.bin_start, "t0": r.bin_end, "usd": r.usd, "z": r.z, "bins": 1, "venues": {v} if v else set()}
        if cur is not None:
            events.append(cur)
    ev = pd.DataFrame(events, columns=cols)
    ev["venues"] = ev["venues"].map(lambda s: ",".join(sorted(s)))
    return ev.sort_values("t0").reset_index(drop=True)


def events(mirror: Path, start: pd.Timestamp = TAPE_START) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`(events, liquidations)` on the twenty names from the mirrored recordings."""
    ctval = okx_ctval(mirror)
    liq = pd.concat([load(mirror, v, ctval, start) for v in ("okx", "bybit")], ignore_index=True)
    per_venue = []
    for venue, g in liq.groupby("venue"):
        q = bursts(g)
        q["venue"] = venue
        per_venue.append(q)
    ev = merge(pd.concat(per_venue, ignore_index=True))
    ev["control"] = ev.base.isin(CONTROL)
    return ev, liq
