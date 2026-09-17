"""Maker-fill study, stage 0: replay virtual post-only orders against the recorded tape.

`docs/24`. The recorder (`scripts/record_tape.py`) writes, per venue and
UTC day, a top-of-book stream (`b`, `B`, `a`, `A`: best bid, its size,
best ask, its size) and every trade (`p`, `q`, and the taker's side —
Binance `m` true means the buyer was the maker, so the taker *sold*;
Bybit `S` is the taker's side). Both carry the exchange time `T` (ms) and
the recorded time `t`.

The question is P(fill | post at the best price, wait T) and what a fill
costs. The model, deliberately conservative:

* A virtual order rests at the best bid (buy) or best ask (sell) at its
  placement time, **behind the whole displayed size** at that price
  (`queue_ahead`). The order's own size is a minimum-notional lot and is
  treated as zero: it fills once the queue ahead is gone.
* Only trades consume the queue. A taker-sell print at the resting bid's
  price reduces `queue_ahead` by its size; a taker-sell print *below* it
  means the level was taken through and the order is filled. The mirror
  holds for a resting ask and taker buys. Cancellations ahead in the
  queue are not observed and are not assumed: the estimate is a floor.
* If the best price moves away (bid rises above the resting bid), the
  order keeps resting and its queue is untouched; it can still fill when
  prints return to its price. If the best price moves through it without
  a print (a level pulled), nothing happens — again the floor.
* Unfilled at `ttl` → cancelled. Filled → the mid `mark_after` seconds
  later is recorded; **the adverse-selection mark is `side × (fill price −
  mid after) / fill price` in bps, positive when the market moved against
  the fill** (bought, then the mid fell). `docs/24`'s rule reads its
  median: below 2 bps.

Every `slot` seconds a new pair of virtual orders (one each side) is
placed per symbol, independently of earlier ones: they are samples of
the same conditional probability, not a book of positions.

Reading: the recorder appends gzip members, so a day file being written
ends in a truncated member; `read_tape` stops there rather than failing.
Two venues' files are replayed separately (`venue` is part of the key).
"""
from __future__ import annotations

import gzip
import heapq
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
import pandas as pd

__all__ = ["read_tape", "merge_streams", "replay", "summarise", "VirtualOrder"]

HORIZONS_S = (60, 300, 900)


def read_tape(path: Path | str) -> Iterator[dict]:
    """Lines of one `YYYY-MM-DD.jsonl.gz`; tolerant of the truncated last member."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        try:
            for line in handle:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except (EOFError, gzip.BadGzipFile, OSError):
            return


def _tag(stream: Iterable[dict], kind: str) -> Iterator[tuple[int, int, str, dict]]:
    order = 0 if kind == "book" else 1  # a book update and a trade at the same ms: book first
    for i, record in enumerate(stream):
        yield (int(record.get("T", record["t"])), order, i, kind, record)


def merge_streams(book: Iterable[dict], trades: Iterable[dict]) -> Iterator[tuple[str, dict]]:
    """Book updates and trades in exchange-time order, as `(kind, record)`."""
    for _, _, _, kind, record in heapq.merge(_tag(book, "book"), _tag(trades, "trade")):
        yield kind, record


def taker_sold(record: dict) -> bool:
    """True when the taker was the seller (the print hit the bid)."""
    if "m" in record:
        return bool(record["m"])  # Binance: buyer was the maker
    return str(record.get("S", "")).lower().startswith("s")  # Bybit: taker side


@dataclass
class VirtualOrder:
    symbol: str
    side: int  # +1 buy resting at the bid, -1 sell resting at the ask
    placed_ms: int
    price: float
    queue_ahead: float
    mid_at_place: float
    hour_utc: int
    ttl_ms: int
    filled_ms: int | None = None
    fill_price: float | None = None
    mid_after: float | None = None
    consumed: float = 0.0
    done: bool = False

    def row(self, mark_after_ms: int) -> dict:
        wait = (self.filled_ms - self.placed_ms) / 1000.0 if self.filled_ms is not None else np.nan
        mark = np.nan
        if self.fill_price is not None and self.mid_after is not None and self.fill_price > 0:
            mark = self.side * (self.fill_price - self.mid_after) / self.fill_price * 1e4
        return {
            "symbol": self.symbol,
            "side": "buy" if self.side > 0 else "sell",
            "placed": pd.Timestamp(self.placed_ms, unit="ms", tz="UTC"),
            "hour_utc": self.hour_utc,
            "price": self.price,
            "queue_ahead": self.queue_ahead,
            "mid_at_place": self.mid_at_place,
            "filled": self.filled_ms is not None,
            "wait_s": wait,
            "fill_price": self.fill_price if self.fill_price is not None else np.nan,
            "mid_after": self.mid_after if self.mid_after is not None else np.nan,
            "mark_bps": mark,
        }


def replay(
    events: Iterable[tuple[str, dict]],
    symbols: Iterable[str] | None = None,
    slot_s: int = 900,
    ttl_s: int = 900,
    mark_after_s: int = 60,
) -> pd.DataFrame:
    """Place a buy and a sell every `slot_s` per symbol and follow each to fill or cancel."""
    wanted = set(symbols) if symbols is not None else None
    slot_ms, ttl_ms, mark_ms = slot_s * 1000, ttl_s * 1000, mark_after_s * 1000
    best: dict[str, tuple[float, float, float, float]] = {}  # symbol -> (bid, bid_size, ask, ask_size)
    next_slot: dict[str, int] = {}
    live: dict[str, list[VirtualOrder]] = {}
    marking: list[VirtualOrder] = []  # filled, waiting for the mid `mark_after_s` later
    rows: list[dict] = []

    def settle_marks(symbol: str, now_ms: int) -> None:
        bid, _, ask, _ = best[symbol]
        keep = []
        for order in marking:
            if order.symbol == symbol and now_ms >= order.filled_ms + mark_ms:
                order.mid_after = (bid + ask) / 2.0
                rows.append(order.row(mark_ms))
            else:
                keep.append(order)
        marking[:] = keep

    for kind, record in events:
        symbol = record.get("s")
        if symbol is None or (wanted is not None and symbol not in wanted):
            continue
        now = int(record.get("T", record["t"]))
        if kind == "book":
            try:
                bid, bid_size, ask, ask_size = float(record["b"]), float(record["B"]), float(record["a"]), float(record["A"])
            except (KeyError, TypeError, ValueError):
                continue
            if bid <= 0 or ask <= 0 or ask < bid:
                continue
            best[symbol] = (bid, bid_size, ask, ask_size)
            settle_marks(symbol, now)
            # expire resting orders
            still = []
            for order in live.get(symbol, []):
                if now >= order.placed_ms + order.ttl_ms:
                    rows.append(order.row(mark_ms))
                else:
                    still.append(order)
            live[symbol] = still
            # a new pair every slot
            due = next_slot.get(symbol)
            if due is None:
                next_slot[symbol] = now - (now % slot_ms) + slot_ms
            elif now >= due:
                hour = int(pd.Timestamp(now, unit="ms", tz="UTC").hour)
                mid = (bid + ask) / 2.0
                live.setdefault(symbol, []).extend(
                    [
                        VirtualOrder(symbol, +1, now, bid, bid_size, mid, hour, ttl_ms),
                        VirtualOrder(symbol, -1, now, ask, ask_size, mid, hour, ttl_ms),
                    ]
                )
                next_slot[symbol] = now - (now % slot_ms) + slot_ms
            continue
        # a trade
        if symbol not in best:
            continue
        try:
            price, qty = float(record["p"]), float(record["q"])
        except (KeyError, TypeError, ValueError):
            continue
        sold = taker_sold(record)
        settle_marks(symbol, now)
        for order in live.get(symbol, []):
            if order.done:
                continue
            if order.side > 0 and sold:
                if price < order.price:
                    order.consumed = order.queue_ahead
                elif price == order.price:
                    order.consumed += qty
                else:
                    continue
            elif order.side < 0 and not sold:
                if price > order.price:
                    order.consumed = order.queue_ahead
                elif price == order.price:
                    order.consumed += qty
                else:
                    continue
            else:
                continue
            if order.consumed >= order.queue_ahead:
                order.done = True
                order.filled_ms = now
                order.fill_price = order.price
                marking.append(order)
        live[symbol] = [o for o in live.get(symbol, []) if not o.done]

    # an order still resting when the tape ends is censored (it had not reached
    # its deadline) and is dropped, not counted as unfilled; a filled order
    # whose mark time lies beyond the tape keeps its fill and a NaN mark
    for order in marking:
        rows.append(order.row(mark_ms))
    columns = [
        "symbol", "side", "placed", "hour_utc", "price", "queue_ahead", "mid_at_place",
        "filled", "wait_s", "fill_price", "mid_after", "mark_bps",
    ]
    return pd.DataFrame(rows, columns=columns)


def summarise(orders: pd.DataFrame, horizons_s: Iterable[int] = HORIZONS_S) -> dict[str, pd.DataFrame | float]:
    """Fill probability by horizon, per symbol and per hour; the adverse-selection mark; waits."""
    if orders.empty:
        return {"by_symbol": pd.DataFrame(), "by_hour": pd.DataFrame(), "median_mark_bps": np.nan, "orders": 0}
    frame = orders.copy()
    for h in horizons_s:
        frame[f"fill_{h}s"] = frame["filled"] & (frame["wait_s"] <= h)
    cols = [f"fill_{h}s" for h in horizons_s]
    by_symbol = frame.groupby(["symbol", "side"])[cols].mean()
    by_symbol["n"] = frame.groupby(["symbol", "side"]).size()
    by_symbol["median_mark_bps"] = frame[frame["filled"]].groupby(["symbol", "side"])["mark_bps"].median()
    by_hour = frame.groupby("hour_utc")[cols].mean()
    by_hour["n"] = frame.groupby("hour_utc").size()
    filled = frame[frame["filled"]]
    return {
        "by_symbol": by_symbol,
        "by_hour": by_hour,
        "overall": frame[cols].mean(),
        "median_mark_bps": float(filled["mark_bps"].median()) if len(filled) else np.nan,
        "mean_mark_bps": float(filled["mark_bps"].mean()) if len(filled) else np.nan,
        "wait_quantiles_s": filled["wait_s"].quantile([0.25, 0.5, 0.75, 0.9]) if len(filled) else pd.Series(dtype=float),
        "orders": int(len(frame)),
    }
