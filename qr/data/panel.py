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

#: `close_unadjusted` is the price that actually changed hands, kept alongside
#: the dividend-adjusted `close` because share counts, a per-share commission
#: and a broker's per-order minimum all key off the former while every return
#: in the book comes from the latter. A source that has no such distinction
#: (crypto) simply does not carry the column, and `from_frames` drops any field
#: that is not present for every symbol.
#: `funding_rate`, `open_interest` and `open_interest_usd` come from the
#: perpetual market rather than from the bars themselves — see
#: `qr/data/funding.py`. They are features *about* a spot pair, never a licence
#: to trade the perp, and they are absent from any panel that was not joined
#: to them.
FIELDS = (
    "open", "high", "low", "close", "close_unadjusted", "volume", "quote_volume", "trades",
    "funding_rate", "open_interest", "open_interest_usd",
    # the carry unit (qr/data/carry.py): the perp's own rate, and perp/spot - 1
    "perp_funding_rate", "basis", "spot_close",
    # the auction instrument (qr/data/auction.py): the session's real open and
    # close, split nights, and the closing-cross snapshots at each cutoff
    "session_open", "session_close", "split_night",
    "imb_1550", "imb_1555", "imb_1558",
    "paired_usd_1550", "paired_usd_1555", "paired_usd_1558",
    "imb_age_1550", "imb_age_1555", "imb_age_1558",
    # the two-bars-a-session instrument (qr/data/intraday.py)
    "ret_to_decision", "is_late",
)


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
        # A bar whose quote volume implies a VWAP outside its own range did not
        # happen either. The perp archive has 24 such bars in 637,705 (19 pairs,
        # five dates in September and November 2023; quote volume about 1.5x
        # too large). Same 5% tolerance as `qa.check_klines`, and only where
        # the bar traded, so a zero-volume bar is judged by the rules above.
        if quote is not None and volume is not None and high is not None and low is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                vwap = quote / volume
            traded = volume > 0
            outside = traded & ((vwap < low * 0.95) | (vwap > high * 1.05))
            mask &= ~outside.fillna(False)
        return mask

    #: Bars per year, for annualising.
    #:
    #: Crypto trades every day of the year; an equity or ETF panel holds only
    #: exchange sessions, about 252 of them. Annualising a stock series by 365
    #: multiplies its Sharpe by sqrt(365/252) = 1.20 — a 20% overstatement that
    #: no gate would catch, because every number downstream is consistent with
    #: it. So the figure is measured off the index rather than assumed, and the
    #: nominal value below is kept only as the answer for a panel too short to
    #: measure, and as the value returned when measurement agrees with it (so a
    #: crypto panel reads exactly 365, not 364.8).
    NOMINAL_PERIODS = {"1d": 365.0, "1h": 365.0 * 24, "4h": 365.0 * 6, "1w": 52.0}

    @property
    def periods_per_year(self) -> float:
        nominal = self.NOMINAL_PERIODS[self.interval]
        index = self.index
        if len(index) < 60:
            return nominal
        span = (index[-1] - index[0]).total_seconds()
        if span <= 0:
            return nominal
        measured = (len(index) - 1) * (365.25 * 24 * 3600) / span
        if abs(measured - nominal) <= 0.05 * nominal:
            return nominal
        return float(measured)
