"""Token unlock calendars: the scheduled seller as a point-in-time feature.

A vesting schedule is published at the token's launch and cliffs on it are
dated years ahead, so "how much insider and investor supply unlocks in the
next 30 days" is known on every bar before it happens — the cleanest kind
of forced flow (`docs/research/10`, Keyrock's 16,000-event study: 90% of
unlocks push the price down, mostly in the 30 days *before* the date; team
cliffs worst; ecosystem unlocks the exception).

Source: DefiLlama's per-protocol emissions dataset, free and unkeyed
(`https://defillama-datasets.llama.fi/emissions/<slug>`). Its
`metadata.events` lists each cliff with a timestamp, a category and a
token count; `documentedData` gives the daily unlocked total per
allocation, whose sum is the documented circulating supply. The raw JSON
is mirrored under `mirror/defillama/emissions/` so a feature can be rebuilt
from the bytes it was built from.

**Point-in-time caveat, stated not hidden:** the dataset is the schedule as
currently documented. A project that revised its vesting after the fact
(extended a cliff, cancelled one) shows the revised dates, and a backtest
sees the revision before the market did. Cliffs that were *added* late are
the dangerous direction (a drop a strategy could not have anticipated
looks anticipated); DefiLlama's changelog is not exposed, so the feature
carries the caveat and the pre-registration's holdout — events after the
schedule was frozen on disk — is the only clean test of it.

Features written per perp symbol under `market="unlocks"` (daily):

- `unlock_pct_30d`: insider + private-sale cliff tokens dated in
  (t, t+30d] as a fraction of documented circulating supply at t.
- `unlock_pct_eco_30d`: the same for ecosystem / community / airdrop
  categories (the control: the study found these positive).
- `days_to_cliff`: calendar days to the next insider/investor cliff of at
  least `min_pct` of supply; NaN when none is scheduled.
- `cliff_pct_next`: that cliff's size as a fraction of supply.
- `circulating`: the documented circulating supply.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

MARKET = "unlocks"
DATASET = "https://defillama-datasets.llama.fi/emissions/{slug}"
PROTOCOLS = "https://api.llama.fi/protocols"
#: Categories whose recipients sell (the mechanism) and those that do not.
SELLER_CATEGORIES = ("insiders", "privateSale")
ECOSYSTEM_CATEGORIES = ("ecosystem", "community", "airdrop", "farming", "liquidity")
HORIZON_DAYS = 30


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def protocol_slugs_by_symbol() -> dict[str, list[str]]:
    """`{TOKEN_SYMBOL: [slug, ...]}` from DefiLlama's free protocol list."""
    protocols = json.loads(_get(PROTOCOLS))
    out: dict[str, list[str]] = {}
    for p in protocols:
        symbol = (p.get("symbol") or "").upper()
        if symbol and symbol != "-":
            out.setdefault(symbol, []).append(p["slug"])
    return out


def base_asset(perp_symbol: str) -> str:
    """`1000PEPEUSDT` -> `PEPE`, `BTCUSDT` -> `BTC`."""
    base = perp_symbol[:-4] if perp_symbol.endswith("USDT") else perp_symbol
    return base[4:] if base.startswith("1000") and len(base) > 4 else base


def mirror_schedule(slug: str, mirror: Path) -> Path | None:
    """Fetch one protocol's emissions JSON into the mirror; None when it has none."""
    path = mirror / "defillama" / "emissions" / f"{slug}.json"
    if path.exists():
        return path
    try:
        payload = _get(DATASET.format(slug=slug), timeout=30)
    except Exception as exc:  # 404 for a protocol with no schedule, or a network error
        log.info("no schedule for %s: %s", slug, exc)
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not (data.get("metadata") or {}).get("events"):
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def cliff_events(payload: dict) -> pd.DataFrame:
    """One row per cliff: `date`, `category` (DefiLlama's bucket), `tokens`."""
    categories = {}
    for bucket, labels in (payload.get("categories") or {}).items():
        for label in labels:
            categories[label] = bucket
    rows = []
    for event in (payload.get("metadata") or {}).get("events") or []:
        if event.get("unlockType") != "cliff" or not event.get("noOfTokens"):
            continue
        rows.append(
            {
                "date": pd.Timestamp(int(event["timestamp"]), unit="s", tz="UTC").normalize(),
                "category": event.get("category") or "Uncategorized",
                "tokens": float(event["noOfTokens"][0]),
            }
        )
    frame = pd.DataFrame(rows, columns=["date", "category", "tokens"])
    return frame.sort_values("date").reset_index(drop=True)


def circulating_supply(payload: dict) -> pd.Series:
    """Documented circulating supply per day: the sum of every allocation's `unlocked`."""
    total = None
    for series in (payload.get("documentedData") or {}).get("data") or []:
        frame = pd.DataFrame(series["data"])
        if frame.empty:
            continue
        s = pd.Series(frame["unlocked"].to_numpy(dtype=float), index=pd.to_datetime(frame["timestamp"], unit="s", utc=True))
        s = s[~s.index.duplicated(keep="last")]
        total = s if total is None else total.add(s, fill_value=0.0)
    if total is None:
        return pd.Series(dtype=float)
    return total.sort_index().rename("circulating")


def unlock_features(
    events: pd.DataFrame,
    circulating: pd.Series,
    index: pd.DatetimeIndex,
    horizon_days: int = HORIZON_DAYS,
    min_pct: float = 0.01,
) -> pd.DataFrame:
    """The per-day features on `index`, each read only from cliffs dated after that day."""
    supply = circulating.reindex(circulating.index.union(index)).sort_index().ffill().reindex(index)
    supply = supply.where(supply > 0)
    sellers = events[events["category"].isin(SELLER_CATEGORIES)]
    eco = events[events["category"].isin(ECOSYSTEM_CATEGORIES)]
    out = pd.DataFrame(index=index)
    out["circulating"] = supply
    out["unlock_pct_30d"] = _window_sum(sellers, index, horizon_days) / supply
    out["unlock_pct_eco_30d"] = _window_sum(eco, index, horizon_days) / supply
    days, size = _next_cliff(sellers, index, supply, min_pct)
    out["days_to_cliff"] = days
    out["cliff_pct_next"] = size
    return out


def _window_sum(events: pd.DataFrame, index: pd.DatetimeIndex, horizon_days: int) -> pd.Series:
    """Tokens from cliffs dated in (t, t + horizon] for each t on `index`."""
    if events.empty:
        return pd.Series(0.0, index=index)
    dates = events["date"].to_numpy(dtype="datetime64[ns]")
    tokens = events["tokens"].to_numpy(dtype=float)
    cum = np.concatenate([[0.0], np.cumsum(tokens)])
    t = index.tz_convert("UTC").tz_localize(None).to_numpy(dtype="datetime64[ns]")
    lo = np.searchsorted(dates, t, side="right")
    hi = np.searchsorted(dates, t + np.timedelta64(horizon_days, "D"), side="right")
    return pd.Series(cum[hi] - cum[lo], index=index)


def _next_cliff(events: pd.DataFrame, index: pd.DatetimeIndex, supply: pd.Series, min_pct: float):
    days = pd.Series(np.nan, index=index)
    size = pd.Series(np.nan, index=index)
    if events.empty:
        return days, size
    dates = events["date"].to_numpy(dtype="datetime64[ns]")
    tokens = events["tokens"].to_numpy(dtype=float)
    t = index.tz_convert("UTC").tz_localize(None).to_numpy(dtype="datetime64[ns]")
    sup = supply.to_numpy(dtype=float)
    start = np.searchsorted(dates, t, side="right")
    for i in range(len(index)):
        if not np.isfinite(sup[i]):
            continue
        j = start[i]
        while j < len(dates):
            pct = tokens[j] / sup[i]
            if pct >= min_pct:
                days.iloc[i] = (dates[j] - t[i]) / np.timedelta64(1, "D")
                size.iloc[i] = pct
                break
            j += 1
    return days, size


def build_unlock_lake(
    lake, mirror: Path, symbols: Iterable[str] | None = None, start: str = "2020-01-01", end: str | None = None
) -> pd.DataFrame:
    """Mirror every matched perp's schedule and write its features under `market="unlocks"`."""
    from qr.data.funding import MARKET as PERP_MARKET  # noqa: F401  (documentation of the pairing)

    perps = list(symbols) if symbols is not None else lake.symbols("1d", market="futures/um")
    slugs = protocol_slugs_by_symbol()
    index = pd.date_range(start, end or pd.Timestamp.utcnow().normalize(), freq="D", tz="UTC")
    index.name = "open_time"
    rows = []
    for perp in perps:
        base = base_asset(perp)
        candidates = slugs.get(base, [])
        path = None
        for slug in candidates[:3]:
            path = mirror_schedule(slug, mirror)
            if path is not None:
                break
        if path is None:
            rows.append({"symbol": perp, "slug": "", "cliffs": 0, "note": "no schedule"})
            continue
        payload = json.loads(path.read_bytes())
        events = cliff_events(payload)
        supply = circulating_supply(payload)
        if events.empty or supply.empty:
            rows.append({"symbol": perp, "slug": path.stem, "cliffs": 0, "note": "schedule without cliffs"})
            continue
        frame = unlock_features(events, supply, index)
        frame.index.name = "open_time"
        lake.write_klines(perp, frame, "1d", market=MARKET)
        sellers = events[events["category"].isin(SELLER_CATEGORIES)]
        rows.append(
            {
                "symbol": perp,
                "slug": path.stem,
                "cliffs": int(len(events)),
                "seller_cliffs": int(len(sellers)),
                "big_seller_cliffs": int((frame["cliff_pct_next"].dropna().drop_duplicates() >= 0.01).sum()),
                "note": "",
            }
        )
    return pd.DataFrame(rows)


def attach_unlocks(panel, lake, start=None, end=None):
    """Join the unlock features onto a perp panel; silent when none are built."""
    from qr.data.panel import Panel

    try:
        available = set(lake.symbols("1d", market=MARKET))
    except Exception:
        return panel
    wanted = [s for s in panel.symbols if s in available]
    if not wanted:
        return panel
    built = dict(panel.fields)
    for field in ("unlock_pct_30d", "unlock_pct_eco_30d", "days_to_cliff", "cliff_pct_next"):
        columns = {}
        for symbol in panel.symbols:
            if symbol in wanted:
                frame = lake.read_klines(symbol, "1d", start, end, market=MARKET)
                columns[symbol] = frame[field].reindex(panel.index) if field in frame.columns else pd.Series(np.nan, index=panel.index)
            else:
                columns[symbol] = pd.Series(np.nan, index=panel.index)
        built[field] = pd.DataFrame(columns, index=panel.index, columns=panel.symbols)
    return Panel(built, panel.interval)
