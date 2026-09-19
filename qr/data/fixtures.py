"""Synthetic Binance bucket mirrors, in the bucket's exact layout.

The cloud sandbox cannot reach data.binance.vision, so every loader test runs
against a mirror built here: real zip archives, real 12-column kline CSVs,
real `.CHECKSUM` files, real `YYYY-MM` monthly partitioning, and the real
millisecond-to-microsecond timestamp switch on 2025-01-01. The only thing
synthetic is the price path.

`qr data pull` on the laptop writes the same layout with the real bytes, so
code that works against a fixture works against the bucket unchanged.
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from qr.data.binance import KLINE_COLUMNS, MICROSECOND_SWITCH, LocalBucket, kline_key


@dataclass(frozen=True)
class SyntheticPair:
    """One pair to plant in a mirror."""

    symbol: str
    start: str
    end: str
    price: float = 100.0
    drift: float = 0.0
    vol: float = 0.03
    quote_volume: float = 1e8
    seed: int = 0


def make_klines(pair: SyntheticPair, interval: str = "1d") -> pd.DataFrame:
    """A deterministic geometric random walk shaped like a Binance kline frame."""
    freq = {"1d": "D", "1h": "h"}[interval]
    index = pd.date_range(pair.start, pair.end, freq=freq, tz="UTC")
    rng = np.random.default_rng(pair.seed)
    step = pair.vol / (1.0 if interval == "1d" else 24**0.5)
    returns = rng.normal(pair.drift, step, len(index))
    close = pair.price * np.exp(np.cumsum(returns))
    open_ = np.concatenate([[pair.price], close[:-1]])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, step / 4, len(index))))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, step / 4, len(index))))
    quote = pair.quote_volume * np.exp(rng.normal(0, 0.2, len(index)))
    base = quote / close
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": base,
            "quote_volume": quote,
            "trades": np.maximum(1, (quote / 5_000).astype(int)),
            "taker_buy_base": base * 0.5,
            "taker_buy_quote": quote * 0.5,
        },
        index=index,
    )


def _epoch(index: pd.DatetimeIndex) -> np.ndarray:
    """Milliseconds before the 2025-01-01 switch, microseconds from it — as the
    bucket really does it, so the loader's unit detection is exercised."""
    micros = index.as_unit("us").asi8
    switch = pd.Timestamp(MICROSECOND_SWITCH, tz="UTC")
    is_us = np.asarray(index >= switch)
    return np.where(is_us, micros, micros // 1_000)


def kline_csv(frame: pd.DataFrame, interval: str = "1d", header: bool = False) -> bytes:
    """Render a canonical frame back into the bucket's raw 12-column CSV."""
    span = {"1d": pd.Timedelta(days=1), "1h": pd.Timedelta(hours=1)}[interval]
    close_index = pd.DatetimeIndex(frame.index + span - pd.Timedelta(milliseconds=1))
    raw = pd.DataFrame(
        {
            "open_time": _epoch(pd.DatetimeIndex(frame.index)),
            "open": frame["open"],
            "high": frame["high"],
            "low": frame["low"],
            "close": frame["close"],
            "volume": frame["volume"],
            "close_time": _epoch(close_index),
            "quote_volume": frame["quote_volume"],
            "trades": frame["trades"],
            "taker_buy_base": frame["taker_buy_base"],
            "taker_buy_quote": frame["taker_buy_quote"],
            "ignore": 0,
        }
    )[KLINE_COLUMNS]
    return raw.to_csv(index=False, header=header).encode("utf-8")


def zip_bytes(name: str, payload: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, payload)
    return buf.getvalue()


def build_mirror(
    root: Path,
    pairs: list[SyntheticPair],
    interval: str = "1d",
    cadence: str = "monthly",
    market: str = "spot",
    checksums: bool = True,
) -> LocalBucket:
    """Write a full mirror and return the `LocalBucket` that reads it."""
    bucket = LocalBucket(Path(root))
    for pair in pairs:
        frame = make_klines(pair, interval)
        for period, chunk in frame.groupby(frame.index.strftime("%Y-%m" if cadence == "monthly" else "%Y-%m-%d")):
            # Binance added a header row to these files during 2025.
            header = period >= "2025-01"
            csv = kline_csv(chunk, interval, header=header)
            key = kline_key(pair.symbol, interval, str(period), cadence, market)
            archive = zip_bytes(f"{pair.symbol}-{interval}-{period}.csv", csv)
            bucket.write(key, archive)
            if checksums:
                digest = hashlib.sha256(archive).hexdigest()
                bucket.write(f"{key}.CHECKSUM", f"{digest}  {Path(key).name}\n".encode())
    return bucket
