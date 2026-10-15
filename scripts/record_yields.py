#!/usr/bin/env python3
"""Record the stablecoin yield ladder and Binance Launchpool/HODLer announcements forward, once a day.

Programme 3 (`docs/31` §2, §4). The ladder in §2 is a set of one-day reads;
the 31 October decision needs a measured series, and Launchpool's "84%
APY" needs measuring against what a capped user actually receives. Free,
no key, standard library:

* **DefiLlama yields** (`https://yields.llama.fi/pools`): APY, base APY,
  TVL for the named pools — Aave v3 USDC/USDT (Ethereum), Maple
  syrupUSDC/USDT, Ethena sUSDe, the largest Morpho USDC vaults — plus
  every pool on the watch list by id.
* **FRED DTB3** (the T-bill comparator, tier 0).
* **Binance announcements** (public CMS list, catalogues 48 "New
  Cryptocurrency Listing", 93 "Latest Activities", 128 "Crypto Airdrop"):
  every article whose title names Launchpool, HODLer Airdrops, Megadrop or
  Simple Earn promotions, with its release time — the event calendar the Launchpool measurement is built on. The
  per-user caps, pool sizes and durations are in the article body, fetched
  once per new article and stored.

Binance Simple Earn's own rates need a signed endpoint and are **not**
recorded here; the owner reads them off the Earn page or a read-only key
is added later (owner decision).

One JSON line per snapshot: `<out>/yields/YYYY-MM-DD.jsonl`, plus
`<out>/announcements/<article code>.json` per article.

    python scripts/record_yields.py --out /root/yield/data
    python scripts/record_yields.py --print-systemd   # service + daily timer
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUT = Path(os.environ.get("QR_ROOT", Path.home() / "qr" / "lake")) / "yields_live"
LLAMA = "https://yields.llama.fi/pools"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3"
BN_LIST = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=50&catalogId={catalog}"
BN_CATALOGS = (48, 93, 128)  # New Cryptocurrency Listing, Latest Activities, Crypto Airdrop (HODLer Airdrops live here, probed 21 Sep 2026)
BN_ARTICLE = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={code}"
WATCH = re.compile(r"launchpool|hodler airdrop|megadrop|simple earn|launchpad|alpha", re.I)
# pools kept by (project, chain, symbol); everything else is dropped to keep the file small
KEEP = {
    ("aave-v3", "Ethereum", "USDC"), ("aave-v3", "Ethereum", "USDT"), ("aave-v3", "Base", "USDC"), ("aave-v3", "Arbitrum", "USDC"),
    ("maple", "Ethereum", "USDC"), ("maple", "Ethereum", "USDT"), ("ethena", "Ethereum", "SUSDE"), ("compound-v3", "Ethereum", "USDC"),
    ("morpho-blue", "Ethereum", "USDC"), ("morpho-blue", "Base", "USDC"), ("sky-lending", "Ethereum", "USDS"), ("spark", "Ethereum", "USDC"),
}


def _get(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as r:
        return r.read()


def snapshot_yields() -> list[dict]:
    data = json.loads(_get(LLAMA))["data"]
    out = []
    for p in data:
        if (p.get("project"), p.get("chain"), p.get("symbol")) in KEEP and (p.get("tvlUsd") or 0) >= 1e7:
            out.append({k: p.get(k) for k in ("pool", "project", "chain", "symbol", "tvlUsd", "apy", "apyBase", "apyReward", "apyMean30d", "stablecoin")})
    return out


TREASURY_BILLS = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all"
                  "?type=daily_treasury_bill_rates&field_tdr_date_value={year}&page&_format=csv")


def tbill() -> dict | None:
    """The 3-month bill: FRED's DTB3 when it answers, else the Treasury's own daily bill-rate file.

    FRED stopped answering the box on 13 October 2026 (Python's reads time out; curl, which worked once, now
    fails with HTTP/2 stream errors and then timeouts — the box's address appears to be shielded). The
    Treasury's file is the primary source of the same number: DTB3 is the 13-week bill on the bank-discount
    basis, which the file carries as "13 WEEKS BANK DISCOUNT". Each row says which source it came from.
    """
    fred_error = None
    try:
        lines = _get(FRED, timeout=20).decode().strip().splitlines()
        for line in reversed(lines):
            d, v = line.split(",")
            if v not in (".", ""):
                return {"date": d, "dtb3": float(v), "source": "fred"}
    except Exception as exc:  # noqa: BLE001
        fred_error = f"{type(exc).__name__}: {str(exc)[:60]}"
    year = datetime.now(timezone.utc).year
    rows = list(csv.DictReader(io.StringIO(_get(TREASURY_BILLS.format(year=year), timeout=60).decode())))
    rows = [r for r in rows if r.get("13 WEEKS BANK DISCOUNT") not in (None, "", "N/A")]
    rows.sort(key=lambda r: datetime.strptime(r["Date"], "%m/%d/%Y"))
    last = rows[-1]
    return {"date": datetime.strptime(last["Date"], "%m/%d/%Y").date().isoformat(), "dtb3": float(last["13 WEEKS BANK DISCOUNT"]),
            "source": "treasury_13w_bank_discount", "fred_error": fred_error}


def announcements(out: Path) -> list[dict]:
    arts, seen = [], set()
    for c in BN_CATALOGS:
        try:
            for a in json.loads(_get(BN_LIST.format(catalog=c)))["data"]["catalogs"][0]["articles"]:
                if a["code"] not in seen:
                    seen.add(a["code"])
                    arts.append(a)
        except Exception as exc:  # noqa: BLE001
            print(f"[announcements] catalogue {c}: {exc!r}", file=sys.stderr)
        time.sleep(2.0)
    hits = []
    for a in arts:
        if not WATCH.search(a.get("title") or ""):
            continue
        rec = {"code": a["code"], "title": a["title"], "release_ms": a.get("releaseDate")}
        hits.append(rec)
        path = out / "announcements" / f"{a['code']}.json"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                body = json.loads(_get(BN_ARTICLE.format(code=a["code"])))
            except Exception as exc:  # noqa: BLE001
                body = {"error": repr(exc)}
            path.write_text(json.dumps({**rec, "fetched_at": time.time(), "detail": body}))
            time.sleep(0.5)
    return hits


SYSTEMD_SERVICE = """[Unit]
Description=qr: daily stablecoin-yield and Launchpool snapshot (Programme 3)

[Service]
Type=oneshot
ExecStart={python} {script} --out {out}
"""
SYSTEMD_TIMER = """[Unit]
Description=qr: run the yield snapshot daily

[Timer]
OnCalendar=*-*-* 06:10:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--print-systemd", action="store_true")
    a = ap.parse_args(argv)
    if a.print_systemd:
        print(SYSTEMD_SERVICE.format(python=sys.executable, script=Path(__file__).resolve(), out=a.out.resolve()))
        print("=== timer ===")
        print(SYSTEMD_TIMER)
        return 0
    now = datetime.now(timezone.utc)
    rec = {"recorded_at": now.isoformat(), "pools": [], "tbill": None, "announcements": [], "errors": {}}
    for key, fn in (("pools", snapshot_yields), ("tbill", tbill), ("announcements", lambda: announcements(a.out))):
        try:
            rec[key] = fn()
        except Exception as exc:  # noqa: BLE001
            rec["errors"][key] = repr(exc)
    d = a.out / "yields"
    d.mkdir(parents=True, exist_ok=True)
    with (d / f"{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    print(f"[yields] {len(rec['pools'])} pools, tbill {rec['tbill']}, {len(rec['announcements'])} watched announcements, errors {rec['errors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
