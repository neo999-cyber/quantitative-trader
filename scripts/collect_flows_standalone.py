#!/usr/bin/env python3
"""Record ETF share counts with nothing but the standard library.

Why this exists as a second copy of logic that already lives in
`qr/data/etf_flows.py`: the collector has to run somewhere always on, which is
a small shared server, and installing `qr` there means pandas, duckdb,
statsmodels and vectorbt to run a job whose real dependencies are `urllib` and
`json`. This file is `scp`-able, has no install step, and cannot break anything
else on the box.

The duplication is real and is held in check by a test
(`test_the_standalone_collector_agrees_with_the_package`) that runs both
parsers over the same fixture and compares the rows. If they ever disagree, the
test says so rather than a dataset quietly forking.

Output is byte-compatible with `qr data flows-collect`, so the file this writes
can be copied back and read by `etf_flows.load()` with nothing in between.

    python3 collect_flows_standalone.py --out ~/flows/etf_shares_outstanding.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCREENER = (
    "https://www.ishares.com/us/product-screener/product-screener-v3.1.jsn"
    "?dcrPath=/templatedata/config/product-screener-v3/data/en/us-ishares"
    "/ishares-product-screener-backend-config&siteEntryPassthrough=true"
)
TICKERS = ("IWM", "EFA", "EEM", "TLT", "IEF", "LQD", "HYG")
SHARE_KEYS = ("sharesoutstanding", "shares_outstanding", "sharesout", "sharecount")
ASSET_KEYS = ("totalnetassets", "total_net_assets", "netassets", "fundnetassets", "aum")
NAV_KEYS = ("nav", "navamount", "netassetvalue")


def number(value):
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("r", "raw", "value"):
            if key in value:
                return number(value[key])
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if not text or text in {"-", "--", "N/A", "NA"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pick(record, wanted):
    for key, value in record.items():
        if key.lower().replace(" ", "") in wanted:
            got = number(value)
            if got is not None:
                return got
    return None


def parse(payload, tickers=TICKERS):
    """Identify a fund record by the ticker inside it, not by where it sits."""
    observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
    wanted = {t.upper() for t in tickers}
    records = []

    def walk(node):
        if isinstance(node, dict):
            if any(isinstance(v, str) and v.upper() in wanted for v in node.values()):
                records.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    if not records:
        raise SystemExit(f"no fund records: none of {sorted(wanted)} appear in the response")

    rows, seen = [], set()
    for record in records:
        ticker = next(
            (str(v).upper() for v in record.values() if isinstance(v, str) and v.upper() in wanted),
            None,
        )
        if ticker is None or ticker in seen:
            continue
        seen.add(ticker)
        shares = pick(record, SHARE_KEYS)
        assets = pick(record, ASSET_KEYS)
        nav = pick(record, NAV_KEYS)
        basis = "reported"
        if shares is None and assets is not None and nav:
            shares, basis = assets / nav, "derived"
        rows.append(
            {
                "observed_utc": observed,
                "ticker": ticker,
                "shares_outstanding": shares,
                "total_net_assets": assets,
                "nav": nav,
                "source": "ishares_product_screener",
                "shares_basis": basis,
            }
        )
    missing = [r["ticker"] for r in rows if r["shares_outstanding"] is None]
    if missing:
        raise SystemExit(f"no share count or net assets for {missing}; the field names have moved")
    return rows


def already_today(path: Path) -> bool:
    """Cheap, and checked before the request. Most runs do nothing."""
    if not path.exists():
        return False
    today = datetime.now(timezone.utc).date().isoformat()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                if json.loads(line)["observed_utc"][:10] == today:
                    return True
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="~/flows/etf_shares_outstanding.jsonl")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="say nothing when there is nothing to say")
    args = parser.parse_args()

    out = Path(args.out).expanduser()
    if not args.force and already_today(out):
        if not args.quiet:
            print(f"already recorded today in {out}")
        return 0

    request = urllib.request.Request(
        SCREENER,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8", "replace").lstrip("﻿"))

    rows = parse(payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} recorded {len(rows)} funds to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
