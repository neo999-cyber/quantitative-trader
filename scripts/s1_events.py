"""S1 events: S&P 500 index changes from Wikipedia's dated table, split into
discretionary deletions (the forced sale), additions (the mirror) and the
rest (M&A, bankruptcy, spin-offs: no seller at a price, excluded).

Reads no prices. Writes `docs/prereg/data/s1_sp500_changes.csv` (the raw
table, for provenance) and `qc/s1_events.b64` (avail_date, symbol, mode,
rank), the format `qc/s1_impl.py` loads, and prints the SHA-256 prefix the
implementation pins.

    .venv/bin/python scripts/s1_events.py

`avail_date` is the change's **effective date**: index funds sell at that
day's close, so the first session *after* it is the earliest a rule could
act on what it had seen. The announcement (usually 3-10 days earlier) is
not used: buying before the forced sale is a different, front-running
claim this family does not make.
"""
from __future__ import annotations

import base64
import hashlib
import io
import re
import urllib.request
import zlib
from pathlib import Path

import pandas as pd

URL = "https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500"
NOT_DISCRETIONARY = re.compile(
    r"acqui|merg|taken private|bought|purchas|spun|spin|bankrupt|chapter 11|delist|reorgan|combin|split|"
    r"went private|privat|buyout|tender|sold to|absorb|liquidat|dissol|convert|renam|was listed",
    re.I,
)


def fetch() -> pd.DataFrame:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=60).read().decode()
    table = pd.read_html(io.StringIO(html))[0]
    table.columns = ["effective_date", "added_ticker", "added_name", "removed_ticker", "removed_name", "reason", "refs"]
    table["effective_date"] = pd.to_datetime(table["effective_date"], errors="coerce")
    return table.drop(columns=["refs"]).dropna(subset=["effective_date"]).sort_values("effective_date")


def classify(table: pd.DataFrame) -> pd.DataFrame:
    reason = table["reason"].fillna("")
    removed = table["removed_ticker"].notna() & (table["removed_ticker"].astype(str).str.strip() != "")
    discretionary = removed & ~reason.str.contains(NOT_DISCRETIONARY)
    table = table.copy()
    table["deletion_discretionary"] = discretionary
    return table


def events(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in table.iterrows():
        avail = r["effective_date"].strftime("%Y-%m-%d")
        if r["deletion_discretionary"]:
            rows.append((avail, str(r["removed_ticker"]).strip(), "deletion", 1))
        if isinstance(r["added_ticker"], str) and r["added_ticker"].strip():
            rows.append((avail, r["added_ticker"].strip(), "addition", 1))
    out = pd.DataFrame(rows, columns=["avail_date", "symbol", "mode", "rank"])
    # one row per (date, symbol, mode); rank orders same-day names alphabetically (no information in it)
    out = out.drop_duplicates(["avail_date", "symbol", "mode"]).sort_values(["avail_date", "mode", "symbol"])
    out["rank"] = out.groupby(["avail_date", "mode"]).cumcount() + 1
    return out


def main() -> None:
    table = classify(fetch())
    Path("docs/prereg/data").mkdir(parents=True, exist_ok=True)
    table.to_csv("docs/prereg/data/s1_sp500_changes.csv", index=False)
    ev = events(table)
    csv = ev.to_csv(index=False)
    Path("qc/s1_events.b64").write_text(base64.b64encode(zlib.compress(csv.encode(), 9)).decode())
    digest = hashlib.sha256(csv.encode()).hexdigest()
    by_mode = ev.groupby("mode").size().to_dict()
    span = (ev["avail_date"].min(), ev["avail_date"].max())
    since_2007 = ev[ev["avail_date"] >= "2007-01-01"].groupby("mode").size().to_dict()
    print(f"changes {len(table)}; events {by_mode}; {span[0]} -> {span[1]}; from 2007: {since_2007}")
    print(f"EVENTS_SHA256_PREFIX = \"{digest[:16]}\"")


if __name__ == "__main__":
    main()
