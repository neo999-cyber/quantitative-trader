"""B14 adapters (fake venue), B11/B15 order walk: the races the journal must survive."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from qr.execution.journal import D, Intent, Journal
from qr.execution.orders import cancel, reconcile, submit
from qr.execution.venues import BinanceUSDM, BybitLinear, FakeVenue, Instrument, VenueTimeout

NOW = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)


def intent(side="BUY", qty="10", limit="0.70", action="ENTRY", signal="s1", symbol="SUIUSDT"):
    return Intent(account="acct", venue="fake", symbol=symbol, side=side, qty=qty, limit=limit, post_only=action == "ENTRY",
                  reduce_only=action == "EXIT", strategy_version="stage1-v1", signal_id=signal, action=action,
                  expires_at=(NOW + timedelta(minutes=15)).isoformat())


@pytest.fixture()
def venue():
    return FakeVenue(instruments={"SUIUSDT": Instrument("fake", "SUIUSDT", D("0.0001"), D("0.1"), D("1"), D("5"))},
                     books={"SUIUSDT": (D("0.70"), D("0.7001"))})


@pytest.fixture()
def journal(tmp_path):
    j = Journal(tmp_path / "j.sqlite")
    j.set_mode("STUDY", "test")
    j.cash_event("dep", "acct", "fake", "USDT", "100", "transfer", NOW.isoformat())
    return j


def test_place_ack_fill_and_the_fee_is_posted_from_the_venues_execution(journal, venue):
    i = intent()
    assert submit(journal, venue, i) == "ACKED"
    venue.fill_on_place = D("10")  # simulate the resting order filling later
    o = venue.orders[i.client_id]
    venue._exec(o, D("10"))
    assert reconcile(journal, venue, i) == "FILLED"
    assert journal.positions("acct")[("fake", "SUIUSDT")] == D("10")
    fee = D("10") * D("0.70") * D("2") / D("10000")
    assert journal.cash("acct")[("fake", "USDT")] == D("100") - D("7") - fee
    assert submit(journal, venue, i) == "FILLED"  # a retry sends nothing and reports the state


def test_a_timeout_after_the_venue_accepted_is_unknown_and_reconciles_without_a_resend(journal, venue):
    venue.timeout_after_accept = True
    i = intent()
    assert submit(journal, venue, i) == "UNKNOWN"
    assert len(venue.orders) == 1
    assert submit(journal, venue, i) == "UNKNOWN"  # still no second order
    assert len(venue.orders) == 1
    assert reconcile(journal, venue, i) == "ACKED"


def test_a_request_the_venue_never_saw_is_rejected_on_reconciliation(journal, venue):
    i = intent()
    journal.stage(i)
    journal.transition(i.client_id, "SUBMITTING", "sending")
    journal.transition(i.client_id, "UNKNOWN", "timeout before any answer")
    assert reconcile(journal, venue, i) == "REJECTED"
    assert journal.reserved("acct") == (D(0), D(0))


def test_a_partial_fill_then_a_cancel_that_fills_the_rest_books_both(journal, venue):
    venue.fill_on_place = D("4")
    i = intent()
    assert submit(journal, venue, i) == "PARTIAL"
    assert journal.positions("acct")[("fake", "SUIUSDT")] == D("4")
    venue.fill_on_cancel = True
    assert cancel(journal, venue, i) == "FILLED"
    assert journal.positions("acct")[("fake", "SUIUSDT")] == D("10")
    assert len(venue.fills) == 2 and len(journal.db.execute("SELECT 1 FROM executions").fetchall()) == 2


def test_a_post_only_order_that_would_cross_is_expired_not_filled(journal, venue):
    i = intent(limit="0.71")  # above the ask
    assert submit(journal, venue, i) == "EXPIRED"
    assert journal.positions("acct") == {}


def test_a_reduce_only_close_cannot_reverse(journal, venue):
    venue.fill_on_place = D("10")
    submit(journal, venue, intent())
    too_big = intent(side="SELL", qty="12", limit="0.7001", action="EXIT", signal="e1")
    assert submit(journal, venue, too_big) == "REJECTED"
    ok = intent(side="SELL", qty="10", limit="0.7001", action="EXIT", signal="e2")
    venue.fill_on_place = D("10")
    assert submit(journal, venue, ok) == "FILLED"
    assert journal.positions("acct") == {}


def test_instrument_rounding_and_minimums():
    ins = Instrument("x", "S", D("0.0001"), D("0.1"), D("1"), D("5"))
    assert ins.round_price(D("0.70007")) == D("0.7000")
    assert ins.qty_for_notional(D("9.5"), D("0.7")) == D("13.5")
    assert ins.qty_for_notional(D("3"), D("0.7")) == D(0)  # under the $5 minimum


class _Recorder:
    """A transport that records the request and answers with a canned body."""

    def __init__(self, body):
        self.body, self.calls = body, []

    def request(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        return 200, self.body


def test_binance_signs_the_query_and_sends_gtx_post_only():
    t = _Recorder(b'{"orderId": 1, "clientOrderId": "c", "symbol": "SUIUSDT", "side": "BUY", "status": "NEW", "origQty": "10", "executedQty": "0", "price": "0.7"}')
    v = BinanceUSDM("k", "s", transport=t)
    o = v.place_post_only("c", "SUIUSDT", "BUY", D("10"), D("0.7"))
    method, url, headers, _ = t.calls[0]
    assert method == "POST" and url.startswith("https://demo-fapi.binance.com/fapi/v1/order?")
    assert "timeInForce=GTX" in url and "signature=" in url and headers["X-MBX-APIKEY"] == "k"
    assert "reduceOnly" not in url and o.status == "NEW"


def test_bybit_signs_headers_over_the_body_and_reads_the_order_back():
    create = b'{"retCode": 0, "result": {"orderId": "9", "orderLinkId": "c"}}'
    read = b'{"retCode": 0, "result": {"list": [{"orderId": "9", "orderLinkId": "c", "symbol": "SUIUSDT", "side": "Buy", "orderStatus": "New", "qty": "10", "cumExecQty": "0", "price": "0.7"}]}}'

    class T:
        def __init__(self):
            self.calls = []

        def request(self, method, url, headers, body):
            self.calls.append((method, url, headers, body))
            return 200, (create if "create" in url else read)

    t = T()
    v = BybitLinear("k", "s", transport=t)
    o = v.place_post_only("c", "SUIUSDT", "BUY", D("10"), D("0.7"), reduce_only=True)
    method, url, headers, body = t.calls[0]
    assert method == "POST" and url == "https://api-testnet.bybit.com/v5/order/create"
    assert b'"timeInForce":"PostOnly"' in body and b'"reduceOnly":true' in body and headers["X-BAPI-SIGN"]
    assert o.status == "NEW" and o.side == "BUY" and o.venue_order_id == "9"


def test_a_transport_timeout_surfaces_as_venue_timeout():
    class T:
        def request(self, *a):
            raise VenueTimeout("no answer")

    with pytest.raises(VenueTimeout):
        BinanceUSDM("k", "s", transport=T()).book("SUIUSDT")
