"""B11/B15 glue — walk one intent through a venue, journal every step, reconcile what is unknown.

`submit()` is the only function that sends an order. It stages the intent
(idempotent), moves it to SUBMITTING *before* the network call, places a
post-only order, and books the venue's answer. A timeout after the request
may have reached the venue books UNKNOWN and returns; nothing is resent.
`reconcile()` asks the venue what it holds for that client id and moves
the order to a known state, posting any executions once by their venue
ids. `cancel()` requests a cancel and reconciles — a cancel request is not
a cancellation, and a fill can land while it is processed.

Fees are posted from the venue's executions as they are reported, in the
fee currency the venue names. Positions and cash in the journal are only
ever changed by executions and cash events, never by an order state.
"""
from __future__ import annotations

from decimal import Decimal

from qr.execution.journal import Intent, Journal
from qr.execution.venues import Order, VenueError, VenueTimeout

__all__ = ["submit", "reconcile", "cancel", "STATE_OF"]

STATE_OF = {"NEW": "ACKED", "PARTIALLY_FILLED": "PARTIAL", "FILLED": "FILLED", "CANCELED": "CANCELLED",
            "REJECTED": "REJECTED", "EXPIRED": "EXPIRED"}


def _post_fills(journal: Journal, venue, intent: Intent, order: Order) -> int:
    """Post every venue execution for this order once; returns how many were new."""
    new = 0
    for x in venue.executions(intent.symbol):
        if x.venue_order_id != order.venue_order_id:
            continue
        if journal.execution(x.exec_id, intent.client_id, x.qty, x.price, x.fee, x.fee_currency, x.venue_ts,
                             content={"venue_order_id": x.venue_order_id, "maker": x.maker}):
            new += 1
    return new


def _book_state(journal: Journal, venue, intent: Intent, order: Order, evidence: str) -> str:
    target = STATE_OF[order.status]
    current = journal.state(intent.client_id)
    if order.filled > 0:
        _post_fills(journal, venue, intent, order)
    if target != current:
        if current == "UNKNOWN":
            evidence = "reconciled: " + evidence
        try:
            journal.transition(intent.client_id, target, evidence, venue_order_id=order.venue_order_id)
        except ValueError:
            # PARTIAL -> PARTIAL is a permitted self-transition; anything else is a real error
            if not (current == "PARTIAL" and target == "PARTIAL"):
                raise
    return journal.state(intent.client_id)


def submit(journal: Journal, venue, intent: Intent, reserve_cash: Decimal | str = "0") -> str:
    """Stage, mark SUBMITTING, place post-only, book the answer. Returns the journal state."""
    state = journal.stage(intent, reserve_cash)
    if state != "STAGED":
        return state  # already sent once: never send again from here
    journal.transition(intent.client_id, "SUBMITTING", f"sending post-only {intent.side} {intent.qty} {intent.symbol} @ {intent.limit} to {venue.name}")
    try:
        order = venue.place_post_only(intent.client_id, intent.symbol, intent.side, Decimal(intent.qty), Decimal(intent.limit), intent.reduce_only)
    except VenueTimeout as exc:
        journal.transition(intent.client_id, "UNKNOWN", f"timeout: {exc}")
        return "UNKNOWN"
    except VenueError as exc:
        journal.transition(intent.client_id, "REJECTED", f"venue refused: {exc}")
        return "REJECTED"
    return _book_state(journal, venue, intent, order, f"venue answered {order.status} ({order.venue_order_id})")


def reconcile(journal: Journal, venue, intent: Intent) -> str:
    """Ask the venue and move the order to what it says. The only way out of UNKNOWN."""
    try:
        order = venue.order(intent.symbol, intent.client_id)
    except VenueError as exc:
        if journal.state(intent.client_id) == "UNKNOWN":
            # the venue never saw it: the request did not arrive, and it may be re-staged under a new signal id
            journal.transition(intent.client_id, "REJECTED", f"reconciled: venue has no order for this client id ({exc})")
            return "REJECTED"
        raise
    return _book_state(journal, venue, intent, order, f"venue reports {order.status} filled {order.filled}/{order.qty}")


def cancel(journal: Journal, venue, intent: Intent) -> str:
    """Request a cancel, then book whatever the venue says happened — including a fill in the meantime."""
    state = journal.state(intent.client_id)
    if state in ("FILLED", "CANCELLED", "REJECTED", "EXPIRED"):
        return state
    if state == "UNKNOWN":
        return reconcile(journal, venue, intent)
    if state != "CANCEL_REQUESTED":  # a repeated cancel does not re-enter the state it is in
        journal.transition(intent.client_id, "CANCEL_REQUESTED", "cancel requested")
    try:
        order = venue.cancel(intent.symbol, intent.client_id)
    except VenueTimeout as exc:
        journal.transition(intent.client_id, "UNKNOWN", f"cancel timeout: {exc}")
        return "UNKNOWN"
    except VenueError as exc:
        # the venue will not cancel it: it is no longer open (filled, expired or already
        # cancelled) — Binance says -2011 "Unknown order sent" for a filled order (18 Sep 2026).
        # A refused cancel is a reason to look, never a reason to assume.
        journal.db.execute("INSERT INTO audit (ts, kind, ref, detail) VALUES (datetime('now'), 'cancel_refused', ?, ?)", (intent.client_id, str(exc)[:300]))
        return reconcile(journal, venue, intent)
    return _book_state(journal, venue, intent, order, f"after cancel request venue reports {order.status} filled {order.filled}/{order.qty}")
