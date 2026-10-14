"""The carry holding's execution leg (`qr/execution/carry.py`, `docs/34`) on the fake venues: both legs, the wait, the take, funding, rebalance, close."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from qr.execution.carry import CarryConfig, CarrySession, matched_qty, preview, start
from qr.execution.journal import Journal
from qr.execution.venues import BinanceSpot, Execution, FakeVenue, Instrument

T0 = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)
SYM = "ETHUSDT"


def _venues(spot_fill=D(0), perp_fill=D(0)):
    spot = FakeVenue(name="binance_spot", cash=D("300"))
    spot.instruments[SYM] = Instrument("binance_spot", SYM, D("0.01"), D("0.001"), D("0.001"), D("5"))
    spot.books[SYM] = (D("100.00"), D("100.10"))
    spot.fill_on_place = spot_fill
    perp = FakeVenue(name="binance", cash=D("100"))
    perp.instruments[SYM] = Instrument("binance", SYM, D("0.01"), D("0.01"), D("0.01"), D("5"))
    perp.books[SYM] = (D("100.05"), D("100.15"))
    perp.fill_on_place = perp_fill
    return {"binance_spot": spot, "binance": perp}


def _config(**kw):
    base = dict(account="carry-test", coin="ETH", spot_symbol=SYM, perp_symbol=SYM, notional_usd="100", max_notional_usd="150",
                ttl_s=120, max_imbalance_pct="1.0", stop_loss_usd="10", max_leverage="2.5", testnet=True, version="carry-test",
                expires_at=(T0 + timedelta(hours=2)).isoformat())
    base.update(kw)
    return CarryConfig(**base)


def _session(tmp_path, venues, config=None, t=None):
    cfg = config or _config()
    journal = Journal(tmp_path / "carry.sqlite")
    clock = {"t": t or T0}
    start(journal, cfg, venues, f"{cfg.digest()} CARRY", now=clock["t"])
    s = CarrySession(journal, cfg, venues, now=lambda: clock["t"], log=lambda *_: None)
    return s, clock


def test_matched_quantity_respects_both_steps_and_minimums():
    spot = Instrument("s", SYM, D("0.01"), D("0.001"), D("0.001"), D("5"))
    perp = Instrument("p", SYM, D("0.01"), D("0.01"), D("0.01"), D("5"))
    assert matched_qty(spot, perp, D("100"), D("100.10")) == D("0.99")     # 0.999 on spot, 0.99 on the perp's coarser step
    assert matched_qty(spot, perp, D("0.5"), D("100.10")) == 0               # under both minimum notionals


def test_mandate_is_typed_and_books_the_opening_balances(tmp_path):
    cfg = _config()
    journal = Journal(tmp_path / "c.sqlite")
    with pytest.raises(PermissionError, match="mandate"):
        start(journal, cfg, _venues(), "nope", now=T0)
    with pytest.raises(PermissionError, match="expiry"):
        start(journal, _config(expires_at=""), _venues(), f"{_config(expires_at='').digest()} CARRY", now=T0)
    start(journal, cfg, _venues(), f"{cfg.digest()} CARRY", now=T0)
    assert journal.mode() == "STUDY"
    assert journal.cash("carry-test") == {("binance_spot", "USDT"): D("300"), ("binance", "USDT"): D("100")}
    with pytest.raises(PermissionError, match="PAUSED"):
        start(journal, cfg, _venues(), f"{cfg.digest()} CARRY", now=T0)


def test_preview_reports_quantity_basis_and_funding():
    out = []
    found = preview(_config(), _venues(), out=out.append)
    assert found["qty"] == "0.99" and found["basis_bps"] == "5.0"
    assert found["funding_rate"] == "0.0001" and found["funding_annualised_pct"] == "10.95"
    assert "TESTNET" in out[0]


def test_both_legs_fill_as_maker_and_the_holding_is_complete(tmp_path):
    s, clock = _session(tmp_path, _venues(spot_fill=D("0.99"), perp_fill=D("0.99")))
    assert s.open(T0) == D("0.99")
    view = s.tick(T0 + timedelta(seconds=5))
    assert s.held("spot") == D("0.99") and s.held("perp") == D("-0.99")
    assert view["complete"] and D(view["imbalance_qty"]) == 0 and view["working"] == 0
    s.park()
    assert s.journal.mode() == "PAUSED"
    with pytest.raises(PermissionError, match="mandate"):    # parked: nothing can be entered without the next typed line
        s.open(T0)
    start(s.journal, s.config, s.venues, f"{s.config.digest()} CARRY", now=T0)   # a mandate while holding is allowed (rebalance needs it)
    with pytest.raises(PermissionError, match="not flat"):   # but a second open is not
        s.open(T0)


def test_a_leg_left_unfilled_after_the_wait_is_taken(tmp_path):
    venues = _venues(spot_fill=D("0.99"))              # the perp maker never fills
    s, clock = _session(tmp_path, venues)
    s.open(T0)
    s.tick(T0 + timedelta(seconds=30))
    assert s.held("perp") == 0 and len(s.working) == 1
    clock["t"] = T0 + timedelta(seconds=121)            # past the maker wait: cancel and take
    view = s.tick(clock["t"])
    assert s.held("perp") == D("-0.99") and view["complete"]
    kinds = [r[0] for r in s.journal.db.execute("SELECT signal_id FROM intents WHERE account = 'carry-test' ORDER BY staged_at").fetchall()]
    assert any(":perp:maker:entry:" in k for k in kinds) and any(":perp:taker:entry:" in k for k in kinds)


def test_a_partial_take_is_completed_on_the_next_tick(tmp_path):
    venues = _venues(spot_fill=D("0.99"))
    venues["binance"].taker_fills = [D("0.40"), D("0.59")]
    s, clock = _session(tmp_path, venues)
    s.open(T0)
    clock["t"] = T0 + timedelta(seconds=121)
    s.tick(clock["t"])
    assert s.held("perp") == D("-0.40")
    clock["t"] += timedelta(seconds=5)
    s.tick(clock["t"])
    assert s.held("perp") == D("-0.99") and s.complete()


def test_funding_is_booked_once_per_transaction(tmp_path):
    venues = _venues(spot_fill=D("0.99"), perp_fill=D("0.99"))
    s, clock = _session(tmp_path, venues)
    s.open(T0); s.tick(T0)
    venues["binance"].funding = [{"tran_id": "f1", "symbol": SYM, "amount": D("0.0123"), "asset": "USDT", "time_ms": int((T0 + timedelta(hours=8)).timestamp() * 1000), "kind": "FUNDING_FEE"},
                                 {"tran_id": "f2", "symbol": SYM, "amount": D("-0.0040"), "asset": "USDT", "time_ms": int((T0 + timedelta(hours=16)).timestamp() * 1000), "kind": "FUNDING_FEE"}]
    assert s.book_funding() == 2 and s.book_funding() == 0
    assert s.status()["funding_collected"] == "0.0083"


def test_rebalance_adds_to_the_perp_leg_when_it_is_short(tmp_path):
    venues = _venues(spot_fill=D("0.99"), perp_fill=D("0.50"))   # the perp maker fills half on place, the rest is cancelled below
    s, clock = _session(tmp_path, venues)
    s.open(T0)
    clock["t"] = T0 + timedelta(seconds=121)
    venues["binance"].taker_fills = [D("0")]                      # the take after the wait gets nothing: a 0.49 imbalance stands
    s.tick(clock["t"])
    assert s.held("spot") == D("0.99") and s.held("perp") == D("-0.50")
    assert s.status()["imbalance_pct"] == "49.49"
    venues["binance"].fill_on_place = D("0.49")
    assert s.rebalance(clock["t"]) == "FILLED"
    assert s.held("perp") == D("-0.99") and s.rebalance(clock["t"]) == "within_tolerance"


def test_close_unwinds_both_legs_and_pauses(tmp_path):
    venues = _venues(spot_fill=D("0.99"), perp_fill=D("0.99"))
    s, clock = _session(tmp_path, venues)
    s.open(T0); s.tick(T0)
    venues["binance_spot"].fill_on_place = D("0.99")
    venues["binance"].fill_on_place = D("0.99")
    events = s.close(rounds=3, pause=lambda _: None, wait_s=0)
    assert s.held("spot") == 0 and s.held("perp") == 0 and events[-1] == "flat"
    assert s.journal.mode() == "PAUSED"


def test_close_falls_through_to_taker_when_makers_do_not_fill(tmp_path):
    venues = _venues(spot_fill=D("0.99"), perp_fill=D("0.99"))
    s, clock = _session(tmp_path, venues)
    s.open(T0); s.tick(T0)
    events = s.close(rounds=3, pause=lambda _: None, wait_s=0)   # no fill_on_place now: the maker exits rest, round 2 takes
    assert events[-1] == "flat" and any("round 2" in e for e in events)
    assert s.held("spot") == 0 and s.held("perp") == 0


class _Capture:
    """A transport that records the request and answers from a script."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def request(self, method, url, headers, body):
        self.calls.append((method, url))
        return 200, self.answers.pop(0)


def test_spot_client_sends_limit_maker_and_reads_trades_and_balances():
    import json

    tr = _Capture([
        json.dumps({"orderId": 7, "clientOrderId": "c1", "symbol": "BTCUSDT", "side": "BUY", "status": "NEW", "origQty": "0.001", "executedQty": "0", "price": "100"}).encode(),
        json.dumps([{"id": 1, "orderId": 7, "symbol": "BTCUSDT", "isBuyer": True, "qty": "0.001", "price": "100", "commission": "0.0000007", "commissionAsset": "BTC", "time": 1, "isMaker": True}]).encode(),
        json.dumps({"balances": [{"asset": "BTC", "free": "0.0010", "locked": "0"}, {"asset": "USDT", "free": "50", "locked": "10"}]}).encode(),
        json.dumps({"symbols": [{"symbol": "BTCUSDT", "baseAsset": "BTC", "filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.01"}, {"filterType": "LOT_SIZE", "stepSize": "0.00001", "minQty": "0.00001"}, {"filterType": "NOTIONAL", "minNotional": "5"}]}]}).encode(),
        json.dumps({"balances": [{"asset": "BTC", "free": "0.0010", "locked": "0"}, {"asset": "USDT", "free": "50", "locked": "10"}]}).encode(),
    ])
    v = BinanceSpot("k", "s", base=BinanceSpot.TESTNET, transport=tr, symbols=("BTCUSDT",))
    o = v.place_post_only("c1", "BTCUSDT", "BUY", D("0.001"), D("100"))
    assert o.status == "NEW" and "type=LIMIT_MAKER" in tr.calls[0][1] and "/api/v3/order" in tr.calls[0][1]
    x = v.executions("BTCUSDT")
    assert isinstance(x[0], Execution) and x[0].side == "BUY" and x[0].maker and x[0].fee_currency == "BTC"
    assert v.balances() == {"BTC": D("0.0010"), "USDT": D("60")}
    assert v.positions() == {"BTCUSDT": D("0.0010")}
