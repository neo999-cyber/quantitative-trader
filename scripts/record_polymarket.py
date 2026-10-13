#!/usr/bin/env python3
"""Record Polymarket crypto threshold/barrier books and Deribit's DVOL/price indices forward.

Programme 3 (`docs/31` §1.3, §4; owner's yes 21 September 2026). The free
history of a resolved Polymarket market is one point per 12 hours; the
wedge over the options-implied probability decays in hours (arXiv
2606.19517), so the intraday structure has to be recorded forward — by us,
point-in-time by construction, like the tape and the liquidations.

Two venues, both public, no key, standard library plus `websockets`:

* **polymarket** — CLOB market channel `wss://ws-subscriptions-clob.polymarket.com/ws/market`:
  `book` (full book on subscribe), `price_change`, `last_trade_price`,
  `tick_size_change`, for the YES and NO tokens of every *active*
  BTC/ETH/SOL threshold market whose life from listing to settlement is at
  least `--min-horizon-days` (7 by default, v1's rule; **1 on the box from
  13 October 2026 05:30 UTC**, the owner's choice of option B in `docs/31`
  §16, which admits the daily "above $X on <date>" ladders — listed with
  just under seven days to run, settled on the Binance 1-minute close at
  noon ET; "Up or Down", dated-hour and "which first" markets stay excluded
  by rule). The token list is rebuilt from Gamma `public-search` every
  `--refresh` seconds and the socket reconnected when it changes, so new
  markets are picked up within the hour. The market catalogue in force is
  written beside the data, with the horizon rule that produced it.
* **deribit** — `wss://www.deribit.com/ws/api/v2`, channels
  `deribit_volatility_index.{btc,eth}_usd` and
  `deribit_price_index.{btc,eth,sol}_usd`: the model inputs, at the
  venue's own cadence (seconds).

Each line: `{"venue","recorded_at","raw"}` — the venue's own message.
Deribit's is untouched; Polymarket's is *compacted* (`compact`): whitespace
and the venue's per-message `hash` removed; in a `price_change` the
mirrored NO-token entry dropped (it is the YES entry at 1 − price with the
side flipped, same size; the CLOB emits both for every order); and — the
one lossy step, measured on 21 September — a `price_change` entry is kept
only when it **moves that token's best bid or ask** or sits **within
`--near` (2¢) of the mid**. The raw feed is ~630,000 price changes an hour
for 160 tokens, 93% of them deep-book bot churn; keeping the top of book
and the 2¢ band is 40% of the bytes, and the hourly full `book` snapshots
carry the rest of the depth. `book`, `last_trade_price` and
`tick_size_change` are never dropped. Files: `<out>/<venue>/YYYY-MM-DD/HH.jsonl.gz`, UTC hours,
gzip-appended (one member per process start), flushed every two seconds:
the raw Polymarket feed is ~2.5 GB a day for 300 tokens, which the box
cannot hold for a quarter; gzip and YES-only tokens (the CLOB merges the
NO side into the YES book) bring it to ~200 MB a day after the top-of-book filter. Reconnects on any
error with a growing pause.

    python scripts/record_polymarket.py --venue polymarket --out /root/pm/data
    python scripts/record_polymarket.py --venue deribit --out /root/pm/data
    python scripts/record_polymarket.py --venue polymarket --smoke 30
    python scripts/record_polymarket.py --venue polymarket --print-systemd
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import heapq
import json
import os
import queue
import re
import signal
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:  # the daily ladders' books are a megabyte each and the CLOB sends every token's on (re)connect; the stdlib
    import orjson  # parser cannot keep up with that dump and the venue closes the socket as a "slow consumer"

    def _loads(s): return orjson.loads(s)
    def _dumps(o): return orjson.dumps(o).decode()
except ImportError:  # pragma: no cover - the laptop; same bytes, slower
    def _loads(s): return json.loads(s)
    def _dumps(o): return json.dumps(o, separators=(",", ":"))

DEFAULT_OUT = Path(os.environ.get("QR_ROOT", Path.home() / "qr" / "lake")) / "polymarket_live"
GAMMA = "https://gamma-api.polymarket.com"
PM_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DERIBIT_WS = "wss://www.deribit.com/ws/api/v2"
DERIBIT_CHANNELS = [
    "deribit_volatility_index.btc_usd", "deribit_volatility_index.eth_usd",
    "deribit_price_index.btc_usd", "deribit_price_index.eth_usd", "deribit_price_index.sol_usd",
]
QUERIES = (
    "bitcoin reach", "bitcoin dip", "bitcoin hit", "what price will bitcoin hit", "bitcoin above",
    "ethereum reach", "ethereum dip", "ethereum hit", "what price will ethereum hit", "ethereum above",
    "solana reach", "solana dip", "what price will solana hit",
    # 13 October 2026 (option B, docs/31 §16): the daily ladders are one event an asset a day, "Bitcoin above ___ on October 13?";
    # "solana above" was missing and "price of <asset>" is how their questions begin
    "solana above", "price of bitcoin", "price of ethereum", "price of solana",
)
# the same classification as qr/data/polymarket.py, copied so the box needs nothing installed
EXCLUDE = re.compile(r"up or down|\b\d{1,2}(:\d{2})?\s?(am|pm)\s?(et|utc)\b|\bfirst\?|\bor \$", re.I)
ASSET = re.compile(r"\b(bitcoin|btc|ethereum|eth|solana|sol)\b", re.I)
STRIKE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s*([kKmM])?")
MIN_HORIZON_DAYS = 7


def _utc_hour(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d/%H")


def _get(url: str) -> dict | list:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        return json.loads(r.read())


def active_markets(min_horizon_days: int = MIN_HORIZON_DAYS) -> list[dict]:
    """Every active, classifiable BTC/ETH/SOL threshold market whose listing-to-settlement life is ≥ `min_horizon_days`, with its two token ids."""
    now = datetime.now(timezone.utc)
    seen, out = set(), []
    for q in QUERIES:
        for page in range(1, 6):
            try:
                r = _get(f"{GAMMA}/public-search?q={urllib.parse.quote(q)}&limit_per_type=50&page={page}&events_status=active")
            except Exception as exc:  # noqa: BLE001
                print(f"[gamma] {q!r} p{page}: {exc}", file=sys.stderr)
                break
            events = r.get("events") or [] if isinstance(r, dict) else []
            if not events:
                break
            for e in events:
                for m in e.get("markets") or []:
                    mid = str(m.get("id"))
                    q_text = m.get("question") or ""
                    if mid in seen or m.get("closed") or EXCLUDE.search(q_text) or not ASSET.search(q_text) or not STRIKE.search(q_text):
                        continue
                    end = m.get("endDate") or e.get("endDate")
                    start = m.get("startDate") or e.get("startDate") or m.get("createdAt")
                    try:
                        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    except Exception:  # noqa: BLE001
                        continue
                    if end_dt <= now or (end_dt - start_dt).days < min_horizon_days:
                        continue
                    tokens = m.get("clobTokenIds")
                    if isinstance(tokens, str):
                        try:
                            tokens = json.loads(tokens)
                        except json.JSONDecodeError:
                            tokens = None
                    if not tokens or len(tokens) < 2:
                        continue
                    seen.add(mid)
                    out.append({"market_id": mid, "question": q_text, "end": end, "start": start,
                                "yes_token": str(tokens[0]), "no_token": str(tokens[1])})
            time.sleep(0.2)
    return out


def compact(raw: str, yes_tokens: set[str], last_tob: dict, near: float = 0.02, book_depth: int | None = None) -> str | None:
    """Polymarket message without whitespace, hashes, the NO-side mirror, or deep-book churn; None when nothing is left.

    `book_depth` keeps the best `book_depth` levels a side of a full `book` snapshot (the best bid is the highest
    bid, the best ask the lowest ask; the CLOB sends bids ascending and asks descending). The daily ladders'
    books run to a megabyte of JSON each — thousands of one-tick levels of bot quotes — and the CLOB sends every
    token's full book on every (re)connect, 40 MB gzipped an hour for 659 tokens; the rules read the top of
    book, and fifty levels is more depth than any reward band or posted order ever touches.
    """
    try:
        msg = _loads(raw)
    except ValueError:  # json.JSONDecodeError and orjson.JSONDecodeError are both ValueErrors
        return raw
    msgs = msg if isinstance(msg, list) else [msg]
    out = []
    for m in msgs:
        if not isinstance(m, dict):
            out.append(m)
            continue
        m.pop("hash", None)
        if book_depth and m.get("event_type") == "book":
            for side, best_is_high in (("bids", True), ("asks", False)):
                levels = m.get(side)
                if isinstance(levels, list) and len(levels) > book_depth:
                    try:
                        pick = heapq.nlargest if best_is_high else heapq.nsmallest
                        levels = pick(book_depth, levels, key=lambda l: float(l["price"]))
                    except (KeyError, TypeError, ValueError):
                        levels = levels[-book_depth:]
                    m[side] = levels
                    m["book_depth"] = book_depth
        if m.get("event_type") == "price_change" and isinstance(m.get("price_changes"), list):
            keep = []
            for c in m["price_changes"]:
                aid = str(c.get("asset_id"))
                if aid not in yes_tokens:
                    continue
                c.pop("hash", None)
                tob = (c.get("best_bid"), c.get("best_ask"))
                moved = last_tob.get(aid) != tob
                last_tob[aid] = tob
                try:
                    mid = (float(tob[0]) + float(tob[1])) / 2
                    close = near > 0 and abs(float(c["price"]) - mid) <= near   # near 0: top-of-book moves only, nothing else
                except (TypeError, ValueError):
                    close = True
                if moved or close:
                    keep.append(c)
            if not keep:
                continue
            m["price_changes"] = keep
        out.append(m)
    if not out:
        return None
    return _dumps(out if isinstance(msg, list) else out[0])


class Writer:
    """Compacts and writes on its own thread, so the socket is always being read.

    On 13 October 2026, with 659 tokens and another project's process holding
    one of the box's two cores, the venue closed the socket as a "slow
    consumer" once or twice an hour (close 1013) and each close cost a
    13-second gap. The event loop now only receives and queues; this thread
    does the parsing, the compaction and the gzip write, and a burst waits
    in memory instead of in the venue's send buffer.
    """

    def __init__(self, rec: "Recorder", near: float, book_depth: int | None, verbose: bool = False) -> None:
        self.rec, self.near, self.book_depth, self.verbose = rec, near, book_depth, verbose
        self.q: queue.Queue = queue.Queue()
        self.yes: set[str] = set()
        self.last_tob: dict = {}
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="pm-writer", daemon=True)
        self.thread.start()

    def put(self, raw: str) -> None:
        self.q.put(raw)

    def _run(self) -> None:
        warned = 0
        while not (self._stop.is_set() and self.q.empty()):
            try:
                raw = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            line = compact(raw, self.yes, self.last_tob, self.near, self.book_depth)
            if line is not None:
                self.rec.write(line)
                if self.verbose and self.rec.lines % 200 == 0:
                    print(f"[polymarket] {self.rec.lines} lines", flush=True)
            n = self.q.qsize()
            if n > 20000 and time.monotonic() - warned > 60:
                print(f"[polymarket] writer {n} messages behind", file=sys.stderr, flush=True)
                warned = time.monotonic()

    def close(self, timeout: float = 30.0) -> None:
        self._stop.set()
        self.thread.join(timeout)


class Recorder:
    def __init__(self, venue: str, out: Path) -> None:
        self.venue = venue
        self.out = out / venue
        self.out.mkdir(parents=True, exist_ok=True)
        self._day = None
        self._fh = None
        self.lines = 0

        self._last_flush = time.monotonic()

    def _file(self, hour: str):
        if hour != self._day:
            if self._fh:
                self._fh.close()
            path = self.out / f"{hour}.jsonl.gz"
            path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = gzip.open(path, "at", encoding="utf-8", compresslevel=9)
            self._day = hour
        return self._fh

    def write(self, raw: str) -> None:
        now = time.time()
        fh = self._file(_utc_hour(now))
        fh.write(json.dumps({"venue": self.venue, "recorded_at": round(now, 3), "raw": raw}, separators=(",", ":")) + "\n")
        self.lines += 1
        if time.monotonic() - self._last_flush > 2.0:
            fh.flush()
            self._last_flush = time.monotonic()

    def close(self) -> None:
        if self._fh:
            self._fh.close()


async def run_polymarket(rec: Recorder, refresh: float, verbose: bool, smoke: float | None, near: float = 0.02,
                         min_horizon_days: int = MIN_HORIZON_DAYS, book_depth: int | None = None) -> None:
    import websockets
    t_end = time.monotonic() + smoke if smoke else None
    backoff = 2.0
    writer = Writer(rec, near, book_depth, verbose)

    def catalogue(markets: list[dict]) -> None:
        (rec.out / "catalogue.json").write_text(json.dumps({"at": time.time(), "min_horizon_days": min_horizon_days, "markets": markets}))
        with (rec.out / "catalogue.jsonl").open("a", encoding="utf-8") as fh:  # every refresh kept: a market that ends drops out of the next one
            fh.write(json.dumps({"at": time.time(), "min_horizon_days": min_horizon_days, "markets": markets}, separators=(",", ":")) + "\n")

    try:
        markets = await asyncio.to_thread(active_markets, min_horizon_days)
        while True:
            yes = {m["yes_token"] for m in markets}
            ids = sorted(yes)  # YES only: the CLOB folds NO orders into the YES book
            writer.yes = yes
            catalogue(markets)
            print(f"[polymarket] {len(markets)} active markets, {len(ids)} tokens", flush=True)
            if not ids:
                await asyncio.sleep(min(refresh, 300))
                markets = await asyncio.to_thread(active_markets, min_horizon_days)
                continue
            t_refresh = time.monotonic() + refresh
            try:
                # max_queue = (high, low) water marks in frames: the library stops reading the socket at `high` queued frames
                # and resumes at `low`. The default (16) throttled the reader so hard that the venue's send buffer filled and
                # it closed the socket as a slow consumer; 8,192 is about a minute of the daily ladders at full tilt.
                # websockets 17 reads nothing at all when given a bare integer here — pass the tuple (measured 13 Oct 2026).
                async with websockets.connect(PM_WS, ping_interval=None, max_size=2**24, max_queue=(8192, 2048)) as ws:
                    await ws.send(json.dumps({"assets_ids": ids, "type": "market"}))
                    backoff = 2.0
                    last_ping = time.monotonic()
                    while True:
                        if t_end and time.monotonic() > t_end:
                            return
                        if time.monotonic() > t_refresh:
                            # rebuild the list off the loop; the socket keeps being read into the library's queue meanwhile
                            fresh = await asyncio.to_thread(active_markets, min_horizon_days)
                            t_refresh = time.monotonic() + refresh
                            if {m["yes_token"] for m in fresh} != yes:
                                markets = fresh
                                break  # reconnect with the new token list
                            catalogue(fresh)  # the hourly record of the list in force, even when nothing changed
                            print(f"[polymarket] {len(fresh)} active markets, list unchanged", flush=True)
                            continue
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        except asyncio.TimeoutError:
                            if time.monotonic() - last_ping > 10:
                                await ws.send("PING")
                                last_ping = time.monotonic()
                            continue
                        if raw == "PONG":
                            continue
                        writer.put(raw if isinstance(raw, str) else raw.decode())
            except Exception as exc:  # noqa: BLE001
                print(f"[polymarket] reconnect after error: {exc!r} (sleep {backoff:.0f}s)", file=sys.stderr, flush=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 120)
    finally:
        writer.close()


async def run_deribit(rec: Recorder, verbose: bool, smoke: float | None) -> None:
    import websockets
    t_end = time.monotonic() + smoke if smoke else None
    backoff = 2.0
    while True:
        try:
            async with websockets.connect(DERIBIT_WS, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "public/subscribe", "params": {"channels": DERIBIT_CHANNELS}}))
                backoff = 2.0
                while True:
                    if t_end and time.monotonic() > t_end:
                        return
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    except asyncio.TimeoutError:
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "public/test"}))
                        continue
                    if '"method":"subscription"' not in raw and '"method": "subscription"' not in raw:
                        continue
                    rec.write(raw)
                    if verbose and rec.lines % 200 == 0:
                        print(f"[deribit] {rec.lines} lines", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[deribit] reconnect after error: {exc!r} (sleep {backoff:.0f}s)", file=sys.stderr, flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 120)


SYSTEMD = """[Unit]
Description=qr: record {venue} for the prediction-market study (Programme 3)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={python} {script} --venue {venue} --out {out}
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--venue", choices=["polymarket", "deribit"], default="polymarket")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--refresh", type=float, default=3600.0, help="seconds between token-list rebuilds (polymarket)")
    ap.add_argument("--smoke", type=float, default=None, help="run this many seconds and stop")
    ap.add_argument("--near", type=float, default=0.02, help="keep price changes within this of the mid (polymarket); top-of-book moves are always kept")
    ap.add_argument("--book-depth", type=int, default=None,
                    help="keep only the best N levels a side of each full book snapshot (None: whole book; 50 on the box from 13 Oct 2026)")
    ap.add_argument("--min-horizon-days", type=int, default=MIN_HORIZON_DAYS,
                    help="admit a market only if its listing-to-settlement life is at least this many days (7: v1's rule; 1 admits the daily ladders)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--print-systemd", action="store_true")
    a = ap.parse_args(argv)
    if a.print_systemd:
        print(SYSTEMD.format(venue=a.venue, python=sys.executable, script=Path(__file__).resolve(), out=a.out.resolve()))
        return 0
    try:
        import websockets  # noqa: F401
    except ImportError:
        print("needs the `websockets` package: pip install websockets", file=sys.stderr)
        return 2
    rec = Recorder(a.venue, a.out)
    loop = asyncio.new_event_loop()

    def _stop(*_):
        for t in asyncio.all_tasks(loop):
            t.cancel()

    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, _stop)
    try:
        coro = run_polymarket(rec, a.refresh, a.verbose, a.smoke, a.near, a.min_horizon_days, a.book_depth) if a.venue == "polymarket" else run_deribit(rec, a.verbose, a.smoke)
        loop.run_until_complete(coro)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        rec.close()
        print(f"[{a.venue}] {rec.lines} lines written to {rec.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
