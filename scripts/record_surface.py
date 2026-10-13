#!/usr/bin/env python3
"""Record the Deribit options surface and Hyperliquid's per-asset positioning forward, once an hour.

Programme 3's data-expansion plan (`docs/31` §15, items 4 and 5): both are
forward-only — the history is paid or does not exist — so every day not
recorded is lost, and recording costs nothing. Free, no key, standard
library, one snapshot an hour:

* **Deribit** `public/get_book_summary_by_currency?currency=BTC|ETH&kind=option`:
  every listed option's mark IV, open interest, volume, bid/ask/mark, the
  underlying — ~900 instruments a currency, ~40 KB gzipped a snapshot.
  Dealer-hedging-into-expiry needs the open interest by strike as the
  expiry approaches; hourly is enough, daily is not (expiry is 08:00 UTC).
* **Hyperliquid** `POST /info {"type":"metaAndAssetCtxs"}`: every perp's
  funding, open interest, oracle and mark price, premium, day volume —
  ~230 assets, ~14 KB gzipped. The per-address liquidation map the plan
  mentions needs a walk over every account and is not this recorder.

One gzipped JSON file a snapshot: `<out>/<venue>/YYYY-MM-DD/HH.json.gz`,
with `recorded_at` and the venue's own timestamps kept. A failed venue
is logged and skipped; the other still records.

    python3 scripts/record_surface.py --out /root/surface/data
    python3 scripts/record_surface.py --print-systemd   # service + hourly timer
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUT = Path(os.environ.get("QR_ROOT", Path.home() / "qr" / "lake")) / "surface_live"
DERIBIT = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={ccy}&kind=option"
DERIBIT_CCYS = ("BTC", "ETH")
HYPERLIQUID = "https://api.hyperliquid.xyz/info"
DERIBIT_KEEP = ("instrument_name", "mark_iv", "open_interest", "volume", "volume_usd", "bid_price", "ask_price", "mark_price",
                "underlying_price", "underlying_index", "interest_rate", "creation_timestamp")


def _get(url: str, data: bytes | None = None, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def compact_deribit(payload: dict) -> list[dict]:
    """The fields the study needs, one row an instrument; nothing is summed or interpreted."""
    rows = []
    for x in payload.get("result") or []:
        rows.append({k: x.get(k) for k in DERIBIT_KEEP})
    return rows


def compact_hyperliquid(payload: list) -> list[dict]:
    """`metaAndAssetCtxs` is `[meta, ctxs]` aligned by index; join the asset name onto its context."""
    if not (isinstance(payload, list) and len(payload) == 2):
        raise ValueError("unexpected metaAndAssetCtxs shape")
    meta, ctxs = payload
    names = [u.get("name") for u in meta.get("universe") or []]
    return [{"name": n, **c} for n, c in zip(names, ctxs) if isinstance(c, dict)]


def snapshot_deribit() -> dict:
    out = {}
    for ccy in DERIBIT_CCYS:
        out[ccy] = compact_deribit(json.loads(_get(DERIBIT.format(ccy=ccy))))
    return out


def snapshot_hyperliquid() -> list[dict]:
    return compact_hyperliquid(json.loads(_get(HYPERLIQUID, data=json.dumps({"type": "metaAndAssetCtxs"}).encode())))


def write_snapshot(out: Path, venue: str, body, at: float | None = None) -> Path:
    at = time.time() if at is None else at
    d = datetime.fromtimestamp(at, tz=timezone.utc)
    path = out / venue / d.strftime("%Y-%m-%d") / f"{d.strftime('%H')}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump({"venue": venue, "recorded_at": at, "body": body}, fh, separators=(",", ":"))
    return path


SYSTEMD_SERVICE = """[Unit]
Description=qr: hourly Deribit options surface and Hyperliquid positioning snapshot (Programme 3 data expansion)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /root/surface/record_surface.py --out /root/surface/data
User=root
"""
SYSTEMD_TIMER = """[Unit]
Description=qr: run the surface snapshot every hour

[Timer]
OnCalendar=*-*-* *:02:00
AccuracySec=30s
Persistent=true

[Install]
WantedBy=timers.target
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--print-systemd", action="store_true")
    ap.add_argument("--venues", default="deribit,hyperliquid")
    a = ap.parse_args(argv)
    if a.print_systemd:
        print("# /etc/systemd/system/qr-surface.service\n" + SYSTEMD_SERVICE + "\n# /etc/systemd/system/qr-surface.timer\n" + SYSTEMD_TIMER)
        return 0
    rc = 0
    for venue in a.venues.split(","):
        try:
            body = snapshot_deribit() if venue == "deribit" else snapshot_hyperliquid() if venue == "hyperliquid" else None
            if body is None:
                raise ValueError(f"unknown venue {venue!r}")
            path = write_snapshot(a.out, venue, body)
            n = sum(len(v) for v in body.values()) if isinstance(body, dict) else len(body)
            print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {venue}: {n} rows -> {path}")
        except Exception as exc:  # noqa: BLE001 — one venue failing must not stop the other
            print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {venue}: FAILED {type(exc).__name__}: {str(exc)[:120]}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
