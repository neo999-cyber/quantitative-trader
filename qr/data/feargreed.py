"""The Crypto Fear & Greed index (alternative.me), as a point-in-time feature.

Adopted from the repo review in `docs/research/06_repo_reviews.md`. It is a
sentiment gauge published daily at roughly 00:00 UTC, built from volatility,
volume, social and dominance components, with history back to 2018-02-01.

Two disciplines apply, and both are enforced here rather than left to the
caller:

* **It enters as a feature, never as a trade.** Nothing in this module produces
  a position.
* **The value stamped with date D is published at the start of D and is
  therefore not usable for a decision taken before it.** `as_feature()` lags by
  one bar by default, which is the setting a backtest must use unless someone
  has checked the publication time against the venue's bar boundary.

The API is unreachable from the cloud sandbox, so `fetch()` takes a source:
`HttpFearGreed` on the laptop, `LocalFearGreed` (a cached JSON file) elsewhere.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

API_URL = "https://api.alternative.me/fng/"

#: The index's own five-way classification, kept as an ordered category.
CLASSIFICATIONS = [
    "Extreme Fear",
    "Fear",
    "Neutral",
    "Greed",
    "Extreme Greed",
]


class FearGreedSource(Protocol):
    def read(self) -> bytes: ...


@dataclass
class HttpFearGreed:
    """The live API. `limit=0` asks for the whole history in one call."""

    limit: int = 0
    timeout: int = 30
    session: object | None = None

    def read(self) -> bytes:
        if self.session is None:
            import requests

            self.session = requests.Session()
        resp = self.session.get(
            API_URL, params={"limit": self.limit, "format": "json"}, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.content


@dataclass
class LocalFearGreed:
    """A cached response on disk, in the API's exact JSON shape."""

    path: Path

    def read(self) -> bytes:
        return Path(self.path).read_bytes()


def parse(payload: bytes) -> pd.DataFrame:
    """API JSON -> a frame indexed by the UTC day the value describes."""
    raw = json.loads(payload)
    rows = raw.get("data", raw if isinstance(raw, list) else [])
    if not rows:
        return pd.DataFrame(
            {"fng_value": pd.Series(dtype=float), "fng_class": pd.Series(dtype="object")},
            index=pd.DatetimeIndex([], tz="UTC", name="date"),
        )
    frame = pd.DataFrame(rows)
    index = pd.DatetimeIndex(
        pd.to_datetime(frame["timestamp"].astype("int64"), unit="s", utc=True).dt.normalize(),
        name="date",
    )
    out = pd.DataFrame(
        {
            # .to_numpy(): the parsed rows carry a RangeIndex, and letting
            # pandas align that against the timestamp index silently NaNs
            # every value.
            "fng_value": frame["value"].astype(float).to_numpy(),
            "fng_class": frame.get(
                "value_classification", pd.Series(index=frame.index, dtype="object")
            ).to_numpy(),
        },
        index=index,
    )
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out["fng_class"] = pd.Categorical(out["fng_class"], categories=CLASSIFICATIONS, ordered=True)
    return out


def fetch(source: FearGreedSource) -> pd.DataFrame:
    return parse(source.read())


def as_feature(
    frame: pd.DataFrame, index: pd.DatetimeIndex, lag: int = 1, column: str = "fng_value"
) -> pd.Series:
    """Align the index onto a panel's bars, lagged so it is knowable at decision time.

    The index is put on the panel's own bars first (forward-filling a missed
    publication day with the last value actually published) and only then
    lagged, so `lag=1` means "one **bar** old" rather than "one publication
    old" — the two differ whenever the index skips a day, and only the former
    is what a decision taken at bar t could have seen.

    Bars before the index existed (it starts 2018-02-01) stay NaN; a strategy
    must treat that as "no signal", not as neutral.
    """
    if lag < 0:
        raise ValueError("a negative lag reads the future; use lag >= 0")
    series = frame[column]
    aligned = series.reindex(series.index.union(index)).ffill().reindex(index)
    return aligned.shift(lag).rename(column)


def normalised(frame: pd.DataFrame, index: pd.DatetimeIndex, lag: int = 1) -> pd.Series:
    """The index mapped to [-1, +1]: -1 extreme fear, +1 extreme greed."""
    return ((as_feature(frame, index, lag) - 50.0) / 50.0).rename("fng_normalised")
