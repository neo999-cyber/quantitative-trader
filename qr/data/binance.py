"""The Binance public data bucket: <https://data.binance.vision>.

The best free dataset in any asset class, and the reason the trial starts on
crypto spot. Three things about it decide whether a backtest built on it is
honest, and all three are handled here:

* **The universe comes from the bucket listing, never from `exchangeInfo`.**
  Delisted pairs stay in the bucket forever but vanish from the live exchange
  info, so a universe built from the API is survivorship-biased by
  construction. `symbols()` reads the listing; `listing_window()` derives each
  pair's first and last month of data, which are its listing and delisting
  dates to within a month.
* **Binance spot timestamps switched from milliseconds to microseconds on
  2025-01-01.** A loader that assumes one unit silently places five years of
  bars in 1970 or in the year 57000. `to_utc()` decides per value by magnitude.
* **Files gained a header row in 2025.** The parser sniffs rather than assumes.

The cloud sandbox cannot reach data.binance.vision, so the loader is written
against a `BucketSource` with two implementations: `HttpBucket` (the real
thing, for `qr data pull` on the laptop) and `LocalBucket` (a mirror directory
in the bucket's exact layout, which is what the tests and the sandbox use).
"""
from __future__ import annotations

import hashlib
import io
import logging
import re
import threading
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol
from xml.etree import ElementTree

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BUCKET_URL = "https://data.binance.vision"
LIST_URL = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

#: Raw kline CSV columns, in the bucket's order. `ignore` is Binance's own name.
KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore",
]

#: What the lake stores. `open_time` becomes the index.
CANONICAL_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
    "close_time",
]

#: Binance spot switched kline timestamps to microseconds on this date.
MICROSECOND_SWITCH = date(2025, 1, 1)

#: Epoch values above this are microseconds; below, milliseconds. A millisecond
#: timestamp only reaches 1e14 in the year 5138, and a microsecond one only
#: falls below it before 1973 — neither is a date this bucket contains.
US_VS_MS_THRESHOLD = 1e14


class BucketError(RuntimeError):
    """The bucket did not return what the layout says it should."""


# --------------------------------------------------------------------- sources


class BucketSource(Protocol):
    """Anything that can list and read keys in the bucket's layout."""

    def list_prefixes(self, prefix: str) -> list[str]: ...

    def list_keys(self, prefix: str) -> list[str]: ...

    def read(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


@dataclass
class LocalBucket:
    """A mirror directory holding the bucket's keys as relative paths.

    `root/data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2024-01.zip` mirrors
    the key `data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2024-01.zip`.
    """

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def list_prefixes(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if not base.is_dir():
            return []
        return sorted(f"{prefix}{p.name}/" for p in base.iterdir() if p.is_dir())

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if not base.is_dir():
            return []
        return sorted(f"{prefix}{p.name}" for p in base.iterdir() if p.is_file())

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(f"{key} is not in the mirror at {self.root}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def write(self, key: str, payload: bytes) -> Path:
        """Used by `qr data pull` to fill the mirror on the laptop."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path


@dataclass
class HttpBucket:
    """The live bucket. Only reachable from a machine with internet access.

    Built for concurrent use, because a full pull is tens of thousands of
    small requests and the bottleneck is round trips, not bytes. The session
    carries a connection pool sized to the caller's worker count and retries
    transient failures — a multi-hour download that dies on one 503 an hour in
    is worse than one that never started.
    """

    session: object | None = None
    timeout: int = 60
    pool_size: int = 32
    retries: int = 3

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def _session(self):
        # Double-checked locking: threads racing here would otherwise each
        # build a session and discard the pool the others were about to use.
        if self.session is None:
            with self._lock:
                if self.session is None:
                    import requests
                    from requests.adapters import HTTPAdapter
                    from urllib3.util.retry import Retry

                    session = requests.Session()
                    adapter = HTTPAdapter(
                        pool_connections=self.pool_size,
                        pool_maxsize=self.pool_size,
                        max_retries=Retry(
                            total=self.retries,
                            backoff_factor=0.5,
                            status_forcelist=(429, 500, 502, 503, 504),
                            allowed_methods=frozenset({"GET", "HEAD"}),
                        ),
                    )
                    session.mount("https://", adapter)
                    self.session = session
        return self.session

    def _list(self, prefix: str) -> tuple[list[str], list[str]]:
        prefixes: list[str] = []
        keys: list[str] = []
        marker = ""
        while True:
            params = {"delimiter": "/", "prefix": prefix}
            if marker:
                params["marker"] = marker
            resp = self._session().get(LIST_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            tree = ElementTree.fromstring(resp.content)
            prefixes += [
                node.findtext(f"{S3_NS}Prefix", "")
                for node in tree.findall(f"{S3_NS}CommonPrefixes")
            ]
            found = [node.findtext(f"{S3_NS}Key", "") for node in tree.findall(f"{S3_NS}Contents")]
            keys += found
            truncated = (tree.findtext(f"{S3_NS}IsTruncated", "false") or "false").lower() == "true"
            if not truncated:
                break
            marker = tree.findtext(f"{S3_NS}NextMarker") or (found[-1] if found else "")
            if not marker:
                break
        return sorted(p for p in prefixes if p), sorted(k for k in keys if k)

    def list_prefixes(self, prefix: str) -> list[str]:
        return self._list(prefix)[0]

    def list_keys(self, prefix: str) -> list[str]:
        return self._list(prefix)[1]

    def read(self, key: str) -> bytes:
        resp = self._session().get(f"{BUCKET_URL}/{key}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.content

    def exists(self, key: str) -> bool:
        resp = self._session().head(f"{BUCKET_URL}/{key}", timeout=self.timeout)
        return resp.status_code == 200


# ----------------------------------------------------------------------- keys


def kline_prefix(symbol: str, interval: str, cadence: str = "monthly", market: str = "spot") -> str:
    return f"data/{market}/{cadence}/klines/{symbol}/{interval}/"


def kline_key(
    symbol: str, interval: str, period: str, cadence: str = "monthly", market: str = "spot"
) -> str:
    """`period` is `YYYY-MM` for monthly files and `YYYY-MM-DD` for daily ones."""
    return f"{kline_prefix(symbol, interval, cadence, market)}{symbol}-{interval}-{period}.zip"


_PERIOD_RE = re.compile(r"-(\d{4}-\d{2}(?:-\d{2})?)\.zip$")


def period_of(key: str) -> str:
    match = _PERIOD_RE.search(key)
    if not match:
        raise BucketError(f"cannot read a period out of key {key!r}")
    return match.group(1)


# --------------------------------------------------------------------- parsing


def to_utc(values: pd.Series | np.ndarray) -> pd.DatetimeIndex:
    """Epoch integers -> UTC timestamps, deciding ms vs us per value.

    Binance spot switched to microsecond kline timestamps on 2025-01-01, so a
    single file is uniform but a concatenation of files spanning the switch is
    not. Judging each value by magnitude is exact for every date the bucket
    holds, and is the only approach that survives the boundary month.
    """
    raw = pd.to_numeric(pd.Series(np.asarray(values)), errors="coerce")
    if raw.isna().any():
        raise BucketError("kline file contains a non-numeric timestamp")
    micros = np.where(raw.to_numpy() >= US_VS_MS_THRESHOLD, raw.to_numpy(), raw.to_numpy() * 1000.0)
    return pd.DatetimeIndex(pd.to_datetime(np.round(micros).astype("int64"), unit="us", utc=True))


def parse_klines(payload: bytes, symbol: str | None = None) -> pd.DataFrame:
    """Parse one kline file (a `.zip` from the bucket, or its bare `.csv`).

    Files written before 2025 have no header row; later ones do. Sniffing the
    first field is the only reliable way to tell, because a header row parsed
    as data becomes a NaN bar that quietly survives to the backtest.
    """
    body = _unzip(payload)
    if not body.strip():
        return _empty_klines()
    first_field = body.split(b"\n", 1)[0].split(b",", 1)[0].strip()
    has_header = not re.fullmatch(rb"\d+(\.\d+)?", first_field)
    frame = pd.read_csv(io.BytesIO(body), header=0 if has_header else None)
    if frame.shape[1] != len(KLINE_COLUMNS):
        raise BucketError(
            f"kline file has {frame.shape[1]} columns, expected {len(KLINE_COLUMNS)}"
        )
    if has_header:
        frame.columns = [str(c).strip().lower() for c in frame.columns]
        missing = [c for c in KLINE_COLUMNS if c not in frame.columns]
        if missing:
            raise BucketError(f"kline file is missing columns {missing}")
        frame = frame[KLINE_COLUMNS]
    else:
        frame.columns = KLINE_COLUMNS

    frame.index = to_utc(frame["open_time"])
    frame.index.name = "open_time"
    out = frame.drop(columns=["open_time", "ignore"])
    out["close_time"] = to_utc(out["close_time"])
    numeric = [c for c in CANONICAL_COLUMNS if c != "close_time"]
    out[numeric] = out[numeric].astype(float)
    out = out[CANONICAL_COLUMNS]
    if symbol is not None:
        out.attrs["symbol"] = symbol
    return out[~out.index.duplicated(keep="last")].sort_index()


def _unzip(payload: bytes) -> bytes:
    if payload[:2] != b"PK":
        return payload
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise BucketError(f"expected one CSV in the archive, found {names}")
        return zf.read(names[0])


def _empty_klines() -> pd.DataFrame:
    idx = pd.DatetimeIndex([], tz="UTC", name="open_time")
    return pd.DataFrame({c: pd.Series(dtype=float) for c in CANONICAL_COLUMNS}, index=idx)


def verify_checksum(payload: bytes, checksum_body: bytes) -> bool:
    """The bucket ships a `.CHECKSUM` beside every archive: `<sha256>  <name>`."""
    expected = checksum_body.decode("utf-8", "replace").strip().split()[0].lower()
    return hashlib.sha256(payload).hexdigest() == expected


# ------------------------------------------------------------------- the loader


@dataclass
class BinanceBucket:
    """Reads klines and the reference universe out of a `BucketSource`."""

    source: BucketSource
    market: str = "spot"
    verify: bool = True

    # -- reference data ----------------------------------------------------

    def symbols(self, interval: str = "1d", cadence: str = "monthly") -> list[str]:
        """Every symbol the bucket has ever carried, delisted ones included.

        This is the survivorship-free universe. `exchangeInfo` is not.
        """
        prefix = f"data/{self.market}/{cadence}/klines/"
        return [p[len(prefix) :].rstrip("/") for p in self.source.list_prefixes(prefix)]

    def periods(self, symbol: str, interval: str = "1d", cadence: str = "monthly") -> list[str]:
        keys = self.source.list_keys(kline_prefix(symbol, interval, cadence, self.market))
        return sorted({period_of(k) for k in keys if k.endswith(".zip")})

    def listing_window(
        self, symbol: str, interval: str = "1d", cadence: str = "monthly"
    ) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
        """First and last period present, i.e. listing and delisting to the month.

        A pair whose last file is the current period is still listed; the caller
        compares against `asof` to decide, because the bucket itself does not say.
        """
        periods = self.periods(symbol, interval, cadence)
        if not periods:
            return None, None
        first = pd.Timestamp(periods[0] if len(periods[0]) > 7 else periods[0] + "-01", tz="UTC")
        last_period = periods[-1]
        if len(last_period) > 7:
            last = pd.Timestamp(last_period, tz="UTC")
        else:
            last = pd.Timestamp(last_period + "-01", tz="UTC") + pd.offsets.MonthEnd(1)
        return first, last.normalize()

    def instruments(
        self, symbols: Iterable[str] | None = None, interval: str = "1d", cadence: str = "monthly"
    ) -> pd.DataFrame:
        """The reference table: one row per pair with its listing window.

        This is what gate 1 (data integrity) checks a universe against, and what
        keeps a delisted pair in the backtest until the day it actually left.
        """
        names = list(symbols) if symbols is not None else self.symbols(interval, cadence)
        rows = []
        for symbol in names:
            first, last = self.listing_window(symbol, interval, cadence)
            if first is None:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "market": self.market,
                    "quote_asset": _quote_asset(symbol),
                    "base_asset": symbol[: -len(_quote_asset(symbol))] if _quote_asset(symbol) else symbol,
                    "listed_on": first,
                    "last_data": last,
                    "months": len(self.periods(symbol, interval, cadence)),
                }
            )
        frame = pd.DataFrame(rows)
        return frame.sort_values("symbol").reset_index(drop=True) if len(frame) else frame

    # -- market data -------------------------------------------------------

    def load_klines(
        self,
        symbol: str,
        interval: str = "1d",
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        cadence: str = "monthly",
    ) -> pd.DataFrame:
        """Every bar the bucket holds for `symbol`, concatenated and de-duplicated.

        Missing periods are skipped with a warning rather than raising: a pair
        delisted mid-history has real holes, and refusing to load it would
        reintroduce exactly the survivorship bias the bucket lets us avoid.
        """
        frames = []
        for period in self.periods(symbol, interval, cadence):
            if not _period_in_range(period, start, end):
                continue
            key = kline_key(symbol, interval, period, cadence, self.market)
            try:
                payload = self.source.read(key)
            except FileNotFoundError:
                log.warning("%s listed in the bucket but not readable; skipped", key)
                continue
            if self.verify:
                self._verify(key, payload)
            frames.append(parse_klines(payload, symbol))
        if not frames:
            return _empty_klines()
        out = pd.concat(frames).sort_index()
        out = out[~out.index.duplicated(keep="last")]
        if start is not None:
            out = out[out.index >= pd.Timestamp(start, tz="UTC")]
        if end is not None:
            out = out[out.index <= pd.Timestamp(end, tz="UTC")]
        out.attrs["symbol"] = symbol
        out.attrs["interval"] = interval
        return out

    def _verify(self, key: str, payload: bytes) -> None:
        checksum_key = f"{key}.CHECKSUM"
        if not self.source.exists(checksum_key):
            return
        if not verify_checksum(payload, self.source.read(checksum_key)):
            raise BucketError(f"{key} does not match its published SHA-256 checksum")


def _quote_asset(symbol: str) -> str:
    for quote in ("USDT", "FDUSD", "BUSD", "USDC", "TUSD", "BTC", "ETH", "BNB", "EUR", "TRY"):
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return quote
    return ""


def _period_in_range(period: str, start, end) -> bool:
    stamp = pd.Timestamp(period if len(period) > 7 else period + "-01", tz="UTC")
    month_end = stamp + (pd.offsets.MonthEnd(1) if len(period) <= 7 else pd.Timedelta(days=1))
    if start is not None and month_end < pd.Timestamp(start, tz="UTC"):
        return False
    if end is not None and stamp > pd.Timestamp(end, tz="UTC"):
        return False
    return True
