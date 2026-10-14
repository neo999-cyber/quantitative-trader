#!/usr/bin/env python3
"""Record the spot bitcoin and ether ETFs' daily history forward, standard library only (the Hetzner box).

Once a day (cron, 06:00 UTC, after the issuer has posted the previous US day's row):

* **iShares' own fund workbook** for IBIT and ETHA — the "Download" on the product page, a SpreadsheetML
  file whose `Historical` sheet lists every day's NAV per share and shares outstanding since launch. The
  whole file is kept as a dated snapshot (`<out>/ishares/<TICKER>_<YYYY-MM-DD>.xls`, ~270 KB), so a later
  restatement shows as a difference between snapshots. The package reads the same files
  (`qr.data.etf_flows.ishares_history`); the parser here is a copy, held equal by a test.
* **A public per-ETF flow table** (bitbo.io, the last ~15 trading days of every US spot bitcoin ETF, in
  millions of dollars), appended as rows to `<out>/etf_flows_table.jsonl` with the observation time — the
  cross-check for the funds whose issuers publish no history. An aggregator, not a source of record.

    python3 collect_btc_etf_standalone.py --out ~/flows
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ISHARES_FUND_DOWNLOAD = (
    "https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document"
    "?appType=PRODUCT_PAGE&appSubType=ISHARES&targetSite=us-ishares&locale=en_US&portfolioId={portfolio_id}"
    "&component=fundDownload&userType=individual"
)
FUNDS = {"IBIT": 333011, "ETHA": 348532}
TABLE_URL = "https://bitbo.io/treasuries/etf-flows/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def _get(url: str, timeout: int = 90) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse_ishares_fund_xls(text: str, sheet: str = "Historical") -> list[dict]:
    """Rows of the `Historical` sheet of an iShares fund workbook (SpreadsheetML): date, nav, shares_outstanding.

    The sheet's columns are `As Of`, `NAV per Share`, `Ex-Dividends`, `Shares Outstanding`; rows are newest
    first and come back oldest first here. A row without a parsable date or number is dropped, not guessed.
    Parsed with expressions, not an XML parser: the workbook's disclaimer text carries unescaped ampersands
    that make ElementTree refuse the whole file (found on the first real download, 14 October 2026).
    """
    if "<ss:Workbook" not in text[:4000]:
        raise ValueError(f"not a SpreadsheetML workbook; starts {text[:120]!r}")
    start = text.find(f'Name="{sheet}"')
    if start < 0:
        names = re.findall(r'Worksheet[^>]*Name="([^"]+)"', text)
        raise ValueError(f"no {sheet!r} sheet; the workbook has {names}")
    body = text[start:]
    body = body[: body.find("</ss:Worksheet>")]
    rows: list[dict] = []
    header: list[str] | None = None
    for row in re.findall(r"<ss:Row[^>]*>(.*?)</ss:Row>", body, re.S):
        cells = [c.strip() for c in re.findall(r"<ss:Data[^>]*>(.*?)</ss:Data>", row, re.S)]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        rec = dict(zip(header, cells))
        try:
            date = datetime.strptime(rec.get("as of", ""), "%b %d, %Y").date().isoformat()
            nav = float(rec.get("nav per share", ""))
            shares = float(rec.get("shares outstanding", ""))
        except ValueError:
            continue
        rows.append({"date": date, "nav": nav, "shares_outstanding": shares, "ex_dividend": rec.get("ex-dividends", "") or None})
    rows.sort(key=lambda r: r["date"])
    return rows


def parse_flow_table(page: str) -> list[dict]:
    """The first HTML table: one row per (date, ticker) with the flow in millions of dollars; summary rows skipped."""
    tables = re.findall(r"<table.*?</table>", page, re.S)
    if not tables:
        raise ValueError("no table in the page")
    rows = re.findall(r"<tr.*?</tr>", tables[0], re.S)
    cells = lambda r: [html.unescape(re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)]
    header = cells(rows[0])
    out = []
    for r in rows[1:]:
        c = cells(r)
        if not c or len(c) != len(header):
            continue
        try:
            date = datetime.strptime(c[0], "%b %d, %Y").date().isoformat()
        except ValueError:
            continue  # "Total", "Average", "Minimum" rows
        for ticker, val in zip(header[1:], c[1:]):
            try:
                out.append({"date": date, "ticker": ticker, "flow_musd": float(val.replace(",", ""))})
            except ValueError:
                pass
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path.home() / "flows")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    rc = 0
    (a.out / "ishares").mkdir(parents=True, exist_ok=True)
    for ticker, pid in FUNDS.items():
        path = a.out / "ishares" / f"{ticker}_{day}.xls"
        if path.exists():
            continue
        try:
            text = _get(ISHARES_FUND_DOWNLOAD.format(portfolio_id=pid))
            rows = parse_ishares_fund_xls(text)  # parse before keeping: an HTML answer must not be stored as a snapshot
            path.write_text(text, encoding="utf-8")
            if not a.quiet:
                print(f"{now.isoformat(timespec='seconds')} {ticker}: {len(rows)} daily rows, last {rows[-1]['date']} -> {path.name}")
        except Exception as exc:  # noqa: BLE001
            print(f"{now.isoformat(timespec='seconds')} {ticker}: FAILED {type(exc).__name__}: {str(exc)[:100]}", file=sys.stderr)
            rc = 1
    try:
        rows = parse_flow_table(_get(TABLE_URL))
        with (a.out / "etf_flows_table.jsonl").open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({**r, "observed_utc": now.isoformat(timespec="seconds"), "source": "bitbo"}) + "\n")
        if not a.quiet:
            print(f"{now.isoformat(timespec='seconds')} table: {len(rows)} rows over {len({r['date'] for r in rows})} days")
    except Exception as exc:  # noqa: BLE001
        print(f"{now.isoformat(timespec='seconds')} table: FAILED {type(exc).__name__}: {str(exc)[:100]}", file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
