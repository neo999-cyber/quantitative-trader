"""`qr` — the platform's command line.

    qr doctor                     what is reachable and where things live
    qr data pull   --symbols ...  fill the local Binance mirror (needs network)
    qr data ingest                mirror -> Parquet lake + manifest
    qr data qa                    QA report over the lake
    qr data universe              the point-in-time top-N, as of today
    qr fng pull | fng show        Fear & Greed index
    qr trial verify | trial show  the hash-chained trial log
    qr backtest --family ...      one strategy, honestly costed

The pull commands need internet and are meant to run on the laptop; everything
else works offline against the mirror and the lake, which is what the cloud
sandbox is limited to.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from qr.config import bucket_mirror, paths
from qr.data.binance import BinanceBucket, HttpBucket, LocalBucket, kline_key
from qr.data.lake import Lake
from qr.data.panel import Panel
from qr.data.qa import check_klines, report_markdown, summarise
from qr.data.universe import UniverseSpec, as_instruments, membership
from qr.execution.costs import TRIAL_BNB_DISCOUNT, TRIAL_FEE_TIER, CostModel
from qr.report import table
from qr.validate.trial_log import TrialLog, TrialLogCorrupt

FAMILIES = {"buy_and_hold": "BuyAndHold", "tsmom": "TSMOM", "random_entry": "RandomEntry"}


def _lake(args) -> Lake:
    return Lake(paths(getattr(args, "root", None)))


def _mirror(args) -> LocalBucket:
    return LocalBucket(bucket_mirror(getattr(args, "mirror", None)))


# ------------------------------------------------------------------- commands


def cmd_doctor(args) -> int:
    p = paths(args.root).ensure()
    mirror = bucket_mirror(args.mirror)
    lake = Lake(p)
    rows = [
        {"item": "lake root", "value": str(p.root), "state": "OK" if p.root.exists() else "MISSING"},
        {"item": "bucket mirror", "value": str(mirror), "state": "OK" if mirror.exists() else "EMPTY"},
        {"item": "manifest", "value": str(p.manifest_db), "state": f"{len(lake.manifest())} artefacts"},
        {"item": "manifest hash", "value": lake.manifest_hash()[:16] + "…", "state": ""},
        {"item": "trial log", "value": str(p.trial_log), "state": _trial_state(p.trial_log)},
    ]
    for name in ("pandas", "numpy", "pyarrow", "duckdb", "scipy", "vectorbt"):
        rows.append({"item": name, "value": _version(name), "state": ""})
    print(table(pd.DataFrame(rows)))
    return 0


def _version(module: str) -> str:
    try:
        return __import__(module).__version__
    except Exception:
        return "not installed"


def _trial_state(path: Path) -> str:
    log = TrialLog(path)
    try:
        return f"{log.verify()} records, {log.trial_count()} trials"
    except TrialLogCorrupt as exc:
        return f"CORRUPT: {exc}"


def cmd_data_pull(args) -> int:
    """Download bucket files into the local mirror. Laptop only."""
    remote = BinanceBucket(HttpBucket(), market=args.market)
    mirror = _mirror(args)
    symbols = args.symbols or remote.symbols(args.interval)
    if args.top:
        symbols = symbols[: args.top]
    pulled = skipped = 0
    for symbol in symbols:
        for period in remote.periods(symbol, args.interval):
            if args.since and period < args.since:
                continue
            for key in (kline_key(symbol, args.interval, period, "monthly", args.market),):
                for suffix in ("", ".CHECKSUM"):
                    target = key + suffix
                    if mirror.exists(target) and not args.force:
                        skipped += 1
                        continue
                    try:
                        mirror.write(target, remote.source.read(target))
                        pulled += 1
                    except Exception as exc:  # a missing CHECKSUM is not fatal
                        if not suffix:
                            print(f"  ! {target}: {exc}", file=sys.stderr)
        print(f"  {symbol}: mirrored", file=sys.stderr)
    print(f"pulled {pulled} files, skipped {skipped} already present, into {mirror.root}")
    return 0


def cmd_data_ingest(args) -> int:
    """Mirror -> lake. Idempotent: re-running rewrites and re-hashes."""
    bucket = BinanceBucket(_mirror(args), market=args.market, verify=not args.no_verify)
    lake = _lake(args)
    symbols = args.symbols or bucket.symbols(args.interval)
    written = []
    for symbol in symbols:
        frame = bucket.load_klines(symbol, args.interval, args.start, args.end)
        if frame.empty:
            print(f"  {symbol}: no bars in the mirror", file=sys.stderr)
            continue
        lake.write_klines(symbol, frame, args.interval)
        written.append({"symbol": symbol, "bars": len(frame), "start": frame.index[0], "end": frame.index[-1]})
    if written:
        lake.write_reference("instruments", bucket.instruments(symbols, args.interval))
    print(table(pd.DataFrame(written)))
    print(f"manifest hash: {lake.manifest_hash()}")
    return 0 if written else 1


def cmd_data_qa(args) -> int:
    lake = _lake(args)
    symbols = args.symbols or lake.symbols(args.interval)
    reports = [check_klines(lake.read_klines(s, args.interval), s, args.interval) for s in symbols]
    text = report_markdown(reports, f"Data QA — {args.interval}, {len(reports)} symbols")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    failed = [r.symbol for r in reports if r.verdict == "FAIL"]
    if failed:
        print(f"FAIL: {', '.join(failed)}", file=sys.stderr)
    return 1 if failed else 0


def cmd_data_universe(args) -> int:
    panel = _lake(args).load_panel(interval=args.interval, start=args.start, end=args.end)
    spec = UniverseSpec(n=args.n, lookback=args.lookback, min_history=args.min_history)
    frame = membership(panel, spec)
    print(f"universe: {spec.describe()}\n")
    print(table(as_instruments(frame)))
    latest = frame.iloc[-1]
    print(f"\nas of {frame.index[-1]}: {', '.join(latest.index[latest.to_numpy()])}")
    return 0


def cmd_fng_pull(args) -> int:
    from qr.data.feargreed import HttpFearGreed

    payload = HttpFearGreed().read()
    target = Path(args.out or (paths(args.root).ensure().reference / "fear_greed.json"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    print(f"wrote {target} ({len(payload)} bytes)")
    return 0


def cmd_fng_show(args) -> int:
    from qr.data.feargreed import LocalFearGreed, fetch

    path = Path(args.path or (paths(args.root).reference / "fear_greed.json"))
    frame = fetch(LocalFearGreed(path))
    print(f"{len(frame)} days, {frame.index.min()} -> {frame.index.max()}\n")
    print(table(frame.tail(args.tail), index=True))
    return 0


def cmd_trial_verify(args) -> int:
    log = TrialLog(paths(args.root).trial_log)
    try:
        count = log.verify()
    except TrialLogCorrupt as exc:
        print(f"TRIAL LOG CORRUPT: {exc}", file=sys.stderr)
        return 2
    print(f"chain verified: {count} records, {log.trial_count()} trials counted")
    return 0


def cmd_trial_show(args) -> int:
    log = TrialLog(paths(args.root).trial_log)
    records = log.records(kind=args.kind, hypothesis_id=args.hypothesis)[-args.tail :]
    if not records:
        print("(empty)")
        return 0
    frame = pd.DataFrame(
        [
            {
                "seq": r.seq,
                "ts": r.ts[:19],
                "kind": r.kind,
                "hypothesis": r.hypothesis_id,
                "summary": _summarise_payload(r.kind, r.payload),
            }
            for r in records
        ]
    )
    print(table(frame))
    return 0


def _summarise_payload(kind: str, payload: dict) -> str:
    if kind == "run":
        metrics = payload.get("metrics") or {}
        sharpe = metrics.get("sharpe")
        return f"{payload.get('family')} {payload.get('params')} variants={payload.get('variants')}" + (
            f" sharpe={sharpe:.2f}" if isinstance(sharpe, (int, float)) else ""
        )
    if kind == "gate":
        return f"gate {payload.get('gate')} {payload.get('name')}: {payload.get('verdict')}"
    if kind == "prereg":
        return f"doc {str(payload.get('doc_sha256'))[:12]}…"
    return json.dumps({k: v for k, v in payload.items() if k != "agent"})[:80]


def cmd_backtest(args) -> int:
    from qr.research import crosscheck
    from qr.research.runner import leakage_probe, run_backtest
    from qr.strategies import library

    lake = _lake(args)
    panel = lake.load_panel(interval=args.interval, start=args.start, end=args.end)
    spec = UniverseSpec(n=args.n, lookback=args.lookback, min_history=args.min_history)
    universe = membership(panel, spec)
    strategy = getattr(library, FAMILIES[args.family])(**_parse_params(args.param))
    costs = _costs(args)

    result = run_backtest(panel, strategy, costs, universe, charge_impact=args.impact)
    stats = result.stats()
    print(f"# {strategy.name}\n")
    print(table(pd.DataFrame([{"metric": k, "value": v} for k, v in stats.items()])))

    if args.crosscheck:
        comparison = crosscheck.compare(panel, result, costs)
        print(f"\nsecond engine agrees: {comparison.agrees} (max relative error {comparison.max_relative_error:.2e})")
    if args.leakage:
        print("\n## gate 1 leakage probe\n")
        probe = leakage_probe(panel, strategy, costs, universe)
        print(table(probe.reset_index()))
        print(f"\nlag-0 / lag-1 gross Sharpe ratio: {probe.attrs['leak_ratio']:.2f} (near 1 is clean)")

    if args.log:
        TrialLog(paths(args.root).trial_log).run(
            hypothesis_id=args.hypothesis or strategy.family,
            family=strategy.family,
            params=strategy.params,
            universe=spec.name,
            metrics={k: v for k, v in stats.items() if k in {"sharpe", "gross_sharpe", "max_drawdown", "net_over_gross"}},
            manifest_hash=lake.manifest_hash(),
            costs=costs.describe(),
        )
        print("\nrecorded in the trial log")
    return 0


def _costs(args) -> CostModel:
    """The trial's verified model unless the tier or the BNB switch is overridden."""
    if args.tier.upper() == TRIAL_FEE_TIER and args.bnb == TRIAL_BNB_DISCOUNT:
        return CostModel.trial(half_spread_bps=args.spread)
    return CostModel.binance_spot(tier=args.tier, bnb_discount=args.bnb, half_spread_bps=args.spread)


def _parse_params(pairs: list[str] | None) -> dict:
    out: dict[str, object] = {}
    for item in pairs or []:
        key, _, value = item.partition("=")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


# --------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qr", description=__doc__.split("\n")[0])
    parser.add_argument("--root", help="lake root (default: $QR_ROOT or <repo>/lake)")
    parser.add_argument("--mirror", help="Binance bucket mirror (default: $QR_BINANCE_MIRROR)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_universe_args(p):
        p.add_argument("--n", type=int, default=30)
        p.add_argument("--lookback", type=int, default=30)
        p.add_argument("--min-history", type=int, default=180, dest="min_history")

    data = sub.add_parser("data", help="ingest and inspect market data").add_subparsers(
        dest="subcommand", required=True
    )

    pull = data.add_parser("pull", help="download bucket files into the local mirror (needs network)")
    pull.add_argument("--symbols", nargs="*")
    pull.add_argument("--interval", default="1d")
    pull.add_argument("--market", default="spot")
    pull.add_argument("--top", type=int, help="only the first N symbols of the listing")
    pull.add_argument("--since", help="skip periods before YYYY-MM")
    pull.add_argument("--force", action="store_true")
    pull.set_defaults(func=cmd_data_pull)

    ingest = data.add_parser("ingest", help="mirror -> Parquet lake")
    ingest.add_argument("--symbols", nargs="*")
    ingest.add_argument("--interval", default="1d")
    ingest.add_argument("--market", default="spot")
    ingest.add_argument("--start")
    ingest.add_argument("--end")
    ingest.add_argument("--no-verify", action="store_true", dest="no_verify")
    ingest.set_defaults(func=cmd_data_ingest)

    qa = data.add_parser("qa", help="QA report over the lake")
    qa.add_argument("--symbols", nargs="*")
    qa.add_argument("--interval", default="1d")
    qa.add_argument("--out")
    qa.set_defaults(func=cmd_data_qa)

    uni = data.add_parser("universe", help="the point-in-time universe")
    uni.add_argument("--interval", default="1d")
    uni.add_argument("--start")
    uni.add_argument("--end")
    add_universe_args(uni)
    uni.set_defaults(func=cmd_data_universe)

    fng = sub.add_parser("fng", help="Fear & Greed index").add_subparsers(dest="subcommand", required=True)
    fng_pull = fng.add_parser("pull", help="download the whole history (needs network)")
    fng_pull.add_argument("--out")
    fng_pull.set_defaults(func=cmd_fng_pull)
    fng_show = fng.add_parser("show", help="show the cached history")
    fng_show.add_argument("--path")
    fng_show.add_argument("--tail", type=int, default=10)
    fng_show.set_defaults(func=cmd_fng_show)

    trial = sub.add_parser("trial", help="the trial log").add_subparsers(dest="subcommand", required=True)
    verify = trial.add_parser("verify", help="check the hash chain")
    verify.set_defaults(func=cmd_trial_verify)
    show = trial.add_parser("show", help="recent records")
    show.add_argument("--kind", choices=["prereg", "run", "gate", "holdout", "note"])
    show.add_argument("--hypothesis")
    show.add_argument("--tail", type=int, default=20)
    show.set_defaults(func=cmd_trial_show)

    doctor = sub.add_parser("doctor", help="paths, versions and the manifest hash")
    doctor.set_defaults(func=cmd_doctor)

    bt = sub.add_parser("backtest", help="run one strategy over the lake")
    bt.add_argument("--family", choices=sorted(FAMILIES), default="tsmom")
    bt.add_argument("--param", action="append", help="name=value, repeatable (JSON values)")
    bt.add_argument("--interval", default="1d")
    bt.add_argument("--start")
    bt.add_argument("--end")
    add_universe_args(bt)
    bt.add_argument("--tier", default=TRIAL_FEE_TIER, help="Binance spot VIP tier")
    bt.add_argument(
        "--bnb",
        action=argparse.BooleanOptionalAction,
        default=TRIAL_BNB_DISCOUNT,
        help="fees paid in BNB (-25%%); on by default, matching the account",
    )
    bt.add_argument("--spread", type=float, default=2.0, help="half-spread in bps per side")
    bt.add_argument("--impact", action="store_true", help="charge square-root impact too")
    bt.add_argument("--crosscheck", action="store_true", help="verify against the share-ledger engine")
    bt.add_argument("--leakage", action="store_true", help="run the gate-1 lag probe")
    bt.add_argument("--log", action="store_true", help="record the run in the trial log")
    bt.add_argument("--hypothesis", help="hypothesis id for the trial log")
    bt.set_defaults(func=cmd_backtest)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
