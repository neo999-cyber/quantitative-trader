"""Maker-fill study stage 1 — the terminal driver (B13/B16, docs/27).

    .venv/bin/python scripts/study_stage1.py preview  --config qc/../study/stage1.json
    .venv/bin/python scripts/study_stage1.py run      --config study/stage1.json      # asks for the mandate hash
    .venv/bin/python scripts/study_stage1.py resume   --config study/stage1.json      # reconcile after a pause
    .venv/bin/python scripts/study_stage1.py close    --config study/stage1.json      # cancel and close everything now

The config is a JSON `StudyConfig`. Keys come from `~/.qr/secrets.env`:
`BINANCE_TESTNET_KEY/SECRET` (a Binance *Demo Trading* API key, demo.binance.com),
`BYBIT_TESTNET_KEY/SECRET` (testnet.bybit.com) when `testnet` is true; `BINANCE_STUDY_KEY/SECRET`, `BYBIT_STUDY_KEY/SECRET` (trade-only, no
withdrawal, IP-restricted) when it is false — and mainnet additionally
requires `--i-have-the-owners-yes` on the command line. Nothing here prints
a key. The journal is `~/qr/lake/study/stage1.sqlite`.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qr import secrets
from qr.config import paths
from qr.execution.journal import Journal
from qr.execution.study import Session, StudyConfig, preview, resume, start
from qr.execution.venues import BinanceUSDM, BybitLinear


def venues_for(config: StudyConfig) -> dict:
    out = {}
    tag = "TESTNET" if config.testnet else "STUDY"
    if "binance" in config.symbols:
        out["binance"] = BinanceUSDM(secrets.require(f"BINANCE_{tag}_KEY"), secrets.require(f"BINANCE_{tag}_SECRET"),
                                     base=BinanceUSDM.TESTNET if config.testnet else BinanceUSDM.MAINNET)
    if "bybit" in config.symbols:
        out["bybit"] = BybitLinear(secrets.require(f"BYBIT_{tag}_KEY"), secrets.require(f"BYBIT_{tag}_SECRET"),
                                   base=BybitLinear.TESTNET if config.testnet else BybitLinear.MAINNET)
    return out


def load_config(path: str, session_hours: float) -> StudyConfig:
    raw = json.loads(Path(path).read_text())
    raw.setdefault("session_expires_at", (datetime.now(timezone.utc) + timedelta(hours=session_hours)).isoformat())
    raw["hours_utc"] = tuple(raw.get("hours_utc", (7, 15)))
    return StudyConfig(**raw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["preview", "run", "resume", "close"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--session-hours", type=float, default=8.0)
    ap.add_argument("--poll", type=int, default=5)
    ap.add_argument("--i-have-the-owners-yes", action="store_true", dest="owners_yes")
    args = ap.parse_args()

    config = load_config(args.config, args.session_hours)
    if not config.testnet and not args.owners_yes:
        print("mainnet needs --i-have-the-owners-yes (docs/24 stage 1: the owner's explicit yes to the live configuration)", file=sys.stderr)
        return 2
    venues = venues_for(config)
    journal_path = Path(paths().root) / "study" / "stage1.sqlite"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal = Journal(journal_path)

    if args.action == "preview":
        preview(config, venues)
        print(f"\njournal {journal_path} mode {journal.mode()}")
        return 0
    if args.action == "resume":
        diffs = resume(journal, venues, config.account)
        print("venues and journal agree" if not diffs else "MISMATCH:\n  " + "\n  ".join(diffs))
        return 0 if not diffs else 1
    if args.action == "close":
        session = Session(journal, config, venues)
        problems = session.close_all()
        print("flat at every venue" if not problems else "NOT FLAT:\n  " + "\n  ".join(problems))
        return 0 if not problems else 1

    preview(config, venues)
    diffs = resume(journal, venues, config.account)
    if diffs:
        print("cannot start: venues and journal disagree:\n  " + "\n  ".join(diffs), file=sys.stderr)
        return 1
    typed = input(f"\nType `{config.digest()} STUDY` to start this session (anything else aborts): ")
    try:
        start(journal, config, venues, typed)
    except PermissionError as exc:
        print(f"not started: {exc}", file=sys.stderr)
        return 1
    print(f"STUDY mode until {config.session_expires_at}; Ctrl-C pauses entries and closes positions")
    session = Session(journal, config, venues)
    problems = session.run(poll_s=args.poll)
    print("session ended flat" if not problems else "SESSION ENDED NOT FLAT — check the venues:\n  " + "\n  ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
