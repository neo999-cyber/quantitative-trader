"""Maker-fill study stage 1 — the terminal driver (B13/B16, docs/27).

    .venv/bin/python scripts/study_stage1.py preview  --config qc/../study/stage1.json
    .venv/bin/python scripts/study_stage1.py run      --config study/stage1.json      # asks for the mandate hash
    .venv/bin/python scripts/study_stage1.py resume   --config study/stage1.json      # reconcile after a pause
    .venv/bin/python scripts/study_stage1.py close    --config study/stage1.json      # cancel and close everything now
    .venv/bin/python scripts/study_stage1.py run      --config study/stage1.json --detach   # as `run`, then leaves the terminal
    .venv/bin/python scripts/study_stage1.py status   --config study/stage1.json      # is it running, and do the venue and the journal agree
    .venv/bin/python scripts/study_stage1.py stop     --config study/stage1.json      # orderly stop of a detached session

    .venv/bin/python scripts/study_stage1.py grant    --config study/stage1.json --through 2026-10-11   # the owner, once: unattended sessions
    .venv/bin/python scripts/study_stage1.py run      --config study/stage1.json --standing             # an unattended start (a timer's command)
    .venv/bin/python scripts/study_stage1.py revoke   --config study/stage1.json                        # withdraw the standing mandate

A **standing mandate** (3 October 2026) is the owner's typed authorisation of one exact configuration for a
bounded period, kept at `~/.qr/stage1.mandate.json` on the machine that runs the sessions. `run --standing`
starts without a prompt only while that file covers the configuration it is about to run; `grant` is
interactive and has no flag that stands in for the typing on mainnet.

`--detach` (2 October 2026): the mandate is still typed at the terminal; the session then forks into
the background with its own log (`~/qr/lake/study/logs/`) and a pid file, so no keystroke in any
window can reach it — the first live day ended on a stray Ctrl-C. `stop` sends it the same orderly
stop a Ctrl-C would (pause entries, cancel, reconcile, close, verify flat) and waits for it.

The config is a JSON `StudyConfig`. Keys come from `~/.qr/secrets.env`:
`BINANCE_TESTNET_KEY/SECRET` (a Binance *Demo Trading* API key, demo.binance.com),
`BYBIT_TESTNET_KEY/SECRET` (testnet.bybit.com) when `testnet` is true; `BINANCE_STUDY_KEY/SECRET`, `BYBIT_STUDY_KEY/SECRET` (trade-only, no
withdrawal, IP-restricted) when it is false — and mainnet additionally
requires `--i-have-the-owners-yes` on the command line. Nothing here prints
a key. The journal is `~/qr/lake/study/stage1.sqlite`.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qr import secrets
from qr.config import paths
from qr.execution.journal import D, Journal
from qr.execution.study import Session, StudyConfig, grant_standing, preview, read_standing, resume, standing_digest, start, start_under_standing
from qr.execution.venues import BinanceUSDM, BybitLinear


def venues_for(config: StudyConfig) -> dict:
    out = {}
    tag = "TESTNET" if config.testnet else "STUDY"
    if "binance" in config.symbols:
        out["binance"] = BinanceUSDM(secrets.require(f"BINANCE_{tag}_KEY"), secrets.require(f"BINANCE_{tag}_SECRET"),
                                     base=BinanceUSDM.TESTNET if config.testnet else BinanceUSDM.MAINNET)
    if "bybit" in config.symbols:
        # BYBIT_TESTNET_HOST=demo selects Bybit's in-account Demo Trading host (api-demo.bybit.com)
        host = {"demo": BybitLinear.DEMO}.get(os.environ.get("BYBIT_TESTNET_HOST", "testnet"), BybitLinear.TESTNET)
        out["bybit"] = BybitLinear(secrets.require(f"BYBIT_{tag}_KEY"), secrets.require(f"BYBIT_{tag}_SECRET"),
                                   base=host if config.testnet else BybitLinear.MAINNET)
    return out


def load_config(path: str, session_hours: float, expires: str | None = None) -> StudyConfig:
    raw = json.loads(Path(path).read_text())
    if expires:
        raw["session_expires_at"] = expires
    raw.setdefault("session_expires_at", (datetime.now(timezone.utc) + timedelta(hours=session_hours)).isoformat())
    raw["hours_utc"] = tuple(raw.get("hours_utc", (7, 15)))
    return StudyConfig(**raw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["preview", "run", "resume", "close", "status", "stop", "grant", "revoke", "session"])  # `session` is the detached child of `run --detach`
    ap.add_argument("--config", required=True)
    ap.add_argument("--session-hours", type=float, default=8.0)
    ap.add_argument("--poll", type=int, default=5)
    ap.add_argument("--i-have-the-owners-yes", action="store_true", dest="owners_yes")
    ap.add_argument("--confirm", default=None, help="testnet only: the `<hash> STUDY` line, instead of typing it")
    ap.add_argument("--detach", action="store_true", help="run: after the mandate is accepted, continue in the background (log + pid file)")
    ap.add_argument("--expires", default=None, help="internal (`session`): the expiry the mandate was typed for")
    ap.add_argument("--standing", action="store_true", help="run: start under the standing mandate (no prompt); refuses when it does not cover this config today")
    ap.add_argument("--through", default=None, help="grant: the standing mandate's last day, YYYY-MM-DD (at most three weeks ahead)")
    args = ap.parse_args()

    config = load_config(args.config, args.session_hours, args.expires)
    if not config.testnet and not args.owners_yes:
        print("mainnet needs --i-have-the-owners-yes (docs/24 stage 1: the owner's explicit yes to the live configuration)", file=sys.stderr)
        return 2
    study_dir = Path(paths().root) / "study"
    journal_path = study_dir / "stage1.sqlite"
    pid_path = study_dir / "stage1.pid"
    log_dir = study_dir / "logs"
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    standing_path = Path(os.environ.get("QR_SECRETS", Path.home() / ".qr" / "secrets.env")).parent / "stage1.mandate.json"

    if args.action == "revoke":
        if standing_path.exists():
            standing_path.unlink()
            print(f"standing mandate withdrawn ({standing_path}); a running session is not affected — `stop` ends it")
        else:
            print("there is no standing mandate")
        return 0

    if args.action == "grant":
        if not args.through:
            print("grant needs --through YYYY-MM-DD (the last day of unattended sessions)", file=sys.stderr)
            return 2
        preview(config, venues_for(config))
        sd = standing_digest(config)
        print(f"\nThis authorises UNATTENDED sessions of exactly this configuration, started by a timer with nobody at a terminal,\n"
              f"every day through {args.through}. Any change to the configuration ends it; `revoke` withdraws it.")
        if args.confirm and not config.testnet:
            print("--confirm is for testnet rehearsals; a live standing mandate is typed at the terminal", file=sys.stderr)
            return 2
        typed = args.confirm or input(f"\nType `{sd} STANDING {args.through}` to grant it (anything else aborts): ")
        try:
            rec = grant_standing(config, typed, args.through, standing_path)
        except (PermissionError, ValueError) as exc:
            print(f"not granted: {exc}", file=sys.stderr)
            return 1
        print(f"standing mandate granted through {rec['through']} ({standing_path})")
        return 0

    if args.action == "stop":
        pid = _read_pid(pid_path)
        if pid is None or not _alive(pid):
            print("no running session found (pid file absent or stale); `status` shows the account, `close` flattens it")
            return 1
        os.kill(pid, signal.SIGINT)
        print(f"stop requested (pid {pid}); waiting for the orderly close…", flush=True)
        for _ in range(120):
            if not _alive(pid):
                break
            time.sleep(2)
        print("\n".join(_tail(log_dir, 6)))
        if _alive(pid):
            print(f"still running after 4 minutes — look at the log in {log_dir}")
            return 1
        return 0

    venues = venues_for(config)

    if args.action in ("preview", "status"):
        # read-only, and deliberately not through `Journal(...)`: its constructor pauses a journal it finds in STUDY
        # mode (the rule for a crashed session), which would end a session running in the background. Seen on the
        # demo exchange, 2 October 2026: `status` stopped the session it was asked about.
        import sqlite3
        ro = sqlite3.connect(f"file:{journal_path}?mode=ro", uri=True) if journal_path.exists() else None
        mode = ro.execute("SELECT mode FROM control WHERE id = 1").fetchone()[0] if ro else "PAUSED (no journal yet)"
        if args.action == "preview":
            preview(config, venues)
            print(f"\njournal {journal_path} mode {mode}")
            return 0
        pid = _read_pid(pid_path)
        print(f"session process: {'running, pid ' + str(pid) if pid and _alive(pid) else 'not running'}; journal mode {mode}")
        held = {(v, sym): q for v, sym, q in ro.execute("SELECT venue, symbol, qty FROM positions WHERE account = ?", (config.account,)).fetchall()} if ro else {}
        for name, venue in venues.items():
            theirs = venue.positions()
            mine = {sym: D(q) for (v, sym), q in held.items() if v == name and D(q) != 0}
            print(f"{name}: venue positions {theirs or 'flat'}; journal {mine or 'flat'} → {'AGREE' if theirs == mine else 'MISMATCH'}; balances {dict(venue.balances())}")
        open_orders = ro.execute("SELECT i.symbol, i.side, i.action, o.state FROM intents i JOIN orders o ON o.client_id = i.client_id WHERE i.account = ? "
                                 "AND o.state NOT IN ('FILLED','CANCELLED','REJECTED','EXPIRED')", (config.account,)).fetchall() if ro else []
        print(f"orders the journal still considers open: {open_orders or 'none'}")
        try:
            rec = read_standing(config, standing_path)
            print(f"standing mandate: covers this configuration through {rec['through']} (granted {rec['granted_at'][:16]})")
        except PermissionError as exc:
            print(f"standing mandate: {exc}")
        tail = _tail(log_dir, 5)
        if tail:
            print("log:\n  " + "\n  ".join(tail))
        return 0

    journal = Journal(journal_path)

    if args.action == "session":
        # the detached child of `run --detach`: the owner's typed mandate line arrives on stdin
        say = lambda m: print(f"{datetime.now(timezone.utc):%H:%M:%S} {m}", flush=True)  # noqa: E731
        typed = sys.stdin.readline().strip() if args.expires else ""
        if not typed:
            say("`session` is started by `run --detach` only")
            return 2
        diffs = resume(journal, venues, config.account)
        if diffs:
            say("cannot start: venues and journal disagree:\n  " + "\n  ".join(diffs))
            return 1
        try:
            start(journal, config, venues, typed)
        except PermissionError as exc:
            say(f"not started: {exc}")
            return 1
        if shutil.which("caffeinate"):
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)   # no sleep while it lives
        say(f"session started, pid {os.getpid()}, config {config.digest()}, until {config.session_expires_at}")
        code = 1
        try:
            problems = Session(journal, config, venues, log=say).run(poll_s=args.poll)
            say("session ended flat" if not problems else "SESSION ENDED NOT FLAT — check the venues:\n  " + "\n  ".join(problems))
            code = 0 if not problems else 1
        except BaseException as exc:  # noqa: BLE001 — nobody is watching a detached process: the traceback goes in the log
            import traceback
            say(f"SESSION CRASHED: {exc!r}\n{traceback.format_exc()}")
        finally:
            if _read_pid(pid_path) == os.getpid():
                pid_path.unlink(missing_ok=True)
        return code


    if args.action == "resume":
        diffs = resume(journal, venues, config.account)
        print("venues and journal agree" if not diffs else "MISMATCH:\n  " + "\n  ".join(diffs))
        return 0 if not diffs else 1
    if args.action == "close":
        session = Session(journal, config, venues)
        problems = session.close_all()
        print("flat at every venue" if not problems else "NOT FLAT:\n  " + "\n  ".join(problems))
        return 0 if not problems else 1

    preview(config, venues)
    diffs = resume(journal, venues, config.account)
    if diffs:
        print("cannot start: venues and journal disagree:\n  " + "\n  ".join(diffs), file=sys.stderr)
        return 1
    if args.confirm and not config.testnet:
        print("--confirm is for testnet rehearsals; a live study is typed at the terminal", file=sys.stderr)
        return 2
    if args.standing:
        if args.detach:
            print("--standing runs in the foreground of its supervisor (a systemd unit); use one or the other", file=sys.stderr)
            return 2
        try:
            rec = start_under_standing(journal, config, venues, standing_path)
        except PermissionError as exc:
            print(f"not started: {exc}", file=sys.stderr)
            return 1
        say = lambda m: print(f"{datetime.now(timezone.utc):%H:%M:%S} {m}", flush=True)  # noqa: E731
        say(f"session started under the standing mandate (through {rec['through']}), pid {os.getpid()}, config {config.digest()}, until {config.session_expires_at}")
        problems = Session(journal, config, venues, log=say).run(poll_s=args.poll)
        say("session ended flat" if not problems else "SESSION ENDED NOT FLAT — check the venues:\n  " + "\n  ".join(problems))
        return 0 if not problems else 1

    typed = args.confirm or input(f"\nType `{config.digest()} STUDY` to start this session (anything else aborts): ")

    if args.detach:
        # A fresh process, not a fork (on macOS a forked Python that touches the network dies without a word), and
        # the *child* starts the mandate: a journal found in STUDY mode by a new process is paused on open, by design,
        # so STUDY cannot be handed over. The line typed here goes to the child over a pipe; the child re-reads the
        # config with the same expiry (the same digest) and calls `start()` with it. (Both learned on the demo
        # exchange, 2 October 2026.)
        if typed.strip() != f"{config.digest()} STUDY":
            print("not started: mandate not confirmed: type the config hash and STUDY exactly", file=sys.stderr)
            return 1
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"session_{datetime.now(timezone.utc):%Y-%m-%d_%H%M}.log"
        journal.close()
        cmd = [sys.executable, str(Path(__file__).resolve()), "session", "--config", str(Path(args.config).resolve()),
               "--expires", config.session_expires_at, "--poll", str(args.poll)] + (["--i-have-the-owners-yes"] if args.owners_yes else [])
        with open(log_path, "a") as log_file:
            child = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True, text=True)
        child.stdin.write(typed.strip() + "\n")
        child.stdin.close()
        pid_path.write_text(str(child.pid))
        time.sleep(6)
        if child.poll() is not None:
            print(f"the background session exited at once (code {child.returncode}):\n  " + "\n  ".join(_tail(log_dir, 6)), file=sys.stderr)
            return 1
        print(f"STUDY mode until {config.session_expires_at}\nrunning in the background: pid {child.pid}\nlog: {log_path}\n"
              f"stop it with: scripts/study_stage1.py stop --config {args.config}" + (" --i-have-the-owners-yes" if not config.testnet else ""))
        return 0

    try:
        start(journal, config, venues, typed)
    except PermissionError as exc:
        print(f"not started: {exc}", file=sys.stderr)
        return 1
    print(f"STUDY mode until {config.session_expires_at}; Ctrl-C pauses entries and closes positions")
    session = Session(journal, config, venues)
    problems = session.run(poll_s=args.poll)
    print("session ended flat" if not problems else "SESSION ENDED NOT FLAT — check the venues:\n  " + "\n  ".join(problems))
    return 0 if not problems else 1


def _read_pid(pid_path: Path) -> int | None:
    try:
        return int(pid_path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _tail(log_dir: Path, n: int) -> list[str]:
    logs = sorted(log_dir.glob("session_*.log")) if log_dir.exists() else []
    if not logs:
        return []
    return logs[-1].read_text().splitlines()[-n:]


if __name__ == "__main__":
    raise SystemExit(main())
