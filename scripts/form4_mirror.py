"""Mirror every SEC insider-transactions quarter, parse it, stamp acceptance
times, and write the point-in-time purchase and cluster files to the lake.

    export QR_ROOT=~/qr/lake
    .venv/bin/python scripts/form4_mirror.py [--from 2006q1] [--to 2026q2]

Outputs under $QR_ROOT/reference/: form4_purchases.parquet (every qualifying
open-market purchase with availability columns), form4_clusters.parquet (the
E5 signals at the registered rule), form4_mirror_summary.json. Idempotent:
quarters and submissions pages already mirrored are not fetched again.
No price data is read here.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from qr.config import paths
from qr.data.form4 import (
    acceptance_times,
    cluster_signals,
    fetch_quarter,
    parse_quarter,
    qualifying_purchases,
    with_acceptance_times,
)

PIT_KEY = ["issuer_cik", "owner_cik", "trans_date", "trans_code", "security_title"]


def periods(start: str, end: str) -> list[str]:
    y0, q0 = int(start[:4]), int(start[-1]); y1, q1 = int(end[:4]), int(end[-1])
    out = []
    y, q = y0, q0
    while (y, q) <= (y1, q1):
        out.append(f"{y}q{q}")
        q += 1
        if q == 5:
            y, q = y + 1, 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2006q1")
    ap.add_argument("--to", dest="end", default="2026q2")
    args = ap.parse_args()
    root = paths().root
    mirror = root / "mirror" / "sec" / "form345"
    cache = root / "mirror" / "sec" / "submissions"
    reference = root / "reference"
    reference.mkdir(parents=True, exist_ok=True)

    frames = []
    summary = {"quarters": {}, "started": pd.Timestamp.now(tz="UTC").isoformat()}
    for period in periods(args.start, args.end):
        t0 = time.time()
        try:
            path = fetch_quarter(period, mirror)
        except Exception as exc:  # noqa: BLE001
            summary["quarters"][period] = {"error": str(exc)[:200]}
            print(f"{period}: {exc}", file=sys.stderr)
            continue
        frame = parse_quarter(path)
        q = qualifying_purchases(frame, 25_000.0)
        frames.append(q)
        summary["quarters"][period] = {"rows": int(len(frame)), "qualifying": int(len(q)), "seconds": round(time.time() - t0, 1)}
        print(f"{period}: {len(frame)} rows, {len(q)} qualifying purchases ({time.time() - t0:.0f}s)", flush=True)

    if not frames:
        print("nothing parsed", file=sys.stderr)
        return 1
    purchases = pd.concat(frames, ignore_index=True)
    ciks = sorted(set(purchases["issuer_cik"].astype(str)))
    print(f"acceptance times for {len(ciks)} issuers…", flush=True)
    t0 = time.time()
    times = acceptance_times(ciks, cache)
    print(f"  {len(times)} accessions stamped ({time.time() - t0:.0f}s)", flush=True)
    purchases = with_acceptance_times(purchases, times)
    stamped = int(purchases["published_at"].notna().sum())
    purchases.to_parquet(reference / "form4_purchases.parquet", index=False)

    # the registered rule, on the latest version of every transaction
    latest = purchases.dropna(subset=["published_at"]).sort_values("published_at").drop_duplicates(PIT_KEY, keep="last")
    clusters = cluster_signals(latest, window_days=10, min_insiders=2, min_combined_usd=100_000.0)
    clusters.to_parquet(reference / "form4_clusters.parquet", index=False)
    summary.update(
        {
            "purchases": int(len(purchases)),
            "published_at_stamped": stamped,
            "issuers": len(ciks),
            "clusters": int(len(clusters)),
            "finished": pd.Timestamp.now(tz="UTC").isoformat(),
        }
    )
    (reference / "form4_mirror_summary.json").write_text(json.dumps(summary, indent=1))
    print(f"purchases {len(purchases)} (stamped {stamped}), clusters {len(clusters)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
