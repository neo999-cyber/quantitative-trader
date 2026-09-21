"""Binance Launchpool — every completed pool, measured (Programme 3, `docs/31` §2 tier 4, §4).

The claim to test is the promoters' "84% APY": what a *stablecoin* staked
in a Launchpool actually earned, per pool, at the listing price, and where
the per-user cap binds. Binance publishes it all on a public, unsigned
endpoint (probed 21 September 2026 from the Hetzner box):

    /bapi/asset/v1/public/launchpool/project/list?pageIndex=N&pageSize=20   (completed pools, paged)
    /bapi/asset/v1/public/launchpool/project/detail?projectId=<id>          (per pool)

The detail carries `asset` (the staked coin: BNB, FDUSD, USDC, USD1, …),
`rebateCoin`, `rebateTotalAmount`, `duration` (days), `totalInvestAmount`
(the whole pool's stake), `avgPerAsset` (reward coins per staked coin over
the pool's life — the number that matters), `maximumHourlyReward` (the
per-user cap, coins per hour), `investUsers`, `coinTradeTime` (listing).

The listing price comes from Binance spot daily klines (`<rebateCoin>USDT`,
the listing day's close: what a holder who sold on day one got, roughly).
Everything is mirrored under `mirror/binance/launchpool/`.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
LIST = "https://www.binance.com/bapi/asset/v1/public/launchpool/project/list?pageIndex={page}&pageSize=20"
DETAIL = "https://www.binance.com/bapi/asset/v1/public/launchpool/project/detail?projectId={pid}"
KLINES = "https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d&startTime={start}&limit={limit}"
STABLES = {"FDUSD", "USDC", "USDT", "USD1", "U", "BUSD", "TUSD"}


def _get(url: str) -> dict | list:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        return json.loads(r.read())


def fetch_projects(mirror: Path, sleep: float = 1.0) -> list[dict]:
    """Every completed pool's detail, mirrored one file per project (skipped when already mirrored)."""
    out_dir = mirror / "binance" / "launchpool"
    out_dir.mkdir(parents=True, exist_ok=True)
    ids: list[str] = []
    for page in range(1, 40):
        d = _get(LIST.format(page=page))
        lst = (d.get("data") or {}).get("completed", {}).get("list") or []
        if not lst:
            break
        ids.extend(p["projectId"] for p in lst)
        time.sleep(sleep)
    ids = list(dict.fromkeys(ids))
    projects = []
    for pid in ids:
        f = out_dir / f"{pid}.json"
        if f.exists():
            projects.append(json.loads(f.read_text()))
            continue
        d = _get(DETAIL.format(pid=pid)).get("data") or {}
        d.pop("activities", None)
        f.write_text(json.dumps(d))
        projects.append(d)
        time.sleep(sleep)
    log.info("launchpool: %d completed pools", len(projects))
    return projects


def listing_prices(projects: list[dict], mirror: Path, sleep: float = 0.3) -> dict[str, dict]:
    """Per reward coin: the listing day's close, the next day's, and the 7th day's, from spot daily klines (mirrored)."""
    out_dir = mirror / "binance" / "launchpool" / "prices"
    out_dir.mkdir(parents=True, exist_ok=True)
    coins = {p["rebateCoin"]: int(p["coinTradeTime"]) for p in projects if p.get("coinTradeTime")}
    prices = {}
    for coin, t_ms in coins.items():
        f = out_dir / f"{coin}.json"
        if f.exists():
            rows = json.loads(f.read_text())
        else:
            try:
                rows = _get(KLINES.format(sym=f"{coin}USDT", start=t_ms - 86_400_000, limit=10))
            except Exception as exc:  # noqa: BLE001
                log.warning("%s: %s", coin, exc)
                rows = []
            f.write_text(json.dumps(rows))
            time.sleep(sleep)
        if not rows:
            continue
        closes = [(int(r[0]), float(r[4])) for r in rows]
        day1 = next((c for t, c in closes if t >= t_ms - 3_600_000), None)
        prices[coin] = {"day1_close": day1, "day2_close": closes[1][1] if len(closes) > 1 else None,
                        "day7_close": closes[min(6, len(closes) - 1)][1] if len(closes) > 6 else None}
    return prices


def measure(projects: list[dict], prices: dict[str, dict]) -> pd.DataFrame:
    """One row per pool: realised yield per staked $ (stablecoin pools) at the listing close, annualised, and the cap."""
    rows = []
    for p in projects:
        coin = p.get("rebateCoin")
        px = prices.get(coin) or {}
        try:
            avg = float(p.get("avgPerAsset") or 0)
            dur = float(p.get("duration") or 0)
            total = float(p.get("totalInvestAmount") or 0)
            cap_h = float(p.get("maximumHourlyReward") or 0)
        except ValueError:
            continue
        day1 = px.get("day1_close")
        yield_per_asset = avg * day1 if day1 else None           # $ of reward per staked coin over the pool
        stable = p.get("asset") in STABLES
        rows.append({
            "project": p.get("projectId"), "coin": coin, "staked": p.get("asset"), "stable": stable,
            "listing": pd.to_datetime(int(p["coinTradeTime"]), unit="ms", utc=True) if p.get("coinTradeTime") else pd.NaT,
            "duration_days": dur, "pool_total": total, "users": int(p.get("investUsers") or 0),
            "reward_total": float(p.get("rebateTotalAmount") or 0), "avg_per_asset": avg, "cap_per_hour": cap_h,
            "day1_close": day1, "day7_close": px.get("day7_close"),
            "yield_per_stake_pool": yield_per_asset if stable else None,
            "apr_at_day1": (yield_per_asset / dur * 365) if (stable and yield_per_asset and dur) else None,
            "apr_at_day7": (avg * px["day7_close"] / dur * 365) if (stable and px.get("day7_close") and dur) else None,
            # the stake at which the per-user cap binds: cap coins/hour ÷ (avg coins per staked coin per hour)
            "cap_binds_at_stake": (cap_h / (avg / (dur * 24))) if (avg and dur and cap_h) else None,
        })
    return pd.DataFrame(rows).sort_values("listing").reset_index(drop=True)
