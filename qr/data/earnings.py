"""E4's events: earnings 8-Ks (Item 2.02) with EDGAR acceptance times.

Read from the cached submissions pages (`mirror/sec/submissions/`, fetched
for the Form 4 work), which list every filing of an issuer with its form,
items and `acceptanceDateTime`. An 8-K carrying item 2.02 ("Results of
Operations and Financial Condition") is the earnings release; its acceptance
time is when the market could read it, so `published_at` = acceptance and a
signal computed at time t may use only events with `published_at <= t`.

The ticker at the time comes from the Form 4 data sets' issuer symbol for
the same CIK nearest the event date (`reference/form4_purchases.parquet`),
because the submissions page carries only today's tickers.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def earnings_events(cache_dir: str | Path, tickers_by_cik: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = []
    for path in sorted(Path(cache_dir).glob("CIK*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            continue
        cik = str(data.get("cik") or path.name[3:13]).lstrip("0")
        blocks = []
        if "filings" in data:
            blocks.append(data["filings"].get("recent", {}))
        elif "accessionNumber" in data:  # an older-filings page
            blocks.append(data)
            cik = path.name[3:13].lstrip("0")
        for b in blocks:
            forms, items, acc, stamps = b.get("form", []), b.get("items", []), b.get("accessionNumber", []), b.get("acceptanceDateTime", [])
            for i in range(len(forms)):
                if forms[i] in ("8-K", "8-K/A") and "2.02" in str(items[i] if i < len(items) else ""):
                    rows.append({"cik": cik, "accession": acc[i], "form": forms[i], "published_at": stamps[i] if i < len(stamps) else None, "report_date": b.get("reportDate", [None] * len(forms))[i]})
    frame = pd.DataFrame(rows).drop_duplicates("accession")
    frame["published_at"] = pd.to_datetime(frame["published_at"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["published_at"]).sort_values("published_at")
    frame["is_amendment"] = frame["form"].str.endswith("/A")
    if tickers_by_cik is not None:
        frame = frame.merge(_nearest_ticker(frame, tickers_by_cik), on=["cik", "accession"], how="left")
    return frame.reset_index(drop=True)


def _nearest_ticker(events: pd.DataFrame, tickers: pd.DataFrame) -> pd.DataFrame:
    """Ticker as of the event: the Form 4 issuer symbol of the same CIK nearest in time."""
    t = tickers.copy()
    t["cik"] = t["issuer_cik"].astype(str).str.lstrip("0")
    t["stamp"] = pd.to_datetime(t["filing_date"], utc=True)
    t = t.dropna(subset=["stamp"]).sort_values("stamp")[["cik", "stamp", "symbol"]]
    e = events[["cik", "accession", "published_at"]].sort_values("published_at").rename(columns={"published_at": "stamp"})
    merged = pd.merge_asof(e, t, on="stamp", by="cik", direction="nearest", tolerance=pd.Timedelta(days=400))
    return merged[["cik", "accession", "symbol"]]
