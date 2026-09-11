"""Stock universes.

The S&P 500 constituent list ships as a bundled snapshot (`sp500.csv`) so
scans work offline; `refresh_sp500()` pulls the live list from Wikipedia and
overwrites the snapshot when the network allows.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

_HERE = Path(__file__).parent
SP500_SNAPSHOT = _HERE / "sp500.csv"

# Instruments used by the macro regime checker (Yahoo Finance symbols).
REGIME_TICKERS = {
    "spy": "SPY",            # S&P 500 ETF
    "qqq": "QQQ",            # Nasdaq-100 ETF
    "vix": "^VIX",           # 30-day implied vol
    "vix3m": "^VIX3M",       # 3-month implied vol (term structure)
    "us10y": "^TNX",         # 10-year Treasury yield in percent (4.25 = 4.25%)
    "us3m": "^IRX",          # 13-week T-bill yield
    "dxy": "DX-Y.NYB",       # US Dollar Index
    "tlt": "TLT",            # 20+ year Treasury ETF (bonds vs stocks)
}


def sp500_tickers(path: Path | str = SP500_SNAPSHOT) -> list[str]:
    with open(path) as fh:
        rows = [ln.strip() for ln in fh if ln.strip()]
    if rows and rows[0].lower() == "ticker":
        rows = rows[1:]
    return rows


def refresh_sp500(path: Path | str = SP500_SNAPSHOT) -> list[str]:
    """Download the current constituent list from Wikipedia and save it."""
    import pandas as pd

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    table = next(t for t in tables if "Symbol" in t.columns)
    tickers = sorted(str(s).strip().replace(".", "-") for s in table["Symbol"])
    with open(path, "w") as fh:
        fh.write("ticker\n" + "\n".join(tickers) + "\n")
    log.info("refreshed S&P 500 snapshot: %d tickers", len(tickers))
    return tickers
