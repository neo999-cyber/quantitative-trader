"""B12 — deterministic limits for the maker-fill study's stage 1 (`docs/24`, `docs/27`).

Pure functions over a `Journal` and a proposed `Intent`: every check
returns the list of reasons an order is refused; an empty list means the
order may be staged. Nothing here talks to a venue. The numbers are the
study's registered caps, frozen in `StudyPolicy`; changing them is a new
version with a reason, not an edit.

Entries (`action == "ENTRY"`):
- the mode is `STUDY`;
- the intent is post-only and not past its expiry;
- notional under `max_order_usd` ($10);
- gross open exposure — held positions at their marks **plus every
  unreleased reservation** — stays at or under `max_gross_usd` ($50)
  across both venues after this order;
- no leverage: cash after reservations covers the order (1×);
- the symbol is on the study's eligible list (chosen from stage 0's
  shape and written down before the first order);
- NAV is known (every held instrument has a fresh mark);
- the session's loss stop (`stop_loss_usd`, $25 against the session's
  opening NAV) has not tripped;
- at most `max_open_per_symbol` (1) working entry per symbol and side.

Exits (`action == "EXIT"`): reduce-only, and the quantity may not exceed
the held quantity minus what other working exits already claim, so an
exit can never reverse a position or double-close. Exits are allowed in
`STUDY` and `PAUSED` (pausing stops new risk, not the way out).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from qr.execution.journal import D, Intent, Journal, NavUncertain

__all__ = ["StudyPolicy", "check_entry", "check_exit", "gross_open_usd"]


@dataclass(frozen=True)
class StudyPolicy:
    version: str = "stage1-v1"
    max_order_usd: Decimal = D("10")
    max_gross_usd: Decimal = D("50")
    max_leverage: Decimal = D("1")
    stop_loss_usd: Decimal = D("25")
    max_mark_age_s: int = 30
    max_open_per_symbol: int = 1
    eligible: tuple[str, ...] = field(default_factory=tuple)  # (venue, symbol) pairs as "venue:SYMBOL"
    currency: str = "USDT"

    def __post_init__(self) -> None:
        if self.max_order_usd <= 0 or self.max_gross_usd < self.max_order_usd or self.max_leverage <= 0 or self.stop_loss_usd <= 0:
            raise ValueError("inconsistent study policy")


def gross_open_usd(journal: Journal, account: str, policy: StudyPolicy, now: datetime | None = None) -> Decimal:
    """|held| at marks plus unreleased reservations, across venues. Raises NavUncertain on a missing mark."""
    total = D(0)
    for (venue, symbol), qty in journal.positions(account).items():
        row = journal.db.execute("SELECT price, ts FROM marks WHERE venue = ? AND symbol = ?", (venue, symbol)).fetchone()
        if row is None:
            raise NavUncertain(f"no mark for {symbol} on {venue}")
        age = ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(row[1])).total_seconds()
        if age > policy.max_mark_age_s:
            raise NavUncertain(f"mark for {symbol} on {venue} is {age:.0f}s old")
        total += abs(qty) * D(row[0])
    _, reserved_notional = journal.reserved(account)
    return total + reserved_notional


def _working(journal: Journal, account: str, symbol: str, venue: str, side: str, action: str) -> int:
    row = journal.db.execute(
        "SELECT COUNT(*) FROM intents i JOIN orders o ON o.client_id = i.client_id "
        "WHERE i.account = ? AND i.symbol = ? AND i.venue = ? AND i.side = ? AND i.action = ? "
        "AND o.state NOT IN ('FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')",
        (account, symbol, venue, side, action),
    ).fetchone()
    return int(row[0])


def check_entry(
    journal: Journal, intent: Intent, policy: StudyPolicy, session_open_nav: Decimal, now: datetime | None = None
) -> list[str]:
    """Reasons this entry is refused; empty means it may be staged."""
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    if intent.action != "ENTRY":
        return ["not_an_entry"]
    if journal.mode() != "STUDY":
        reasons.append(f"mode_{journal.mode().lower()}")
    if not intent.post_only:
        reasons.append("entry_must_be_post_only")
    if intent.reduce_only:
        reasons.append("entry_cannot_be_reduce_only")
    if intent.currency != policy.currency:
        reasons.append("currency_not_in_policy")
    if f"{intent.venue}:{intent.symbol}" not in policy.eligible:
        reasons.append("symbol_not_eligible")
    try:
        if datetime.fromisoformat(intent.expires_at) <= now:
            reasons.append("intent_expired")
    except ValueError:
        reasons.append("bad_expiry")
    notional = intent.notional()
    if notional >= policy.max_order_usd:
        reasons.append("order_over_cap")
    try:
        gross = gross_open_usd(journal, intent.account, policy, now)
        nav = journal.nav(intent.account, policy.currency, policy.max_mark_age_s, now)
    except NavUncertain as exc:
        reasons.append(f"nav_uncertain:{exc}")
        return sorted(set(reasons))
    if gross + notional > policy.max_gross_usd:
        reasons.append("gross_cap")
    reserved_cash, reserved_notional = journal.reserved(intent.account)
    free_cash = sum((a for (v, c), a in journal.cash(intent.account).items() if c == policy.currency), D(0)) - reserved_cash - reserved_notional
    if notional > free_cash * policy.max_leverage:
        reasons.append("insufficient_unreserved_cash")
    if nav <= session_open_nav - policy.stop_loss_usd:
        reasons.append("session_loss_stop")
    if _working(journal, intent.account, intent.symbol, intent.venue, intent.side, "ENTRY") >= policy.max_open_per_symbol:
        reasons.append("entry_already_working")
    return sorted(set(reasons))


def check_exit(journal: Journal, intent: Intent, policy: StudyPolicy) -> list[str]:
    """Reasons this exit is refused: it must reduce, and only what is held and unclaimed."""
    reasons: list[str] = []
    if intent.action != "EXIT":
        return ["not_an_exit"]
    if journal.mode() not in ("STUDY", "PAUSED"):
        reasons.append(f"mode_{journal.mode().lower()}")
    if not intent.reduce_only:
        reasons.append("exit_must_be_reduce_only")
    held = journal.positions(intent.account).get((intent.venue, intent.symbol), D(0))
    signed = D(intent.qty) if intent.side == "BUY" else -D(intent.qty)
    if held == 0 or (held > 0) == (signed > 0):
        reasons.append("exit_does_not_reduce")
        return sorted(set(reasons))
    claimed = D(0)
    for (qty,) in journal.db.execute(
        "SELECT i.qty FROM intents i JOIN orders o ON o.client_id = i.client_id "
        "WHERE i.account = ? AND i.venue = ? AND i.symbol = ? AND i.action = 'EXIT' AND i.client_id != ? "
        "AND o.state NOT IN ('FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')",
        (intent.account, intent.venue, intent.symbol, intent.client_id),
    ).fetchall():
        claimed += D(qty)
    if D(intent.qty) > abs(held) - claimed:
        reasons.append("exit_exceeds_unclaimed_holding")
    return sorted(set(reasons))
