"""The Parquet lake and its DuckDB manifest.

Layout (hive-partitioned, so DuckDB and Polars can both read it directly):

    lake/raw/<source>/<market>/klines/interval=<i>/symbol=<S>/data.parquet
    lake/reference/<name>.parquet
    lake/manifest.db                  DuckDB: one row per artefact written

The manifest is what makes a backtest reproducible. Every file written is
recorded with its SHA-256, its row count and its time span, and
`manifest_hash()` folds all of those into one hash. That hash goes into the
trial log with every run, so a Hypothesis Report can always answer "which
bytes was this computed on" — and changing any byte of the lake changes it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

from qr.config import Paths, paths as default_paths
from qr.data.panel import Panel

MANIFEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS manifest (
    dataset     VARCHAR NOT NULL,
    source      VARCHAR NOT NULL,
    market      VARCHAR,
    symbol      VARCHAR,
    interval    VARCHAR,
    path        VARCHAR NOT NULL,
    rows        BIGINT  NOT NULL,
    bytes       BIGINT  NOT NULL,
    sha256      VARCHAR NOT NULL,
    first_ts    TIMESTAMPTZ,
    last_ts     TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (dataset, path)
);
"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class Lake:
    """Writes Parquet, records it in the manifest, reads it back as a `Panel`."""

    paths: Paths = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.paths = (self.paths or default_paths()).ensure()
        with self._db() as con:
            con.execute(MANIFEST_SCHEMA)

    def _db(self):
        return duckdb.connect(str(self.paths.manifest_db))

    # -- writing -----------------------------------------------------------

    def kline_path(self, symbol: str, interval: str, source: str = "binance", market: str = "spot") -> Path:
        return (
            self.paths.raw
            / source
            / market
            / "klines"
            / f"interval={interval}"
            / f"symbol={symbol}"
            / "data.parquet"
        )

    def write_klines(
        self,
        symbol: str,
        frame: pd.DataFrame,
        interval: str = "1d",
        source: str = "binance",
        market: str = "spot",
    ) -> Path:
        """Write one symbol's bars and record them. Rewriting replaces the row."""
        path = self.kline_path(symbol, interval, source, market)
        path.parent.mkdir(parents=True, exist_ok=True)
        out = frame.copy()
        out.index.name = "open_time"
        out.reset_index().to_parquet(path, index=False, compression="zstd")
        self._record(
            dataset="klines",
            source=source,
            market=market,
            symbol=symbol,
            interval=interval,
            path=path,
            rows=len(frame),
            first_ts=frame.index.min() if len(frame) else None,
            last_ts=frame.index.max() if len(frame) else None,
        )
        return path

    def write_reference(self, name: str, frame: pd.DataFrame, source: str = "binance") -> Path:
        path = self.paths.reference / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False, compression="zstd")
        self._record(
            dataset=f"reference/{name}",
            source=source,
            market=None,
            symbol=None,
            interval=None,
            path=path,
            rows=len(frame),
            first_ts=None,
            last_ts=None,
        )
        return path

    def _record(self, dataset: str, source: str, market, symbol, interval, path: Path, rows: int, first_ts, last_ts) -> None:
        rel = str(path.relative_to(self.paths.root))
        row = (
            dataset,
            source,
            market,
            symbol,
            interval,
            rel,
            int(rows),
            path.stat().st_size,
            sha256_file(path),
            _ts(first_ts),
            _ts(last_ts),
            datetime.now(timezone.utc),
        )
        with self._db() as con:
            con.execute("DELETE FROM manifest WHERE dataset = ? AND path = ?", [dataset, rel])
            con.execute("INSERT INTO manifest VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", list(row))

    # -- reading -----------------------------------------------------------

    def manifest(self) -> pd.DataFrame:
        with self._db() as con:
            return con.execute("SELECT * FROM manifest ORDER BY dataset, path").fetch_df()

    def manifest_hash(self) -> str:
        """One hash over every artefact in the lake — the data version of a run."""
        with self._db() as con:
            rows = con.execute(
                "SELECT dataset, path, rows, sha256 FROM manifest ORDER BY dataset, path"
            ).fetchall()
        digest = hashlib.sha256()
        for dataset, path, nrows, sha in rows:
            digest.update(f"{dataset}|{path}|{nrows}|{sha}\n".encode())
        return digest.hexdigest()

    def symbols(self, interval: str = "1d", source: str = "binance", market: str = "spot") -> list[str]:
        with self._db() as con:
            rows = con.execute(
                """SELECT symbol FROM manifest
                   WHERE dataset = 'klines' AND interval = ? AND source = ? AND market = ?
                   ORDER BY symbol""",
                [interval, source, market],
            ).fetchall()
        return [r[0] for r in rows]

    def read_klines(
        self,
        symbol: str,
        interval: str = "1d",
        start=None,
        end=None,
        source: str = "binance",
        market: str = "spot",
    ) -> pd.DataFrame:
        path = self.kline_path(symbol, interval, source, market)
        if not path.exists():
            raise FileNotFoundError(f"{symbol} {interval} is not in the lake at {path}")
        frame = pd.read_parquet(path).set_index("open_time").sort_index()
        if start is not None:
            frame = frame[frame.index >= pd.Timestamp(start, tz="UTC")]
        if end is not None:
            frame = frame[frame.index <= pd.Timestamp(end, tz="UTC")]
        return frame

    def load_panel(
        self,
        symbols: Iterable[str] | None = None,
        interval: str = "1d",
        start=None,
        end=None,
        source: str = "binance",
        market: str = "spot",
    ) -> Panel:
        names = list(symbols) if symbols is not None else self.symbols(interval, source, market)
        frames = {s: self.read_klines(s, interval, start, end, source, market) for s in names}
        frames = {s: f for s, f in frames.items() if len(f)}
        if not frames:
            raise ValueError("no symbols in the lake match that query")
        panel = Panel.from_frames(frames, interval=interval)
        return self._attach_perp_features(panel, interval, start, end, source, market)

    def _attach_perp_features(self, panel, interval, start, end, source, market):
        """Join perp funding and open interest onto a spot panel, if ingested.

        Silent when there is nothing to join, because every command that loaded
        a panel before this existed must keep working unchanged — and loudly
        absent otherwise: a strategy that needs funding raises rather than
        holding nothing, since a book holding nothing for want of a column
        looks exactly like a book that found no signal.
        """
        from qr.data.funding import MARKET, attach

        if market == MARKET or source != "binance":
            return panel
        # A panel that already carries `funding_rate` is one that defined it
        # itself — the carry unit (`qr/data/carry.py`) stores the rate with
        # the short leg's sign, and joining the raw perp feature over it
        # would flip a receipt back into a payment. Found by the carry
        # round-trip test on 2026-09-15: the file on disk was right and the
        # loaded panel was wrong.
        if "funding_rate" in panel.fields:
            return panel
        available = set(self.symbols("1d", source, MARKET))
        wanted = [s for s in panel.symbols if s in available]
        if not wanted:
            return panel
        features = {}
        for symbol in wanted:
            try:
                features[symbol] = self.read_klines(symbol, "1d", start, end, source, MARKET)
            except FileNotFoundError:
                continue
        panel = attach(panel, features)
        if market == "futures/um":
            from qr.data.unlocks import attach_unlocks

            panel = attach_unlocks(panel, self, start, end)
        return panel


def _ts(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    stamp = pd.Timestamp(value)
    return (stamp.tz_localize("UTC") if stamp.tz is None else stamp).to_pydatetime()
