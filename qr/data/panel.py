"""The `Panel`: several symbols' bars aligned on one time index.

Strategies see a panel, never a loader, so the same strategy code runs over a
bucket mirror, the Parquet lake or a synthetic fixture. Alignment is outer-join
on the time index with **no filling**: a pair that had not listed yet, or has
already delisted, is NaN there and must stay NaN. Forward-filling it is how a
backtest quietly starts trading a coin that did not exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

FIELDS = ("open", "high", "low", "close", "volume", "quote_volume", "trades")


@dataclass(frozen=True)
class Panel:
    """Aligned per-field frames, each indexed by bar open time (UTC) x symbol."""

    fields: Mapping[str, pd.DataFrame]
    interval: str = "1d"

    def __post_init__(self) -> None:
        if "close" not in self.fields:
            raise ValueError("a panel needs at least a `close` frame")
        index = self.close.index
        if getattr(index, "tz", None) is None:
            raise ValueError("panel index must be timezone-aware UTC")
        for name, frame in self.fields.items():
            if not frame.index.equals(index) or list(frame.columns) != list(self.close.columns):
                raise ValueError(f"field {name!r} is not aligned with `close`")

    # -- access ------------------------------------------------------------

    def __getitem__(self, field: str) -> pd.DataFrame:
        return self.fields[field]

    def get(self, field: str) -> pd.DataFrame | None:
        return self.fields.get(field)

    @property
    def close(self) -> pd.DataFrame:
        return self.fields["close"]

    @property
    def index(self) -> pd.DatetimeIndex:
        return self.close.index

    @property
    def symbols(self) -> list[str]:
        return list(self.close.columns)

    def __len__(self) -> int:
        return len(self.close)

    # -- construction ------------------------------------------------------

    @classmethod
    def from_frames(
        cls, frames: Mapping[str, pd.DataFrame], fields: Iterable[str] = FIELDS, interval: str = "1d"
    ) -> "Panel":
        """Build from `{symbol: bars}` as the bucket loader returns them."""
        symbols = sorted(frames)
        wanted = [f for f in fields if all(f in frames[s].columns for s in symbols)] if symbols else []
        if "close" not in wanted:
            raise ValueError("every symbol must carry a `close` column")
        index = pd.DatetimeIndex([], tz="UTC")
        for symbol in symbols:
            index = index.union(frames[symbol].index)
        index.name = "open_time"
        built = {
            field: pd.DataFrame(
                {s: frames[s][field].reindex(index) for s in symbols}, index=index, columns=symbols
            )
            for field in wanted
        }
        return cls(built, interval)

    def slice(self, start=None, end=None) -> "Panel":
        mask = pd.Series(True, index=self.index)
        if start is not None:
            mask &= self.index >= pd.Timestamp(start, tz="UTC")
        if end is not None:
            mask &= self.index <= pd.Timestamp(end, tz="UTC")
        return Panel({k: v.loc[mask.to_numpy()] for k, v in self.fields.items()}, self.interval)

    def select(self, symbols: Iterable[str]) -> "Panel":
        cols = [s for s in symbols if s in self.close.columns]
        return Panel({k: v[cols] for k, v in self.fields.items()}, self.interval)

    # -- derived -----------------------------------------------------------

    def returns(self) -> pd.DataFrame:
        """Simple close-to-close returns. NaN where either end is missing."""
        return self.close.pct_change(fill_method=None)

    def log_returns(self) -> pd.DataFrame:
        return np.log(self.close).diff()

    def tradable(self, min_quote_volume: float = 0.0) -> pd.DataFrame:
        """Where a bar is real: a price exists, it traded, and it is possible.

        This is the mask every strategy must intersect its positions with. It
        keeps a delisted pair out of the portfolio after its last bar without
        pretending it was never there, and it excludes bars whose values cannot
        be true.

        That last part is not hypothetical. Binance's published archive — whose
        SHA-256 checksums verify, so the corruption is upstream of this loader —
        contains bars with **negative** base volume (BTTUSDT, five bars in its
        first fortnight in 2019, when nominal volumes ran to 10^11 tokens) and
        bars whose high is below their own close (AUDUSDT, 2020-11-13). Six such
        bars in roughly 740,000 across 734 pairs.

        Excluding them rather than repairing them is deliberate: a repaired
        value is a number nobody measured, and it would propagate into a report
        that claims to be reproducible from the manifest hash. Excluding them
        rather than dropping the whole symbol is also deliberate: BTT's other
        1,078 bars are fine, and discarding a pair over five bad prints would
        quietly reintroduce the survivorship bias the bucket exists to avoid.
        """
        mask = self.close.notna() & (self.close > 0)
        quote = self.get("quote_volume")
        if quote is not None:
            mask &= quote.fillna(0.0) > min_quote_volume

        volume = self.get("volume")
        if volume is not None:
            mask &= volume.fillna(0.0) >= 0.0

        # A bar whose extremes do not bracket its own open and close is not a
        # bar. Checked only where the fields exist, and tolerant of float noise.
        high, low, open_ = self.get("high"), self.get("low"), self.get("open")
        if high is not None and low is not None:
            body = open_ if open_ is not None else self.close
            body_high = np.maximum(self.close, body)
            body_low = np.minimum(self.close, body)
            mask &= (high >= body_high * (1 - 1e-9)) | high.isna()
            mask &= (low <= body_low * (1 + 1e-9)) | low.isna()
        return mask

    #: Bars per year, for annualising. Crypto trades every day of the year.
    @property
    def periods_per_year(self) -> float:
        return {"1d": 365.0, "1h": 365.0 * 24, "4h": 365.0 * 6, "1w": 52.0}[self.interval]
