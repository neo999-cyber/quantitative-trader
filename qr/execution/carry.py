"""The carry holding's execution leg: long spot, short perp, the same coin, the same quantity (`docs/34`).

Built 14 October 2026 while the Programme 3 recording accumulates, so that
the owner's ladder decision (C1's funding carry as a *holding*, `docs/31`
§15) has an execution path when it is taken — and nothing else: no live
order is placed by this code without the owner's typed mandate at a
terminal, exactly as stage 1 (`qr/execution/study.py`).

What a holding needs that the 15-minute study did not: two venues at
once (spot and USDⓈ-M perp), legs that must end up equal, a maker wait
followed by a taker completion so the hedge never stays half on,
funding booked as cash from the venue's own income rows, an imbalance
check with a rebalance, and an unwind that works in any state. Everything
goes through the journal (`qr/execution/journal.py`): every order is an
intent with a client id, every fill an execution posted once, every
funding payment a cash event keyed by the venue's transaction id.

Modes: `open` and `rebalance` run under a mandate (STUDY) and leave the
journal PAUSED with the positions standing; `close` works from PAUSED;
`status` and `funding` only read and book.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable

from qr.execution.journal import D, Intent, Journal, NavUncertain
from qr.execution.limits import StudyPolicy, check_entry, check_exit, gross_open_usd
from qr.execution.orders import cancel, reconcile, submit
from qr.execution.venues import Instrument, VenueError, VenueTimeout

__all__ = ["CarryConfig", "CarrySession", "preview", "start"]

SPOT_TAKER_BPS = D("7.5")     # Binance spot VIP 0 with BNB, maker = taker (the trial's verified tier)
PERP_MAKER_BPS = D("3.2")     # the measured maker cost, stage 1 (`docs/33`): fee blended at the fill rate plus the 60 s mark
PERP_TAKER_BPS = D("5.5")     # 4.5 taker with BNB plus a 1 bp half-spread
FUNDING_PERIODS_PER_YEAR = D(3 * 365)


@dataclass(frozen=True)
class CarryConfig:
    account: str
    coin: str
    spot_symbol: str
    perp_symbol: str
    notional_usd: str = "100"
    max_notional_usd: str = "150"
    ttl_s: int = 900
    max_imbalance_pct: str = "1.0"
    stop_loss_usd: str = "10"
    max_leverage: str = "2.5"
    testnet: bool = True
    version: str = "carry-v1"
    expires_at: str = ""            # ISO; the mandate's expiry, set by the CLI for one open/rebalance
    spot_venue: str = "binance_spot"
    perp_venue: str = "binance"

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]

    def policy(self) -> StudyPolicy:
        cap = D(self.max_notional_usd)
        return StudyPolicy(version=self.version, max_order_usd=cap, max_gross_usd=cap * 2 + D("1"), max_leverage=D(self.max_leverage),
                           stop_loss_usd=D(self.stop_loss_usd), max_mark_age_s=120,
                           eligible=(f"{self.spot_venue}:{self.spot_symbol}", f"{self.perp_venue}:{self.perp_symbol}"))


def matched_qty(spot: Instrument, perp: Instrument, notional: Decimal, price: Decimal) -> Decimal:
    """The largest quantity both venues accept for `notional` at `price`: rounded to the coarser step, above both minimums."""
    q = min(spot.qty_for_notional(notional, price), perp.qty_for_notional(notional, price))
    q = perp.round_qty(spot.round_qty(q))
    if q <= 0 or q < spot.min_qty or q < perp.min_qty or q * price < max(spot.min_notional, perp.min_notional):
        return D(0)
    return q


def preview(config: CarryConfig, venues: dict, out: Callable[[str], None] = print) -> dict:
    """Books, the matched quantity, the basis, the funding rate and the cost of a round trip; prints and returns it."""
    spot, perp = venues[config.spot_venue], venues[config.perp_venue]
    ins_s, ins_p = spot.instrument(config.spot_symbol), perp.instrument(config.perp_symbol)
    sb, sa = spot.book(config.spot_symbol)
    pb, pa = perp.book(config.perp_symbol)
    qty = matched_qty(ins_s, ins_p, D(config.notional_usd), sa)
    rate, next_ms = perp.funding_rate(config.perp_symbol)
    basis_bps = ((pb + pa) / 2 - (sb + sa) / 2) / ((sb + sa) / 2) * 10000
    entry_bps = SPOT_TAKER_BPS + PERP_MAKER_BPS           # the spot leg pays the taker fee either way at VIP 0; the perp leg at the measured maker cost
    found = {
        "config_hash": config.digest(), "testnet": config.testnet, "qty": str(qty), "spot": {"bid": str(sb), "ask": str(sa)}, "perp": {"bid": str(pb), "ask": str(pa)},
        "basis_bps": str(basis_bps.quantize(D("0.1"))), "funding_rate": str(rate), "funding_annualised_pct": str((rate * FUNDING_PERIODS_PER_YEAR * 100).quantize(D("0.01"))),
        "round_trip_bps": str(2 * entry_bps), "next_funding_ms": next_ms,
        # the coin and the quote currencies only: the spot testnet's faucet account holds hundreds of fake coins
        "balances": {config.spot_venue: {k: str(v) for k, v in spot.balances().items() if k in (config.coin, "USDT", "BNB", "USDC")},
                     config.perp_venue: {k: str(v) for k, v in perp.balances().items() if k in (config.coin, "USDT", "BNB", "USDC")}},
        "positions": {config.spot_venue: {k: str(v) for k, v in spot.positions().items()}, config.perp_venue: {k: str(v) for k, v in perp.positions().items()}},
    }
    out(f"carry {config.version}  config {config.digest()}  {'TESTNET' if config.testnet else 'MAINNET — REAL MONEY'}")
    out(f"{config.coin}: ${config.notional_usd} a leg (cap ${config.max_notional_usd}), qty {qty} ({'below a venue minimum' if qty == 0 else 'ok'}); "
        f"spot {sb}/{sa}, perp {pb}/{pa}, basis {found['basis_bps']} bps; funding {rate} per 8 h = {found['funding_annualised_pct']}%/yr at today's rate; "
        f"round trip ≈ {found['round_trip_bps']} bps; maker wait {config.ttl_s}s then taker; imbalance tolerance {config.max_imbalance_pct}%; "
        f"stop ${config.stop_loss_usd}; expires {config.expires_at or '(unset)'}")
    out(f"  balances {found['balances']}  positions {found['positions']}")
    return found


def start(journal: Journal, config: CarryConfig, venues: dict, typed: str, now: datetime | None = None) -> None:
    """The only way into a mandate: the operator types `<config hash> CARRY`. Books the venues' balances as the opening cash."""
    now = now or datetime.now(timezone.utc)
    if typed.strip() != f"{config.digest()} CARRY":
        raise PermissionError("mandate not confirmed: type the config hash and CARRY exactly")
    if not config.expires_at or datetime.fromisoformat(config.expires_at) <= now:
        raise PermissionError("the mandate expiry is unset or already past")
    if journal.mode() != "PAUSED":
        raise PermissionError(f"start only from PAUSED (mode is {journal.mode()})")
    for name in (config.spot_venue, config.perp_venue):
        balances = venues[name].balances()
        if not balances:
            raise PermissionError(f"{name} reports no balance: wrong key or account?")
        for currency, amount in balances.items():
            held = journal.cash(config.account).get((name, currency), D(0))
            if amount - held != 0:
                journal.cash_event(f"balance:{name}:{currency}:{now.isoformat(timespec='seconds')}:{amount}", config.account, name, currency,
                                   amount - held, "venue_balance_snapshot", now.isoformat())
    journal.db.execute("INSERT INTO audit (ts, kind, ref, detail) VALUES (?, ?, ?, ?)",
                       (now.isoformat(), "carry_mandate", config.digest(), json.dumps({"config": asdict(config), "venues": sorted(venues)})))
    journal.set_mode("STUDY", f"carry mandate {config.digest()} confirmed at the terminal; expires {config.expires_at}")


@dataclass
class _Leg:
    name: str          # "spot" | "perp"
    venue: str
    symbol: str
    side: str          # the holding's entry side on this leg: BUY (spot) | SELL (perp)


@dataclass
class _Working:
    intent: Intent
    leg: str
    placed_at: datetime
    kind: str          # maker | taker


@dataclass
class CarrySession:
    journal: Journal
    config: CarryConfig
    venues: dict
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    log: Callable[[str], None] = print
    working: dict[str, _Working] = field(default_factory=dict)
    instruments: dict[tuple[str, str], Instrument] = field(default_factory=dict)
    target_qty: Decimal = D(0)
    open_nav: Decimal | None = None

    def __post_init__(self) -> None:
        self.policy = self.config.policy()
        self.legs = {"spot": _Leg("spot", self.config.spot_venue, self.config.spot_symbol, "BUY"),
                     "perp": _Leg("perp", self.config.perp_venue, self.config.perp_symbol, "SELL")}
        self._attempt_n = 0
        self._load_working()
        self._restore_target()

    def _restore_target(self) -> None:
        """A new process picks the open's target up from the audit trail, so a half-open holding is still completed."""
        row = self.journal.db.execute("SELECT kind, detail FROM audit WHERE kind IN ('carry_open', 'carry_close') AND ref = ? ORDER BY seq DESC LIMIT 1",
                                      (self.config.digest(),)).fetchone()
        if row and row[0] == "carry_open":
            self.target_qty = D(row[1])

    # -- state ---------------------------------------------------------------------------------------------------------
    def _load_working(self) -> None:
        rows = self.journal.db.execute(
            "SELECT i.client_id, i.payload, o.state FROM intents i JOIN orders o ON o.client_id = i.client_id "
            "WHERE i.account = ? AND i.strategy_version = ? AND o.state IN ('STAGED', 'SUBMITTING', 'ACKED', 'PARTIAL', 'UNKNOWN', 'CANCEL_REQUESTED')",
            (self.config.account, self.config.version)).fetchall()
        for cid, payload, _ in rows:
            intent = Intent(**json.loads(payload))
            leg = "spot" if intent.venue == self.config.spot_venue else "perp"
            self.working[cid] = _Working(intent, leg, self.now(), "maker" if intent.post_only else "taker")

    def _instrument(self, leg: _Leg) -> Instrument:
        key = (leg.venue, leg.symbol)
        if key not in self.instruments:
            self.instruments[key] = self.venues[leg.venue].instrument(leg.symbol)
        return self.instruments[key]

    def _mark(self, leg: _Leg, t: datetime | None = None) -> tuple[Decimal, Decimal] | None:
        try:
            bid, ask = self.venues[leg.venue].book(leg.symbol)
        except (VenueError, VenueTimeout) as exc:
            self.log(f"no book for {leg.venue} {leg.symbol}: {exc}")
            return None
        self.journal.mark(leg.venue, leg.symbol, (bid + ask) / 2, (t or self.now()).isoformat())
        return bid, ask

    def held(self, leg_name: str) -> Decimal:
        leg = self.legs[leg_name]
        return self.journal.positions(self.config.account).get((leg.venue, leg.symbol), D(0))

    def _signal(self, leg: _Leg, kind: str, action: str) -> str:
        self._attempt_n = self.journal.db.execute("SELECT COUNT(*) FROM intents WHERE account = ? AND strategy_version = ?",
                                                  (self.config.account, self.config.version)).fetchone()[0] + 1
        return f"carry:{self.config.coin}:{leg.name}:{kind}:{action.lower()}:{self._attempt_n}"

    # -- orders --------------------------------------------------------------------------------------------------------
    def _maker(self, leg: _Leg, side: str, qty: Decimal, action: str, t: datetime) -> str | None:
        book = self._mark(leg, t)
        if book is None:
            return None
        bid, ask = book
        price = bid if side == "BUY" else ask
        reduce = action == "EXIT"
        intent = Intent(self.config.account, leg.venue, leg.symbol, side, str(qty), str(price), True, reduce, self.config.version,
                        self._signal(leg, "maker", action), action, (t + timedelta(seconds=self.config.ttl_s)).isoformat())
        reasons = (check_exit(self.journal, intent, self.policy) if reduce
                   else check_entry(self.journal, intent, self.policy, self.open_nav if self.open_nav is not None else self._nav(), t))
        if reasons:
            self.log(f"{leg.name} maker {action} refused: {reasons}")
            return None
        state = submit(self.journal, self.venues[leg.venue], intent)
        self.log(f"{leg.name} maker {action}: {side} {qty} {leg.symbol} @ {price} -> {state}")
        if state in ("ACKED", "PARTIAL", "UNKNOWN", "FILLED"):
            self.working[intent.client_id] = _Working(intent, leg.name, t, "maker")
        if state in ("FILLED", "CANCELLED", "REJECTED", "EXPIRED"):
            self.working.pop(intent.client_id, None)
        return state

    def _taker(self, leg: _Leg, side: str, qty: Decimal, action: str, t: datetime, market: bool = False) -> str | None:
        """An IOC through the touch (or a market order on the last round of a close) that completes a leg the maker wait left short."""
        book = self._mark(leg, t)
        if book is None:
            return None
        bid, ask = book
        ins = self._instrument(leg)
        price = ins.round_price(ask * D("1.002")) if side == "BUY" else ins.round_price(bid * D("0.998"))
        reduce = action == "EXIT"
        intent = Intent(self.config.account, leg.venue, leg.symbol, side, str(qty), str(price), False, reduce, self.config.version,
                        self._signal(leg, "market" if market else "taker", action), action, (t + timedelta(minutes=5)).isoformat())
        if reduce:
            reasons = check_exit(self.journal, intent, self.policy)
        else:
            # `check_entry` insists on post-only; a taker completion is the policy's own choice after the wait, so the caps are checked here
            reasons = []
            if self.journal.mode() != "STUDY":
                reasons.append(f"mode_{self.journal.mode().lower()}")
            if intent.notional() >= self.policy.max_order_usd:
                reasons.append("order_over_cap")
            try:
                if gross_open_usd(self.journal, self.config.account, self.policy, t) + intent.notional() > self.policy.max_gross_usd:
                    reasons.append("gross_cap")
            except NavUncertain as exc:
                reasons.append(f"nav_uncertain:{exc}")
        if reasons:
            self.log(f"{leg.name} taker {action} refused: {reasons}")
            return None
        self.journal.stage(intent)
        self.journal.transition(intent.client_id, "SUBMITTING", "market order (close's last resort)" if market else "IOC through the touch after the maker wait")
        venue = self.venues[leg.venue]
        try:
            if market:
                order = venue.close_market(intent.client_id, leg.symbol, side, qty) if reduce else venue.place_ioc(intent.client_id, leg.symbol, side, qty, price)
            else:
                order = venue.close_taker(intent.client_id, leg.symbol, side, qty, price) if reduce else venue.place_ioc(intent.client_id, leg.symbol, side, qty, price)
        except VenueTimeout as exc:
            self.journal.transition(intent.client_id, "UNKNOWN", f"timeout: {exc}")
            self.working[intent.client_id] = _Working(intent, leg.name, t, "taker")
            return "UNKNOWN"
        except VenueError as exc:
            self.journal.transition(intent.client_id, "REJECTED", f"venue refused: {exc}")
            return "REJECTED"
        state = reconcile(self.journal, venue, intent)
        filled = self.journal.db.execute("SELECT filled_qty FROM orders WHERE client_id = ?", (intent.client_id,)).fetchone()[0]
        self.log(f"{leg.name} taker {action}: {side} {qty} {leg.symbol} @ {price} -> {state} (filled {filled}/{order.qty})")
        if state in ("ACKED", "PARTIAL", "UNKNOWN"):
            self.working[intent.client_id] = _Working(intent, leg.name, t, "taker")
        return state

    def _reconcile_working(self, t: datetime, take_after_ttl: bool = True) -> None:
        for cid, w in list(self.working.items()):
            venue = self.venues[w.intent.venue]
            try:
                state = reconcile(self.journal, venue, w.intent)
            except (VenueError, VenueTimeout) as exc:
                self.log(f"reconcile {cid[:8]}: {exc}")
                continue
            if state in ("FILLED", "CANCELLED", "REJECTED", "EXPIRED"):
                self.working.pop(cid, None)
                continue
            if w.kind == "maker" and take_after_ttl and (t - w.placed_at).total_seconds() >= self.config.ttl_s:
                try:
                    state = cancel(self.journal, venue, w.intent)
                except (VenueError, VenueTimeout) as exc:
                    self.log(f"cancel {cid[:8]}: {exc}")
                    continue
                if state in ("FILLED", "CANCELLED", "REJECTED", "EXPIRED"):
                    self.working.pop(cid, None)

    def _nav(self, t: datetime | None = None) -> Decimal:
        return self.journal.nav(self.config.account, self.policy.currency, self.policy.max_mark_age_s, t or self.now())

    # -- the holding ---------------------------------------------------------------------------------------------------
    def open(self, t: datetime | None = None) -> Decimal:
        """Post both legs at the touch, post-only. Returns the matched quantity (0 when nothing was posted)."""
        t = t or self.now()
        if self.journal.mode() != "STUDY":
            raise PermissionError(f"open needs the mandate (mode is {self.journal.mode()})")
        if self.held("spot") != 0 or self.held("perp") != 0:
            raise PermissionError(f"not flat: spot {self.held('spot')}, perp {self.held('perp')}")
        spot, perp = self.legs["spot"], self.legs["perp"]
        books = self._mark(spot, t), self._mark(perp, t)
        if None in books:
            return D(0)
        self.open_nav = self._nav(t)
        qty = matched_qty(self._instrument(spot), self._instrument(perp), D(self.config.notional_usd), books[0][1])
        if qty == 0:
            self.log("quantity below a venue minimum; nothing posted")
            return D(0)
        self.target_qty = qty
        self.journal.db.execute("INSERT INTO audit (ts, kind, ref, detail) VALUES (?, ?, ?, ?)", (t.isoformat(), "carry_open", self.config.digest(), str(qty)))
        for leg in (spot, perp):
            self._maker(leg, leg.side, qty, "ENTRY", t)
        return qty

    def tick(self, t: datetime | None = None) -> dict:
        """Reconcile, cancel-and-take after the maker wait, re-mark both legs; returns the imbalance view."""
        t = t or self.now()
        for leg in self.legs.values():   # fresh marks first: every cap and NAV check below reads them at this tick's time
            self._mark(leg, t)
        self._reconcile_working(t)
        if self.target_qty > 0 and self.journal.mode() == "STUDY":
            for name in ("spot", "perp"):
                leg = self.legs[name]
                short = self.target_qty - abs(self.held(name))
                has_working = any(w.leg == name for w in self.working.values())
                if short > 0 and not has_working:
                    ins = self._instrument(leg)
                    short = ins.round_qty(short)
                    if short >= ins.min_qty:
                        self._taker(leg, leg.side, short, "ENTRY", t)
        return self.status(t)

    def complete(self) -> bool:
        """Both legs on, equal within the tolerance, nothing working."""
        spot, perp = abs(self.held("spot")), abs(self.held("perp"))
        if spot == 0 or perp == 0 or self.working:
            return False
        if self.target_qty > 0 and (spot < self.target_qty or perp < self.target_qty):
            return False
        return abs(spot - perp) / max(spot, perp) * 100 <= D(self.config.max_imbalance_pct)

    def status(self, t: datetime | None = None) -> dict:
        t = t or self.now()
        spot_q, perp_q = self.held("spot"), self.held("perp")
        marks = {name: self._mark(self.legs[name], t) for name in ("spot", "perp")}
        mid = {name: ((b[0] + b[1]) / 2 if b else None) for name, b in marks.items()}
        imbalance = spot_q - abs(perp_q)
        base = max(spot_q, abs(perp_q))
        funding = sum((D(a) for (a,) in self.journal.db.execute("SELECT amount FROM cash_events WHERE account = ? AND kind = 'funding'",
                                                               (self.config.account,)).fetchall()), D(0))
        try:
            nav = self._nav(t)
        except NavUncertain:
            nav = None
        basis = ((mid["perp"] - mid["spot"]) / mid["spot"] * 10000) if (mid["spot"] and mid["perp"]) else None
        view = {"mode": self.journal.mode(), "spot_qty": str(spot_q), "perp_qty": str(perp_q), "imbalance_qty": str(imbalance),
                "imbalance_pct": str((abs(imbalance) / base * 100).quantize(D("0.01"))) if base else "0", "working": len(self.working),
                "funding_collected": str(funding), "nav": str(nav) if nav is not None else None, "basis_bps": str(basis.quantize(D("0.1"))) if basis is not None else None,
                "marks": {k: (str(v) if v is not None else None) for k, v in mid.items()}, "complete": self.complete()}
        return view

    def book_funding(self, t: datetime | None = None) -> int:
        """Post every funding payment the perp venue reports, once each; returns how many were new."""
        perp = self.legs["perp"]
        last = self.journal.db.execute("SELECT MAX(venue_ts) FROM cash_events WHERE account = ? AND kind = 'funding'", (self.config.account,)).fetchone()[0]
        since = int(datetime.fromisoformat(last).timestamp() * 1000) - 1 if last else None
        new = 0
        for row in self.venues[perp.venue].income(perp.symbol, since_ms=since):
            ts = datetime.fromtimestamp(row["time_ms"] / 1000, tz=timezone.utc).isoformat()
            if self.journal.cash_event(f"funding:{row['tran_id']}", self.config.account, perp.venue, row["asset"], row["amount"], "funding", ts):
                new += 1
        return new

    def rebalance(self, t: datetime | None = None) -> str:
        """Bring the perp leg back to the spot leg's quantity when the imbalance exceeds the tolerance; the perp is the cheaper leg to touch."""
        t = t or self.now()
        spot_q, perp_q = self.held("spot"), abs(self.held("perp"))
        diff = spot_q - perp_q
        base = max(spot_q, perp_q)
        if base == 0 or abs(diff) / base * 100 <= D(self.config.max_imbalance_pct):
            return "within_tolerance"
        perp = self.legs["perp"]
        ins = self._instrument(perp)
        q = ins.round_qty(abs(diff))
        if q < ins.min_qty:
            return "below_min_qty"
        if diff > 0:   # too little perp short: sell more (an entry, needs the mandate)
            if self.journal.mode() != "STUDY":
                raise PermissionError("adding to the perp leg needs the mandate")
            self.target_qty = spot_q
            return self._maker(perp, "SELL", q, "ENTRY", t) or "refused"
        return self._maker(perp, "BUY", q, "EXIT", t) or "refused"   # too much perp short: buy some back (reduce-only, no mandate needed)

    def close(self, rounds: int = 4, pause: Callable[[float], None] = time.sleep, wait_s: float | None = None) -> list[str]:
        """Unwind both legs: cancel what is working, maker exits, then taker, then market; leaves the journal PAUSED."""
        t = self.now()
        self.target_qty = D(0)
        self.journal.db.execute("INSERT INTO audit (ts, kind, ref, detail) VALUES (?, ?, ?, ?)", (t.isoformat(), "carry_close", self.config.digest(), "close requested"))
        for cid, w in list(self.working.items()):
            try:
                if cancel(self.journal, self.venues[w.intent.venue], w.intent) in ("FILLED", "CANCELLED", "REJECTED", "EXPIRED"):
                    self.working.pop(cid, None)
            except (VenueError, VenueTimeout) as exc:
                self.log(f"cancel {cid[:8]} during close: {exc}")
        events: list[str] = []
        for rnd in range(rounds):
            flat = True
            for name in ("spot", "perp"):
                leg = self.legs[name]
                held = self.held(name)
                if held == 0:
                    continue
                flat = False
                side = "SELL" if held > 0 else "BUY"
                qty = abs(held)
                if rnd == 0:
                    state = self._maker(leg, side, qty, "EXIT", self.now())
                else:
                    state = self._taker(leg, side, qty, "EXIT", self.now(), market=(rnd == rounds - 1))
                events.append(f"round {rnd + 1} {name} {side} {qty} -> {state}")
            if flat:
                break
            pause(wait_s if wait_s is not None else (self.config.ttl_s if rnd == 0 else 2.0))
            self._reconcile_working(self.now(), take_after_ttl=False)
            for cid, w in list(self.working.items()):   # whatever is still resting is cancelled before the next round
                try:
                    if cancel(self.journal, self.venues[w.intent.venue], w.intent) in ("FILLED", "CANCELLED", "REJECTED", "EXPIRED"):
                        self.working.pop(cid, None)
                except (VenueError, VenueTimeout) as exc:
                    self.log(f"cancel {cid[:8]} during close: {exc}")
        flat = self.held("spot") == 0 and self.held("perp") == 0
        events.append("flat" if flat else f"NOT FLAT: spot {self.held('spot')} perp {self.held('perp')}")
        if self.journal.mode() == "STUDY":
            self.journal.set_mode("PAUSED", "carry close finished" if flat else "carry close finished with a remainder")
        return events

    def park(self) -> None:
        """After the legs are on: leave the mandate (the positions stand; nothing else can be entered until the next typed line)."""
        if self.journal.mode() == "STUDY":
            self.journal.set_mode("PAUSED", "carry holding on; mandate released")
