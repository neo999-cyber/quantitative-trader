#!/usr/bin/env python3
"""The carry holding at a terminal: preview, open, status, funding, rebalance, close (`docs/34`).

    QR_ROOT=~/qr/lake python scripts/study_carry.py preview --config study/carry.testnet.json
    QR_ROOT=~/qr/lake python scripts/study_carry.py open    --config study/carry.testnet.json --confirm   # testnet only
    QR_ROOT=~/qr/lake python scripts/study_carry.py status  --config study/carry.testnet.json
    QR_ROOT=~/qr/lake python scripts/study_carry.py funding --config study/carry.testnet.json
    QR_ROOT=~/qr/lake python scripts/study_carry.py close   --config study/carry.testnet.json

`open` and `rebalance` run under a mandate: the prompt prints the line to type (`<config hash> CARRY`),
the journal goes STUDY for that one sequence and returns to PAUSED with the positions standing. `close`
needs no mandate. `--confirm` types the line for you and is refused outside the testnet. Keys come from
`~/.qr/secrets.env`: the spot testnet (testnet.binance.vision) issues its own pair,
`BINANCE_SPOT_TESTNET_KEY/SECRET`; the futures demo uses `BINANCE_TESTNET_KEY/SECRET`; mainnet uses the
owner's `BINANCE_STUDY_KEY/SECRET` for both, which needs *Enable Spot & Margin Trading* and *Enable
Futures* ticked — the owner's toggles, off today.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qr import secrets  # noqa: E402
from qr.config import paths  # noqa: E402
from qr.execution.carry import CarryConfig, CarrySession, preview, start  # noqa: E402
from qr.execution.journal import Journal  # noqa: E402
from qr.execution.venues import BinanceSpot, BinanceUSDM  # noqa: E402


def load_config(path: Path, expires_h: float | None) -> CarryConfig:
    raw = json.loads(Path(path).read_text())
    if expires_h is not None:
        raw["expires_at"] = (datetime.now(timezone.utc) + timedelta(hours=expires_h)).isoformat()
    return CarryConfig(**raw)


def venues_for(config: CarryConfig) -> dict:
    if config.testnet:
        spot = BinanceSpot(secrets.require("BINANCE_SPOT_TESTNET_KEY"), secrets.require("BINANCE_SPOT_TESTNET_SECRET"), base=BinanceSpot.TESTNET, symbols=(config.spot_symbol,))
        perp = BinanceUSDM(secrets.require("BINANCE_TESTNET_KEY"), secrets.require("BINANCE_TESTNET_SECRET"), base=BinanceUSDM.TESTNET)
    else:
        spot = BinanceSpot(secrets.require("BINANCE_STUDY_KEY"), secrets.require("BINANCE_STUDY_SECRET"), base=BinanceSpot.MAINNET, symbols=(config.spot_symbol,))
        perp = BinanceUSDM(secrets.require("BINANCE_STUDY_KEY"), secrets.require("BINANCE_STUDY_SECRET"), base=BinanceUSDM.MAINNET)
    return {config.spot_venue: spot, config.perp_venue: perp}


def mandate(journal: Journal, config: CarryConfig, venues: dict, confirm: bool) -> None:
    expected = f"{config.digest()} CARRY"
    if confirm:
        if not config.testnet:
            raise SystemExit("--confirm is for the testnet only; on mainnet the line is typed")
        typed = expected
    else:
        print(f"To proceed, type exactly:  {expected}")
        typed = input("> ")
    start(journal, config, venues, typed)


def run_until(session: CarrySession, done, poll_s: float, max_s: float) -> dict:
    t0 = time.monotonic()
    view = session.tick()
    while not done(session, view) and time.monotonic() - t0 < max_s:
        time.sleep(poll_s)
        view = session.tick()
    return view


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=["preview", "open", "tick", "status", "funding", "rebalance", "close", "park"])
    ap.add_argument("--config", type=Path, default=Path("study/carry.testnet.json"))
    ap.add_argument("--db", type=Path, default=None, help="journal (default <lake>/study/carry.sqlite)")
    ap.add_argument("--confirm", action="store_true", help="type the mandate line for me (testnet only)")
    ap.add_argument("--expires-h", type=float, default=2.0, help="the mandate's life for open/rebalance")
    ap.add_argument("--poll", type=float, default=5.0)
    ap.add_argument("--max-wait", type=float, default=None, help="seconds to keep ticking after open/rebalance (default 3 × TTL)")
    a = ap.parse_args(argv)
    p = paths().ensure()
    config = load_config(a.config, a.expires_h if a.action in ("open", "rebalance") else None)
    venues = venues_for(config)
    if a.action == "preview":
        preview(config, venues)
        return 0
    db = a.db or (p.root / "study" / "carry.sqlite")
    db.parent.mkdir(parents=True, exist_ok=True)
    journal = Journal(db)
    session = CarrySession(journal, config, venues)
    max_wait = a.max_wait if a.max_wait is not None else 3 * config.ttl_s
    try:
        if a.action == "open":
            preview(config, venues)
            mandate(journal, config, venues, a.confirm)
            qty = session.open()
            if qty == 0:
                session.park()
                return 2
            view = run_until(session, lambda s, v: s.complete(), a.poll, max_wait)
            session.park()
            view = session.status()   # after the park, so the mode printed is the one left behind
            print(json.dumps(view, indent=1))
            return 0 if view["complete"] else 3
        if a.action == "rebalance":
            view = session.status()
            if session.held("spot") - abs(session.held("perp")) > 0:
                mandate(journal, config, venues, a.confirm)
            print("rebalance:", session.rebalance())
            run_until(session, lambda s, v: not s.working, a.poll, max_wait)
            session.park()
            print(json.dumps(session.status(), indent=1))
            return 0
        if a.action == "tick":
            print(json.dumps(session.tick(), indent=1))
            return 0
        if a.action == "status":
            print(json.dumps(session.status(), indent=1))
            return 0
        if a.action == "funding":
            n = session.book_funding()
            print(f"{n} new funding payment(s) booked; collected {session.status()['funding_collected']} USDT")
            return 0
        if a.action == "close":
            for line in session.close():
                print(line)
            print(json.dumps(session.status(), indent=1))
            return 0
        if a.action == "park":
            session.park()
            print("mode", journal.mode())
            return 0
    finally:
        journal.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
