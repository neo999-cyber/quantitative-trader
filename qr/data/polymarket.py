"""Polymarket crypto threshold / barrier markets, as a point-in-time panel (Programme 3, P3-A).

`docs/31` §1.3. Free, unauthenticated reads only:

* **Discovery** through Gamma's `public-search` (the plain `markets` listing
  refuses offsets past ~2,000): a fixed list of queries — "bitcoin reach",
  "what price will ethereum hit", … — returns resolved *events* with their
  markets. Each market carries its question, dates, volume, the two CLOB
  token ids (YES first) and the resolved outcome prices.
* **Daily price history** per YES token from the CLOB `prices-history`
  endpoint (`interval=max&fidelity=1440`). Resolved markets serve nothing
  finer than 12 hours, which is why the study is a daily one.
* **Classification** from the question text, frozen here: `kind` is
  `reach` (touch from below: "reach / hit … by / in"), `dip` (touch from
  above), or `above` (terminal: "be above $X on <date>"); `strike` is the
  dollar level; `asset` BTC/ETH/SOL. Sub-daily and dated-hour markets
  ("Up or Down", "on September 21, 4AM ET") are **excluded by rule**
  (`docs/31` §1.2 — the settlement-manipulation markets).

Everything is mirrored under `mirror/polymarket/` as the JSON the API
returned, and the panel is rebuilt from the mirror, so a kill test can be
re-run from the bytes it was built from. Nothing here signs, trades, or
needs a wallet.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
QUERIES = (
    "bitcoin reach", "bitcoin dip", "bitcoin hit", "what price will bitcoin hit", "bitcoin above", "bitcoin all-time high",
    "ethereum reach", "ethereum dip", "ethereum hit", "what price will ethereum hit", "ethereum above",
    "solana reach", "solana dip", "what price will solana hit",
)
EXCLUDE = re.compile(r"up or down|\b\d{1,2}(:\d{2})?\s?(am|pm)\s?(et|utc)\b|\bfirst\?|\bor \$", re.I)  # dated-hour and up/down markets; daily "on <date>" ones fall to the horizon floor
ASSET = re.compile(r"\b(bitcoin|btc|ethereum|eth|solana|sol)\b", re.I)
STRIKE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s*([kKmM])?")
KIND = (
    ("dip", re.compile(r"\b(dip|fall|drop|below)\b", re.I)),
    ("above", re.compile(r"\babove\b.*\bon\b", re.I)),
    ("reach", re.compile(r"\b(reach|hit|above|exceed|all-time high|ath)\b", re.I)),
)


def _get(url: str, retries: int = 3) -> dict | list:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
                return json.loads(r.read())
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            log.info("retry %s: %s", url[:80], exc)
            time.sleep(1.5 * (attempt + 1))
    return {}


def classify(question: str) -> dict | None:
    """`{asset, kind, strike}` from the question text, or None when it is not a threshold/barrier market."""
    if EXCLUDE.search(question):
        return None
    a = ASSET.search(question)
    s = STRIKE.search(question)
    if not a or not s:
        return None
    asset = {"bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH", "solana": "SOL", "sol": "SOL"}[a.group(1).lower()]
    strike = float(s.group(1).replace(",", ""))
    if s.group(2):
        strike *= {"k": 1e3, "m": 1e6}[s.group(2).lower()]
    for kind, pat in KIND:
        if pat.search(question):
            return {"asset": asset, "kind": kind, "strike": strike}
    return None


def discover(mirror: Path, queries=QUERIES, pages: int = 8, resolved_only: bool = True) -> pd.DataFrame:
    """Search Gamma for the crypto threshold/barrier markets; mirror the raw events; return one row per market."""
    out_dir = mirror / "polymarket" / "gamma"
    out_dir.mkdir(parents=True, exist_ok=True)
    seen, rows = set(), []
    for q in queries:
        for page in range(1, pages + 1):
            status = "&events_status=resolved" if resolved_only else ""
            r = _get(f"{GAMMA}/public-search?q={urllib.parse.quote(q)}&limit_per_type=50&page={page}{status}")
            events = r.get("events") or [] if isinstance(r, dict) else []
            if not events:
                break
            (out_dir / f"search_{q.replace(' ', '_')}_{page}.json").write_text(json.dumps(events))
            for e in events:
                for m in e.get("markets") or []:
                    mid = str(m.get("id"))
                    if mid in seen:
                        continue
                    seen.add(mid)
                    c = classify(m.get("question") or "")
                    tokens = m.get("clobTokenIds")
                    if isinstance(tokens, str):
                        try:
                            tokens = json.loads(tokens)
                        except json.JSONDecodeError:
                            tokens = None
                    prices = m.get("outcomePrices")
                    if isinstance(prices, str):
                        try:
                            prices = json.loads(prices)
                        except json.JSONDecodeError:
                            prices = None
                    rows.append({
                        "market_id": mid, "event": (e.get("title") or ""), "question": m.get("question") or "",
                        "asset": c["asset"] if c else None, "kind": c["kind"] if c else None, "strike": c["strike"] if c else None,
                        "start": (m.get("startDate") or e.get("startDate") or m.get("createdAt") or "")[:10],
                        "end": (m.get("endDate") or e.get("endDate") or "")[:10],
                        "volume": float(m.get("volumeNum") or m.get("volume") or 0), "closed": bool(m.get("closed")),
                        "yes_token": tokens[0] if tokens else None, "no_token": tokens[1] if tokens and len(tokens) > 1 else None,
                        "resolved_yes": (float(prices[0]) if prices else None),
                    })
            time.sleep(0.2)
    df = pd.DataFrame(rows)
    df["start"] = pd.to_datetime(df["start"], errors="coerce", utc=True)
    df["end"] = pd.to_datetime(df["end"], errors="coerce", utc=True)
    df["horizon_days"] = (df["end"] - df["start"]).dt.days
    return df


def eligible(df: pd.DataFrame, min_horizon_days: int = 7, min_volume: float = 10_000.0) -> pd.DataFrame:
    """The kill test's universe, frozen: classified, resolved, horizon ≥ 7 days, volume ≥ $10k, both tokens known."""
    ok = df["kind"].notna() & df["closed"] & (df["horizon_days"] >= min_horizon_days) & (df["volume"] >= min_volume) & df["yes_token"].notna()
    return df[ok].sort_values("end").reset_index(drop=True)


def price_history(mirror: Path, token: str, fidelity_min: int = 1440) -> pd.Series:
    """Daily YES price for one token, mirrored; NaN-free series indexed by UTC day."""
    out = mirror / "polymarket" / "prices" / f"{token}.json"
    if out.exists():
        data = json.loads(out.read_text())
    else:
        data = _get(f"{CLOB}/prices-history?market={token}&interval=max&fidelity={fidelity_min}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data))
        time.sleep(0.15)
    hist = data.get("history") or []
    if not hist:
        return pd.Series(dtype=float)
    s = pd.Series([float(h["p"]) for h in hist], index=pd.to_datetime([int(h["t"]) for h in hist], unit="s", utc=True))
    return s.groupby(s.index.normalize()).last().rename(token)


def build_polymarket_lake(lake, mirror: Path, min_horizon_days: int = 7, min_volume: float = 10_000.0) -> pd.DataFrame:
    """Discover, filter, fetch every eligible market's daily YES history, write the catalogue to the lake."""
    df = discover(mirror)
    uni = eligible(df, min_horizon_days, min_volume)
    n_hist = 0
    for token in uni["yes_token"]:
        if len(price_history(mirror, token)):
            n_hist += 1
    path = mirror / "polymarket" / "catalogue.parquet"
    uni.to_parquet(path, index=False)
    lake.write_reference("polymarket_crypto_markets", uni, source="polymarket")
    log.info("polymarket: %d markets discovered, %d eligible, %d with daily history", len(df), len(uni), n_hist)
    return uni
