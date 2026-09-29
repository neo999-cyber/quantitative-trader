"""B10 — the execution journal: every intent, order state, execution and cash event, once, in SQLite.

`docs/27`. The research ledger (`qr/research/ledger.py`) simulates an
account from bars; this is the account. It holds what the maker-fill
study's stage 1 needs and nothing more:

* **Intents** with a stable client id (account, strategy version, signal,
  side, action → sha256) and the digest of the exact payload. The same id
  with a different payload is refused; the same id and payload is a
  no-op, which is what a retry must be.
* **Order states** with an explicit transition table. `UNKNOWN` (a request
  that timed out after it may have reached the venue) can only leave by
  reconciliation against the venue's own record, never by a resend.
* **Executions** keyed by the venue's execution id, each posted to cash
  and position exactly once; a duplicate callback with the same content
  is ignored, with different content is an error to investigate.
* **Reservations**: cash and gross notional a not-yet-filled order has
  claimed, so a second intent cannot spend the same dollar. Released only
  on a confirmed terminal state, and only the unfilled part.
* **Cash events** (fees, funding, transfers) with their own ids.
* **Marks**: NAV is `cash + Σ qty × mark` where every held instrument has a
  mark; a missing or invalid mark makes NAV *uncertain* (`nav()` raises)
  — a held position is never liquidated at an invented price. That is
  the execution-mode answer to the research ledger's "sell at the last
  close" convention.
* **Control**: the mode (`PAUSED` on every open, whatever it was before;
  `MONITOR`, `PAPER`, `STUDY`) and an audit row for every change. Live
  order placement is `STUDY` mode only, entered by `qr.execution.limits`
  after the mandate check — the journal itself has no venue code.

Everything is append-only except the projections (`positions`, `cash`,
`orders.state`), which `rebuild()` recomputes from the events so that a
restart replays to the same state. Quantities and money are `Decimal`
stored as text.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

__all__ = ["Intent", "Journal", "TRANSITIONS", "NavUncertain"]

TRANSITIONS: dict[str, set[str]] = {
    "STAGED": {"SUBMITTING", "CANCELLED"},
    "SUBMITTING": {"ACKED", "PARTIAL", "FILLED", "REJECTED", "EXPIRED", "UNKNOWN"},  # EXPIRED: a post-only that would have crossed
    "UNKNOWN": {"ACKED", "PARTIAL", "FILLED", "REJECTED", "CANCELLED", "EXPIRED"},  # by reconciliation only
    "ACKED": {"PARTIAL", "FILLED", "CANCEL_REQUESTED", "UNKNOWN", "EXPIRED"},
    "PARTIAL": {"PARTIAL", "FILLED", "CANCEL_REQUESTED", "UNKNOWN", "EXPIRED"},
    "CANCEL_REQUESTED": {"PARTIAL", "FILLED", "CANCELLED", "EXPIRED", "UNKNOWN"},
    "FILLED": set(),
    "CANCELLED": set(),
    "REJECTED": set(),
    "EXPIRED": set(),
}
TERMINAL = {s for s, nxt in TRANSITIONS.items() if not nxt}
MODES = ("PAUSED", "MONITOR", "PAPER", "STUDY")


class NavUncertain(ValueError):
    """A held instrument has no valid mark; the account's value is not known."""


def D(value) -> Decimal:
    out = Decimal(str(value))
    if not out.is_finite():
        raise ValueError("non-finite number")
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class Intent:
    account: str
    venue: str
    symbol: str
    side: str  # BUY | SELL
    qty: str
    limit: str
    post_only: bool
    reduce_only: bool
    strategy_version: str
    signal_id: str
    action: str  # ENTRY | EXIT
    expires_at: str
    currency: str = "USDT"

    @property
    def client_id(self) -> str:
        key = "|".join([self.account, self.strategy_version, self.signal_id, self.side, self.action])
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def notional(self) -> Decimal:
        return D(self.qty) * D(self.limit)


SCHEMA = """
CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY CHECK (id = 1), mode TEXT NOT NULL, since TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS intents (
  client_id TEXT PRIMARY KEY, account TEXT NOT NULL, venue TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
  qty TEXT NOT NULL, limit_price TEXT NOT NULL, post_only INTEGER NOT NULL, reduce_only INTEGER NOT NULL,
  strategy_version TEXT NOT NULL, signal_id TEXT NOT NULL, action TEXT NOT NULL, expires_at TEXT NOT NULL,
  currency TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL, staged_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders (client_id TEXT PRIMARY KEY REFERENCES intents(client_id), state TEXT NOT NULL,
  venue_order_id TEXT, filled_qty TEXT NOT NULL DEFAULT '0', updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS order_events (seq INTEGER PRIMARY KEY, client_id TEXT NOT NULL, ts TEXT NOT NULL,
  from_state TEXT NOT NULL, to_state TEXT NOT NULL, evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS executions (exec_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, venue TEXT NOT NULL, symbol TEXT NOT NULL,
  side TEXT NOT NULL, qty TEXT NOT NULL, price TEXT NOT NULL, fee TEXT NOT NULL, fee_currency TEXT NOT NULL,
  venue_ts TEXT NOT NULL, recorded_at TEXT NOT NULL, content TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cash_events (event_id TEXT PRIMARY KEY, account TEXT NOT NULL, venue TEXT NOT NULL,
  currency TEXT NOT NULL, amount TEXT NOT NULL, kind TEXT NOT NULL, venue_ts TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reservations (client_id TEXT PRIMARY KEY, account TEXT NOT NULL, venue TEXT NOT NULL,
  currency TEXT NOT NULL, cash TEXT NOT NULL, notional TEXT NOT NULL, released INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS cash (account TEXT NOT NULL, venue TEXT NOT NULL, currency TEXT NOT NULL, amount TEXT NOT NULL,
  PRIMARY KEY (account, venue, currency));
CREATE TABLE IF NOT EXISTS positions (account TEXT NOT NULL, venue TEXT NOT NULL, symbol TEXT NOT NULL, qty TEXT NOT NULL,
  PRIMARY KEY (account, venue, symbol));
CREATE TABLE IF NOT EXISTS marks (venue TEXT NOT NULL, symbol TEXT NOT NULL, price TEXT NOT NULL, ts TEXT NOT NULL,
  PRIMARY KEY (venue, symbol));
"""


class Journal:
    def __init__(self, path: Path | str) -> None:
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        with self._tx():
            row = self.db.execute("SELECT mode FROM control WHERE id = 1").fetchone()
            if row is None:
                self.db.execute("INSERT INTO control VALUES (1, 'PAUSED', ?)", (_now(),))
                self._audit("open", None, "journal created; PAUSED")
            elif row[0] != "PAUSED":
                # every open starts paused: a restored backup or a crash never restores permission to trade
                self.db.execute("UPDATE control SET mode = 'PAUSED', since = ? WHERE id = 1", (_now(),))
                self._audit("open", None, f"reopened; mode {row[0]} -> PAUSED pending reconciliation")

    def close(self) -> None:
        self.db.close()

    # -- transactions and audit -------------------------------------------

    def _tx(self):
        journal = self

        class Tx:
            def __enter__(self_inner):
                journal.db.execute("BEGIN IMMEDIATE")
                return journal

            def __exit__(self_inner, exc_type, exc, tb):
                if exc_type is None:
                    journal.db.execute("COMMIT")
                else:
                    journal.db.execute("ROLLBACK")
                return False

        return Tx()

    def _audit(self, kind: str, ref: str | None, detail: str) -> None:
        self.db.execute("INSERT INTO audit (ts, kind, ref, detail) VALUES (?, ?, ?, ?)", (_now(), kind, ref, detail))

    # -- control -----------------------------------------------------------

    def mode(self) -> str:
        return self.db.execute("SELECT mode FROM control WHERE id = 1").fetchone()[0]

    def set_mode(self, mode: str, reason: str) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; one of {MODES}")
        if not reason:
            raise ValueError("a mode change needs a reason")
        with self._tx():
            self.db.execute("UPDATE control SET mode = ?, since = ? WHERE id = 1", (mode, _now()))
            self._audit("mode", None, f"{mode}: {reason}")

    def pause(self, reason: str) -> None:
        self.set_mode("PAUSED", reason)

    # -- intents and orders ------------------------------------------------

    def stage(self, intent: Intent, reserve_cash: Decimal | str = "0") -> str:
        """Record an intent once; returns the order's current state.

        A second call with the same client id and payload returns the
        existing state (idempotent). The same id with a different payload
        is refused. Staging reserves `reserve_cash` and the intent's
        notional against the account, released on a terminal state.
        """
        if intent.side not in ("BUY", "SELL") or intent.action not in ("ENTRY", "EXIT"):
            raise ValueError("side is BUY|SELL, action is ENTRY|EXIT")
        if D(intent.qty) <= 0 or D(intent.limit) <= 0:
            raise ValueError("qty and limit must be positive")
        with self._tx():
            old = self.db.execute("SELECT digest FROM intents WHERE client_id = ?", (intent.client_id,)).fetchone()
            if old is not None:
                if old[0] != intent.digest():
                    raise ValueError(f"client id {intent.client_id} reused with a different payload")
                return self.state(intent.client_id)
            mode = self.mode()
            # an EXIT may be staged while PAUSED: pausing stops new risk, not the way out
            if mode not in ("PAPER", "STUDY") and not (mode == "PAUSED" and intent.action == "EXIT"):
                raise ValueError(f"staging refused in mode {mode}")
            self.db.execute(
                "INSERT INTO intents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    intent.client_id, intent.account, intent.venue, intent.symbol, intent.side, intent.qty, intent.limit,
                    int(intent.post_only), int(intent.reduce_only), intent.strategy_version, intent.signal_id,
                    intent.action, intent.expires_at, intent.currency, intent.digest(),
                    json.dumps(asdict(intent), sort_keys=True), _now(),
                ),
            )
            self.db.execute("INSERT INTO orders VALUES (?, 'STAGED', NULL, '0', ?)", (intent.client_id, _now()))
            self.db.execute(
                "INSERT INTO reservations VALUES (?, ?, ?, ?, ?, ?, 0)",
                (intent.client_id, intent.account, intent.venue, intent.currency, str(D(reserve_cash)), str(intent.notional())),
            )
            self.db.execute(
                "INSERT INTO order_events (client_id, ts, from_state, to_state, evidence) VALUES (?, ?, '', 'STAGED', 'staged')",
                (intent.client_id, _now()),
            )
            self._audit("stage", intent.client_id, f"{intent.side} {intent.qty} {intent.symbol} @ {intent.limit} on {intent.venue}")
        return "STAGED"

    def state(self, client_id: str) -> str:
        row = self.db.execute("SELECT state FROM orders WHERE client_id = ?", (client_id,)).fetchone()
        if row is None:
            raise KeyError(client_id)
        return row[0]

    def transition(self, client_id: str, to_state: str, evidence: str, venue_order_id: str | None = None) -> None:
        """Move an order along the table; `evidence` is what the venue said (or 'timeout')."""
        if not evidence:
            raise ValueError("a transition needs evidence")
        with self._tx():
            row = self.db.execute("SELECT state FROM orders WHERE client_id = ?", (client_id,)).fetchone()
            if row is None:
                raise KeyError(client_id)
            from_state = row[0]
            if to_state not in TRANSITIONS[from_state]:
                raise ValueError(f"{client_id[:8]}: {from_state} -> {to_state} is not a permitted transition")
            if from_state == "UNKNOWN" and not evidence.startswith("reconciled:"):
                raise ValueError("an UNKNOWN order leaves that state only by reconciliation ('reconciled: ...')")
            self.db.execute(
                "UPDATE orders SET state = ?, venue_order_id = COALESCE(?, venue_order_id), updated_at = ? WHERE client_id = ?",
                (to_state, venue_order_id, _now(), client_id),
            )
            self.db.execute(
                "INSERT INTO order_events (client_id, ts, from_state, to_state, evidence) VALUES (?, ?, ?, ?, ?)",
                (client_id, _now(), from_state, to_state, evidence),
            )
            if to_state in TERMINAL:
                self._release(client_id)

    def _release(self, client_id: str) -> None:
        """Release the *unfilled* part of a reservation on a terminal state."""
        res = self.db.execute("SELECT cash, notional, released FROM reservations WHERE client_id = ?", (client_id,)).fetchone()
        if res is None or res[2]:
            return
        self.db.execute("UPDATE reservations SET released = 1 WHERE client_id = ?", (client_id,))
        self._audit("release", client_id, f"reservation released: cash {res[0]}, notional {res[1]}")

    # -- executions and cash -----------------------------------------------

    def execution(
        self, exec_id: str, client_id: str, qty, price, fee, fee_currency: str, venue_ts: str, content: dict | None = None
    ) -> bool:
        """Post one venue execution exactly once. Returns False on an identical duplicate."""
        q, p, f = D(qty), D(price), D(fee)
        if q <= 0 or p <= 0 or f < 0:
            raise ValueError("invalid execution")
        payload = json.dumps({"client_id": client_id, "qty": str(q), "price": str(p), "fee": str(f), **(content or {})}, sort_keys=True)
        with self._tx():
            old = self.db.execute("SELECT content FROM executions WHERE exec_id = ?", (exec_id,)).fetchone()
            if old is not None:
                if old[0] != payload:
                    raise ValueError(f"execution {exec_id} reported twice with different content")
                return False
            intent = self.db.execute(
                "SELECT account, venue, symbol, side, qty, currency FROM intents WHERE client_id = ?", (client_id,)
            ).fetchone()
            if intent is None:
                raise KeyError(f"execution {exec_id} for an unknown intent {client_id}")
            account, venue, symbol, side, ordered, currency = intent
            filled = D(self.db.execute("SELECT filled_qty FROM orders WHERE client_id = ?", (client_id,)).fetchone()[0])
            if filled + q > D(ordered):
                raise ValueError(f"execution {exec_id} overfills {client_id[:8]}: {filled} + {q} > {ordered}")
            self.db.execute(
                "INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (exec_id, client_id, venue, symbol, side, str(q), str(p), str(f), fee_currency, venue_ts, _now(), payload),
            )
            signed = q if side == "BUY" else -q
            self._post_position(account, venue, symbol, signed)
            self._post_cash(account, venue, currency, -signed * p)
            if f:
                self._post_cash(account, venue, fee_currency, -f)
            self.db.execute("UPDATE orders SET filled_qty = ?, updated_at = ? WHERE client_id = ?", (str(filled + q), _now(), client_id))
            self._audit("execution", client_id, f"{exec_id}: {side} {q} {symbol} @ {p}, fee {f} {fee_currency}")
        return True

    def cash_event(self, event_id: str, account: str, venue: str, currency: str, amount, kind: str, venue_ts: str) -> bool:
        """Funding, a fee correction, a transfer: one posting per venue event id."""
        with self._tx():
            if self.db.execute("SELECT 1 FROM cash_events WHERE event_id = ?", (event_id,)).fetchone():
                return False
            self.db.execute(
                "INSERT INTO cash_events VALUES (?,?,?,?,?,?,?,?)",
                (event_id, account, venue, currency, str(D(amount)), kind, venue_ts, _now()),
            )
            self._post_cash(account, venue, currency, D(amount))
            self._audit("cash", event_id, f"{kind} {amount} {currency} on {venue}")
        return True

    def _post_cash(self, account: str, venue: str, currency: str, delta: Decimal) -> None:
        row = self.db.execute("SELECT amount FROM cash WHERE account = ? AND venue = ? AND currency = ?", (account, venue, currency)).fetchone()
        amount = (D(row[0]) if row else D(0)) + delta
        self.db.execute("INSERT OR REPLACE INTO cash VALUES (?, ?, ?, ?)", (account, venue, currency, str(amount)))

    def _post_position(self, account: str, venue: str, symbol: str, delta: Decimal) -> None:
        row = self.db.execute("SELECT qty FROM positions WHERE account = ? AND venue = ? AND symbol = ?", (account, venue, symbol)).fetchone()
        qty = (D(row[0]) if row else D(0)) + delta
        self.db.execute("INSERT OR REPLACE INTO positions VALUES (?, ?, ?, ?)", (account, venue, symbol, str(qty)))

    # -- marks and NAV -----------------------------------------------------

    def mark(self, venue: str, symbol: str, price, ts: str) -> None:
        p = D(price)
        if p <= 0:
            raise ValueError("a mark must be positive")
        self.db.execute("INSERT OR REPLACE INTO marks VALUES (?, ?, ?, ?)", (venue, symbol, str(p), ts))

    def positions(self, account: str) -> dict[tuple[str, str], Decimal]:
        rows = self.db.execute("SELECT venue, symbol, qty FROM positions WHERE account = ?", (account,)).fetchall()
        return {(v, s): D(q) for v, s, q in rows if D(q) != 0}

    def cash(self, account: str) -> dict[tuple[str, str], Decimal]:
        rows = self.db.execute("SELECT venue, currency, amount FROM cash WHERE account = ?", (account,)).fetchall()
        return {(v, c): D(a) for v, c, a in rows}

    def reserved(self, account: str) -> tuple[Decimal, Decimal]:
        """Open reservations: (cash, notional) claimed by orders not yet terminal."""
        row = self.db.execute(
            "SELECT COALESCE(SUM(CAST(cash AS REAL)), 0), COALESCE(SUM(CAST(notional AS REAL)), 0) "
            "FROM reservations WHERE account = ? AND released = 0",
            (account,),
        ).fetchone()
        return D(row[0]), D(row[1])

    def nav(self, account: str, currency: str = "USDT", max_mark_age_s: float | None = None, now: datetime | None = None) -> Decimal:
        """`cash + Σ qty × mark` in one currency; raises `NavUncertain` on any held instrument without a valid mark."""
        total = sum((a for (v, c), a in self.cash(account).items() if c == currency), D(0))
        for (venue, symbol), qty in self.positions(account).items():
            row = self.db.execute("SELECT price, ts FROM marks WHERE venue = ? AND symbol = ?", (venue, symbol)).fetchone()
            if row is None:
                raise NavUncertain(f"no mark for {symbol} on {venue}; holding {qty}, NAV not known")
            if max_mark_age_s is not None:
                age = ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(row[1])).total_seconds()
                if age > max_mark_age_s:
                    raise NavUncertain(f"mark for {symbol} on {venue} is {age:.0f}s old; NAV not known")
            total += qty * D(row[0])
        return total

    # -- replay --------------------------------------------------------------

    def rebuild(self) -> None:
        """Recompute cash, positions and filled quantities from the event tables."""
        with self._tx():
            self.db.execute("DELETE FROM cash")
            self.db.execute("DELETE FROM positions")
            self.db.execute("UPDATE orders SET filled_qty = '0'")
            for exec_id, client_id, venue, symbol, side, qty, price, fee, fee_currency in self.db.execute(
                "SELECT exec_id, client_id, venue, symbol, side, qty, price, fee, fee_currency FROM executions ORDER BY venue_ts, exec_id"
            ).fetchall():
                account, currency = self.db.execute("SELECT account, currency FROM intents WHERE client_id = ?", (client_id,)).fetchone()
                signed = D(qty) if side == "BUY" else -D(qty)
                self._post_position(account, venue, symbol, signed)
                self._post_cash(account, venue, currency, -signed * D(price))
                if D(fee):
                    self._post_cash(account, venue, fee_currency, -D(fee))
                filled = D(self.db.execute("SELECT filled_qty FROM orders WHERE client_id = ?", (client_id,)).fetchone()[0])
                self.db.execute("UPDATE orders SET filled_qty = ? WHERE client_id = ?", (str(filled + D(qty)), client_id))
            for account, venue, currency, amount in self.db.execute("SELECT account, venue, currency, amount FROM cash_events").fetchall():
                self._post_cash(account, venue, currency, D(amount))
            self._audit("rebuild", None, "projections rebuilt from events")
