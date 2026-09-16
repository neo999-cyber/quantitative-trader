"""Bybit USDT-perpetual funding history from the public REST API (C2: cross-venue funding).

`GET /v5/market/funding/history?category=linear&symbol=...` returns up to
200 settlements a page, newest first; paging by `endTime`. Free, no key.
Rates settle every 8 hours (some symbols 4 or 1); `funding_rate` is what a
long paid that interval, the same convention as the Binance feature. Stored
per symbol under `mirror/bybit/funding/<SYMBOL>.parquet` with the pull time.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE = "https://api.bybit.com"


def _get(path: str, params: dict) -> dict:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(f"{BASE}{path}?{query}", headers={"User-Agent": "quantitative-trader research"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def linear_symbols() -> list[dict]:
    out, cursor = [], ""
    while True:
        params = {"category": "linear", "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        data = _get("/v5/market/instruments-info", params)
        out += data["result"]["list"]
        cursor = data["result"].get("nextPageCursor", "")
        if not cursor:
            break
    return [s for s in out if s.get("quoteCoin") == "USDT" and s.get("contractType") == "LinearPerpetual"]


def funding_history(symbol: str, since_ms: int = 0, pause: float = 0.1) -> pd.DataFrame:
    rows, end = [], None
    while True:
        params = {"category": "linear", "symbol": symbol, "limit": 200}
        if end:
            params["endTime"] = end
        data = _get("/v5/market/funding/history", params)
        page = data["result"]["list"]
        if not page:
            break
        rows += page
        oldest = int(page[-1]["fundingRateTimestamp"])
        if len(page) < 200 or oldest <= since_ms:
            break
        end = oldest - 1
        time.sleep(pause)
    if not rows:
        return pd.DataFrame(columns=["funding_rate"], index=pd.DatetimeIndex([], tz="UTC", name="calc_time"))
    frame = pd.DataFrame(rows)
    frame["calc_time"] = pd.to_datetime(frame["fundingRateTimestamp"].astype(int), unit="ms", utc=True)
    frame["funding_rate"] = frame["fundingRate"].astype(float)
    return frame.set_index("calc_time")[["funding_rate"]].sort_index().pipe(lambda f: f[~f.index.duplicated(keep="last")])


def pull_all(mirror: Path, pause: float = 0.1) -> pd.DataFrame:
    mirror.mkdir(parents=True, exist_ok=True)
    rows = []
    for inst in linear_symbols():
        sym = inst["symbol"]
        target = mirror / f"{sym}.parquet"
        if target.exists():
            continue
        try:
            frame = funding_history(sym, pause=pause)
        except Exception as exc:  # noqa: BLE001
            rows.append({"symbol": sym, "note": str(exc)[:60]})
            continue
        frame["first_observed_at"] = pd.Timestamp(datetime.now(timezone.utc))
        frame.reset_index().to_parquet(target, index=False)
        rows.append({"symbol": sym, "settlements": len(frame), "start": frame.index.min() if len(frame) else None})
        time.sleep(pause)
    return pd.DataFrame(rows)
