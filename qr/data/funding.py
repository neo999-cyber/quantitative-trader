"""Perpetual funding and open interest, from Binance's public data bucket.

Three autopilot nights produced twelve candidates and twelve kills, and ten of
them failed on **access** rather than on the idea (`docs/15`). The single most
repeated objection was this one:

> "the transfer is real but structurally out of reach: funding is paid on
> perps"

That is the right objection and it names two different problems, which this
module addresses one of. A spot book genuinely cannot *collect* funding — that
needs a perpetual, a margin model and Phase 4. But it can *see* funding, and
what funding says is where the leveraged crowd is and what it is paying to
stay there. That is a point-in-time feature about positioning, available free,
and nothing in this project could read it.

## What it is

Funding is paid every eight hours between the two sides of a perpetual. When
it is **positive**, longs pay shorts: the crowd is long and paying to stay
there. When it is **negative**, shorts pay longs. The payer is real, the
obligation is contractual, and the size of the payment is a direct measure of
how one-sided the book has become.

Open interest is the other half: funding says which way the crowd leans, open
interest says how much of it there is. A large negative funding rate on a
shrinking open interest is a squeeze ending; on a growing one it is a squeeze
building.

## The claim this does and does not support

It supports: *"the levered crowd is positioned this way and paying for it"* as
a **feature** on a spot book. It does not support "collect the funding" — no
spot position earns it, and any memo proposing otherwise should be killed at
question 1 for naming a payer whose payment it cannot receive.

## Timing, and why there is no lookahead here

Funding settles at 00:00, 08:00 and 16:00 UTC. The daily aggregate for day *D*
is therefore complete by 16:00 on *D*, before the daily bar closes, so a
feature computed from day *D* and traded on *D+1* — which is what the runner's
one-bar lag enforces — uses nothing it could not have known. `daily_funding`
sums within the UTC day rather than taking a last value, because what a
position pays over a day is the sum of its three settlements and the
individual settlements are not separately interesting.

## What the first real pull found

The bucket paths and CSV column names were written from Binance's published
layout without ever meeting the live bucket, and the first real pull (14
September 2026) confirmed them: 40 symbols, funding and metrics files, no
missing-column error.

One thing was wrong and it was the timestamps. `fundingRate` carries epoch
integers like the klines; **`metrics` carries formatted datetimes**, and the
ingest died on `to_utc` refusing `create_time` as non-numeric. `_timestamps`
now takes either and still refuses anything else, quoting the value — a
timestamp coerced to NaT is a row silently dropped from a feature, and a
feature with undeclared holes is worse than a loader that stops.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

import numpy as np
import pandas as pd

from qr.data.binance import BucketError, BucketSource, to_utc

#: Binance publishes USD-margined perpetual data under `futures/um`.
MARKET = "futures-um"

#: Columns this project needs from each file. Extra columns are ignored; a
#: missing one is an error that quotes what did arrive.
FUNDING_COLUMNS = ("calc_time", "last_funding_rate")
METRICS_COLUMNS = ("create_time", "sum_open_interest", "sum_open_interest_value")


def funding_prefix(symbol: str, cadence: str = "monthly") -> str:
    return f"data/futures/um/{cadence}/fundingRate/{symbol}/"


def funding_key(symbol: str, period: str, cadence: str = "monthly") -> str:
    return f"{funding_prefix(symbol, cadence)}{symbol}-fundingRate-{period}.zip"


def metrics_prefix(symbol: str, cadence: str = "daily") -> str:
    return f"data/futures/um/{cadence}/metrics/{symbol}/"


def metrics_key(symbol: str, period: str, cadence: str = "daily") -> str:
    return f"{metrics_prefix(symbol, cadence)}{symbol}-metrics-{period}.zip"


def _unzip(payload: bytes) -> bytes:
    if payload[:2] != b"PK":
        return payload
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise BucketError(f"expected one CSV in the archive, found {names}")
        return zf.read(names[0])


def _read_csv(payload: bytes, required: tuple[str, ...], what: str) -> pd.DataFrame:
    """Parse a bucket CSV, insisting on the columns this project reads.

    Header sniffing follows `parse_klines`: these files are documented as
    having a header, but a header row silently parsed as data becomes a NaN
    observation that survives all the way to a backtest, so it is worth the
    check rather than the assumption.
    """
    body = _unzip(payload)
    if not body.strip():
        return pd.DataFrame(columns=list(required))
    first = body.split(b"\n", 1)[0].split(b",", 1)[0].strip()
    has_header = not re.fullmatch(rb"-?\d+(\.\d+)?([eE][-+]?\d+)?", first)
    if not has_header:
        raise BucketError(
            f"{what} file has no header row, so its columns cannot be identified. "
            f"First field was {first!r}. The parser needs {list(required)}."
        )
    frame = pd.read_csv(io.BytesIO(body))
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise BucketError(
            f"{what} file is missing {missing}. It carries {list(frame.columns)}. "
            f"The paths and column names in qr/data/funding.py are written from Binance's "
            f"published layout and have never been checked against the live bucket — if this "
            f"is the first pull, the list above is the correction to make."
        )
    return frame


def _timestamps(values, what: str) -> pd.DatetimeIndex:
    """Bucket timestamps, whichever of the two shapes this file uses.

    The kline and fundingRate files carry epoch integers. The **metrics** files
    do not — `create_time` is a formatted datetime like `2024-01-01 00:00:00`,
    and the first real ingest died on `to_utc` refusing it as non-numeric. The
    paths and columns were right; only this was wrong.

    Numeric first, because that is the format with the millisecond/microsecond
    ambiguity `to_utc` exists to resolve. Strings second. Anything else raises
    with the offending value quoted, because a timestamp coerced to NaT becomes
    a row silently dropped from a feature, and a feature with holes nobody
    declared is worse than a loader that stops.
    """
    series = pd.Series(np.asarray(values))
    numeric = pd.to_numeric(series, errors="coerce")
    if not numeric.isna().any():
        return to_utc(series)

    parsed = pd.to_datetime(series, errors="coerce", utc=True, format="mixed")
    if parsed.isna().any():
        bad = series[parsed.isna()].iloc[0]
        raise BucketError(
            f"{what} file has a timestamp this loader cannot read: {bad!r}. It is neither "
            f"an epoch integer nor a datetime string."
        )
    return pd.DatetimeIndex(parsed)


def parse_funding(payload: bytes, symbol: str | None = None) -> pd.DataFrame:
    """One `fundingRate` file -> a UTC-indexed frame with `funding_rate`."""
    frame = _read_csv(payload, FUNDING_COLUMNS, "fundingRate")
    if frame.empty:
        idx = pd.DatetimeIndex([], tz="UTC", name="calc_time")
        return pd.DataFrame({"funding_rate": pd.Series(dtype=float)}, index=idx)
    # `.to_numpy()`, not the Series: handing pandas a Series alongside a
    # different `index=` reindexes it onto that index rather than assigning
    # positionally, and since the source index is 0..n and the target is
    # timestamps, every value silently becomes NaN. A test caught it; the
    # parser would otherwise have produced a column of nothing.
    out = pd.DataFrame(
        {
            "funding_rate": pd.to_numeric(frame["last_funding_rate"], errors="coerce")
            .astype(float)
            .to_numpy()
        },
        index=_timestamps(frame["calc_time"], "fundingRate"),
    )
    out.index.name = "calc_time"
    if out["funding_rate"].isna().any():
        raise BucketError("fundingRate file contains a non-numeric rate")
    if symbol is not None:
        out.attrs["symbol"] = symbol
    return out[~out.index.duplicated(keep="last")].sort_index()


def parse_metrics(payload: bytes, symbol: str | None = None) -> pd.DataFrame:
    """One `metrics` file -> `open_interest` and `open_interest_usd`."""
    frame = _read_csv(payload, METRICS_COLUMNS, "metrics")
    if frame.empty:
        idx = pd.DatetimeIndex([], tz="UTC", name="create_time")
        return pd.DataFrame(
            {"open_interest": pd.Series(dtype=float), "open_interest_usd": pd.Series(dtype=float)},
            index=idx,
        )
    out = pd.DataFrame(
        {
            "open_interest": pd.to_numeric(frame["sum_open_interest"], errors="coerce")
            .astype(float)
            .to_numpy(),
            "open_interest_usd": pd.to_numeric(frame["sum_open_interest_value"], errors="coerce")
            .astype(float)
            .to_numpy(),
        },
        index=_timestamps(frame["create_time"], "metrics"),
    )
    out.index.name = "create_time"
    if symbol is not None:
        out.attrs["symbol"] = symbol
    return out[~out.index.duplicated(keep="last")].sort_index()


# ------------------------------------------------------------- daily features


def daily_funding(frame: pd.DataFrame) -> pd.Series:
    """The funding a position paid over each UTC day: the **sum** of settlements.

    A sum rather than a mean or a last value, because the quantity with a
    meaning is what changed hands. Three settlements of 0.01% cost a long 0.03%
    that day, and a day that settled twice because the venue skipped one is
    honestly cheaper rather than artificially averaged back up.
    """
    if frame.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC", name="open_time"))
    daily = frame["funding_rate"].groupby(frame.index.floor("D")).sum()
    daily.index.name = "open_time"
    return daily.astype(float)


def daily_open_interest(frame: pd.DataFrame) -> pd.DataFrame:
    """Open interest as of each UTC day's **last** observation.

    A stock, not a flow: the last reading of the day is the position that was
    open going into the next one, which is what a next-day signal acts on.
    """
    if frame.empty:
        idx = pd.DatetimeIndex([], tz="UTC", name="open_time")
        return pd.DataFrame(
            {"open_interest": pd.Series(dtype=float), "open_interest_usd": pd.Series(dtype=float)},
            index=idx,
        )
    daily = frame.groupby(frame.index.floor("D")).last()
    daily.index.name = "open_time"
    return daily.astype(float)


def combine(funding: pd.DataFrame, metrics: pd.DataFrame | None = None) -> pd.DataFrame:
    """One symbol's daily perp features, as the lake stores them."""
    out = pd.DataFrame({"funding_rate": daily_funding(funding)})
    if metrics is not None and not metrics.empty:
        out = out.join(daily_open_interest(metrics), how="outer")
    out.index.name = "open_time"
    return out.sort_index()


# -------------------------------------------------------------------- loading


@dataclass(frozen=True)
class FundingBucket:
    """Reads perp funding and metrics out of a bucket, local mirror or HTTP."""

    source: BucketSource

    def symbols(self, cadence: str = "monthly") -> list[str]:
        prefix = f"data/futures/um/{cadence}/fundingRate/"
        return sorted(p.rstrip("/").rsplit("/", 1)[-1] for p in self.source.list_prefixes(prefix))

    def periods(self, symbol: str, cadence: str = "monthly") -> list[str]:
        keys = self.source.list_keys(funding_prefix(symbol, cadence))
        return sorted({_period_of(k) for k in keys if k.endswith(".zip")})

    def load_funding(self, symbol: str, cadence: str = "monthly") -> pd.DataFrame:
        frames = [
            parse_funding(self.source.read(funding_key(symbol, period, cadence)), symbol)
            for period in self.periods(symbol, cadence)
        ]
        if not frames:
            return parse_funding(b"", symbol)
        return pd.concat(frames).sort_index().pipe(lambda f: f[~f.index.duplicated(keep="last")])

    def load_metrics(self, symbol: str, cadence: str = "daily") -> pd.DataFrame:
        keys = [k for k in self.source.list_keys(metrics_prefix(symbol, cadence)) if k.endswith(".zip")]
        frames = [parse_metrics(self.source.read(k), symbol) for k in sorted(keys)]
        if not frames:
            return parse_metrics(b"", symbol)
        return pd.concat(frames).sort_index().pipe(lambda f: f[~f.index.duplicated(keep="last")])


_PERIOD_RE = re.compile(r"-(\d{4}-\d{2}(?:-\d{2})?)\.zip$")


def _period_of(key: str) -> str:
    match = _PERIOD_RE.search(key)
    if not match:
        raise BucketError(f"cannot read a period out of key {key!r}")
    return match.group(1)


# --------------------------------------------------------------- the panel join


def attach(panel, features: dict[str, pd.DataFrame]):
    """Add per-symbol perp features to a spot panel, aligned to its index.

    The join is deliberately left-handed: the spot panel decides the index and
    the symbol set, and a perp series is reindexed onto it. A pair that trades
    spot but has no perp simply carries NaN, which every downstream ranking
    already handles, and a perp with history the spot pair does not have
    contributes nothing.

    The asymmetry is the honest one. This project trades spot; perp data is a
    *feature* about it, and a feature must never quietly extend the tradable
    universe to instruments the cost model has never priced.
    """
    from qr.data.panel import Panel

    if not features:
        return panel
    built = dict(panel.fields)
    index, symbols = panel.index, panel.symbols
    for field in ("funding_rate", "open_interest", "open_interest_usd"):
        columns = {}
        for symbol in symbols:
            frame = features.get(symbol)
            if frame is None or field not in frame.columns:
                columns[symbol] = pd.Series(np.nan, index=index)
            else:
                columns[symbol] = frame[field].reindex(index)
        merged = pd.DataFrame(columns, index=index, columns=symbols)
        if merged.notna().any().any():
            built[field] = merged
    return Panel(built, panel.interval)
