#!/usr/bin/env python3
"""Record the public top-of-book and trade tape forward, for the maker-fill study (docs/24, stage 0).

No key, no order. Two venues' public websockets:

* **binance** — `<sym>@bookTicker` (best bid/ask and their sizes, every
  change) and `<sym>@trade` (every print; `m` true = the buyer was the
  maker, i.e. a *sell* hit the bid). `@aggTrade` and `!forceOrder` send
  nothing to this host (probed 17 September 2026); `@trade` does.
* **bybit** — `orderbook.1.<SYM>` (best level, snapshot + deltas) and
  `publicTrade.<SYM>` (every print with side `S`/`B` of the taker).

Written as `<out>/<venue>/<kind>/YYYY-MM-DD.jsonl.gz`, UTC days, one line
per message: `{"t": recorded_ms, "s": symbol, ...venue fields}`. The book
stream is thinned to changes of the best price or size, at most ten a
second a symbol; trades are kept in full — the fill simulation needs every
print at or through a resting price. Gzip members are appended, so a
file is readable after a crash. Reconnects on any error with a growing
pause. Needs `websockets`; everything else is stdlib.

    python record_tape.py --venue binance --symbols BTCUSDT ETHUSDT --out /root/tape/data
    python record_tape.py --venue bybit --symbols BTCUSDT --out /root/tape/data
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets

BINANCE = "wss://fstream.binance.com/stream?streams="
BYBIT = "wss://stream.bybit.com/v5/public/linear"


class Writer:
    """One gzip file per venue/kind/day, buffered, flushed every few seconds."""

    def __init__(self, out: Path, venue: str):
        self.out, self.venue = out, venue
        self.files: dict[tuple[str, str], gzip.GzipFile] = {}
        self.last_flush = time.time()
        self.count = 0

    def close(self) -> None:
        for f in self.files.values():
            f.close()
        self.files.clear()

    def write(self, kind: str, row: dict) -> None:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = (kind, day)
        if key not in self.files:
            for (k, d), f in list(self.files.items()):
                if k == kind and d != day:
                    f.close()
                    del self.files[(k, d)]
            path = self.out / self.venue / kind
            path.mkdir(parents=True, exist_ok=True)
            self.files[key] = gzip.open(path / f"{day}.jsonl.gz", "ab")
        self.files[key].write((json.dumps(row, separators=(",", ":")) + "\n").encode())
        self.count += 1
        if time.time() - self.last_flush > 5:
            for f in self.files.values():
                f.flush()
            self.last_flush = time.time()


class Thinner:
    """Keep a book update only if the best changed, and at most ten a second a symbol."""

    def __init__(self):
        self.last: dict[str, tuple] = {}
        self.stamp: dict[str, float] = {}

    def keep(self, sym: str, best: tuple, now: float) -> bool:
        if self.last.get(sym) == best:
            return False
        if now - self.stamp.get(sym, 0.0) < 0.1:
            return False
        self.last[sym], self.stamp[sym] = best, now
        return True


async def run_binance(symbols: list[str], writer: Writer) -> None:
    streams = "/".join(f"{s.lower()}@{k}" for s in symbols for k in ("bookTicker", "trade"))
    thin = Thinner()
    async with websockets.connect(BINANCE + streams, ping_interval=20, open_timeout=15, max_size=2**22) as ws:
        async for raw in ws:
            m = json.loads(raw)
            d = m.get("data") or {}
            now = time.time()
            if d.get("e") == "bookTicker":
                best = (d["b"], d["B"], d["a"], d["A"])
                if thin.keep(d["s"], best, now):
                    writer.write("book", {"t": int(now * 1000), "s": d["s"], "T": d.get("T"), "b": d["b"], "B": d["B"], "a": d["a"], "A": d["A"]})
            elif d.get("e") == "trade":
                writer.write("trade", {"t": int(now * 1000), "s": d["s"], "T": d["T"], "p": d["p"], "q": d["q"], "m": d.get("m"), "X": d.get("X"), "i": d["t"]})


async def run_bybit(symbols: list[str], writer: Writer) -> None:
    args = [f"orderbook.1.{s}" for s in symbols] + [f"publicTrade.{s}" for s in symbols]
    thin = Thinner()
    book: dict[str, dict] = {}
    async with websockets.connect(BYBIT, ping_interval=20, open_timeout=15, max_size=2**22) as ws:
        for i in range(0, len(args), 10):
            await ws.send(json.dumps({"op": "subscribe", "args": args[i : i + 10]}))
        async for raw in ws:
            m = json.loads(raw)
            topic = m.get("topic", "")
            now = time.time()
            if topic.startswith("orderbook.1."):
                d = m["data"]
                s = d["s"]
                cur = book.setdefault(s, {"b": None, "B": None, "a": None, "A": None})
                if d.get("b"):
                    cur["b"], cur["B"] = d["b"][0][0], d["b"][0][1]
                if d.get("a"):
                    cur["a"], cur["A"] = d["a"][0][0], d["a"][0][1]
                best = (cur["b"], cur["B"], cur["a"], cur["A"])
                if None not in best and thin.keep(s, best, now):
                    writer.write("book", {"t": int(now * 1000), "s": s, "T": m.get("ts"), **cur})
            elif topic.startswith("publicTrade."):
                for d in m["data"]:
                    writer.write("trade", {"t": int(now * 1000), "s": d["s"], "T": d["T"], "p": d["p"], "q": d["v"], "S": d["S"], "i": d["i"]})


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=("binance", "bybit"), required=True)
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--print-systemd", action="store_true")
    a = ap.parse_args()
    if a.print_systemd:
        print(
            f"[Unit]\nDescription=qr: record {a.venue} top-of-book and trades (maker-fill study)\nAfter=network-online.target\nWants=network-online.target\n\n"
            f"[Service]\nType=simple\nExecStart=/root/liq/.venv/bin/python /root/tape/record_tape.py --venue {a.venue} --symbols {' '.join(a.symbols)} --out {a.out}\n"
            "Restart=always\nRestartSec=10\nUser=root\n\n[Install]\nWantedBy=multi-user.target\n"
        )
        return
    writer = Writer(Path(a.out), a.venue)
    import signal

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    pause = 5
    while not stop.is_set():
        started = time.time()
        try:
            print(f"{datetime.now(timezone.utc).isoformat()} connect {a.venue} {len(a.symbols)} symbols", flush=True)
            task = asyncio.ensure_future((run_binance if a.venue == "binance" else run_bybit)(a.symbols, writer))
            waiter = asyncio.ensure_future(stop.wait())
            done, _ = await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
            if waiter in done:
                task.cancel()
                break
            waiter.cancel()
            task.result()
        except Exception as exc:  # noqa: BLE001
            print(f"{datetime.now(timezone.utc).isoformat()} {a.venue} error after {writer.count} rows: {exc!r}; retry in {pause}s", flush=True)
        pause = 5 if time.time() - started > 300 else min(pause * 2, 300)
        await asyncio.sleep(pause)
    writer.close()
    print(f"{datetime.now(timezone.utc).isoformat()} stopped after {writer.count} rows", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
