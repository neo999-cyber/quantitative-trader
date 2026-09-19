"""FRED series, for the cash benchmark (`docs/20_PROGRAMME_2.md`, §10).

Gate 5 asks whether the best variant beats a benchmark once the search is paid
for. For a long-only spot book that benchmark is holding the universe; for a
book that is dollar-neutral, beta-neutral or a carry trade — nothing it holds
is "the market" — the right null is the risk-free rate, and this module is
where that rate comes from.

**DTB3** is the 3-month Treasury bill secondary-market rate, daily, in percent
per annum on a discount basis. It is published free by the St. Louis Fed
without a key at

    https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3

The discount basis understates the investment yield by a few basis points at
today's levels. That direction is the safe one: a benchmark set slightly too
low makes the gate slightly easier, by an amount an order of magnitude below
anything a verdict turns on, and it is stated here rather than corrected so
nobody later "fixes" it into a number that was never verified.

The file is cached in the lake as a reference table, so a report is
reproducible against the pull it was computed from and the manifest hash
changes when the series does.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
DEFAULT_SERIES = "DTB3"
REFERENCE_NAME = "risk_free_{series}"


def fetch(series: str = DEFAULT_SERIES, timeout: float = 30.0) -> str:
    """The raw CSV, as FRED serves it. Needs the network."""
    import requests

    response = requests.get(FRED_CSV.format(series=series), timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_fred_csv(text: str, series: str = DEFAULT_SERIES) -> pd.Series:
    """`observation_date,DTB3` rows to an annualised **decimal** rate.

    FRED writes a missing observation as a bare `.` (or leaves the cell
    empty, which pandas reads as NaN); those days are dropped
    rather than filled, because filling is the benchmark's job (it carries the
    last published rate forward) and a loader that fills quietly would hide
    how often the source is silent. Anything that is neither a number nor a
    `.` is an error that quotes the offending value.
    """
    frame = pd.read_csv(io.StringIO(text))
    columns = [c.strip() for c in frame.columns]
    frame.columns = columns
    date_col = next((c for c in columns if c.lower() in ("observation_date", "date")), None)
    if date_col is None or series not in columns:
        raise ValueError(f"expected columns observation_date and {series}; got {columns}")
    column = frame[series]
    raw = column.astype(str).str.strip()
    # FRED writes a missing day as `.` in the file and pandas reads a blank
    # cell as NaN; both are "not published", neither is a number.
    missing = (raw == ".") | (raw == "") | column.isna()
    values = pd.to_numeric(raw.where(~missing), errors="coerce")
    bad = column[values.isna() & ~missing]
    if len(bad):
        raise ValueError(f"{series} has non-numeric values: {bad.head(3).tolist()}")
    index = pd.DatetimeIndex(pd.to_datetime(frame[date_col]), name="date").tz_localize("UTC")
    out = pd.Series(values.to_numpy() / 100.0, index=index, name=series.lower())
    return out.dropna().sort_index()


def write_risk_free(lake, rates: pd.Series, series: str = DEFAULT_SERIES) -> Path:
    """Store the series as a reference table; returns the path written."""
    frame = pd.DataFrame({"date": rates.index, "rate": rates.to_numpy(), "series": series})
    return lake.write_reference(REFERENCE_NAME.format(series=series.lower()), frame, source="fred")


def load_risk_free(lake, series: str = DEFAULT_SERIES) -> pd.Series | None:
    """The stored series as a decimal annual rate, or None if never pulled."""
    path = lake.paths.reference / f"{REFERENCE_NAME.format(series=series.lower())}.parquet"
    if not path.exists():
        return None
    frame = pd.read_parquet(path)
    index = pd.DatetimeIndex(pd.to_datetime(frame["date"], utc=True), name="date")
    return pd.Series(frame["rate"].to_numpy(), index=index, name=series.lower()).sort_index()
