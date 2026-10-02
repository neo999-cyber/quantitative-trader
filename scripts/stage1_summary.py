#!/usr/bin/env python3
"""Stage 1, one line a day, standard library only (it runs on the box, where nothing else is installed).

    QR_ROOT=/root/stage1/lake python3 scripts/stage1_summary.py --config study/stage1.live.json [--day 2026-10-03] [--alert-only]

Reads the journal (read-only) and asks the venue for its positions and wallet. Prints
`stage 1 <day>: <n> accepted, <x>% filled within 15 min, net <$>, FLAT/NOT FLAT (journal vs venue AGREE/MISMATCH)`,
appends it to `<lake>/study/logs/summary.log`, and — only when `QR_NTFY_TOPIC` is set (the owner's choice) —
sends the same line as a push through ntfy.sh. `--alert-only` sends nothing unless something is wrong
(not flat, mismatch, or no session today), for the close-on-failure unit.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qr import secrets  # noqa: E402
from qr.config import paths  # noqa: E402
from qr.execution.venues import BinanceUSDM  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--day", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--alert-only", action="store_true")
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.config).read_text())
    account, testnet = cfg["account"], bool(cfg.get("testnet", True))
    root = Path(paths().root) / "study"
    db = root / "stage1.sqlite"
    nxt = (datetime.fromisoformat(a.day) + timedelta(days=1)).strftime("%Y-%m-%d")
    accepted = filled = 0
    net = None
    mine: dict[str, Decimal] = {}
    cash_now = None
    if db.exists():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("SELECT a.client_id, o.state FROM study_attempts a JOIN orders o ON o.client_id = a.client_id JOIN intents i ON i.client_id = a.client_id "
                           "WHERE a.slot >= ? AND a.slot < ? AND i.account = ? AND a.outcome = 'placed:ACKED'", (a.day, nxt, account)).fetchall()
        accepted = len(rows)
        for cid, state in rows:
            if state != "FILLED":
                continue
            ack = con.execute("SELECT MIN(ts) FROM order_events WHERE client_id = ? AND to_state = 'ACKED'", (cid,)).fetchone()[0]
            last = con.execute("SELECT MAX(CAST(venue_ts AS INTEGER)) FROM executions WHERE client_id = ?", (cid,)).fetchone()[0]
            if ack and last and (last / 1000 - datetime.fromisoformat(ack).timestamp()) <= 900:
                filled += 1
        snap = con.execute("SELECT amount FROM cash_events WHERE account = ? AND kind = 'venue_balance_snapshot' AND currency = 'USDT' AND recorded_at >= ? AND recorded_at < ? "
                           "ORDER BY recorded_at LIMIT 1", (account, a.day, nxt)).fetchone()
        cash = con.execute("SELECT amount FROM cash WHERE account = ? AND currency = 'USDT'", (account,)).fetchone()
        cash_now = Decimal(cash[0]) if cash else None
        if snap and cash_now is not None:
            # the day's opening snapshot is a delta against the cash held then; the opening wallet is in the event id
            first = con.execute("SELECT event_id FROM cash_events WHERE account = ? AND kind = 'venue_balance_snapshot' AND currency = 'USDT' AND recorded_at >= ? AND recorded_at < ? "
                                "ORDER BY recorded_at LIMIT 1", (account, a.day, nxt)).fetchone()[0]
            net = cash_now - Decimal(first.rsplit(":", 1)[1])
        mine = {s: Decimal(q) for s, q in con.execute("SELECT symbol, qty FROM positions WHERE account = ?", (account,)).fetchall() if Decimal(q) != 0}
    tag, base = ("TESTNET", BinanceUSDM.TESTNET) if testnet else ("STUDY", BinanceUSDM.MAINNET)
    try:
        venue = BinanceUSDM(secrets.require(f"BINANCE_{tag}_KEY"), secrets.require(f"BINANCE_{tag}_SECRET"), base=base)
        theirs = {s: q for s, q in venue.positions().items() if q != 0}
        wallet = venue.balances().get("USDT")
        flat = not theirs
        agree = theirs == mine and (cash_now is None or wallet is None or abs(wallet - cash_now) < Decimal("0.01"))
        venue_txt = f"{'FLAT' if flat else 'NOT FLAT ' + str({k: str(v) for k, v in theirs.items()})}, wallet {wallet:.2f}, journal vs Binance {'AGREE' if agree else 'MISMATCH'}"
    except Exception as exc:  # noqa: BLE001
        flat, agree, venue_txt = False, False, f"venue check failed: {type(exc).__name__}: {str(exc)[:80]}"
    rate = f"{filled / accepted:.0%} filled within 15 min" if accepted else "no accepted orders"
    money = f"net {net:+.2f}" if net is not None else "net n/a"
    wrong = (not flat) or (not agree) or accepted == 0
    line = f"stage 1 {a.day}: {accepted} accepted, {rate}, {money}, {venue_txt}" + (f" — {a.note}" if a.note else "")
    print(line)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    with (root / "logs" / "summary.log").open("a") as fh:
        fh.write(f"{datetime.now(timezone.utc).isoformat()} {line}\n")
    topic = os.environ.get("QR_NTFY_TOPIC")
    if topic and (wrong or not a.alert_only):
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=line.encode(), method="POST",
                                         headers={"Title": "stage 1 ALERT" if wrong else "stage 1", "Priority": "urgent" if wrong else "default"})
            urllib.request.urlopen(req, timeout=20).read()
        except Exception as exc:  # noqa: BLE001
            print(f"push failed: {exc}", file=sys.stderr)
    return 1 if (wrong and a.alert_only) else 0


if __name__ == "__main__":
    sys.exit(main())
