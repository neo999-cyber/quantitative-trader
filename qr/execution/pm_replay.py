"""Replay of the recorded Polymarket book and Deribit indices for the intraday wedge (`docs/prereg/p3_threshold_wedge_v2_intraday.md`, seq 934).

The recording (`scripts/record_polymarket.py`) is hourly gzip files of
`{"venue","recorded_at","raw"}` lines. This module turns them into one
time-ordered stream of events, keeps the state the registered rule needs
— best bid/ask per YES token, the last DVOL and index prints — and runs
the rule with the registered fill model:

* a **maker sell** posted at the best ask is filled when a
  `last_trade_price` for that token prints **at or above** the ask after
  the post (price-through; the queue ahead is assumed to fill first);
  a maker buy at the best bid fills on a print at or below it;
* unfilled after `TTL` it is cancelled; a forced exit **crosses** at the
  touch and pays the crypto-tier taker fee `0.07 · p · (1 − p)`.

Decisions are taken on the hour, UTC, from the state at that instant.
Nothing here reads the network: resolutions are passed in.
"""
from __future__ import annotations

import gzip
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd
from scipy.stats import norm

TAKER_RATE = 0.07
PPY_DAYS = 365.0


# ------------------------------------------------------------------ events
def iter_events(mirror: Path, start: pd.Timestamp | None = None, end: pd.Timestamp | None = None) -> Iterator[tuple[float, str, dict]]:
    """`(t_seconds, venue, message)` in time order across the polymarket and deribit folders."""
    files = []
    for venue in ("polymarket", "deribit"):
        for f in sorted((mirror / venue).glob("*/*.jsonl.gz")):
            files.append((f.parent.name + "/" + f.name, venue, f))
    files.sort()
    heads: list[tuple[float, str, dict]] = []
    for _, venue, f in files:
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    raw = json.loads(d["raw"])
                except (json.JSONDecodeError, KeyError):
                    continue
                t = float(d["recorded_at"])
                if start is not None and t < start.timestamp():
                    continue
                if end is not None and t > end.timestamp():
                    continue
                msgs = raw if isinstance(raw, list) else [raw]
                for m in msgs:
                    if isinstance(m, dict):
                        heads.append((t, venue, m))
        heads.sort(key=lambda e: e[0])
        yield from heads
        heads = []


@dataclass
class Quote:
    bid: float = float("nan")
    ask: float = float("nan")

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2


@dataclass
class State:
    quotes: dict = field(default_factory=dict)      # token -> Quote
    dvol: dict = field(default_factory=dict)        # "BTC"/"ETH" -> vol points
    index: dict = field(default_factory=dict)       # "BTC"/"ETH"/"SOL" -> price
    rv_hist: dict = field(default_factory=dict)     # asset -> list of (t, price) for the placebo's realised vol

    def apply(self, venue: str, m: dict) -> list[dict]:
        """Update; return the trade prints in the message (as dicts with token, price, side, size, t_ms)."""
        trades = []
        if venue == "polymarket":
            et = m.get("event_type")
            if et == "book":
                bids = [float(b["price"]) for b in m.get("bids") or []]
                asks = [float(a["price"]) for a in m.get("asks") or []]
                self.quotes[str(m["asset_id"])] = Quote(max(bids) if bids else float("nan"), min(asks) if asks else float("nan"))
            elif et == "price_change":
                for c in m.get("price_changes") or []:
                    try:
                        self.quotes[str(c["asset_id"])] = Quote(float(c["best_bid"]), float(c["best_ask"]))
                    except (KeyError, TypeError, ValueError):
                        pass
            elif et == "last_trade_price":
                trades.append({"token": str(m["asset_id"]), "price": float(m["price"]), "side": m.get("side"), "size": float(m.get("size") or 0), "t_ms": int(m.get("timestamp") or 0)})
        elif venue == "deribit" and m.get("method") == "subscription":
            ch = m["params"]["channel"]
            data = m["params"]["data"]
            ccy = ch.split(".")[-1].split("_")[0].upper()
            if ch.startswith("deribit_volatility_index"):
                self.dvol[ccy] = float(data["volatility"])
            elif ch.startswith("deribit_price_index"):
                self.index[ccy] = float(data["price"])
        return trades


# ------------------------------------------------------------------- model
def model_prob(kind: str, S: float, X: float, sigma: float, tau: float) -> float:
    if not (S > 0 and X > 0 and sigma > 0 and tau > 0):
        return float("nan")
    st = sigma * math.sqrt(tau)
    mu = -0.5 * sigma * sigma
    if kind == "above":
        return float(norm.cdf((math.log(S / X) + mu * tau) / st))
    if kind == "reach":
        b = math.log(X / S)
        if b <= 0:
            return 1.0
        return float(norm.cdf((-b + mu * tau) / st) + math.exp(2 * mu * b / sigma**2) * norm.cdf((-b - mu * tau) / st))
    if kind == "dip":
        b = math.log(S / X)
        if b <= 0:
            return 1.0
        mu = -mu
        return float(norm.cdf((-b + mu * tau) / st) + math.exp(2 * mu * b / sigma**2) * norm.cdf((-b - mu * tau) / st))
    raise ValueError(kind)


def taker_fee(p: float) -> float:
    return TAKER_RATE * p * (1 - p)


# -------------------------------------------------------------------- rule
@dataclass
class Market:
    token: str
    market_id: str
    asset: str
    kind: str
    strike: float
    end: pd.Timestamp
    resolved_yes: float | None = None


@dataclass
class Order:
    token: str
    side: str            # "sell" or "buy" of YES
    price: float
    posted_at: float
    purpose: str         # "entry" or "exit"


@dataclass
class Position:
    market: Market
    side: str            # "sell" (family/placebo/naive) or "buy" (mirror)
    fill: float
    filled_at: float
    wedge_at_entry: float
    decision_at: float


class WedgeSession:
    """The registered rule over the event stream. `sigma_source` is "dvol" or "rv" (the placebo)."""

    def __init__(self, markets: dict[str, Market], k: float, T, side: str = "sell", x: float = 0.02, ttl_h: float = 4.0,
                 sigma_source: str = "dvol", naive: bool = False, rv_window_h: float = 24 * 30):
        self.markets = markets
        self.k, self.T, self.side, self.x, self.ttl = k, T, side, x, ttl_h * 3600
        self.sigma_source, self.naive = sigma_source, naive
        self.rv_window = rv_window_h * 3600
        self.state = State()
        self.orders: dict[str, Order] = {}
        self.positions: dict[str, Position] = {}
        self.done: set = set()
        self.trades: list[dict] = []
        self.marks: dict[str, float] = {}   # token -> last mid, for the book P&L
        self.pnl_events: list[tuple[float, str, float]] = []   # (t, token, cash flow per share)
        self._next_hour: float | None = None
        self._pending_meta: dict[str, tuple[float, float]] = {}
        self.taken_groups: set = set()   # (asset, end date): one market per settlement ladder
        self._rv_samples: dict[str, list[tuple[float, float]]] = {"BTC": [], "ETH": [], "SOL": []}

    # -- helpers
    def sigma(self, asset: str) -> float:
        if self.sigma_source == "rv":
            s = self._rv_samples.get(asset) or []
            if len(s) < 48:
                return float("nan")
            px = np.array([p for _, p in s])
            r = np.diff(np.log(px))
            dt_h = (s[-1][0] - s[0][0]) / 3600 / max(len(s) - 1, 1)
            return float(r.std() * math.sqrt(PPY_DAYS * 24 / max(dt_h, 1e-6)))
        if asset in ("BTC", "ETH"):
            return self.state.dvol.get(asset, float("nan")) / 100.0
        # SOL: BTC DVOL scaled by the realised-vol ratio
        b, s = self._rv("BTC"), self._rv("SOL")
        if not (b > 0 and s > 0):
            return float("nan")
        return self.state.dvol.get("BTC", float("nan")) / 100.0 * s / b

    def _rv(self, asset: str) -> float:
        s = self._rv_samples.get(asset) or []
        if len(s) < 48:
            return float("nan")
        px = np.array([p for _, p in s])
        return float(np.diff(np.log(px)).std())

    def p_model(self, mk: Market, t: float) -> float:
        S = self.state.index.get(mk.asset)
        if S is None:
            return float("nan")
        tau = (mk.end.timestamp() - t) / 86400 / PPY_DAYS
        return model_prob(mk.kind, S, mk.strike, self.sigma(mk.asset), tau)

    # -- event loop
    def run(self, events) -> None:
        for t, venue, m in events:
            if self._next_hour is None:
                self._next_hour = math.floor(t / 3600) * 3600 + 3600
            while t >= self._next_hour:
                self.decide(self._next_hour)
                self._next_hour += 3600
            for tr in self.state.apply(venue, m):
                self.on_trade(t, tr)
            if venue == "deribit" and m.get("method") == "subscription" and m["params"]["channel"].startswith("deribit_price_index"):
                ccy = m["params"]["channel"].split(".")[-1].split("_")[0].upper()
                buf = self._rv_samples.setdefault(ccy, [])
                if not buf or t - buf[-1][0] >= 3600:
                    buf.append((t, float(m["params"]["data"]["price"])))
                    while buf and t - buf[0][0] > self.rv_window:
                        buf.pop(0)
            self.expire(t)
        self.settle()

    def decide(self, t: float) -> None:
        entries: list[tuple[float, str, float]] = []   # (wedge, token, post price)
        for token, mk in self.markets.items():
            q = self.state.quotes.get(token)
            if q is None or not (q.bid > 0 and q.ask < 1 and q.ask > q.bid) or mk.end.timestamp() <= t:
                continue
            pos = self.positions.get(token)
            if pos is None:
                if token in self.done or token in self.orders or (mk.asset, mk.end.normalize()) in self.taken_groups:
                    continue
                if self.naive:
                    if q.bid <= 0.20:
                        entries.append((-q.bid, token, q.ask))
                    else:
                        self.done.add(token)  # first sight only
                    continue
                p = self.p_model(mk, t)
                if not np.isfinite(p):
                    continue
                w = (q.bid - p) if self.side == "sell" else (p - q.ask)
                if w >= self.k:
                    entries.append((w, token, q.ask if self.side == "sell" else q.bid))
            else:
                if token in self.orders or self.naive:
                    continue
                held_days = (t - pos.filled_at) / 86400
                p = self.p_model(mk, t)
                w = (q.bid - p) if self.side == "sell" else (p - q.ask)
                if (np.isfinite(w) and w <= self.x) or (self.T != "resolution" and held_days >= self.T):
                    exit_side = "buy" if self.side == "sell" else "sell"
                    price = q.bid if exit_side == "buy" else q.ask
                    self.orders[token] = Order(token, exit_side, price, t, "exit" if (np.isfinite(w) and w <= self.x) else "max_hold")
        # one market per asset × settlement date: the largest wedge in the ladder
        best: dict[tuple, tuple[float, str, float]] = {}
        for w, token, price in entries:
            mk = self.markets[token]
            g = (mk.asset, mk.end.normalize())
            if g not in best or w > best[g][0]:
                best[g] = (w, token, price)
        for g, (w, token, price) in best.items():
            self.taken_groups.add(g)
            self.orders[token] = Order(token, self.side, price, t, "entry")
            self._pending_meta[token] = (w, t)

    def on_trade(self, t: float, tr: dict) -> None:
        o = self.orders.get(tr["token"])
        if o is None:
            return
        through = (tr["price"] >= o.price) if o.side == "sell" else (tr["price"] <= o.price)
        if not through:
            return
        self._fill(t, o, o.price, crossed=False)

    def _fill(self, t: float, o: Order, price: float, crossed: bool) -> None:
        mk = self.markets[o.token]
        self.orders.pop(o.token, None)
        fee = taker_fee(price) if crossed else 0.0
        if o.purpose == "entry":
            w, t_dec = self._pending_meta.pop(o.token, (float("nan"), o.posted_at))
            self.positions[o.token] = Position(mk, o.side, price, t, w, t_dec)
            return
        pos = self.positions.pop(o.token)
        self.done.add(o.token)
        edge = (pos.fill - price - fee) if pos.side == "sell" else (price - fee - pos.fill)
        self._record(pos, t, price, "crossed_" + o.purpose if crossed else o.purpose, edge, fee)

    def _record(self, pos: Position, t_exit: float, exit_px: float, reason: str, edge: float, fee: float) -> None:
        mk = pos.market
        self.trades.append({"market_id": mk.market_id, "token": mk.token, "asset": mk.asset, "kind": mk.kind, "end": mk.end,
                            "decision": pd.Timestamp(pos.decision_at, unit="s", tz="UTC"), "fill_day": pd.Timestamp(pos.filled_at, unit="s", tz="UTC"),
                            "fill": pos.fill, "exit_day": pd.Timestamp(t_exit, unit="s", tz="UTC"), "exit": exit_px, "reason": reason, "edge": edge,
                            "fee": fee, "wedge_at_entry": pos.wedge_at_entry, "capital_per_share": (1 - pos.fill) if pos.side == "sell" else pos.fill,
                            "hold_days": (t_exit - pos.filled_at) / 86400})

    def expire(self, t: float) -> None:
        for token, o in list(self.orders.items()):
            if t - o.posted_at < self.ttl:
                continue
            if o.purpose == "entry":
                self.orders.pop(token)
                self._pending_meta.pop(token, None)
                self.done.add(token)   # one attempt per market: an unfilled entry is a "not sellable" observation
                self.trades.append({"market_id": self.markets[token].market_id, "token": token, "asset": self.markets[token].asset,
                                    "kind": self.markets[token].kind, "end": self.markets[token].end, "reason": "entry_unfilled", "edge": float("nan")})
            else:
                q = self.state.quotes.get(token)
                if q is None:
                    continue
                price = q.ask if o.side == "buy" else q.bid
                self._fill(t, o, price, crossed=True)

    def settle(self) -> None:
        for token, pos in list(self.positions.items()):
            mk = pos.market
            if mk.resolved_yes is None:
                self.trades.append({"market_id": mk.market_id, "token": token, "asset": mk.asset, "kind": mk.kind, "end": mk.end, "reason": "unresolved_at_read", "edge": float("nan")})
                continue
            settle_px = float(round(mk.resolved_yes))
            edge = (pos.fill - settle_px) if pos.side == "sell" else (settle_px - pos.fill)
            self._record(pos, mk.end.timestamp(), settle_px, "resolution", edge, 0.0)
        self.positions.clear()

    def trade_table(self) -> pd.DataFrame:
        return pd.DataFrame(self.trades)
