"""Paths and environment for the platform.

Everything the platform writes lives under one root so a run is reproducible
from a single directory: `QR_ROOT` (default: `<repo>/lake`).

    lake/
      raw/        immutable vendor bytes, hive-partitioned Parquet
      reference/  instruments, listing/delisting dates, calendars
      features/   versioned feature sets
      manifest.db DuckDB catalog: one row per ingested artefact
      trial_log.jsonl   append-only, hash-chained record of every run
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


@dataclass(frozen=True)
class Paths:
    """Resolved locations for everything the platform reads and writes."""

    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def reference(self) -> Path:
        return self.root / "reference"

    @property
    def features(self) -> Path:
        return self.root / "features"

    @property
    def manifest_db(self) -> Path:
        return self.root / "manifest.db"

    @property
    def trial_log(self) -> Path:
        return self.root / "trial_log.jsonl"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def flows(self) -> Path:
        """Append-only record of ETF share counts, one line per observation.

        Not under `raw/`, which is a mirror of something downloadable. This
        file cannot be re-fetched: every line is what was true on the day it
        was written, and that is the entire reason it is worth having.
        """
        return self.root / "flows" / "etf_shares_outstanding.jsonl"

    def ensure(self) -> "Paths":
        for p in (self.root, self.raw, self.reference, self.features, self.reports):
            p.mkdir(parents=True, exist_ok=True)
        return self


def paths(root: str | os.PathLike[str] | None = None) -> Paths:
    """The platform's paths, rooted at `root`, else `$QR_ROOT`, else `<repo>/lake`."""
    if root is not None:
        return Paths(Path(root).expanduser().resolve())
    return Paths(_env_path("QR_ROOT", REPO_ROOT / "lake"))


#: Where a local mirror of the Binance public data bucket lives on the laptop.
#: The cloud sandbox cannot reach data.binance.vision, so loaders read this
#: directory in the bucket's exact layout and `qr data pull` fills it.
def bucket_mirror(root: str | os.PathLike[str] | None = None) -> Path:
    if root is not None:
        return Path(root).expanduser().resolve()
    return _env_path("QR_BINANCE_MIRROR", paths().root / "mirror" / "binance")
