"""Deribit DVOL — the options-implied volatility index, daily (Programme 3, P3-A).

`docs/31` §1.3. DVOL is Deribit's 30-day implied-volatility index for BTC
and ETH, computed from the listed option surface the way VIX is; it is the
comparator for the Polymarket threshold markets: the probability that the
spot touches a strike within the market's horizon, under a driftless
lognormal at the DVOL-implied volatility, against the price the market
quotes for the same event. The public endpoint needs no key:

    https://www.deribit.com/api/v2/public/get_volatility_index_data
        ?currency=BTC&resolution=1D&start_timestamp=..&end_timestamp=..

The response is `data: [[t_ms, open, high, low, close], ...]`, paged by
`continuation`. Each pull is mirrored under `mirror/deribit/dvol/` and the
daily close is written to the lake as `reference/dvol_<CCY>`.

SOL has no DVOL; a SOL market is compared against BTC DVOL scaled by the
realised-vol ratio, and that scaling is a stated approximation in the memo,
not a hidden one.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

API = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
REFERENCE_NAME = "dvol_{ccy}"


def _get(params: dict) -> dict:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        return json.loads(r.read())


def fetch(ccy: str = "BTC", start: str = "2021-01-01", end: str | None = None) -> list[list]:
    """All daily DVOL rows from `start`, paging with `continuation`. Needs the network."""
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    end_ms = int((pd.Timestamp(end, tz="UTC") if end else pd.Timestamp.now(tz="UTC")).timestamp() * 1000)
    rows: list[list] = []
    cont = end_ms
    for _ in range(100):
        r = _get({"currency": ccy, "resolution": "1D", "start_timestamp": start_ms, "end_timestamp": cont})
        res = r.get("result") or {}
        data = res.get("data") or []
        rows.extend(data)
        cont = res.get("continuation")
        if not data or cont is None or cont <= start_ms:
            break
        time.sleep(0.2)
    return rows


def to_frame(rows: list[list]) -> pd.DataFrame:
    """`date, open, high, low, close` per UTC day, deduplicated and sorted."""
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    df = pd.DataFrame(rows, columns=["t_ms", "open", "high", "low", "close"])
    df["date"] = pd.to_datetime(df["t_ms"], unit="ms", utc=True).dt.normalize()
    df = df.drop(columns="t_ms").drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return df[["date", "open", "high", "low", "close"]].astype({"open": float, "high": float, "low": float, "close": float})


def build_dvol(lake, mirror: Path, ccy: str = "BTC", start: str = "2021-01-01") -> pd.DataFrame:
    """Fetch, mirror the raw rows, write the daily frame to the lake as a reference table."""
    rows = fetch(ccy, start)
    out = mirror / "deribit" / "dvol" / f"{ccy}_1D.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows))
    df = to_frame(rows)
    lake.write_reference(REFERENCE_NAME.format(ccy=ccy), df, source="deribit")
    log.info("dvol %s: %d days %s → %s", ccy, len(df), df["date"].min() if len(df) else None, df["date"].max() if len(df) else None)
    return df


def load_dvol(lake, ccy: str = "BTC") -> pd.Series:
    """Daily DVOL close (vol points, e.g. 55.0 = 55% annualised), indexed by UTC day; from the lake only."""
    path = lake.paths.reference / f"{REFERENCE_NAME.format(ccy=ccy)}.parquet"
    df = pd.read_parquet(path)
    return pd.Series(df["close"].to_numpy(), index=pd.DatetimeIndex(df["date"]), name=f"dvol_{ccy}")
