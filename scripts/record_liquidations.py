#!/usr/bin/env python3
"""Record perpetual-futures liquidations forward: one line per event, never rewritten.

Programme 2 (`docs/20_PROGRAMME_2.md`, §4.3, family C3). No public archive of
liquidations exists on any venue; the streams are live-only, so the history
has to be recorded, and data you record yourself is point-in-time by
construction (`docs/17`).

Three venues, chosen on 2026-09-15 by probing what actually streams from the
machines this runs on:

* **okx** — `liquidation-orders` for every SWAP in one subscription. Global,
  no symbol list to maintain. The default.
* **bybit** — `allLiquidation.<SYMBOL>` per symbol; the symbol list is read
  from the venue's instrument endpoint at start-up (USDT linear perps).
* **binance** — `!forceOrder@arr`, throttled by Binance to one event per
  symbol per second (the largest in that second). Its REST endpoint answers
  from Dubai but the websocket connects and sends nothing, so this venue is
  kept for a host where it does stream (test with `--smoke 60`).

Each line is the venue's own message under `raw`, plus a small normalised
header so the three files can be read together:

    {"venue","event_time_ms","symbol","side","price","qty","recorded_at","raw"}

`side` is the venue's word for the *liquidation order*: on every venue here
a `sell`/`SELL` liquidation is a long being closed out.

    python scripts/record_liquidations.py --venue okx --out ~/qr/lake/liquidations
    python scripts/record_liquidations.py --venue bybit --out ~/qr/lake/liquidations
    python scripts/record_liquidations.py --venue okx --print-systemd

Files: `<out>/<venue>/YYYY-MM-DD.jsonl`, UTC days, appended, flushed per
line. Reconnects on any error with a growing pause. Needs `websockets` and,
for bybit's symbol list, `requests`; everything else is stdlib.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUT = Path(os.environ.get("QR_ROOT", Path.home() / "qr" / "lake")) / "liquidations"

VENUES = {
    "okx": {
        "url": "wss://ws.okx.com:8443/ws/v5/public",
        "subscribe": [{"op": "subscribe", "args": [{"channel": "liquidation-orders", "instType": "SWAP"}]}],
        "ping": '{"op":"ping"}',
    },
    "bybit": {
        "url": "wss://stream.bybit.com/v5/public/linear",
        "instruments": "https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000",
        "ping": '{"op":"ping"}',
    },
    "binance": {
        "url": "wss://fstream.binance.com/ws/!forceOrder@arr",
        "subscribe": [],
        "ping": None,
    },
}

SYSTEMD = """[Unit]
Description=qr: record {venue} perpetual liquidations forward
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={python} {script} --venue {venue} --out {out}
Restart=always
RestartSec=10
User={user}

[Install]
WantedBy=multi-user.target
"""


def _utc_day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")


def _now_ms() -> int:
    return int(time.time() * 1000)


# ------------------------------------------------------------ normalisation


def parse_okx(msg: dict) -> list[dict]:
    if msg.get("arg", {}).get("channel") != "liquidation-orders" or "data" not in msg:
        return []
    out = []
    for inst in msg["data"]:
        for d in inst.get("details", []):
            out.append(
                {
                    "event_time_ms": int(d.get("ts", _now_ms())),
                    "symbol": inst.get("instId"),
                    "side": d.get("side"),
                    "price": d.get("bkPx"),
                    "qty": d.get("sz"),
                    "raw": {"instId": inst.get("instId"), **d},
                }
            )
    return out


def parse_bybit(msg: dict) -> list[dict]:
    if not str(msg.get("topic", "")).startswith("allLiquidation") or "data" not in msg:
        return []
    return [
        {
            "event_time_ms": int(d.get("T", msg.get("ts", _now_ms()))),
            "symbol": d.get("s"),
            "side": d.get("S"),
            "price": d.get("p"),
            "qty": d.get("v"),
            "raw": d,
        }
        for d in msg["data"]
    ]


def parse_binance(msg: dict) -> list[dict]:
    if msg.get("e") != "forceOrder" or "o" not in msg:
        return []
    o = msg["o"]
    return [
        {
            "event_time_ms": int(o.get("T", msg.get("E", _now_ms()))),
            "symbol": o.get("s"),
            "side": o.get("S"),
            "price": o.get("ap") or o.get("p"),
            "qty": o.get("z") or o.get("q"),
            "raw": o,
        }
    ]


PARSERS = {"okx": parse_okx, "bybit": parse_bybit, "binance": parse_binance}


# ------------------------------------------------------------------- files


class Recorder:
    def __init__(self, venue: str, out: Path) -> None:
        self.venue = venue
        self.out = out / venue
        self.out.mkdir(parents=True, exist_ok=True)
        self._day: str | None = None
        self._fh = None
        self.written = 0
        self.stopping = False

    def _file(self, day: str):
        if day != self._day:
            if self._fh:
                self._fh.close()
            self._fh = (self.out / f"{day}.jsonl").open("a", encoding="utf-8")
            self._day = day
        return self._fh

    def write(self, raw: str) -> int:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return 0
        events = PARSERS[self.venue](msg) if isinstance(msg, dict) else []
        for ev in events:
            line = {
                "venue": self.venue,
                **ev,
                "recorded_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            }
            fh = self._file(_utc_day(ev["event_time_ms"]))
            fh.write(json.dumps(line, separators=(",", ":")) + "\n")
            fh.flush()
            self.written += 1
        return len(events)

    def close(self) -> None:
        if self._fh:
            self._fh.close()


# ----------------------------------------------------------------- venues


def bybit_symbols() -> list[str]:
    import requests

    symbols: list[str] = []
    cursor = None
    while True:
        url = VENUES["bybit"]["instruments"] + (f"&cursor={cursor}" if cursor else "")
        body = requests.get(url, timeout=20).json()
        result = body.get("result", {})
        symbols += [
            i["symbol"]
            for i in result.get("list", [])
            if i.get("contractType") == "LinearPerpetual" and i.get("status") == "Trading" and i["symbol"].endswith("USDT")
        ]
        cursor = result.get("nextPageCursor")
        if not cursor:
            break
    return sorted(set(symbols))


def subscriptions(venue: str, symbols: list[str] | None) -> list[dict]:
    if venue == "bybit":
        names = symbols or bybit_symbols()
        batches = [names[i : i + 10] for i in range(0, len(names), 10)]
        return [{"op": "subscribe", "args": [f"allLiquidation.{s}" for s in batch]} for batch in batches]
    return list(VENUES[venue].get("subscribe", []))


async def run(recorder: Recorder, subs: list[dict], verbose: bool, smoke: float | None) -> None:
    import websockets

    venue = VENUES[recorder.venue]
    pause = 1.0
    deadline = time.time() + smoke if smoke else None
    while not recorder.stopping:
        try:
            async with websockets.connect(venue["url"], ping_interval=20, ping_timeout=20, max_size=2**21) as ws:
                pause = 1.0
                for sub in subs:
                    await ws.send(json.dumps(sub))
                print(f"[{recorder.venue}] connected {venue['url']} ({len(subs)} subscription messages)", file=sys.stderr)
                last_ping = time.time()
                while not recorder.stopping:
                    if deadline and time.time() >= deadline:
                        recorder.stopping = True
                        break
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    except asyncio.TimeoutError:
                        if venue["ping"] and time.time() - last_ping > 20:
                            await ws.send(venue["ping"])
                            last_ping = time.time()
                        continue
                    n = recorder.write(raw)
                    if verbose and n:
                        print(f"[{recorder.venue}] {recorder.written} events", file=sys.stderr)
        except (asyncio.CancelledError, KeyboardInterrupt):
            break
        except Exception as exc:  # any network error: reconnect, never die quietly
            if recorder.stopping:
                break
            print(f"[{recorder.venue}] stream error: {exc!r}; reconnecting in {pause:.0f}s", file=sys.stderr)
            await asyncio.sleep(pause)
            pause = min(pause * 2, 60.0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--venue", choices=sorted(VENUES), default="okx")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--symbols", nargs="*", help="bybit only: override the instrument list")
    ap.add_argument("--smoke", type=float, default=None, help="run for this many seconds, then stop")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--print-systemd", action="store_true", help="print a systemd unit for the always-on box")
    args = ap.parse_args(argv)
    if args.print_systemd:
        print(
            SYSTEMD.format(
                venue=args.venue,
                python=sys.executable,
                script=Path(__file__).resolve(),
                out=args.out,
                user=os.environ.get("USER", "root"),
            )
        )
        return 0
    try:
        import websockets  # noqa: F401
    except ImportError:
        print("needs the `websockets` package: pip install websockets", file=sys.stderr)
        return 2

    recorder = Recorder(args.venue, args.out)
    subs = subscriptions(args.venue, args.symbols)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _stop(*_):
        recorder.stopping = True
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _stop)
    try:
        loop.run_until_complete(run(recorder, subs, args.verbose, args.smoke))
    except asyncio.CancelledError:
        pass
    finally:
        recorder.close()
        print(f"[{args.venue}] stopped after {recorder.written} events -> {recorder.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
