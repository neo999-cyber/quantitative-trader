"""Market data providers.

`MarketDataProvider` is the interface the screens depend on.  Three
implementations ship:

* `YFinanceProvider` - free daily data from Yahoo Finance with an on-disk
  CSV cache so a full S&P 500 scan only hits the network once a day.
* `CSVProvider`      - fully offline; reads `<dir>/<TICKER>.csv` files with
  Date,Open,High,Low,Close,Volume columns (what the cache writes).
* `SyntheticProvider` - deterministic random-walk data for tests and demos.
"""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Iterable, Protocol

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce a frame to the canonical OHLCV layout with a tz-naive DatetimeIndex."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=OHLCV)
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    rename = {c: c.title() for c in out.columns if isinstance(c, str)}
    out = out.rename(columns=rename)
    if "Adj Close" in out.columns and "Close" not in out.columns:
        out["Close"] = out["Adj Close"]
    missing = [c for c in OHLCV if c not in out.columns]
    if missing:
        raise ValueError(f"OHLCV frame missing columns: {missing}")
    out = out[OHLCV].astype(float)
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out.index.name = "Date"
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out.dropna(subset=["Close"])


class MarketDataProvider(Protocol):
    def history(self, ticker: str, years: int = 10) -> pd.DataFrame: ...

    def histories(self, tickers: Iterable[str], years: int = 10) -> dict[str, pd.DataFrame]: ...

    def next_earnings_date(self, ticker: str) -> dt.date | None: ...

    def insider_transactions(self, ticker: str) -> pd.DataFrame: ...

    def option_chain(self, ticker: str) -> pd.DataFrame: ...


# --------------------------------------------------------------------------- #
# Offline providers
# --------------------------------------------------------------------------- #
class CSVProvider:
    """Reads `<directory>/<TICKER>.csv`. Ticker names are matched case-insensitively."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def _path(self, ticker: str) -> Path | None:
        for cand in (f"{ticker}.csv", f"{ticker.upper()}.csv", f"{ticker.lower()}.csv"):
            p = self.directory / cand
            if p.is_file():
                return p
        return None

    def history(self, ticker: str, years: int = 10) -> pd.DataFrame:
        p = self._path(ticker)
        if p is None:
            return pd.DataFrame(columns=OHLCV)
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        df = normalize_ohlcv(df)
        cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=years)
        return df[df.index >= cutoff]

    def histories(self, tickers: Iterable[str], years: int = 10) -> dict[str, pd.DataFrame]:
        return {t: self.history(t, years) for t in tickers}

    def next_earnings_date(self, ticker: str) -> dt.date | None:
        p = self.directory / "earnings.csv"
        if not p.is_file():
            return None
        table = pd.read_csv(p)
        row = table[table["ticker"].str.upper() == ticker.upper()]
        if row.empty:
            return None
        return pd.to_datetime(row.iloc[0]["date"]).date()

    def insider_transactions(self, ticker: str) -> pd.DataFrame:
        p = self.directory / f"{ticker.upper()}_insiders.csv"
        return pd.read_csv(p, parse_dates=["Start Date"]) if p.is_file() else pd.DataFrame()

    def option_chain(self, ticker: str) -> pd.DataFrame:
        p = self.directory / f"{ticker.upper()}_options.csv"
        return pd.read_csv(p, parse_dates=["expiration"]) if p.is_file() else pd.DataFrame()


class SyntheticProvider:
    """Deterministic geometric random walks. Useful for tests and dry runs."""

    def __init__(self, seed: int = 7, days: int = 2600, start_price: float = 100.0):
        self.seed = seed
        self.days = days
        self.start_price = start_price

    def history(self, ticker: str, years: int = 10) -> pd.DataFrame:
        rng = np.random.default_rng(abs(hash((self.seed, ticker))) % (2**32))
        n = min(self.days, years * 252)
        idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
        rets = rng.normal(0.0004, 0.018, n)
        close = self.start_price * np.exp(np.cumsum(rets))
        spread = np.abs(rng.normal(0.01, 0.004, n))
        high = close * (1 + spread)
        low = close * (1 - spread)
        opn = np.concatenate([[close[0]], close[:-1]]) * (1 + rng.normal(0, 0.003, n))
        vol = rng.lognormal(mean=15.0, sigma=0.35, size=n)
        df = pd.DataFrame({"Open": opn, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)
        return normalize_ohlcv(df)

    def histories(self, tickers: Iterable[str], years: int = 10) -> dict[str, pd.DataFrame]:
        return {t: self.history(t, years) for t in tickers}

    def next_earnings_date(self, ticker: str) -> dt.date | None:
        return None

    def insider_transactions(self, ticker: str) -> pd.DataFrame:
        return pd.DataFrame()

    def option_chain(self, ticker: str) -> pd.DataFrame:
        return pd.DataFrame()


# --------------------------------------------------------------------------- #
# Yahoo Finance (free) with a daily CSV cache
# --------------------------------------------------------------------------- #
class YFinanceProvider:
    def __init__(self, cache_dir: str | Path = ".cache", max_cache_age_hours: float = 12.0):
        self.cache = Path(cache_dir) / "prices"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.max_age = dt.timedelta(hours=max_cache_age_hours)

    # -- helpers --------------------------------------------------------- #
    def _cache_path(self, ticker: str) -> Path:
        safe = ticker.replace("^", "_idx_").replace("=", "_").replace("/", "_")
        return self.cache / f"{safe}.csv"

    def _fresh(self, p: Path) -> bool:
        if not p.is_file():
            return False
        age = dt.datetime.now() - dt.datetime.fromtimestamp(p.stat().st_mtime)
        return age < self.max_age

    def _read_cache(self, ticker: str, years: int) -> pd.DataFrame | None:
        p = self._cache_path(ticker)
        if not self._fresh(p):
            return None
        df = normalize_ohlcv(pd.read_csv(p, index_col=0, parse_dates=True))
        cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=years)
        if len(df) and df.index[0] > cutoff + pd.Timedelta(days=10):
            return None  # cache does not go back far enough
        return df[df.index >= cutoff]

    def _write_cache(self, ticker: str, df: pd.DataFrame) -> None:
        if len(df):
            df.to_csv(self._cache_path(ticker))

    # -- interface ------------------------------------------------------- #
    def history(self, ticker: str, years: int = 10) -> pd.DataFrame:
        return self.histories([ticker], years).get(ticker, pd.DataFrame(columns=OHLCV))

    def histories(self, tickers: Iterable[str], years: int = 10) -> dict[str, pd.DataFrame]:
        import yfinance as yf

        tickers = list(dict.fromkeys(tickers))
        out: dict[str, pd.DataFrame] = {}
        to_fetch: list[str] = []
        for t in tickers:
            cached = self._read_cache(t, years)
            if cached is not None:
                out[t] = cached
            else:
                to_fetch.append(t)

        for i in range(0, len(to_fetch), 100):
            batch = to_fetch[i : i + 100]
            try:
                raw = yf.download(
                    batch,
                    period=f"{years}y",
                    interval="1d",
                    auto_adjust=True,
                    group_by="ticker",
                    progress=False,
                    threads=True,
                )
            except Exception as exc:  # network / API errors
                log.warning("yfinance download failed for %s tickers: %s", len(batch), exc)
                continue
            for t in batch:
                try:
                    sub = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                    df = normalize_ohlcv(sub)
                except Exception as exc:
                    log.warning("no data for %s: %s", t, exc)
                    df = pd.DataFrame(columns=OHLCV)
                out[t] = df
                self._write_cache(t, df)
        return out

    def next_earnings_date(self, ticker: str) -> dt.date | None:
        import yfinance as yf

        try:
            cal = yf.Ticker(ticker).calendar or {}
            dates = cal.get("Earnings Date") or []
            if isinstance(dates, (dt.date, dt.datetime, pd.Timestamp)):
                dates = [dates]
            today = dt.date.today()
            future = sorted(pd.Timestamp(d).date() for d in dates if pd.Timestamp(d).date() >= today)
            return future[0] if future else None
        except Exception as exc:
            log.warning("earnings date lookup failed for %s: %s", ticker, exc)
            return None

    def insider_transactions(self, ticker: str) -> pd.DataFrame:
        import yfinance as yf

        try:
            df = yf.Ticker(ticker).insider_transactions
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            log.warning("insider lookup failed for %s: %s", ticker, exc)
            return pd.DataFrame()

    def option_chain(self, ticker: str) -> pd.DataFrame:
        """All listed expirations flattened into one frame with an `expiration`
        and `type` (call/put) column."""
        import yfinance as yf

        tk = yf.Ticker(ticker)
        frames = []
        try:
            expirations = tk.options
        except Exception as exc:
            log.warning("option expirations lookup failed for %s: %s", ticker, exc)
            return pd.DataFrame()
        for exp in expirations:
            try:
                chain = tk.option_chain(exp)
            except Exception as exc:
                log.warning("option chain %s %s failed: %s", ticker, exp, exc)
                continue
            for kind, part in (("call", chain.calls), ("put", chain.puts)):
                part = part.copy()
                part["type"] = kind
                part["expiration"] = pd.Timestamp(exp)
                frames.append(part)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
