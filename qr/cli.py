"""`qr` — the platform's command line.

    qr doctor                     what is reachable and where things live
    qr data pull   --symbols ...  fill the local Binance mirror (needs network)
    qr data ingest                mirror -> Parquet lake + manifest
    qr data etf-pull              fill the Tiingo mirror (ETF trial; needs network)
    qr data etf-ingest            Tiingo mirror -> lake, dividend-adjusted
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
import os
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
from qr.execution.costs import ETF_TRIAL_EQUITY, TRIAL_BNB_DISCOUNT, TRIAL_FEE_TIER, CostModel
from qr.report import table
from qr.validate.trial_log import TrialLog, TrialLogCorrupt

FAMILIES = {
    "buy_and_hold": "BuyAndHold",
    "tsmom": "TSMOM",
    "xsmom": "CrossSectionalMomentum",
    "reversal": "ShortTermReversal",
    "rsi_reversal": "RSIReversal",
    "random_entry": "RandomEntry",
}


def _lake(args) -> Lake:
    return Lake(paths(getattr(args, "root", None)))


def _restrict_to_universe(panel, membership_frame, label: str = ""):
    """Drop symbols the universe never admits. Identical backtests, ~4x faster.

    `load_panel` returns every symbol in the lake — 734 of them for the crypto
    trial — and every backtest then computes over 734 columns to hold at most
    thirty. The rest are masked to zero before anything is summed, so they
    contribute nothing but time, and they contribute a lot of it: gate 6 alone
    re-runs 25 variants over 100 permuted panels.

    Membership must be decided on the **full** panel first, because ranking the
    top thirty is a comparison against everything that existed on the day. Only
    once that ranking is done is it safe to drop what it never chose.

    One thing this genuinely changes, stated rather than buried: gate 1's
    shuffled-ticker placebo reassigns each bar's weights to different columns,
    so a smaller column set is a different null. The restricted one is the
    better-posed of the two — the question that placebo asks is whether the
    strategy picked the right names *among those it could have held*, and
    scattering its weights onto delisted microcaps it was never eligible to buy
    makes the null easier to beat for a reason that has nothing to do with the
    strategy. It is a change to a gate's null all the same, which is why it is
    a documented default with a way to turn it off rather than a silent
    optimisation.
    """
    ever = [s for s in panel.symbols if bool(membership_frame[s].any())]
    if not ever or len(ever) == len(panel.symbols):
        return panel, membership_frame
    print(
        f"{label}restricted panel to {len(ever)} of {len(panel.symbols)} symbols "
        f"(the rest are never in the universe)",
        file=sys.stderr,
    )
    return panel.select(ever), membership_frame[ever]


def _progress(line: str) -> None:
    """Gate-by-gate progress to stderr, flushed, so a slow gate is visible."""
    print(line, file=sys.stderr, flush=True)


def _load_panel(lake: Lake, interval: str, start=None, end=None):
    """Load a panel, or explain *why* there is nothing to load.

    Pointing `QR_ROOT` at a directory that is not the lake cost this project
    three runs, twice because the traceback came from three frames inside
    `load_panel` and said "no symbols match that query" — which sounds like a
    filter problem and is not one. An empty manifest is never a legitimate
    state for a command that is about to backtest something, so it is worth one
    cheap check and a message that names the root it actually looked in.
    """
    if not lake.symbols(interval):
        env = os.environ.get("QR_ROOT")
        where = f"QR_ROOT={env}" if env else "QR_ROOT is unset, so this is the <repo>/lake default"
        print(
            f"the lake at {lake.paths.root} holds no {interval} klines ({where}).\n"
            "Either point QR_ROOT at the root that has one, or build this one with "
            "`qr data ingest`.\n"
            "`qr doctor` prints the root every command will use.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return lake.load_panel(interval=interval, start=start, end=end)


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
    for name in ("pandas", "numpy", "pyarrow", "duckdb", "scipy", "arch", "statsmodels", "skfolio", "jsharpe"):
        rows.append({"item": name, "value": _version(name), "state": ""})
    # Reported separately: vectorbt can be installed and still refuse to import
    # (plotly >= 6 removes a trace it references), and a third engine that has
    # quietly stopped running must not read as one that was never asked for.
    from qr.research.crosscheck import vectorbt_status

    rows.append({"item": "vectorbt", "value": _version("vectorbt"), "state": vectorbt_status()[1]})
    print(table(pd.DataFrame(rows)))
    return 0


def _version(module: str) -> str:
    """Installed version, without conflating "absent" with "has no __version__"."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(module)
    except PackageNotFoundError:
        return "not installed"


def _trial_state(path: Path) -> str:
    log = TrialLog(path)
    try:
        return f"{log.verify()} records, {log.trial_count()} trials"
    except TrialLogCorrupt as exc:
        return f"CORRUPT: {exc}"


def cmd_data_pull(args) -> int:
    """Download bucket files into the local mirror. Laptop only.

    A full spot pull is tens of thousands of small files, so the bottleneck is
    round trips rather than bytes and the work runs across a thread pool. Both
    phases are parallel: enumerating each symbol's months is itself one request
    per symbol, and there are thousands of symbols.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    remote = BinanceBucket(HttpBucket(pool_size=max(8, args.workers * 2)), market=args.market)
    mirror = _mirror(args)

    symbols = args.symbols or remote.symbols(args.interval)
    if args.quote:
        # Most of the bucket is pairs quoted in BTC, ETH, BNB, EUR, TRY and a
        # dozen retired stablecoins. The trial models USDT pairs, and pulling
        # the rest multiplies a long download for data no gate will ever read.
        wanted = tuple(q.upper() for q in args.quote)
        symbols = [s for s in symbols if any(s.endswith(q) and len(s) > len(q) for q in wanted)]
    if args.limit:
        symbols = symbols[: args.limit]
    if not symbols:
        print("no symbols matched", file=sys.stderr)
        return 1

    print(f"enumerating {len(symbols)} symbols…", file=sys.stderr)
    targets: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(remote.periods, symbol, args.interval): symbol for symbol in symbols
        }
        for done in as_completed(futures):
            symbol = futures[done]
            try:
                periods = done.result()
            except Exception as exc:
                print(f"  ! {symbol}: {exc}", file=sys.stderr)
                continue
            for period in periods:
                if args.since and period < args.since:
                    continue
                key = kline_key(symbol, args.interval, period, "monthly", args.market)
                targets.append(key)
                if args.checksums:
                    targets.append(key + ".CHECKSUM")

    todo = [k for k in targets if args.force or not mirror.exists(k)]
    skipped = len(targets) - len(todo)
    print(
        f"{len(targets):,} files ({skipped:,} already mirrored, {len(todo):,} to fetch)"
        + ("  [checksums included]" if args.checksums else "  [checksums skipped]"),
        file=sys.stderr,
    )
    if args.dry_run:
        print(f"dry run: would fetch {len(todo):,} files into {mirror.root}")
        return 0

    pulled = failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(remote.source.read, key): key for key in todo}
        for i, done in enumerate(as_completed(futures), start=1):
            key = futures[done]
            try:
                mirror.write(key, done.result())
                pulled += 1
            except Exception as exc:
                # A missing .CHECKSUM is normal for some older months; a
                # missing data file is not, and is worth seeing.
                if not key.endswith(".CHECKSUM"):
                    failed += 1
                    print(f"  ! {key}: {exc}", file=sys.stderr)
            if i % 500 == 0 or i == len(todo):
                print(f"  {i:,}/{len(todo):,} ({pulled:,} written)", file=sys.stderr)

    print(f"pulled {pulled:,} files, skipped {skipped:,}, {failed:,} failed, into {mirror.root}")
    return 1 if failed else 0


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


def _root_cause(exc: BaseException) -> str:
    """The innermost exception, which is the only one that says what went wrong.

    `requests` wraps a connection failure four deep: ConnectionError over
    MaxRetryError over NewConnectionError over the socket error that actually
    happened. Only the last distinguishes "DNS does not resolve" from "the
    handshake was refused" from "the proxy dropped it" — and the outer one, the
    one that gets printed, says the same `Max retries exceeded` in all three
    cases.
    """
    seen: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in seen:
        seen.append(current)
        current = current.__cause__ or current.__context__
    inner = seen[-1]
    return f"{type(inner).__name__}: {inner}".strip()


def _tiingo_mirror(args):
    from qr.data.tiingo import LocalTiingo

    root = getattr(args, "tiingo_mirror", None)
    return LocalTiingo(Path(root).expanduser() if root else paths(args.root).root / "mirror" / "tiingo")


def cmd_etf_pull(args) -> int:
    """Fill the local Tiingo mirror. Laptop only — the sandbox cannot reach it."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from qr.data.tiingo import HttpTiingo
    from qr.data.universe import ETF_BASKET

    tickers = args.symbols or list(ETF_BASKET)
    mirror = _tiingo_mirror(args)
    try:
        client = HttpTiingo()
    except ValueError as exc:
        print(f"{exc}", file=sys.stderr)
        return 2

    def fetch(ticker: str):
        rows = client.prices(ticker, args.start, args.end)
        meta = {}
        try:
            meta = client.meta(ticker)
        except Exception as exc:  # metadata is a nicety, prices are not
            log_line = f"  {ticker}: metadata unavailable ({exc})"
            print(log_line, file=sys.stderr)
        mirror.write(ticker, rows, meta)
        return ticker, len(rows)

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch, t): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                name, count = future.result()
                rows.append({"symbol": name, "bars": count})
            except PermissionError as exc:
                # An auth failure is the same for every ticker, so printing it
                # twelve times buries the one thing worth reading.
                print(f"\n{exc}\n", file=sys.stderr)
                return 2
            except Exception as exc:
                rows.append({"symbol": ticker, "bars": 0, "error": _root_cause(exc)[:70]})
    print(table(pd.DataFrame(rows).sort_values("symbol")))
    print(f"mirrored into {mirror.root}")
    if any(r["bars"] for r in rows):
        return 0
    causes = sorted({str(r.get("error", "")) for r in rows if not r["bars"]})
    print(
        "\nnothing was mirrored. The client already retries five times with backoff, so "
        "these are failures that survived that:\n  "
        + "\n  ".join(causes)
        + "\n\nIf that names DNS or a refused connection, api.tiingo.com is not reachable "
        "from this machine (VPN, captive wifi, a corporate proxy). Confirm with:\n"
        "  curl -sS -o /dev/null -w '%{http_code}\\n' https://api.tiingo.com/api/test\n"
        f"If curl works and this does not, retry serially: qr data etf-pull --workers 1",
        file=sys.stderr,
    )
    return 1


def cmd_etf_ingest(args) -> int:
    """Tiingo mirror -> Parquet lake, adjusted for dividends and splits."""
    from qr.data.tiingo import TiingoDaily

    mirror = _tiingo_mirror(args)
    loader = TiingoDaily(mirror, adjusted=not args.unadjusted)
    lake = _lake(args)
    tickers = args.symbols or mirror.tickers()
    if not tickers:
        print(f"the Tiingo mirror at {mirror.root} is empty; run `qr data etf-pull`", file=sys.stderr)
        return 2

    written = []
    for ticker in tickers:
        frame = loader.load(ticker, args.start, args.end)
        if frame.empty:
            print(f"  {ticker}: no bars in the mirror", file=sys.stderr)
            continue
        lake.write_klines(ticker.upper(), frame, args.interval, source="tiingo", market="etf")
        written.append(
            {
                "symbol": ticker.upper(),
                "bars": len(frame),
                "start": frame.index[0].date(),
                "end": frame.index[-1].date(),
                "adjusted": frame.attrs.get("adjusted", False),
            }
        )
    # A history of one bar is not a history. Tiingo returns a single latest bar
    # when a request omits `startDate`, and an ingest that accepts it writes a
    # lake that looks complete and backtests to nothing.
    stub = [r["symbol"] for r in written if r["bars"] < 100]
    if stub:
        print(
            f"\nrefusing to write: {', '.join(stub)} have fewer than 100 bars. "
            f"That is what a Tiingo pull with no start date returns — one quote, not a "
            f"history. Re-run `qr data etf-pull` after `git pull`.",
            file=sys.stderr,
        )
        return 2
    if written:
        lake.write_reference("etf_instruments", loader.instruments(tickers), source="tiingo")
    print(table(pd.DataFrame(written)))
    unadjusted = [r["symbol"] for r in written if not r["adjusted"]]
    if unadjusted:
        print(
            f"\nWARNING: no adjusted prices for {', '.join(unadjusted)}. Returns will "
            f"understate total return by the distribution yield, which for a bond or "
            f"REIT ETF is several percent a year in one direction.",
            file=sys.stderr,
        )
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
    panel = _load_panel(_lake(args), args.interval, args.start, args.end)
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


def cmd_trial_prereg(args) -> int:
    """Stamp a pre-registration document before any run touches the data."""
    log = TrialLog(paths(args.root).ensure().trial_log)
    doc = Path(args.file).read_text(encoding="utf-8") if args.file else args.text
    if not doc or not doc.strip():
        print("a pre-registration needs a mechanism, a predicted sign and size, "
              "the universe, the horizon, the parameter ranges and the OOS period", file=sys.stderr)
        return 2
    existing = log.records(kind="run", hypothesis_id=args.hypothesis)
    if existing:
        print(
            f"{args.hypothesis!r} already has {len(existing)} run(s) in the log. Registering now "
            "does not make this a test — gate 0 will fail, and correctly so. Use a new "
            "hypothesis id for a genuinely new prediction.",
            file=sys.stderr,
        )
    record = log.prereg(args.hypothesis, doc, source=args.file or "inline")
    print(f"registered {args.hypothesis!r} at seq {record.seq}, doc sha256 {record.payload['doc_sha256'][:16]}…")
    return 0


def cmd_trial_note(args) -> int:
    """Write the justification a WARN requires."""
    log = TrialLog(paths(args.root).ensure().trial_log)
    record = log.note(args.hypothesis, args.text)
    print(f"noted at seq {record.seq}")
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


def cmd_selftest(args) -> int:
    """Point the validation engine at data whose answer is known in advance."""
    from qr.validate.selftest import run_selftest

    log = TrialLog(paths(args.root).ensure().trial_log) if args.log else None
    report = run_selftest(
        n_variants=args.variants,
        permutations=args.permutations,
        trial_log=log,
        seed=args.seed,
        stop_on_fail=not args.all_gates,
    )
    print(table(report.to_frame()))
    if report.ok:
        print("\nself-test OK: noise is rejected at the deflation gates, the planted edge survives.")
        return 0
    print("\nSELF-TEST BROKEN — the gates cannot be trusted until this passes:\n", file=sys.stderr)
    print(report.failure_summary(), file=sys.stderr)
    for case in report.cases:
        if not case.passed:
            print(f"\n--- {case.name} ---", file=sys.stderr)
            print(table(case.report.to_frame()), file=sys.stderr)
    return 2


def cmd_gates(args) -> int:
    """Run a family through the gates and write its Hypothesis Report."""
    from qr.research.sweep import run_sweep
    from qr.strategies import library
    from qr.validate.gates import GateContext, GateThresholds, run_gates
    from qr.validate.report import headline_verdict, write_report

    lake = _lake(args)
    panel = _load_panel(lake, args.interval, args.start, args.end)
    spec = UniverseSpec(n=args.n, lookback=args.lookback, min_history=args.min_history)
    universe = membership(panel, spec)
    if not args.no_restrict_universe:
        panel, universe = _restrict_to_universe(panel, universe)
    costs = _costs(args)
    log = TrialLog(paths(args.root).ensure().trial_log)

    cls = getattr(library, FAMILIES[args.family])
    grid = cls.grid(**_parse_grid(args.grid)) if args.grid else [cls(**_parse_params(args.param))]
    hypothesis_id = args.hypothesis or args.family

    sweep = run_sweep(
        panel, grid, costs, universe, spec.name, trial_log=log, hypothesis_id=hypothesis_id
    )
    log.run(
        hypothesis_id,
        family=sweep.family,
        params={"grid": f"{len(grid)} variants"},
        universe=spec.name,
        metrics={"best_sharpe": float(sweep.sharpes().max())},
        variants=len(grid),
        manifest_hash=lake.manifest_hash(),
    )

    best = sweep.best()
    holdout_panel = holdout_universe = None
    if args.holdout_start:
        holdout_panel = _load_panel(lake, args.interval, args.holdout_start, args.holdout_end)
        holdout_universe = membership(holdout_panel, spec)
        if not args.no_restrict_universe:
            holdout_panel, holdout_universe = _restrict_to_universe(
                holdout_panel, holdout_universe, "holdout: "
            )

    context = GateContext(
        hypothesis_id=hypothesis_id,
        panel=panel,
        strategy=next(s for s in grid if s.name == best),
        costs=costs,
        result=sweep.results[best],
        sweep=sweep,
        universe=universe,
        trial_log=log,
        manifest_hash=lake.manifest_hash(),
        holdout_panel=holdout_panel,
        holdout_universe=holdout_universe,
        permutations=args.permutations,
        vol_preserving_permutations=args.vol_permutations,
    )
    report = run_gates(
        context, upto=args.upto, stop_on_fail=not args.all_gates, progress=_progress
    )

    print(table(report.to_frame()))
    verdict, reason = headline_verdict(report, log)
    print(f"\nverdict: {verdict} — {reason}")

    md, js = write_report(report, paths(args.root).reports, log, sweep.results[best].stats())
    print(f"\nwrote {md}\n      {js}")
    return 0 if verdict != "FAIL" else 1


def cmd_families(args) -> int:
    """Run the four registered trial families through the gates."""
    from qr.research.families import BY_ID, ETF_FAMILIES, TRIAL_FAMILIES, run_family, summarise
    from qr.validate.report import write_report

    etf = args.asset == "etf"
    lake = _lake(args)
    panel = _load_panel(lake, args.interval, args.start, args.end)
    if etf:
        # A named basket, not a ranking: twelve funds that all still trade have
        # no membership decision to make through time. `spec.name` still travels
        # into the trial log, so a report says which universe it ran on.
        from qr.data.universe import ETF_BASKET, fixed_basket

        spec = UniverseSpec(n=len(ETF_BASKET), name="etf_basket_12")
        try:
            universe = fixed_basket(panel, ETF_BASKET)
        except ValueError as exc:
            print(f"{exc}", file=sys.stderr)
            raise SystemExit(2) from None
        missing = universe.attrs.get("missing") or []
        if missing:
            print(
                f"warning: {len(missing)} of {len(ETF_BASKET)} basket funds are not in the "
                f"lake ({', '.join(missing)}); running on the {len(ETF_BASKET) - len(missing)} "
                f"that are. The pre-registered universe is all twelve.",
                file=sys.stderr,
            )
    else:
        spec = UniverseSpec(n=args.n, lookback=args.lookback, min_history=args.min_history)
        universe = membership(panel, spec)
    if not args.no_restrict_universe:
        panel, universe = _restrict_to_universe(panel, universe)
    costs = CostModel.etf_trial() if etf else _costs(args)
    log = TrialLog(paths(args.root).ensure().trial_log)

    holdout_panel = holdout_universe = None
    if args.holdout_start:
        holdout_panel = _load_panel(lake, args.interval, args.holdout_start, args.holdout_end)
        holdout_universe = (
            fixed_basket(holdout_panel, ETF_BASKET) if etf else membership(holdout_panel, spec)
        )
        if not args.no_restrict_universe:
            holdout_panel, holdout_universe = _restrict_to_universe(
                holdout_panel, holdout_universe, "holdout: "
            )

    default_families = ETF_FAMILIES if etf else TRIAL_FAMILIES
    chosen = [BY_ID[h] for h in args.only] if args.only else default_families
    missing = [f.hypothesis_id for f in chosen if not log.records(kind="prereg", hypothesis_id=f.hypothesis_id)]
    if missing and not args.skip_prereg_check:
        print(
            "not pre-registered: " + ", ".join(missing) + "\n"
            "Register each before running, or gate 0 will fail them — which it should:\n"
            + "\n".join(f"  qr trial prereg {h} --file docs/prereg/{h}.md" for h in missing),
            file=sys.stderr,
        )
        return 2

    runs = []
    for family in chosen:
        print(f"\n### {family.hypothesis_id} — {family.summary} ({family.n_variants} variants)\n", file=sys.stderr)
        run = run_family(
            family,
            panel,
            costs,
            universe,
            spec.name,
            trial_log=log,
            manifest_hash=lake.manifest_hash(),
            holdout_panel=holdout_panel,
            holdout_universe=holdout_universe,
            permutations=args.permutations,
            vol_preserving_permutations=args.vol_permutations,
            equity=args.equity if args.equity else (ETF_TRIAL_EQUITY if etf else None),
            upto=args.upto,
            stop_on_fail=not args.all_gates,
            progress=_progress,
        )
        runs.append(run)
        md, _ = write_report(run.report, paths(args.root).reports, log, run.sweep.results[run.best_variant].stats())
        print(table(run.report.to_frame()), file=sys.stderr)
        print(f"wrote {md}", file=sys.stderr)

    print("\n# Trial summary\n")
    print(table(summarise(runs, log)))
    passed = [r for r in runs if r.row(log)["verdict"] != "FAIL" and not r.spec.control]
    control_passed = [r for r in runs if r.row(log)["verdict"] != "FAIL" and r.spec.control]
    if control_passed:
        print(
            "\nThe CONTROL passed. Check the engine before believing the strategy — "
            "see docs/prereg/rsi_reversal_v1.md."
        )
    print(f"\n{len(passed)} of {len([r for r in runs if not r.spec.control])} real families survived.")
    return 0


def _parse_grid(pairs: list[str] | None) -> dict:
    """`--grid lookback=[30,60,90]` -> {"lookback": [30, 60, 90]}."""
    out: dict[str, object] = {}
    for item in pairs or []:
        key, _, value = item.partition("=")
        parsed = json.loads(value)
        out[key] = parsed if isinstance(parsed, list) else [parsed]
    return out


def cmd_backtest(args) -> int:
    from qr.research import crosscheck
    from qr.research.runner import leakage_probe, run_backtest
    from qr.strategies import library

    lake = _lake(args)
    panel = _load_panel(lake, args.interval, args.start, args.end)
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
        print(
            f"\npeek ratio (lag 0 / lag 1): {probe.attrs['peek_ratio']:.2f} — high is normal, not a leak"
            f"\nspike ratio (lag 1 / its neighbours): {probe.attrs['spike_ratio']:.2f} — above 1.5 means"
            f" the edge exists only at the reported lag, which is either a one-bar-ahead signal or a look-ahead"
        )

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
    pull.add_argument(
        "--quote",
        nargs="*",
        default=["USDT"],
        help="only pairs quoted in these assets (default USDT); pass none for everything",
    )
    pull.add_argument(
        "--limit",
        type=int,
        help="only the first N symbols of the listing — ALPHABETICAL, not by volume, "
        "so this is for smoke-testing the pull, never for building a universe",
    )
    pull.add_argument("--since", help="skip periods before YYYY-MM")
    pull.add_argument("--workers", type=int, default=16, help="concurrent downloads")
    pull.add_argument(
        "--checksums",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also fetch the published SHA-256 files (doubles the request count)",
    )
    pull.add_argument("--dry-run", action="store_true", dest="dry_run", help="count files, fetch nothing")
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

    etf_pull = data.add_parser("etf-pull", help="fill the local Tiingo mirror (needs network + TIINGO_API_KEY)")
    etf_pull.add_argument("--symbols", nargs="*", help="default: the twelve-ETF trial basket")
    etf_pull.add_argument("--start", help="earliest date, default: each fund's inception")
    etf_pull.add_argument("--end")
    etf_pull.add_argument("--workers", type=int, default=4)
    etf_pull.add_argument("--tiingo-mirror", dest="tiingo_mirror")
    etf_pull.set_defaults(func=cmd_etf_pull)

    etf_ingest = data.add_parser("etf-ingest", help="Tiingo mirror -> Parquet lake (dividend-adjusted)")
    etf_ingest.add_argument("--symbols", nargs="*")
    etf_ingest.add_argument("--interval", default="1d")
    etf_ingest.add_argument("--start")
    etf_ingest.add_argument("--end")
    etf_ingest.add_argument("--tiingo-mirror", dest="tiingo_mirror")
    etf_ingest.add_argument(
        "--unadjusted",
        action="store_true",
        help="use traded rather than dividend-adjusted prices. Almost always wrong: a "
        "bond or REIT ETF on unadjusted prices looks like a steady loser",
    )
    etf_ingest.set_defaults(func=cmd_etf_ingest)

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
    prereg = trial.add_parser("prereg", help="stamp a pre-registration (gate 0) before running anything")
    prereg.add_argument("hypothesis")
    prereg.add_argument("--file", help="path to the pre-registration document")
    prereg.add_argument("--text", help="the document inline, instead of --file")
    prereg.set_defaults(func=cmd_trial_prereg)
    note = trial.add_parser("note", help="write the justification a WARN requires")
    note.add_argument("hypothesis")
    note.add_argument("text", help='e.g. "gate 3: short sample by design, CI still excludes zero"')
    note.set_defaults(func=cmd_trial_note)
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

    st = sub.add_parser("selftest", help="check the validation engine against known answers")
    st.add_argument("--variants", type=int, default=200, help="grid size for each world")
    st.add_argument("--permutations", type=int, default=100)
    st.add_argument("--seed", type=int, default=0)
    st.add_argument("--log", action="store_true", help="record the self-test in the trial log")
    st.add_argument("--all-gates", action="store_true", dest="all_gates", help="do not stop at the first FAIL")
    st.set_defaults(func=cmd_selftest)

    gt = sub.add_parser("gates", help="run a family through the gates and write its Hypothesis Report")
    gt.add_argument("--family", choices=sorted(FAMILIES), default="tsmom")
    gt.add_argument("--param", action="append", help="name=value for a single variant")
    gt.add_argument("--grid", action="append", help="name=[v1,v2,...] to sweep, repeatable")
    gt.add_argument("--hypothesis", help="hypothesis id (default: the family name)")
    gt.add_argument("--interval", default="1d")
    gt.add_argument("--start")
    gt.add_argument("--end")
    gt.add_argument("--holdout-start", dest="holdout_start", help="gate 9 period, opened exactly once")
    gt.add_argument("--holdout-end", dest="holdout_end")
    add_universe_args(gt)
    gt.add_argument("--tier", default=TRIAL_FEE_TIER)
    gt.add_argument("--bnb", action=argparse.BooleanOptionalAction, default=TRIAL_BNB_DISCOUNT)
    gt.add_argument("--spread", type=float, default=2.0)
    gt.add_argument("--permutations", type=int, default=200)
    gt.add_argument(
        "--vol-permutations",
        dest="vol_permutations",
        type=int,
        default=None,
        help="permutations for gate 6's volatility-preserving null (0 skips it; default: same as --permutations)",
    )
    gt.add_argument(
        "--no-restrict-universe",
        action="store_true",
        dest="no_restrict_universe",
        help="keep every symbol in the lake in the panel, not only those the universe admits (slower; changes gate 1's shuffled-ticker null)",
    )
    gt.add_argument("--upto", type=int, default=9, help="highest gate to run")
    gt.add_argument("--all-gates", action="store_true", dest="all_gates", help="do not stop at the first FAIL")
    gt.set_defaults(func=cmd_gates)

    fam = sub.add_parser("families", help="run the four registered trial families through the gates")
    fam.add_argument("--only", nargs="*", help="hypothesis ids to run (default: all four)")
    fam.add_argument("--interval", default="1d")
    fam.add_argument("--start")
    fam.add_argument("--end")
    fam.add_argument("--holdout-start", dest="holdout_start")
    fam.add_argument("--holdout-end", dest="holdout_end")
    add_universe_args(fam)
    fam.add_argument("--tier", default=TRIAL_FEE_TIER)
    fam.add_argument("--bnb", action=argparse.BooleanOptionalAction, default=TRIAL_BNB_DISCOUNT)
    fam.add_argument("--spread", type=float, default=2.0)
    fam.add_argument(
        "--asset",
        choices=("crypto", "etf"),
        default="crypto",
        help="which trial: the Binance crypto families or the Tiingo ETF basket",
    )
    fam.add_argument(
        "--equity",
        type=float,
        default=None,
        help="account size the cost model prices orders against (ETF default: $1,000, "
        "the account that exists — see CostModel.etf_trial)",
    )
    fam.add_argument("--permutations", type=int, default=200)
    fam.add_argument(
        "--vol-permutations",
        dest="vol_permutations",
        type=int,
        default=None,
        help="permutations for gate 6's volatility-preserving null (0 skips it; default: same as --permutations)",
    )
    fam.add_argument(
        "--no-restrict-universe",
        action="store_true",
        dest="no_restrict_universe",
        help="keep every symbol in the lake in the panel, not only those the universe admits (slower; changes gate 1's shuffled-ticker null)",
    )
    fam.add_argument("--upto", type=int, default=9)
    fam.add_argument("--all-gates", action="store_true", dest="all_gates")
    fam.add_argument(
        "--skip-prereg-check",
        action="store_true",
        dest="skip_prereg_check",
        help="run without pre-registrations; gate 0 will fail them, which is the point",
    )
    fam.set_defaults(func=cmd_families)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
