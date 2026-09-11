"""Prompt #3 - The Options Flow Vulture.

    "Flag stocks where call option volume is >300% of the 30-day average,
     specifically in strikes expiring within 14 days."

The flagging logic (`flag_unusual_calls`) is pure and provider-agnostic.
Activity comes from one of:

* `UnusualWhalesFlowProvider` - paid API, needs UNUSUAL_WHALES_API_KEY.
* `ChainHistoryFlowProvider`  - free: snapshots today's aggregate call volume
  from the Yahoo option chain into a local history file and computes the
  30-day baseline itself.  The baseline is honest only once ~30 snapshots
  exist, so run `centaur flow` daily and read the `baseline_days` column.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Protocol

import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class OptionActivity:
    ticker: str
    expiration: dt.date
    strike: float
    kind: str                 # "call" | "put"
    volume: float             # today's contract volume
    avg_volume_30d: float     # baseline for the same bucket
    open_interest: float = float("nan")
    baseline_days: int = 30   # how many days actually went into the baseline


@dataclass
class FlowFlag:
    ticker: str
    expiration: str
    strike: float
    volume: float
    avg_volume_30d: float
    ratio: float
    days_to_expiry: int
    open_interest: float
    baseline_days: int
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def flag_unusual_calls(
    activity: Iterable[OptionActivity],
    threshold: float = 3.0,
    max_dte: int = 14,
    as_of: dt.date | None = None,
    min_volume: float = 500,
) -> list[FlowFlag]:
    """Return call buckets whose volume exceeds `threshold` x its 30-day average
    and that expire within `max_dte` calendar days."""
    today = as_of or dt.date.today()
    flags: list[FlowFlag] = []
    for a in activity:
        if a.kind != "call":
            continue
        dte = (a.expiration - today).days
        if dte < 0 or dte > max_dte:
            continue
        if a.volume < min_volume or not a.avg_volume_30d or a.avg_volume_30d <= 0:
            continue
        ratio = a.volume / a.avg_volume_30d
        if ratio < threshold:
            continue
        note = ""
        if not pd.isna(a.open_interest) and a.open_interest > 0 and a.volume > a.open_interest:
            note = "volume > open interest (new positioning, not closing)"
        if a.baseline_days < 20:
            note = (note + "; " if note else "") + f"baseline only {a.baseline_days} days - low confidence"
        flags.append(FlowFlag(
            ticker=a.ticker, expiration=str(a.expiration), strike=a.strike,
            volume=a.volume, avg_volume_30d=a.avg_volume_30d, ratio=ratio,
            days_to_expiry=dte, open_interest=a.open_interest,
            baseline_days=a.baseline_days, note=note,
        ))
    flags.sort(key=lambda f: -f.ratio)
    return flags


class FlowProvider(Protocol):
    def activity(self, ticker: str) -> list[OptionActivity]: ...


# --------------------------------------------------------------------------- #
# Unusual Whales adapter (paid).  Endpoint paths are configurable because the
# vendor's API evolves; check https://api.unusualwhales.com/docs and set
# UNUSUAL_WHALES_CONTRACTS_PATH if the default below has moved.
# --------------------------------------------------------------------------- #
class UnusualWhalesFlowProvider:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: float = 20.0):
        self.api_key = api_key or os.environ.get("UNUSUAL_WHALES_API_KEY")
        if not self.api_key:
            raise RuntimeError("UNUSUAL_WHALES_API_KEY is not set")
        self.base_url = (base_url or os.environ.get("UNUSUAL_WHALES_BASE_URL") or "https://api.unusualwhales.com").rstrip("/")
        self.path = os.environ.get("UNUSUAL_WHALES_CONTRACTS_PATH", "/api/stock/{ticker}/option-contracts")
        self.timeout = timeout

    def activity(self, ticker: str) -> list[OptionActivity]:
        import requests

        url = self.base_url + self.path.format(ticker=ticker)
        resp = requests.get(url, headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
                            timeout=self.timeout)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        out: list[OptionActivity] = []
        for r in rows:
            try:
                out.append(OptionActivity(
                    ticker=ticker,
                    expiration=pd.Timestamp(r["expiry"]).date(),
                    strike=float(r["strike"]),
                    kind="call" if str(r.get("option_type", r.get("type", ""))).lower().startswith("c") else "put",
                    volume=float(r.get("volume", 0)),
                    avg_volume_30d=float(r.get("avg_30_day_volume") or r.get("avg_volume_30d") or 0),
                    open_interest=float(r.get("open_interest", float("nan"))),
                ))
            except (KeyError, ValueError, TypeError) as exc:
                log.debug("skipping malformed contract row %s: %s", r, exc)
        return out


# --------------------------------------------------------------------------- #
# Free adapter: build your own 30-day baseline from daily chain snapshots
# --------------------------------------------------------------------------- #
class ChainHistoryFlowProvider:
    """Aggregates today's call volume per (ticker, expiration) from the option
    chain and keeps a rolling history on disk to derive the 30-day average."""

    def __init__(self, provider, history_path: str | Path = ".cache/option_volume_history.json", window: int = 30):
        self.provider = provider
        self.history_path = Path(history_path)
        self.window = window
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self._hist: dict[str, dict[str, float]] = self._load()

    def _load(self) -> dict:
        if self.history_path.is_file():
            with open(self.history_path) as fh:
                return json.load(fh)
        return {}

    def _save(self) -> None:
        with open(self.history_path, "w") as fh:
            json.dump(self._hist, fh, indent=1, sort_keys=True)

    def record(self, ticker: str, total_call_volume: float, day: dt.date | None = None) -> None:
        day = day or dt.date.today()
        series = self._hist.setdefault(ticker.upper(), {})
        series[str(day)] = float(total_call_volume)
        # keep only the trailing window (+ today)
        for k in sorted(series)[:-(self.window + 1)]:
            del series[k]
        self._save()

    def baseline(self, ticker: str, exclude_day: dt.date | None = None) -> tuple[float, int]:
        series = self._hist.get(ticker.upper(), {})
        vals = [v for d, v in series.items() if exclude_day is None or d != str(exclude_day)]
        if not vals:
            return float("nan"), 0
        return sum(vals) / len(vals), len(vals)

    def activity(self, ticker: str, as_of: dt.date | None = None) -> list[OptionActivity]:
        today = as_of or dt.date.today()
        chain = self.provider.option_chain(ticker)
        if chain is None or chain.empty:
            return []
        calls = chain[chain["type"] == "call"].copy()
        calls["volume"] = pd.to_numeric(calls.get("volume"), errors="coerce").fillna(0.0)
        calls["openInterest"] = pd.to_numeric(calls.get("openInterest"), errors="coerce")
        total = float(calls["volume"].sum())
        self.record(ticker, total, today)
        base_total, days = self.baseline(ticker, exclude_day=today)

        out: list[OptionActivity] = []
        if not days or not base_total:
            return out
        # Distribute the ticker-level baseline across expirations by today's
        # share of volume, which keeps the per-expiry ratio equal to the
        # ticker-level ratio when we lack per-contract history.
        for (exp, strike), grp in calls.groupby(["expiration", "strike"]):
            vol = float(grp["volume"].sum())
            if vol <= 0:
                continue
            share = vol / total if total else 0.0
            out.append(OptionActivity(
                ticker=ticker,
                expiration=pd.Timestamp(exp).date(),
                strike=float(strike),
                kind="call",
                volume=vol,
                avg_volume_30d=base_total * share,
                open_interest=float(grp["openInterest"].sum()),
                baseline_days=days,
            ))
        return out


def scan_flow(flow_provider, tickers: Iterable[str], threshold: float = 3.0, max_dte: int = 14,
              as_of: dt.date | None = None) -> list[FlowFlag]:
    flags: list[FlowFlag] = []
    for t in tickers:
        try:
            acts = flow_provider.activity(t)
        except Exception as exc:
            log.warning("flow lookup failed for %s: %s", t, exc)
            continue
        flags.extend(flag_unusual_calls(acts, threshold=threshold, max_dte=max_dte, as_of=as_of))
    flags.sort(key=lambda f: -f.ratio)
    return flags
