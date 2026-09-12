"""Tiingo end-of-day prices: <https://api.tiingo.com>.

The ETF trial's system of record, chosen over the IBKR connector for one
reason: **depth**. The connector serves at most five years of daily bars and
takes no start date, and minimum backtest length at 200 variants and a Sharpe
of 1 is 10.6 years. Five years would have forced the search down to about
thirty variants and left gate 8's regime test with a single bear market to look
at. Tiingo's free tier carries US ETFs back to their inception.

Three things decide whether an ETF backtest built on this is honest.

**Adjusted prices, or the bond sleeve is a lie.** This is the one that has no
crypto analogue and it is not a detail. TLT distributes roughly 4% a year, HYG
closer to 6%: on unadjusted prices a total-return-flat bond ETF looks like a
steady loser, and a trend follower reading those prices would learn to short
it. Tiingo returns both — `close` as traded and `adjClose` back-adjusted for
dividends and splits — and this loader uses the **adjusted** series throughout,
which is what a total-return backtest requires. `close_unadjusted` is carried
alongside, because share counts and the $1 commission minimum are computed on
the price actually paid, not the adjusted one.

**Back-adjustment rewrites history every time a dividend is paid.** Yesterday's
adjusted close for TLT is not the number that was in yesterday's file. This is
survivorship bias's quieter cousin: it cannot be avoided with dividend-paying
instruments, but it means the manifest hash for an adjusted series legitimately
changes on every distribution, and a report that cites one is reproducible only
against the pull it was computed from. The raw JSON is cached for exactly that
reason — the mirror, not the API, is the system of record.

**A fixed basket needs no survivorship handling, and that is the point.** The
crypto universe had to be ranked point-in-time over 734 pairs because
membership changed. A dozen named ETFs that all still trade have no membership
problem at all, which removes an entire class of error from this trial. What it
does not remove is *selection* of the basket itself: choosing today's
well-known ETFs is a choice made with hindsight, and that belongs in the
pre-registration where it can be argued with, not in the loader.

The cloud sandbox cannot reach api.tiingo.com, so this is written against a
`PriceSource` with two implementations: `HttpTiingo` (the real client, for
`qr data pull --source tiingo` on the laptop) and `LocalTiingo` (a mirror of
cached JSON, which is what the tests and the sandbox use).
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

API_ROOT = "https://api.tiingo.com/tiingo/daily"

#: Tiingo's `/prices` endpoint returns **only the most recent bar** when no
#: `startDate` is given — it is not a "give me everything" default, it is a
#: quote. Asking for a ticker's whole history means naming a date before it
#: existed, so the loader floors every request here rather than leaving the
#: parameter unset. The first US ETF (SPY) listed in 1993; 1990 is comfortably
#: before anything in any basket this platform will trade.
#:
#: This cost a pull: twelve tickers came back with one bar each, dated
#: yesterday, and the ingest cheerfully wrote twelve one-row Parquet files.
EARLIEST = "1990-01-01"

#: Columns Tiingo returns from `/prices`. The adjusted four are what a
#: total-return backtest reads; `divCash` and `splitFactor` are kept so the
#: adjustment can be audited rather than trusted.
RAW_COLUMNS = (
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "adjOpen",
    "adjHigh",
    "adjLow",
    "adjClose",
    "adjVolume",
    "divCash",
    "splitFactor",
)


class PriceSource(Protocol):
    """Anything that can return Tiingo's raw JSON for one ticker."""

    def prices(self, ticker: str, start: str | None = None, end: str | None = None) -> list[dict]: ...

    def meta(self, ticker: str) -> dict: ...


@dataclass
class LocalTiingo:
    """A mirror directory of cached Tiingo responses.

    Layout, chosen to be obvious rather than clever:

        <root>/prices/<TICKER>.json    the price array, exactly as returned
        <root>/meta/<TICKER>.json      the ticker's metadata

    `qr data pull --source tiingo` fills it. Everything downstream reads it, so
    a backtest never depends on the API being up or on the adjustment factors
    being what they were last week.
    """

    root: Path

    def _read(self, kind: str, ticker: str) -> object:
        path = self.root / kind / f"{ticker.upper()}.json"
        if not path.exists():
            raise FileNotFoundError(f"{ticker} is not in the Tiingo mirror at {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def prices(self, ticker: str, start: str | None = None, end: str | None = None) -> list[dict]:
        rows = self._read("prices", ticker)
        assert isinstance(rows, list)
        if start is not None:
            rows = [r for r in rows if str(r["date"])[:10] >= str(start)[:10]]
        if end is not None:
            rows = [r for r in rows if str(r["date"])[:10] <= str(end)[:10]]
        return rows

    def meta(self, ticker: str) -> dict:
        out = self._read("meta", ticker)
        assert isinstance(out, dict)
        return out

    def tickers(self) -> list[str]:
        directory = self.root / "prices"
        if not directory.exists():
            return []
        return sorted(p.stem for p in directory.glob("*.json"))

    def write(self, ticker: str, rows: list[dict], meta: dict | None = None) -> None:
        for kind, payload in (("prices", rows), ("meta", meta)):
            if payload is None:
                continue
            path = self.root / kind / f"{ticker.upper()}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")


@dataclass
class HttpTiingo:
    """The real client. Laptop only — the sandbox cannot reach the API.

    The token is read from `$TIINGO_API_KEY` rather than taken as an argument,
    so it cannot end up in a command line, a trial-log record or a commit.
    """

    token: str | None = None
    timeout: float = 30.0
    _session: object | None = None
    _lock: threading.Lock = threading.Lock()

    def __post_init__(self) -> None:
        self.token = self.token or os.environ.get("TIINGO_API_KEY")
        if not self.token:
            raise ValueError(
                "no Tiingo token: set TIINGO_API_KEY (free key from https://tiingo.com)"
            )

    def _client(self):
        # Built lazily and under a lock, so a thread pool shares one connection
        # pool rather than opening a socket per ticker.
        if self._session is None:
            with self._lock:
                if self._session is None:
                    import requests
                    from requests.adapters import HTTPAdapter
                    from urllib3.util.retry import Retry

                    session = requests.Session()
                    retry = Retry(
                        total=5,
                        backoff_factor=1.0,
                        status_forcelist=(429, 500, 502, 503, 504),
                        allowed_methods=frozenset({"GET"}),
                    )
                    session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
                    # Tiingo documents both a `token` query parameter and this
                    # header. The header is sent too because a redirect drops
                    # the query string, and Tiingo redirects to its root on an
                    # auth failure — which is what makes a bad token surface as
                    # a bare 403 against a URL you never requested.
                    session.headers.update(
                        {
                            "Content-Type": "application/json",
                            "Authorization": f"Token {self.token}",
                        }
                    )
                    self._session = session
        return self._session

    def _get(self, path: str, **params) -> object:
        params = {k: v for k, v in params.items() if v is not None}
        params["token"] = self.token
        response = self._client().get(f"{API_ROOT}/{path}", params=params, timeout=self.timeout)
        if response.status_code in (401, 403):
            raise PermissionError(
                f"Tiingo refused the request ({response.status_code}). The token is present "
                f"but not accepted. Three things cause this, in order of likelihood:\n"
                f"  1. the email address on the account has not been confirmed — Tiingo "
                f"issues a token immediately but serves no data until you click the link;\n"
                f"  2. TIINGO_API_KEY holds a placeholder rather than the real token "
                f"(currently {len(self.token or '')} characters);\n"
                f"  3. the free tier's daily request limit is spent.\n"
                f"Check with: curl -s -o /dev/null -w '%{{http_code}}' "
                f"'https://api.tiingo.com/tiingo/daily/SPY/prices?token=$TIINGO_API_KEY'"
            )
        response.raise_for_status()
        return response.json()

    def prices(self, ticker: str, start: str | None = None, end: str | None = None) -> list[dict]:
        out = self._get(f"{ticker}/prices", startDate=start or EARLIEST, endDate=end, format="json")
        return list(out) if isinstance(out, list) else []

    def meta(self, ticker: str) -> dict:
        out = self._get(f"{ticker}")
        return dict(out) if isinstance(out, dict) else {}


def to_frame(rows: Iterable[dict], adjusted: bool = True) -> pd.DataFrame:
    """Tiingo's JSON rows as the platform's bar frame, indexed by UTC date.

    With `adjusted` (the default and the only setting a backtest should use)
    the OHLC columns are the dividend- and split-adjusted series. The traded
    close is kept as `close_unadjusted` because position sizing, share counts
    and the broker's per-order minimum all key off the price actually paid.

    `quote_volume` is dollar volume — volume times price — which is the field
    the universe and the impact model both expect, and it is computed from the
    **unadjusted** pair, because that is the notional that actually changed
    hands on the day.
    """
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "volume", "quote_volume", "close_unadjusted"]
        )
    missing = {"date", "close"} - set(frame.columns)
    if missing:
        raise ValueError(f"Tiingo rows are missing {sorted(missing)}")

    index = pd.DatetimeIndex(pd.to_datetime(frame["date"], utc=True)).normalize()
    index.name = "open_time"

    def column(name: str) -> pd.Series:
        adjusted_name = "adj" + name.capitalize()
        if adjusted and adjusted_name in frame.columns:
            values = pd.to_numeric(frame[adjusted_name], errors="coerce")
            # A gap in the adjusted series is a hole in the adjustment, not a
            # hole in the market: fall back to raw rather than to NaN, and say
            # so in `adjustment_gaps` so QA can see it happened.
            raw = pd.to_numeric(frame[name], errors="coerce")
            return values.where(values.notna(), raw)
        return pd.to_numeric(frame[name], errors="coerce")

    volume = pd.to_numeric(frame.get("volume", pd.Series(np.nan, index=frame.index)), errors="coerce")
    raw_close = pd.to_numeric(frame["close"], errors="coerce")
    out = pd.DataFrame(
        {
            "open": column("open").to_numpy(),
            "high": column("high").to_numpy(),
            "low": column("low").to_numpy(),
            "close": column("close").to_numpy(),
            "volume": volume.to_numpy(),
            "quote_volume": (volume * raw_close).to_numpy(),
            "close_unadjusted": raw_close.to_numpy(),
        },
        index=index,
    )
    if "divCash" in frame.columns:
        out["dividend"] = pd.to_numeric(frame["divCash"], errors="coerce").to_numpy()
    if "splitFactor" in frame.columns:
        out["split_factor"] = pd.to_numeric(frame["splitFactor"], errors="coerce").to_numpy()
    adjusted_present = adjusted and "adjClose" in frame.columns
    out.attrs["adjusted"] = bool(adjusted_present)
    out.attrs["adjustment_gaps"] = (
        int(pd.to_numeric(frame["adjClose"], errors="coerce").isna().sum()) if adjusted_present else 0
    )
    return out[~out.index.duplicated(keep="last")].sort_index()


@dataclass
class TiingoDaily:
    """The loader the platform talks to: one ticker in, one bar frame out."""

    source: PriceSource
    adjusted: bool = True

    def load(self, ticker: str, start=None, end=None) -> pd.DataFrame:
        rows = self.source.prices(ticker, _date(start), _date(end))
        frame = to_frame(rows, adjusted=self.adjusted)
        if not frame.empty and not frame.attrs.get("adjusted", False) and self.adjusted:
            # Loud, because a bond ETF on unadjusted prices is a strategy input
            # that is wrong by several percent a year in a consistent direction.
            log.warning(
                "%s has no adjusted prices; returns will understate total return by the "
                "distribution yield",
                ticker,
            )
        return frame

    def instruments(self, tickers: Iterable[str]) -> pd.DataFrame:
        """First and last bar per ticker, which is its usable history."""
        rows = []
        for ticker in tickers:
            frame = self.load(ticker)
            if frame.empty:
                continue
            row = {
                "symbol": ticker.upper(),
                "first_bar": frame.index[0],
                "last_bar": frame.index[-1],
                "bars": len(frame),
                "adjusted": bool(frame.attrs.get("adjusted", False)),
            }
            try:
                meta = self.source.meta(ticker)
                row["name"] = meta.get("name", "")
                row["exchange"] = meta.get("exchangeCode", "")
            except Exception:  # metadata is a nicety; missing it is not a failure
                row["name"] = row["exchange"] = ""
            rows.append(row)
        return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


def _date(value) -> str | None:
    if value is None:
        return None
    return str(pd.Timestamp(value).date())
