"""B13 + B16 — the maker-fill study's stage 1: the mandate, and the attended runner.

`docs/24` (protocol), `docs/27` (scope). Nothing in this module runs
unless an operator is at the terminal and has typed the mandate's hash.

**Mandate (B13).** `StudyConfig` is the frozen study: venues and their
symbols (chosen from stage 0's shape), the attended hours, the slot and
TTL, the exit rule, the caps, the session's expiry, and whether the base
URLs are the testnets. `preview()` resolves it against the venues — the
account it will trade (balances and open positions read back), each
symbol's filters, the quantity a $10 order becomes — and prints the
config hash. `start()` takes that hash typed back and the word STUDY,
checks the venues are flat and the expiry is ahead, records the mandate
in the journal's audit, and is the only path from PAUSED to STUDY.

**Runner (B16).** `Session.tick()` does one pass and is called every few
seconds by `run()`: on each slot boundary place one post-only order per
symbol at the best price on the alternating side (sized to just under the
per-order cap, through `check_entry`); reconcile every working order;
cancel an entry that has rested `ttl_s`; on a fill, schedule the close as
a post-only order on the other side with the same TTL and re-post it on
cancel; if the fill is still open `exit_after_fill_s` after the fill
(**from the fill**, not the placement), close it with a reduce-only taker
through the touch; mark the mid `mark_after_s` after each fill. Every
scheduled attempt is recorded — placed, refused by the limits, or
skipped for a missing price — so the denominator is the schedule. At the
session's end, cancel every working entry, close every position with the
taker exit, and verify **at the venues** that nothing is held or working.

A crash, Ctrl-C or a laptop asleep past its deadline lands the journal in
PAUSED on the next open (`Journal` does that itself); `resume()` refuses
until the venues' positions and the journal's agree.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable

from qr.execution.journal import D, Intent, Journal
from qr.execution.limits import StudyPolicy, check_entry, check_exit
from qr.execution.orders import cancel, reconcile, submit
from qr.execution.venues import Instrument, VenueError, VenueTimeout

__all__ = ["StudyConfig", "Session", "preview", "start", "resume"]


@dataclass(frozen=True)
class StudyConfig:
    account: str
    symbols: dict  # venue name -> [symbols]
    hours_utc: tuple = (7, 15)  # attended window [start, end)
    slot_s: int = 900
    ttl_s: int = 900
    exit_after_fill_s: int = 3600
    mark_after_s: int = 60
    max_order_usd: str = "10"
    max_gross_usd: str = "50"
    stop_loss_usd: str = "25"
    days: int = 10
    testnet: bool = True
    version: str = "stage1-v1"
    session_expires_at: str = ""  # ISO; set by preview for today's session

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]

    def policy(self) -> StudyPolicy:
        eligible = tuple(f"{v}:{s}" for v, syms in self.symbols.items() for s in syms)
        return StudyPolicy(version=self.version, max_order_usd=D(self.max_order_usd), max_gross_usd=D(self.max_gross_usd),
                           stop_loss_usd=D(self.stop_loss_usd), eligible=eligible)


def preview(config: StudyConfig, venues: dict, out: Callable[[str], None] = print) -> dict:
    """Resolve the mandate against the venues and print it; returns what it found."""
    found: dict = {"config_hash": config.digest(), "testnet": config.testnet, "venues": {}}
    out(f"study {config.version}  config {config.digest()}  {'TESTNET' if config.testnet else 'MAINNET — REAL MONEY'}")
    out(f"caps: ${config.max_order_usd}/order, ${config.max_gross_usd} gross incl. pending, ${config.stop_loss_usd} session stop, "
        f"hours {config.hours_utc[0]:02d}-{config.hours_utc[1]:02d} UTC, slot {config.slot_s}s, TTL {config.ttl_s}s, "
        f"taker exit {config.exit_after_fill_s}s after a fill; expires {config.session_expires_at or '(unset)'}")
    for name, venue in venues.items():
        bal = venue.balances()
        pos = venue.positions()
        rows = []
        for symbol in config.symbols.get(name, []):
            ins = venue.instrument(symbol)
            bid, ask = venue.book(symbol)
            qty = ins.qty_for_notional(D(config.max_order_usd) - D("0.01"), ask)
            rows.append({"symbol": symbol, "tick": str(ins.tick), "step": str(ins.step), "min_notional": str(ins.min_notional),
                         "bid": str(bid), "ask": str(ask), "qty_at_cap": str(qty), "spread_bps": str(((ask - bid) / ask * 10000).quantize(D("0.01")))})
            out(f"  {name} {symbol}: bid {bid} ask {ask} spread {rows[-1]['spread_bps']} bps; a ${config.max_order_usd} order is {qty} "
                f"({'below the venue minimum' if qty == 0 else 'ok'})")
        found["venues"][name] = {"balances": {k: str(v) for k, v in bal.items()}, "positions": {k: str(v) for k, v in pos.items()}, "instruments": rows}
        out(f"  {name} balances {found['venues'][name]['balances']} positions {found['venues'][name]['positions'] or 'flat'}")
    return found


def start(journal: Journal, config: StudyConfig, venues: dict, typed: str, now: datetime | None = None) -> None:
    """The only way into STUDY mode: the operator types `<config hash> STUDY`."""
    now = now or datetime.now(timezone.utc)
    expected = f"{config.digest()} STUDY"
    if typed.strip() != expected:
        raise PermissionError("mandate not confirmed: type the config hash and STUDY exactly")
    if not config.session_expires_at or datetime.fromisoformat(config.session_expires_at) <= now:
        raise PermissionError("the session expiry is unset or already past")
    if journal.mode() != "PAUSED":
        raise PermissionError(f"start only from PAUSED (mode is {journal.mode()})")
    for name, venue in venues.items():
        if venue.positions():
            raise PermissionError(f"{name} is not flat: {venue.positions()}")
        balances = venue.balances()
        if not balances:
            raise PermissionError(f"{name} reports no balance: wrong key or account?")
        # the venue's balance is the journal's opening cash: booked once per venue
        # and day as a cash event, so the limits see what the account can spend
        # and a later reconciliation has a baseline (first rehearsal, 18 Sep 2026:
        # every entry was refused for "insufficient unreserved cash" because the
        # journal had never been told the balance)
        for currency, amount in balances.items():
            held = journal.cash(config.account).get((name, currency), D(0))
            delta = amount - held
            if delta != 0:
                journal.cash_event(f"balance:{name}:{currency}:{now.date().isoformat()}:{amount}", config.account, name, currency,
                                   delta, "venue_balance_snapshot", now.isoformat())
    journal.db.execute("INSERT INTO audit (ts, kind, ref, detail) VALUES (?, ?, ?, ?)",
                       (now.isoformat(), "mandate", config.digest(), json.dumps({"config": asdict(config), "venues": sorted(venues)})))
    journal.set_mode("STUDY", f"mandate {config.digest()} confirmed at the terminal; expires {config.session_expires_at}")


def resume(journal: Journal, venues: dict, account: str) -> list[str]:
    """After a pause: reconcile the venues' positions against the journal's; empty means they agree."""
    diffs = []
    held = journal.positions(account)
    for name, venue in venues.items():
        theirs = venue.positions()
        for symbol, qty in theirs.items():
            if held.get((name, symbol), D(0)) != qty:
                diffs.append(f"{name} {symbol}: venue {qty}, journal {held.get((name, symbol), D(0))}")
        for (v, symbol), qty in held.items():
            if v == name and symbol not in theirs:
                diffs.append(f"{name} {symbol}: journal {qty}, venue flat")
    if not diffs:
        journal.db.execute("INSERT INTO audit (ts, kind, ref, detail) VALUES (?, 'reconcile', NULL, 'venues and journal agree')",
                           (datetime.now(timezone.utc).isoformat(),))
    return diffs


SCHEMA = """
CREATE TABLE IF NOT EXISTS study_attempts (seq INTEGER PRIMARY KEY, slot TEXT NOT NULL, venue TEXT NOT NULL, symbol TEXT NOT NULL,
  side TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL, client_id TEXT);
CREATE TABLE IF NOT EXISTS study_marks (client_id TEXT PRIMARY KEY, venue TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
  fill_price TEXT NOT NULL, filled_at TEXT NOT NULL, mid_at_place TEXT, mid_after TEXT, marked_at TEXT);
"""


@dataclass
class _Working:
    intent: Intent
    venue: str
    placed_at: datetime
    kind: str  # entry | exit_maker | exit_taker
    mid_at_place: Decimal
    filled_at: datetime | None = None
    fill_price: Decimal | None = None
    parent: str | None = None  # the entry this exit closes


@dataclass
class Session:
    journal: Journal
    config: StudyConfig
    venues: dict
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    log: Callable[[str], None] = print
    working: dict[str, _Working] = field(default_factory=dict)
    instruments: dict[tuple[str, str], Instrument] = field(default_factory=dict)
    last_slot: dict[tuple[str, str], int] = field(default_factory=dict)
    side_toggle: dict[tuple[str, str], int] = field(default_factory=dict)
    open_nav: Decimal | None = None

    def __post_init__(self) -> None:
        self.journal.db.executescript(SCHEMA)
        self.policy = self.config.policy()
        self._load_working()

    def _load_working(self) -> None:
        """Rebuild the working set from the journal's non-terminal orders (a restart must not forget
        a resting order: on 18 Sep 2026 one filled while the runner was down and a fresh session
        did not know it held 12.5 SUI). Fills are re-read by the first reconcile."""
        rows = self.journal.db.execute(
            "SELECT i.client_id, i.payload, i.staged_at, o.state, o.filled_qty FROM intents i JOIN orders o ON o.client_id = i.client_id "
            "WHERE i.account = ? AND o.state NOT IN ('FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')", (self.config.account,)).fetchall()
        filled_entries = self.journal.db.execute(
            "SELECT i.client_id, i.payload, i.staged_at FROM intents i JOIN orders o ON o.client_id = i.client_id "
            "WHERE i.account = ? AND i.action = 'ENTRY' AND o.state = 'FILLED'", (self.config.account,)).fetchall()
        for cid, payload, staged_at, state, filled in rows:
            intent = Intent(**json.loads(payload))
            kind = "entry" if intent.action == "ENTRY" else ("exit_taker" if not intent.post_only else "exit_maker")
            parent = intent.signal_id.split(":exit_")[0] if kind != "entry" else None
            parent_cid = next((c for c, w in self.working.items() if w.intent.signal_id == parent), None) if parent else None
            self.working[cid] = _Working(intent, intent.venue, datetime.fromisoformat(staged_at), kind, D(0), parent=parent_cid)
        # a filled entry whose position is still held needs its exit path back
        held = self.journal.positions(self.config.account)
        for cid, payload, staged_at in filled_entries:
            intent = Intent(**json.loads(payload))
            if (intent.venue, intent.symbol) in held and cid not in self.working:
                row = self.journal.db.execute("SELECT filled_at, fill_price FROM study_marks WHERE client_id = ?", (cid,)).fetchone()
                filled_at = datetime.fromisoformat(row[0]) if row else datetime.fromisoformat(staged_at)
                self.working[cid] = _Working(intent, intent.venue, datetime.fromisoformat(staged_at), "entry", D(0),
                                             filled_at=filled_at, fill_price=D(row[1]) if row else D(intent.limit))
        for w in self.working.values():
            if w.kind != "entry":
                for cid, e in self.working.items():
                    if e.kind == "entry" and e.intent.signal_id == w.intent.signal_id.split(":exit_")[0]:
                        w.parent = cid

    # -- helpers -------------------------------------------------------------

    def _attempt(self, slot: datetime, venue: str, symbol: str, side: str, outcome: str, detail: str, client_id: str | None = None) -> None:
        self.journal.db.execute("INSERT INTO study_attempts (slot, venue, symbol, side, outcome, detail, client_id) VALUES (?,?,?,?,?,?,?)",
                                (slot.isoformat(), venue, symbol, side, outcome, detail, client_id))

    def _instrument(self, venue: str, symbol: str) -> Instrument:
        key = (venue, symbol)
        if key not in self.instruments:
            self.instruments[key] = self.venues[venue].instrument(symbol)
        return self.instruments[key]

    def _mark(self, venue: str, symbol: str) -> tuple[Decimal, Decimal] | None:
        try:
            bid, ask = self.venues[venue].book(symbol)
        except (VenueError, VenueTimeout) as exc:
            self.log(f"no book for {venue} {symbol}: {exc}")
            return None
        self.journal.mark(venue, symbol, (bid + ask) / 2, self.now().isoformat())
        return bid, ask

    def in_hours(self, t: datetime) -> bool:
        return self.config.hours_utc[0] <= t.hour < self.config.hours_utc[1]

    # -- one pass --------------------------------------------------------------

    def tick(self) -> None:
        t = self.now()
        if self.open_nav is None:
            try:
                self.open_nav = self.journal.nav(self.config.account, max_mark_age_s=None)
            except Exception:
                self.open_nav = D(0)
        # a fault in one step is logged and the rest of the pass still runs: the
        # exits and the marks must not depend on the entries' code path
        for step in (self._reconcile_working, self._place_entries if (self.journal.mode() == "STUDY" and self.in_hours(t)) else None,
                     self._expire_and_exit, self._settle_marks):
            if step is None:
                continue
            try:
                step(t)
            except Exception as exc:  # noqa: BLE001
                self.log(f"ERROR in {step.__name__}: {exc!r}")
                self.journal.db.execute("INSERT INTO audit (ts, kind, ref, detail) VALUES (?, 'error', ?, ?)", (t.isoformat(), step.__name__, repr(exc)[:500]))

    def _reconcile_working(self, t: datetime) -> None:
        for cid, w in list(self.working.items()):
            state = reconcile(self.journal, self.venues[w.venue], w.intent)
            if state in ("FILLED",) and w.filled_at is None:
                w.filled_at = t
                fills = [x for x in self.venues[w.venue].executions(w.intent.symbol)]
                w.fill_price = D(w.intent.limit)
                if w.kind == "entry":
                    self.journal.db.execute("INSERT OR IGNORE INTO study_marks VALUES (?,?,?,?,?,?,?,NULL,NULL)",
                                            (cid, w.venue, w.intent.symbol, w.intent.side, str(w.fill_price), t.isoformat(), str(w.mid_at_place)))
                    self.log(f"FILL {w.venue} {w.intent.symbol} {w.intent.side} {w.intent.qty} @ {w.intent.limit}")
                else:
                    self.log(f"CLOSED {w.venue} {w.intent.symbol} via {w.kind}")
                    del self.working[cid]
                    if w.parent in self.working:
                        del self.working[w.parent]
            elif state in ("CANCELLED", "REJECTED", "EXPIRED"):
                if w.kind == "exit_maker":
                    self._repost_exit(w, t)
                del self.working[cid]

    def _place_entries(self, t: datetime) -> None:
        slot_n = int(t.timestamp()) // self.config.slot_s
        for venue, symbols in self.config.symbols.items():
            for symbol in symbols:
                key = (venue, symbol)
                if self.last_slot.get(key) == slot_n:
                    continue
                self.last_slot[key] = slot_n
                slot = datetime.fromtimestamp(slot_n * self.config.slot_s, tz=timezone.utc)
                side = "BUY" if self.side_toggle.get(key, 0) % 2 == 0 else "SELL"
                self.side_toggle[key] = self.side_toggle.get(key, 0) + 1
                book = self._mark(venue, symbol)
                if book is None:
                    self._attempt(slot, venue, symbol, side, "no_book", "book unavailable")
                    continue
                bid, ask = book
                ins = self._instrument(venue, symbol)
                price = bid if side == "BUY" else ask
                qty = ins.qty_for_notional(D(self.config.max_order_usd) - D("0.01"), price)
                if qty == 0:
                    self._attempt(slot, venue, symbol, side, "below_minimum", f"${self.config.max_order_usd} buys no lot at {price}")
                    continue
                intent = Intent(account=self.config.account, venue=venue, symbol=symbol, side=side, qty=str(qty), limit=str(price),
                                post_only=True, reduce_only=False, strategy_version=self.config.version,
                                # venue and symbol are part of the signal: the client id hashes it, and
                                # the first live slot collided two symbols on the bare slot time (18 Sep)
                                signal_id=f"{venue}:{symbol}:{slot.isoformat()}", action="ENTRY",
                                expires_at=(t + timedelta(seconds=self.config.ttl_s)).isoformat())
                reasons = check_entry(self.journal, intent, self.policy, self.open_nav or D(0), t)
                if reasons:
                    self._attempt(slot, venue, symbol, side, "refused", ",".join(reasons), intent.client_id)
                    if "session_loss_stop" in reasons:
                        self.journal.pause("session loss stop reached")
                        self.log("PAUSED: session loss stop")
                    continue
                state = submit(self.journal, self.venues[venue], intent, reserve_cash=str(qty * price))
                self._attempt(slot, venue, symbol, side, f"placed:{state}", f"{qty} @ {price}", intent.client_id)
                if state in ("ACKED", "PARTIAL", "UNKNOWN"):
                    self.working[intent.client_id] = _Working(intent, venue, t, "entry", (bid + ask) / 2)
                elif state == "FILLED":
                    w = _Working(intent, venue, t, "entry", (bid + ask) / 2, filled_at=t, fill_price=price)
                    self.working[intent.client_id] = w
                    self.journal.db.execute("INSERT OR IGNORE INTO study_marks VALUES (?,?,?,?,?,?,?,NULL,NULL)",
                                            (intent.client_id, venue, symbol, side, str(price), t.isoformat(), str((bid + ask) / 2)))

    def _expire_and_exit(self, t: datetime) -> None:
        for cid, w in list(self.working.items()):
            if w.filled_at is None:
                if (t - w.placed_at).total_seconds() >= self.config.ttl_s:
                    state = cancel(self.journal, self.venues[w.venue], w.intent)
                    if state in ("CANCELLED", "EXPIRED", "REJECTED"):
                        if w.kind == "exit_maker":
                            self._repost_exit(w, t)
                        del self.working[cid]
                    elif state == "FILLED":
                        w.filled_at = t
                continue
            if w.kind != "entry":
                continue
            has_exit = any(x.parent == cid for x in self.working.values())
            if not has_exit:
                self._post_exit(w, t, taker=(t - w.filled_at).total_seconds() >= self.config.exit_after_fill_s)

    def _post_exit(self, w: _Working, t: datetime, taker: bool) -> None:
        venue, symbol = w.venue, w.intent.symbol
        book = self._mark(venue, symbol)
        if book is None:
            return
        bid, ask = book
        side = "SELL" if w.intent.side == "BUY" else "BUY"
        held = abs(self.journal.positions(self.config.account).get((venue, symbol), D(0)))
        if held == 0:
            del self.working[w.intent.client_id]
            return
        ins = self._instrument(venue, symbol)
        # exits are numbered from the journal, not from memory: a counter over the
        # working set reset once an earlier exit left it, and the re-post reused the
        # first exit's client id with a new price (refused; rehearsal take 3, 18 Sep)
        n = self.journal.db.execute("SELECT COUNT(*) FROM intents WHERE account = ? AND action = 'EXIT' AND signal_id LIKE ?",
                                    (self.config.account, f"{w.intent.signal_id}:exit_%")).fetchone()[0] + 1
        if taker:
            price = ins.round_price(ask * D("1.002")) if side == "BUY" else ins.round_price(bid * D("0.998"))
            intent = Intent(self.config.account, venue, symbol, side, str(held), str(price), False, True, self.config.version,
                            f"{w.intent.signal_id}:exit_taker:{n}", "EXIT", (t + timedelta(minutes=5)).isoformat())
            reasons = check_exit(self.journal, intent, self.policy)
            if reasons:
                self.log(f"taker exit refused for {symbol}: {reasons}")
                return
            self.journal.stage(intent)
            self.journal.transition(intent.client_id, "SUBMITTING", "taker reduce-only through the touch")
            try:
                order = self.venues[venue].close_taker(intent.client_id, symbol, side, held, price)
            except VenueTimeout as exc:
                self.journal.transition(intent.client_id, "UNKNOWN", f"timeout: {exc}")
                self.working[intent.client_id] = _Working(intent, venue, t, "exit_taker", (bid + ask) / 2, parent=w.intent.client_id)
                return
            except VenueError as exc:
                self.journal.transition(intent.client_id, "REJECTED", f"venue refused: {exc}")
                return
            self.working[intent.client_id] = _Working(intent, venue, t, "exit_taker", (bid + ask) / 2, parent=w.intent.client_id)
            if reconcile(self.journal, self.venues[venue], intent) == "FILLED":
                self.log(f"CLOSED {venue} {symbol} via exit_taker")
                self.working.pop(intent.client_id, None)
                self.working.pop(w.intent.client_id, None)
            return
        price = ask if side == "SELL" else bid
        intent = Intent(self.config.account, venue, symbol, side, str(held), str(price), True, True, self.config.version,
                        f"{w.intent.signal_id}:exit_maker:{n}", "EXIT", (t + timedelta(seconds=self.config.ttl_s)).isoformat())
        reasons = check_exit(self.journal, intent, self.policy)
        if reasons:
            self.log(f"maker exit refused for {symbol}: {reasons}")
            return
        state = submit(self.journal, self.venues[venue], intent)
        if state in ("ACKED", "PARTIAL", "UNKNOWN", "FILLED"):
            self.working[intent.client_id] = _Working(intent, venue, t, "exit_maker", (bid + ask) / 2, parent=w.intent.client_id,
                                                      filled_at=t if state == "FILLED" else None)

    def _repost_exit(self, w: _Working, t: datetime) -> None:
        parent = self.working.get(w.parent) if w.parent else None
        if parent is not None:
            self._post_exit(parent, t, taker=(t - parent.filled_at).total_seconds() >= self.config.exit_after_fill_s)

    def _settle_marks(self, t: datetime) -> None:
        rows = self.journal.db.execute("SELECT client_id, venue, symbol, filled_at FROM study_marks WHERE mid_after IS NULL").fetchall()
        for cid, venue, symbol, filled_at in rows:
            if (t - datetime.fromisoformat(filled_at)).total_seconds() >= self.config.mark_after_s:
                book = self._mark(venue, symbol)
                if book is None:
                    continue
                bid, ask = book
                self.journal.db.execute("UPDATE study_marks SET mid_after = ?, marked_at = ? WHERE client_id = ?",
                                        (str((bid + ask) / 2), t.isoformat(), cid))

    # -- the end of a session -------------------------------------------------

    def close_all(self) -> list[str]:
        """Cancel every working entry, close every position with the taker exit, verify flat at the venues."""
        t = self.now()
        for cid, w in list(self.working.items()):
            if w.filled_at is None:
                cancel(self.journal, self.venues[w.venue], w.intent)
                reconcile(self.journal, self.venues[w.venue], w.intent)
        self._reconcile_working(t)
        for cid, w in list(self.working.items()):
            if w.kind == "entry" and w.filled_at is not None:
                for x in list(self.working.values()):
                    if x.parent == cid and x.filled_at is None:
                        cancel(self.journal, self.venues[x.venue], x.intent)
                        self.working.pop(x.intent.client_id, None)
                self._post_exit(w, t, taker=True)
        self._reconcile_working(t)
        problems = []
        for name, venue in self.venues.items():
            pos = venue.positions()
            if pos:
                problems.append(f"{name} still holds {pos}")
        problems += resume(self.journal, self.venues, self.config.account)
        self.journal.pause("session ended" + ("" if not problems else "; NOT FLAT: " + "; ".join(problems)))
        return problems

    def run(self, poll_s: int = 5, sleep: Callable[[float], None] = time.sleep) -> list[str]:
        """Attended loop until the session expiry, then `close_all()`."""
        expiry = datetime.fromisoformat(self.config.session_expires_at)
        try:
            while self.now() < expiry and self.journal.mode() == "STUDY":
                self.tick()
                sleep(poll_s)
        except KeyboardInterrupt:
            self.journal.pause("operator interrupt")
            self.log("interrupted: entries paused; closing positions")
        return self.close_all()
