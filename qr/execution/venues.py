"""B14 — venue adapters for the maker-fill study's stage 1: Binance USDⓈ-M and Bybit linear.

`docs/27`. Post-only entries, reduce-only closes, cancels, order and
execution reads, positions, balances, the top of book, and the
instrument filters (tick, step, minimum notional) an order must respect.
Nothing else: no leverage changes, no transfers, no withdrawals — the
keys are trade-only and the adapter has no method that could move funds.

Both venues speak signed REST over HTTPS; `Transport` isolates the wire
so tests run against `FakeVenue`, which implements the same interface in
memory and can be told to time out after accepting, to fill partially, or
to fill during a cancel — the races the journal must survive.

Base URLs default to the **testnets** (`demo-fapi.binance.com` — Binance's
futures demo environment, keyed from the main account's API Management —
and `api-testnet.bybit.com`); mainnet is a constructor argument that the
study runner passes only under the owner's mandate (`docs/24` stage 1).

Every response is returned normalised as small dicts; the raw payload is
kept on `last_raw` for the journal's evidence field.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from typing import Any

__all__ = ["Instrument", "Order", "Execution", "VenueError", "VenueTimeout", "BinanceUSDM", "BybitLinear", "FakeVenue"]


class VenueError(RuntimeError):
    """The venue answered, and the answer is a refusal (bad symbol, filter, permission)."""


class VenueTimeout(RuntimeError):
    """No answer: the request may or may not have reached the venue. The caller books UNKNOWN."""


@dataclass(frozen=True)
class Instrument:
    venue: str
    symbol: str
    tick: Decimal
    step: Decimal
    min_qty: Decimal
    min_notional: Decimal

    def round_price(self, price: Decimal) -> Decimal:
        return (price / self.tick).to_integral_value(rounding=ROUND_DOWN) * self.tick

    def round_qty(self, qty: Decimal) -> Decimal:
        return (qty / self.step).to_integral_value(rounding=ROUND_DOWN) * self.step

    def qty_for_notional(self, notional: Decimal, price: Decimal) -> Decimal:
        """The largest step-multiple under `notional`, or 0 when the venue's minimum is above it."""
        qty = self.round_qty(notional / price)
        if qty < self.min_qty or qty * price < self.min_notional:
            return Decimal(0)
        return qty


@dataclass(frozen=True)
class Order:
    venue_order_id: str
    client_id: str
    symbol: str
    side: str
    status: str  # NEW | PARTIALLY_FILLED | FILLED | CANCELED | REJECTED | EXPIRED
    qty: Decimal
    filled: Decimal
    price: Decimal


@dataclass(frozen=True)
class Execution:
    exec_id: str
    venue_order_id: str
    symbol: str
    side: str
    qty: Decimal
    price: Decimal
    fee: Decimal
    fee_currency: str
    venue_ts: str
    maker: bool


def _D(x) -> Decimal:
    return Decimal(str(x))


class Transport:
    """One HTTPS request; raises `VenueTimeout` when the outcome is unknown."""

    def __init__(self, timeout_s: float = 10.0) -> None:
        self.timeout_s = timeout_s

    def request(self, method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise VenueTimeout(f"{method} {url.split('?')[0]}: {exc}") from exc


# ---------------------------------------------------------------- Binance


class BinanceUSDM:
    name = "binance"
    #: Binance folded the futures testnet into "Demo Trading" inside the main
    #: account (demo.binance.com/en/futures) in 2025-26; a demo API key is made
    #: under the main account's API Management and works only against this host.
    #: testnet.binancefuture.com now redirects to the main site (18 Sep 2026).
    TESTNET = "https://demo-fapi.binance.com"
    MAINNET = "https://fapi.binance.com"

    def __init__(self, key: str, secret: str, base: str = TESTNET, transport: Transport | None = None, recv_window: int = 5000) -> None:
        self.key, self.secret, self.base = key, secret.encode(), base.rstrip("/")
        self.transport = transport or Transport()
        self.recv_window = recv_window
        self.last_raw: Any = None

    def _signed(self, method: str, path: str, params: dict[str, Any]) -> dict:
        params = {k: v for k, v in params.items() if v is not None}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.recv_window
        query = urllib.parse.urlencode(params)
        sig = hmac.new(self.secret, query.encode(), hashlib.sha256).hexdigest()
        url = f"{self.base}{path}?{query}&signature={sig}"
        status, raw = self.transport.request(method, url, {"X-MBX-APIKEY": self.key}, None)
        return self._parse(status, raw)

    def _public(self, path: str, params: dict[str, Any] | None = None) -> dict:
        url = f"{self.base}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        status, raw = self.transport.request("GET", url, {}, None)
        return self._parse(status, raw)

    def _parse(self, status: int, raw: bytes) -> Any:
        try:
            data = json.loads(raw or b"null")
        except json.JSONDecodeError as exc:
            raise VenueError(f"binance: unparseable response ({status})") from exc
        self.last_raw = data
        if status >= 400 or (isinstance(data, dict) and "code" in data and data.get("code", 0) < 0):
            raise VenueError(f"binance {status}: {data}")
        return data

    def instrument(self, symbol: str) -> Instrument:
        info = self._public("/fapi/v1/exchangeInfo")
        for s in info.get("symbols", []):
            if s["symbol"] == symbol:
                f = {x["filterType"]: x for x in s.get("filters", [])}
                return Instrument(
                    self.name, symbol, _D(f["PRICE_FILTER"]["tickSize"]), _D(f["LOT_SIZE"]["stepSize"]),
                    _D(f["LOT_SIZE"]["minQty"]), _D(f.get("MIN_NOTIONAL", {}).get("notional", "5")),
                )
        raise VenueError(f"binance: {symbol} not listed")

    def book(self, symbol: str) -> tuple[Decimal, Decimal]:
        t = self._public("/fapi/v1/ticker/bookTicker", {"symbol": symbol})
        return _D(t["bidPrice"]), _D(t["askPrice"])

    def place_post_only(self, client_id: str, symbol: str, side: str, qty: Decimal, price: Decimal, reduce_only: bool = False) -> Order:
        r = self._signed("POST", "/fapi/v1/order", {
            "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "GTX",
            "quantity": str(qty), "price": str(price), "newClientOrderId": client_id,
            "reduceOnly": "true" if reduce_only else None,
        })
        return self._order(r)

    def close_taker(self, client_id: str, symbol: str, side: str, qty: Decimal, price: Decimal) -> Order:
        """Reduce-only IOC limit through the touch: the study's 60-minute fallback exit."""
        r = self._signed("POST", "/fapi/v1/order", {
            "symbol": symbol, "side": side, "type": "LIMIT", "timeInForce": "IOC",
            "quantity": str(qty), "price": str(price), "newClientOrderId": client_id, "reduceOnly": "true",
        })
        return self._order(r)

    def cancel(self, symbol: str, client_id: str) -> Order:
        return self._order(self._signed("DELETE", "/fapi/v1/order", {"symbol": symbol, "origClientOrderId": client_id}))

    def order(self, symbol: str, client_id: str) -> Order:
        return self._order(self._signed("GET", "/fapi/v1/order", {"symbol": symbol, "origClientOrderId": client_id}))

    def _order(self, r: dict) -> Order:
        return Order(str(r["orderId"]), r["clientOrderId"], r["symbol"], r["side"], r["status"], _D(r["origQty"]), _D(r["executedQty"]), _D(r["price"]))

    def executions(self, symbol: str, since_ms: int | None = None) -> list[Execution]:
        rows = self._signed("GET", "/fapi/v1/userTrades", {"symbol": symbol, "startTime": since_ms, "limit": 1000})
        return [
            Execution(str(x["id"]), str(x["orderId"]), x["symbol"], x["side"], _D(x["qty"]), _D(x["price"]), _D(x["commission"]),
                      x["commissionAsset"], str(x["time"]), bool(x["maker"]))
            for x in rows
        ]

    def positions(self) -> dict[str, Decimal]:
        rows = self._signed("GET", "/fapi/v2/positionRisk", {})
        return {x["symbol"]: _D(x["positionAmt"]) for x in rows if _D(x["positionAmt"]) != 0}

    def balances(self) -> dict[str, Decimal]:
        rows = self._signed("GET", "/fapi/v2/balance", {})
        return {x["asset"]: _D(x["balance"]) for x in rows if _D(x["balance"]) != 0}


# ------------------------------------------------------------------ Bybit


class BybitLinear:
    name = "bybit"
    TESTNET = "https://api-testnet.bybit.com"
    MAINNET = "https://api.bybit.com"
    STATUS = {"New": "NEW", "PartiallyFilled": "PARTIALLY_FILLED", "Filled": "FILLED", "Cancelled": "CANCELED",
              "PartiallyFilledCanceled": "CANCELED", "Rejected": "REJECTED", "Deactivated": "EXPIRED", "Untriggered": "NEW"}

    def __init__(self, key: str, secret: str, base: str = TESTNET, transport: Transport | None = None, recv_window: int = 5000) -> None:
        self.key, self.secret, self.base = key, secret.encode(), base.rstrip("/")
        self.transport = transport or Transport()
        self.recv_window = recv_window
        self.last_raw: Any = None

    def _call(self, method: str, path: str, params: dict[str, Any]) -> dict:
        params = {k: v for k, v in params.items() if v is not None}
        ts = str(int(time.time() * 1000))
        if method == "GET":
            payload = urllib.parse.urlencode(params)
            url, body = f"{self.base}{path}?{payload}", None
        else:
            payload = json.dumps(params, separators=(",", ":"))
            url, body = f"{self.base}{path}", payload.encode()
        sign = hmac.new(self.secret, (ts + self.key + str(self.recv_window) + payload).encode(), hashlib.sha256).hexdigest()
        headers = {"X-BAPI-API-KEY": self.key, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": str(self.recv_window),
                   "X-BAPI-SIGN": sign, "Content-Type": "application/json"}
        status, raw = self.transport.request(method, url, headers, body)
        try:
            data = json.loads(raw or b"null")
        except json.JSONDecodeError as exc:
            raise VenueError(f"bybit: unparseable response ({status})") from exc
        self.last_raw = data
        if status >= 400 or data.get("retCode", 0) != 0:
            raise VenueError(f"bybit {status}: {data.get('retCode')} {data.get('retMsg')}")
        return data.get("result", {})

    def instrument(self, symbol: str) -> Instrument:
        r = self._call("GET", "/v5/market/instruments-info", {"category": "linear", "symbol": symbol})
        for s in r.get("list", []):
            if s["symbol"] == symbol:
                lot, pf = s["lotSizeFilter"], s["priceFilter"]
                return Instrument(self.name, symbol, _D(pf["tickSize"]), _D(lot["qtyStep"]), _D(lot["minOrderQty"]), _D(lot.get("minNotionalValue", "5")))
        raise VenueError(f"bybit: {symbol} not listed")

    def book(self, symbol: str) -> tuple[Decimal, Decimal]:
        r = self._call("GET", "/v5/market/tickers", {"category": "linear", "symbol": symbol})
        t = r["list"][0]
        return _D(t["bid1Price"]), _D(t["ask1Price"])

    def place_post_only(self, client_id: str, symbol: str, side: str, qty: Decimal, price: Decimal, reduce_only: bool = False) -> Order:
        r = self._call("POST", "/v5/order/create", {
            "category": "linear", "symbol": symbol, "side": side.capitalize(), "orderType": "Limit", "qty": str(qty),
            "price": str(price), "timeInForce": "PostOnly", "orderLinkId": client_id, "reduceOnly": bool(reduce_only),
        })
        # create returns ids only; the state comes from a read
        return self.order(symbol, client_id, venue_order_id=r.get("orderId"))

    def close_taker(self, client_id: str, symbol: str, side: str, qty: Decimal, price: Decimal) -> Order:
        r = self._call("POST", "/v5/order/create", {
            "category": "linear", "symbol": symbol, "side": side.capitalize(), "orderType": "Limit", "qty": str(qty),
            "price": str(price), "timeInForce": "IOC", "orderLinkId": client_id, "reduceOnly": True,
        })
        return self.order(symbol, client_id, venue_order_id=r.get("orderId"))

    def cancel(self, symbol: str, client_id: str) -> Order:
        self._call("POST", "/v5/order/cancel", {"category": "linear", "symbol": symbol, "orderLinkId": client_id})
        return self.order(symbol, client_id)

    def order(self, symbol: str, client_id: str, venue_order_id: str | None = None) -> Order:
        r = self._call("GET", "/v5/order/realtime", {"category": "linear", "symbol": symbol, "orderLinkId": client_id})
        rows = r.get("list", [])
        if not rows:
            r = self._call("GET", "/v5/order/history", {"category": "linear", "symbol": symbol, "orderLinkId": client_id})
            rows = r.get("list", [])
        if not rows:
            raise VenueError(f"bybit: order {client_id} not found")
        x = rows[0]
        return Order(str(x.get("orderId") or venue_order_id), x["orderLinkId"], x["symbol"], x["side"].upper(),
                     self.STATUS.get(x["orderStatus"], x["orderStatus"]), _D(x["qty"]), _D(x.get("cumExecQty", "0")), _D(x["price"]))

    def executions(self, symbol: str, since_ms: int | None = None) -> list[Execution]:
        r = self._call("GET", "/v5/execution/list", {"category": "linear", "symbol": symbol, "startTime": since_ms, "limit": 100})
        return [
            Execution(x["execId"], x["orderId"], x["symbol"], x["side"].upper(), _D(x["execQty"]), _D(x["execPrice"]), _D(x.get("execFee", "0")),
                      x.get("feeCurrency", "USDT"), str(x["execTime"]), bool(x.get("isMaker", False)))
            for x in r.get("list", [])
        ]

    def positions(self) -> dict[str, Decimal]:
        r = self._call("GET", "/v5/position/list", {"category": "linear", "settleCoin": "USDT"})
        out = {}
        for x in r.get("list", []):
            size = _D(x["size"])
            if size != 0:
                out[x["symbol"]] = size if x["side"] == "Buy" else -size
        return out

    def balances(self) -> dict[str, Decimal]:
        r = self._call("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
        out = {}
        for acct in r.get("list", []):
            for c in acct.get("coin", []):
                if _D(c.get("walletBalance", "0")) != 0:
                    out[c["coin"]] = _D(c["walletBalance"])
        return out


# ------------------------------------------------------------- fake venue


@dataclass
class FakeVenue:
    """The same interface in memory, with the races the journal must survive."""

    name: str = "fake"
    instruments: dict[str, Instrument] = field(default_factory=dict)
    books: dict[str, tuple[Decimal, Decimal]] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    fills: list[Execution] = field(default_factory=list)
    pos: dict[str, Decimal] = field(default_factory=dict)
    cash: Decimal = Decimal("100")
    #: raise VenueTimeout on the next place() *after* the venue has accepted it
    timeout_after_accept: bool = False
    #: fill this much of the next order as soon as it is placed
    fill_on_place: Decimal = Decimal(0)
    #: fill the remainder while a cancel is being processed
    fill_on_cancel: bool = False
    fee_bps: Decimal = Decimal("2")
    _seq: int = 0

    def instrument(self, symbol: str) -> Instrument:
        return self.instruments[symbol]

    def book(self, symbol: str) -> tuple[Decimal, Decimal]:
        return self.books[symbol]

    def _exec(self, o: Order, qty: Decimal) -> Order:
        self._seq += 1
        fee = qty * o.price * self.fee_bps / Decimal(10000)
        self.fills.append(Execution(f"x{self._seq}", o.venue_order_id, o.symbol, o.side, qty, o.price, fee, "USDT", str(self._seq), True))
        signed = qty if o.side == "BUY" else -qty
        self.pos[o.symbol] = self.pos.get(o.symbol, Decimal(0)) + signed
        self.cash -= signed * o.price + fee
        filled = o.filled + qty
        status = "FILLED" if filled >= o.qty else "PARTIALLY_FILLED"
        o = Order(o.venue_order_id, o.client_id, o.symbol, o.side, status, o.qty, filled, o.price)
        self.orders[o.client_id] = o
        return o

    def place_post_only(self, client_id, symbol, side, qty, price, reduce_only=False) -> Order:
        if client_id in self.orders:
            return self.orders[client_id]  # the venue deduplicates on the client id
        ins = self.instruments[symbol]
        if qty < ins.min_qty or qty * price < ins.min_notional or (qty / ins.step) % 1 != 0:
            raise VenueError("filter")
        bid, ask = self.books[symbol]
        if (side == "BUY" and price >= ask) or (side == "SELL" and price <= bid):
            o = Order(f"v{len(self.orders)+1}", client_id, symbol, side, "EXPIRED", qty, Decimal(0), price)  # post-only would cross
            self.orders[client_id] = o
            return o
        if reduce_only:
            held = self.pos.get(symbol, Decimal(0))
            signed = qty if side == "BUY" else -qty
            if held == 0 or (held > 0) == (signed > 0) or abs(signed) > abs(held):
                raise VenueError("reduce-only would not reduce")
        o = Order(f"v{len(self.orders)+1}", client_id, symbol, side, "NEW", qty, Decimal(0), price)
        self.orders[client_id] = o
        if self.fill_on_place > 0:
            o = self._exec(o, min(self.fill_on_place, qty))
            self.fill_on_place = Decimal(0)
        if self.timeout_after_accept:
            self.timeout_after_accept = False
            raise VenueTimeout("accepted, then the response was lost")
        return o

    def close_taker(self, client_id, symbol, side, qty, price) -> Order:
        if client_id in self.orders:
            return self.orders[client_id]
        held = self.pos.get(symbol, Decimal(0))
        signed = qty if side == "BUY" else -qty
        if held == 0 or (held > 0) == (signed > 0) or abs(signed) > abs(held):
            raise VenueError("reduce-only would not reduce")
        bid, ask = self.books[symbol]
        touch = ask if side == "BUY" else bid
        o = Order(f"v{len(self.orders)+1}", client_id, symbol, side, "NEW", qty, Decimal(0), touch)
        self.orders[client_id] = o
        return self._exec(o, qty)  # a taker through the touch fills at once

    def cancel(self, symbol, client_id) -> Order:
        o = self.orders[client_id]
        if o.status in ("FILLED", "CANCELED", "REJECTED", "EXPIRED"):
            return o
        if self.fill_on_cancel:
            self.fill_on_cancel = False
            o = self._exec(o, o.qty - o.filled)
            return o
        o = Order(o.venue_order_id, o.client_id, o.symbol, o.side, "CANCELED", o.qty, o.filled, o.price)
        self.orders[client_id] = o
        return o

    def order(self, symbol, client_id, venue_order_id=None) -> Order:
        if client_id not in self.orders:
            raise VenueError("not found")
        return self.orders[client_id]

    def executions(self, symbol, since_ms=None) -> list[Execution]:
        return [f for f in self.fills if f.symbol == symbol]

    def positions(self) -> dict[str, Decimal]:
        return {s: q for s, q in self.pos.items() if q != 0}

    def balances(self) -> dict[str, Decimal]:
        return {"USDT": self.cash}
