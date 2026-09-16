"""`qr` — the platform's command line.

    qr doctor                     what is reachable and where things live
    qr data pull   --symbols ...  fill the local Binance mirror (needs network)
    qr data ingest                mirror -> Parquet lake + manifest
    qr data etf-pull              fill the Tiingo mirror (ETF trial; needs network)
    qr data etf-ingest            Tiingo mirror -> lake, dividend-adjusted
    qr data funding-pull          perp funding + open interest (needs network)
    qr data funding-ingest        funding mirror -> lake, as daily features
    qr data riskfree-pull         FRED DTB3 -> lake, the cash benchmark's rate (needs network)
    qr data qa                    QA report over the lake
    qr data universe              the point-in-time top-N, as of today
    qr fng pull | fng show        Fear & Greed index
    qr trial verify | trial show  the hash-chained trial log
    qr forward observe | status   the live paper record gate 10 reads
    qr backtest --family ...      one strategy, honestly costed
    qr account-size               every family at $1k/$10k/$100k (a sensitivity)
    qr sandbox declare|show       the discovery slice, where looking is free
    qr policy declare|show        the budget an unattended run may not exceed
    qr autopilot                  the overnight loop: memo -> kill test -> gates
    qr site                       every gate report as one readable page

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
from qr.execution.costs import (
    ETF_TRIAL_EQUITY,
    LONG_SHORT_TRIAL_EQUITY,
    TRIAL_BNB_DISCOUNT,
    TRIAL_FEE_TIER,
    CostModel,
)
from qr.report import table
from qr.validate.trial_log import TrialLog, TrialLogCorrupt

FAMILIES = {
    "buy_and_hold": "BuyAndHold",
    "tsmom": "TSMOM",
    "xsmom": "CrossSectionalMomentum",
    "reversal": "ShortTermReversal",
    "rsi_reversal": "RSIReversal",
    "random_entry": "RandomEntry",
    "funding_carry": "FundingCarry",
    "auction_fade": "AuctionFade",
    "late_day_momentum": "LateDayMomentum",
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


ASSET_PARTITION = {
    "crypto": ("binance", "spot"),
    "etf": ("tiingo", "etf"),
    # Same bars as `etf`; a different trial over them, with a short book, a
    # borrow fee and an account large enough to be allowed one.
    "etf-ls": ("tiingo", "etf"),
}


def _partition(args) -> tuple[str, str]:
    """Which corner of the lake a command reads.

    The lake is partitioned by source and market, so the crypto klines and the
    dividend-adjusted ETF bars sit side by side under one root and one manifest.
    A command that forgets to say which it wants silently gets the Binance
    default — which is how an ETF run came to search 734 crypto pairs for SPY.
    """
    return ASSET_PARTITION[getattr(args, "asset", "crypto") or "crypto"]


def _load_panel(lake: Lake, interval: str, start=None, end=None, source="binance", market="spot"):
    """Load a panel, or explain *why* there is nothing to load.

    Pointing `QR_ROOT` at a directory that is not the lake cost this project
    three runs, twice because the traceback came from three frames inside
    `load_panel` and said "no symbols match that query" — which sounds like a
    filter problem and is not one. An empty manifest is never a legitimate
    state for a command that is about to backtest something, so it is worth one
    cheap check and a message that names the root it actually looked in.
    """
    if not lake.symbols(interval, source, market):
        env = os.environ.get("QR_ROOT")
        where = f"QR_ROOT={env}" if env else "QR_ROOT is unset, so this is the <repo>/lake default"
        build = "qr data etf-ingest" if market == "etf" else "qr data ingest"
        print(
            f"the lake at {lake.paths.root} holds no {interval} {source}/{market} klines "
            f"({where}).\n"
            f"Either point QR_ROOT at the root that has one, or build this one with "
            f"`{build}`.\n"
            "`qr doctor` prints the root every command will use.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return lake.load_panel(interval=interval, start=start, end=end, source=source, market=market)


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
        # Under the market it came from. The first perp ingest (2026-09-15)
        # omitted this and wrote 864 perpetual series over the spot market,
        # replacing 471 spot histories and the instruments table; the mirror
        # was untouched, so a full spot re-ingest restored them.
        lake.write_klines(symbol, frame, args.interval, market=args.market)
        written.append({"symbol": symbol, "bars": len(frame), "start": frame.index[0], "end": frame.index[-1]})
    if written:
        reference = "instruments" if args.market == "spot" else f"instruments_{args.market.replace('/', '_')}"
        lake.write_reference(reference, bucket.instruments(symbols, args.interval))
    print(table(pd.DataFrame(written)))
    print(f"manifest hash: {lake.manifest_hash()}")
    return 0 if written else 1


def _launchd_plist(out: Path) -> str:
    """A macOS agent that runs every half hour and catches up after sleep.

    `cron` is the wrong tool here and the reason is specific: it fires at a
    wall-clock time and does not run a slot the machine slept through. A daily
    cron entry on a laptop that is shut at 22:00 records nothing, ever, and a
    missed day is gone — nobody publishes a past day's share count.

    `StartInterval` runs at the next wake instead, so a closed lid delays a
    reading rather than losing it. The collector skips days it already has, so
    running every half hour costs a file read and takes the first chance it
    gets.
    """
    import shutil
    import sys as _sys

    executable = shutil.which("qr") or f"{Path(_sys.executable).parent}/qr"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.qr.flows</string>
  <key>ProgramArguments</key>
  <array>
    <string>{executable}</string>
    <string>data</string>
    <string>flows-collect</string>
  </array>
  <key>WorkingDirectory</key><string>{Path.cwd()}</string>
  <key>EnvironmentVariables</key>
  <dict><key>QR_ROOT</key><string>{out.parent.parent}</string></dict>
  <key>StartInterval</key><integer>1800</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{Path.home()}/flows.log</string>
  <key>StandardErrorPath</key><string>{Path.home()}/flows.log</string>
</dict>
</plist>"""


def cmd_data_flows_collect(args) -> int:
    """Record today's ETF share counts. Laptop or server; needs network.

    Built to be a cron job. It appends one line per fund per run and never
    rewrites a previous line, so the file's value grows with nothing but
    patience — and unlike anything downloadable, it is point-in-time by
    construction.

    The URL and field names in `qr/data/etf_flows.py` have never been checked
    against the live site, because the environment they were written in has no
    egress to issuer pages. This command is that verification, and `--dump`
    keeps the payload so a wrong guess costs one run rather than two.
    """
    from qr.data import etf_flows

    out = Path(args.out) if args.out else paths(args.root).flows
    dump = Path(args.dump) if args.dump else None

    if args.print_launchd:
        print(_launchd_plist(out))
        return 0

    # Checked before the request, not after: a scheduler that fires hourly
    # should cost one file read on the twenty-three attempts that do nothing,
    # not twenty-three fetches of a page that has not changed.
    if not args.dry_run and not args.force and etf_flows.already_recorded_today(out):
        print(f"already recorded today in {out}; nothing to do (--force to add another reading)")
        return 0

    try:
        payload = etf_flows.fetch(args.url or etf_flows.ISHARES_SCREENER, dump=dump)
    except Exception as exc:
        print(f"could not fetch {args.url}\n  {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    try:
        counts = etf_flows.parse_ishares(payload)
    except etf_flows.FlowSourceError as exc:
        print(
            f"the response parsed as JSON but not as funds:\n  {exc}\n"
            + (f"The raw payload is at {dump}." if dump else
               "Re-run with --dump lake/flows/raw.json to keep the payload."),
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        # Printed raw rather than through `table()`, whose 4-significant-figure
        # formatting is precisely what would hide the question this run exists
        # to answer: whether the source publishes enough digits for a daily
        # flow to be visible at all.
        print(f"{'ticker':<8}{'shares_outstanding':>22}{'total_net_assets':>22}"
              f"{'nav':>12}  basis")
        for count in counts:
            shares = "" if count.shares_outstanding is None else f"{count.shares_outstanding:,.2f}"
            assets = "" if count.total_net_assets is None else f"{count.total_net_assets:,.2f}"
            nav = "" if count.nav is None else f"{count.nav:,.4f}"
            print(f"{count.ticker:<8}{shares:>22}{assets:>22}{nav:>12}  {count.shares_basis}")

        step = etf_flows.share_quantum(counts)
        if step:
            smallest = min(c.shares_outstanding for c in counts if c.shares_outstanding)
            print(
                f"\nShare counts move in steps of {step:,.0f} — {step / smallest:.3%} of the "
                f"smallest fund here. That is the finest flow this source can report."
            )
        warning = etf_flows.precision_warning(counts)
        if warning:
            print(f"\n{warning}")
        print("\n--dry-run: nothing was written")
        return 0

    warning = etf_flows.precision_warning(counts)
    if warning:
        # Recorded anyway. The figures are what the issuer published, and a
        # collector that dropped them would leave no evidence of why the
        # dataset is thin — but nobody should start a cron job believing this
        # will work without having read the sentence.
        print(f"{warning}\n", file=sys.stderr)

    written = etf_flows.append(out, counts)
    frame = etf_flows.load(out)
    days = frame["observed_utc"].dt.date.nunique() if not frame.empty else 0
    print(f"recorded {written} funds to {out}")
    print(f"{len(frame)} observations over {days} day(s) so far")
    if days < 2:
        print(
            "\nOne day is not a flow. A flow is a change between two observations, so the "
            "first useful number arrives tomorrow and the first usable sample in months. "
            "Put this in cron now rather than remembering to run it."
        )
    return 0


def _add_benchmark_args(parser) -> None:
    parser.add_argument(
        "--benchmark",
        choices=("buyhold", "cash", "exposure"),
        default="buyhold",
        help="what gate 5 asks the best variant to beat: the costed equal-weight universe "
        "(long-only timing books), the risk-free rate (market-neutral and carry books), or "
        "the universe scaled to the book's own mean gross exposure with the rest in cash "
        "(long-only stock selection). Part of the pre-registration.",
    )
    parser.add_argument(
        "--risk-free",
        dest="risk_free",
        default=None,
        help="annualised decimal rate for --benchmark cash, or 'fred' for the DTB3 series "
        "pulled by `qr data riskfree-pull` (the default when it is in the lake)",
    )


def _benchmark_kwargs(args, lake) -> dict:
    """`--benchmark` and `--risk-free` into what `GateContext` takes.

    `--risk-free` is an annualised decimal ("0.04"), or "fred" to read the
    DTB3 series pulled by `qr data riskfree-pull`. With `--benchmark cash` and
    nothing given, the FRED series is used if it is in the lake; if it is not,
    that is an error rather than a silent zero, because a benchmark that was
    never chosen is not a pre-registered one.
    """
    benchmark = getattr(args, "benchmark", "buyhold") or "buyhold"
    raw = getattr(args, "risk_free", None)
    risk_free = None
    if benchmark == "cash":
        from qr.data.fred import load_risk_free

        if raw is None or str(raw).lower() == "fred":
            risk_free = load_risk_free(lake)
            if risk_free is None:
                raise SystemExit(
                    "--benchmark cash needs a risk-free rate: run `qr data riskfree-pull` "
                    "(FRED DTB3, no key) or pass --risk-free 0.04"
                )
        else:
            risk_free = float(raw)
    return {"benchmark": benchmark, "risk_free": risk_free}


def cmd_data_auction_build(args) -> int:
    """E1's panel: one overnight-return instrument per Nasdaq name, with the imbalance features."""
    from pathlib import Path

    import databento as db

    from qr.data.auction import NASDAQ31, build_auction_lake

    lake = _lake(args)
    root = Path(paths(args.root).root) / "mirror" / "databento" / "XNAS.ITCH"
    files = sorted((root / "ohlcv-1d").rglob("*.dbn.zst"))
    if not files:
        print(f"no Databento ohlcv-1d files under {root / 'ohlcv-1d'}", file=sys.stderr)
        return 2
    bars = pd.concat([db.DBNStore.from_file(f).to_df() for f in files]).sort_index()
    bars = bars[~bars.index.duplicated(keep="last") | bars["symbol"].duplicated(keep=False)]
    wanted = args.symbols or list(NASDAQ31)
    daily = {}
    for symbol in wanted:
        one = bars[bars["symbol"] == symbol][["open", "high", "low", "close", "volume"]].copy()
        if one.empty:
            print(f"  {symbol}: no daily bars", file=sys.stderr)
            continue
        one.index = pd.DatetimeIndex(one.index).tz_convert("UTC").normalize()
        one = one[~one.index.duplicated(keep="last")]
        one.index.name = "open_time"
        daily[symbol] = one
    snapshots = pd.read_parquet(Path(paths(args.root).root) / "features" / "imbalance" / "xnas_closing_snapshots.parquet")
    summary = build_auction_lake(lake, daily, snapshots)
    print(table(summary))
    print(f"\n{len(summary)} auction instruments written under market 'auction-xnas'; manifest hash: {lake.manifest_hash()}")
    return 0


def cmd_data_intraday_build(args) -> int:
    """E2's panel: the session to the decision time, then the last half hour."""
    from qr.data.intraday import build_intraday_lake

    lake = _lake(args)
    summary = build_intraday_lake(lake, args.symbols, args.decision)
    print(table(summary))
    print(f"\n{len(summary)} intraday instruments written under market 'intraday-xnas'; manifest hash: {lake.manifest_hash()}")
    return 0


def cmd_data_carry_build(args) -> int:
    """Spot + futures/um bars + funding -> the carry-unit panel (`carry-um`)."""
    from qr.data.carry import build_carry_lake

    from qr.data.funding import FundingBucket

    lake = _lake(args)
    bucket = FundingBucket(_mirror(args)) if args.interval != "1d" else None
    summary = build_carry_lake(lake, args.symbols, args.interval, funding_bucket=bucket)
    if summary.empty:
        print(
            "nothing to build: no symbol has both a spot and a futures/um kline series in the lake.\n"
            "Run `qr data ingest --market futures/um` (after `qr data pull --market futures/um`) "
            "and `qr data funding-ingest` first.",
            file=sys.stderr,
        )
        return 2
    print(table(summary))
    built = int((summary["days"] > 0).sum())
    print(f"{built} carry units written under market {'carry-um'!r}; manifest hash: {lake.manifest_hash()}")
    return 0 if built else 1


def cmd_data_riskfree_pull(args) -> int:
    """FRED DTB3 -> lake reference table. Needs the network, no key."""
    from qr.data.fred import fetch, parse_fred_csv, write_risk_free

    lake = Lake(paths(args.root))
    text = fetch(args.series)
    if args.dump:
        Path(args.dump).write_text(text, encoding="utf-8")
    rates = parse_fred_csv(text, args.series)
    path = write_risk_free(lake, rates, args.series)
    print(
        f"{args.series}: {len(rates)} observations, {rates.index[0].date()} to "
        f"{rates.index[-1].date()}, latest {rates.iloc[-1]:.4%} p.a.\nwrote {path}"
    )
    return 0


def cmd_data_funding_pull(args) -> int:
    """Download perp funding (and metrics) into the local mirror. Laptop only.

    The bucket paths and column names in `qr/data/funding.py` are written from
    Binance's published layout and have never been checked against the live
    bucket, because this repository is developed where that bucket is
    unreachable. This command is the verification: an empty listing means the
    prefix is wrong, and a parse error quotes the header that actually arrived.
    """
    from qr.data.binance import HttpBucket
    from qr.data.funding import FundingBucket, funding_key, metrics_key

    mirror = _mirror(args)
    remote = FundingBucket(HttpBucket())
    symbols = args.symbols or remote.symbols()
    if not symbols:
        print(
            "the bucket listed no symbols under data/futures/um/monthly/fundingRate/.\n"
            "Either the prefix in qr/data/funding.py is wrong or the network is not "
            "reachable; `qr doctor` shows what is.",
            file=sys.stderr,
        )
        return 2
    if args.limit:
        symbols = symbols[: args.limit]

    rows = []
    for symbol in symbols:
        periods = remote.periods(symbol)
        got = 0
        for period in periods:
            if not _period_in_window(period, args.start, args.end):
                continue
            key = funding_key(symbol, period)
            if mirror.exists(key) and not args.force:
                got += 1
                continue
            try:
                mirror.write(key, remote.source.read(key))
                got += 1
            except Exception as exc:  # one missing month must not end the pull
                print(f"  {symbol} {period}: {_root_cause(exc)}", file=sys.stderr)
        metrics = 0
        if args.metrics:
            for key in remote.source.list_keys(f"data/futures/um/daily/metrics/{symbol}/"):
                if not key.endswith(".zip") or (mirror.exists(key) and not args.force):
                    metrics += 1
                    continue
                try:
                    mirror.write(key, remote.source.read(key))
                    metrics += 1
                except Exception as exc:
                    print(f"  {symbol} metrics: {_root_cause(exc)}", file=sys.stderr)
        rows.append({"symbol": symbol, "funding_files": got, "metrics_files": metrics})
    print(table(pd.DataFrame(rows)))
    print(f"mirrored into {mirror.root}")
    return 0


def _period_in_window(period: str, start, end) -> bool:
    stamp = pd.Timestamp(period, tz="UTC")
    if start is not None and stamp < pd.Timestamp(start, tz="UTC").normalize().replace(day=1):
        return False
    if end is not None and stamp > pd.Timestamp(end, tz="UTC"):
        return False
    return True


def cmd_data_funding_ingest(args) -> int:
    """Mirror -> lake, as daily per-symbol perp features."""
    from qr.data.funding import MARKET, FundingBucket, combine

    bucket = FundingBucket(_mirror(args))
    lake = _lake(args)
    symbols = args.symbols or bucket.symbols()
    if not symbols:
        print(
            "no funding files in the mirror. Run `qr data funding-pull` on a machine with "
            "network first.",
            file=sys.stderr,
        )
        return 2

    written = []
    for symbol in symbols:
        funding = bucket.load_funding(symbol)
        if funding.empty:
            print(f"  {symbol}: no funding in the mirror", file=sys.stderr)
            continue
        metrics = bucket.load_metrics(symbol) if args.metrics else None
        frame = combine(funding, metrics)
        lake.write_klines(symbol, frame, "1d", market=MARKET)
        written.append(
            {
                "symbol": symbol,
                "days": len(frame),
                "start": frame.index[0],
                "end": frame.index[-1],
                "mean_daily_funding_bps": round(float(frame["funding_rate"].mean() * 1e4), 3),
            }
        )
    print(table(pd.DataFrame(written)))
    print(f"manifest hash: {lake.manifest_hash()}")
    if written:
        print(
            "\nThese are a feature about spot pairs, not a licence to trade the perp. "
            "No spot position collects funding — see qr/strategies/funding.py."
        )
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
    source, market = _partition(args)
    symbols = args.symbols or lake.symbols(args.interval, source, market)
    if not symbols:
        print(
            f"no {source}/{market} {args.interval} klines in the lake at {lake.paths.root}. "
            f"`qr data qa --asset etf` reads the Tiingo bars; the default reads Binance.",
            file=sys.stderr,
        )
        return 2
    calendar = "xnys" if market == "etf" else "continuous"
    reports = [
        check_klines(
            lake.read_klines(s, args.interval, source=source, market=market),
            s,
            args.interval,
            calendar=calendar,
        )
        for s in symbols
    ]
    text = report_markdown(
        reports, f"Data QA — {source}/{market} {args.interval}, {len(reports)} symbols"
    )
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
    drift = log.document_drift(getattr(args, "prereg_dir", None))
    if drift:
        print(table(pd.DataFrame(drift)))
        print(
            f"\n{len(drift)} pre-registration document(s) no longer match what was stamped. "
            "The chain is intact; the documents it points at are not, so those predictions "
            "can no longer be shown to predate their runs.",
            file=sys.stderr,
        )
        return 1
    print("pre-registration documents match their stamps")
    return 0


def cmd_forward_observe(args) -> int:
    """Record one bar of the live paper run into the same chain as everything else."""
    log = TrialLog(paths(args.root).trial_log)
    weights = json.loads(args.weights) if args.weights else None
    expected = json.loads(args.expected_weights) if args.expected_weights else None
    rec = log.forward(
        args.hypothesis,
        date=args.date,
        net_return=args.net_return,
        cost=args.cost,
        weights=weights,
        expected_weights=expected,
        expected_cost=args.expected_cost,
    )
    print(f"seq {rec.seq}: {args.hypothesis} {args.date} net {args.net_return:+.4%}")
    if expected is None:
        print(
            "no expected book supplied, so gate 10 cannot check the wiring for this bar; "
            "pass --expected-weights to make it a real check",
            file=sys.stderr,
        )
    return 0


def cmd_forward_status(args) -> int:
    """Where each incubating hypothesis stands against gate 10's requirements."""
    from qr.validate import forward as fwd
    from qr.validate.gates import GateThresholds

    log = TrialLog(paths(args.root).trial_log)
    need = GateThresholds().min_forward_observations
    ids = args.hypothesis and [args.hypothesis] or sorted(
        {r.hypothesis_id for r in log.records(kind="forward")}
    )
    if not ids:
        print("nothing is incubating")
        return 0
    rows = []
    for hid in ids:
        records = fwd.frame(log, hid)
        summary = fwd.summarise(records, args.periods_per_year)
        rows.append(
            {
                "hypothesis": hid,
                "observations": f"{summary.observations}/{need}",
                "since": summary.first or "—",
                "fwd sharpe": round(summary.net_sharpe, 3),
                "cost vs model": round(summary.cost_ratio, 2),
                "worst wiring gap": round(summary.max_weight_error, 4),
                "wiring checked": f"{summary.checked_bars}/{summary.observations}",
            }
        )
    print(table(pd.DataFrame(rows)))
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
    market = getattr(args, "market", "spot") or "spot"
    source = _source_of(market)
    panel = _load_panel(lake, args.interval, args.start, args.end, source=source, market=market)
    spec = _universe_spec(args, market)
    universe = _universe_for(panel, spec, getattr(args, "basket", None))
    if not args.no_restrict_universe:
        panel, universe = _restrict_to_universe(panel, universe)
    costs = _costs(args)
    log = TrialLog(paths(args.root).ensure().trial_log)

    cls = _family_class(args.family)
    grid = _build_grid(cls, args.grid, args.param)
    hypothesis_id = args.hypothesis or args.family

    equity = getattr(args, "equity", None)
    sweep = run_sweep(
        panel, grid, costs, universe, spec.name, trial_log=log, hypothesis_id=hypothesis_id,
        **({"equity": equity} if equity else {}),
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
        holdout_panel = _load_panel(lake, args.interval, args.holdout_start, args.holdout_end, source=source, market=market)
        holdout_universe = _universe_for(holdout_panel, spec, getattr(args, "basket", None))
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
        calendar={"auction-xnas": "xnys", "intraday-xnas": "sessions2"}.get(market, "continuous"),
        **({"equity": equity} if equity else {}),
        **_benchmark_kwargs(args, lake),
    )
    report = run_gates(
        context, upto=args.upto, stop_on_fail=not args.all_gates, progress=_progress
    )

    print(table(report.to_frame()))
    verdict, reason = headline_verdict(report, log)
    print(f"\nverdict: {verdict} — {reason}")

    md, js = write_report(report, paths(args.root).reports, log, sweep.results[best].stats())
    # The per-variant net return matrix beside the report, so a gate that
    # failed inside a library call (gate 5's SPA on the C1 v2 run,
    # 2026-09-16: "zero-size array to reduction operation maximum") can be
    # diagnosed from the run that produced it rather than from a re-run.
    returns_path = js.with_name(f"{js.stem}_variant_returns.parquet")
    sweep.returns.to_parquet(returns_path)
    print(f"\nwrote {md}\n      {js}\n      {returns_path}")
    return 0 if verdict != "FAIL" else 1


def cmd_families(args) -> int:
    """Run the four registered trial families through the gates."""
    from qr.research.families import (
        BY_ID,
        ETF_FAMILIES,
        LONG_SHORT_FAMILIES,
        TRIAL_FAMILIES,
        run_family,
        summarise,
    )
    from qr.validate.report import write_report

    long_short = args.asset == "etf-ls"
    etf = args.asset == "etf" or long_short
    source, market = _partition(args)
    lake = _lake(args)
    panel = _load_panel(lake, args.interval, args.start, args.end, source, market)
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
    if long_short:
        costs = CostModel.etf_long_short()
    elif etf:
        costs = CostModel.etf_trial()
    else:
        costs = _costs(args)
    log = TrialLog(paths(args.root).ensure().trial_log)

    holdout_panel = holdout_universe = None
    if args.holdout_start:
        holdout_panel = _load_panel(
            lake, args.interval, args.holdout_start, args.holdout_end, source, market
        )
        holdout_universe = (
            fixed_basket(holdout_panel, ETF_BASKET) if etf else membership(holdout_panel, spec)
        )
        if not args.no_restrict_universe:
            holdout_panel, holdout_universe = _restrict_to_universe(
                holdout_panel, holdout_universe, "holdout: "
            )

    if long_short:
        default_families = LONG_SHORT_FAMILIES
    elif etf:
        default_families = ETF_FAMILIES
    else:
        default_families = TRIAL_FAMILIES
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
            equity=args.equity or (LONG_SHORT_TRIAL_EQUITY if long_short else ETF_TRIAL_EQUITY if etf else None),
            calendar="xnys" if etf else "continuous",
            upto=args.upto,
            stop_on_fail=not args.all_gates,
            progress=_progress,
            **_benchmark_kwargs(args, lake),
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


def _asset_panel(args, asset: str):
    """The panel and universe one asset class runs on.

    The same three lines `cmd_families` uses, pulled out because the
    account-size sweep needs all three asset classes in one invocation and a
    second copy of the ETF basket handling is exactly where the two would
    drift apart.
    """
    from qr.data.universe import ETF_BASKET, fixed_basket

    source, market = ASSET_PARTITION[asset]
    lake = _lake(args)
    panel = _load_panel(lake, args.interval, args.start, args.end, source, market)
    if asset in ("etf", "etf-ls"):
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
                f"lake ({', '.join(missing)}); running on the rest. The pre-registered "
                f"universe is all twelve.",
                file=sys.stderr,
            )
    else:
        spec = UniverseSpec(n=args.n, lookback=args.lookback, min_history=args.min_history)
        universe = membership(panel, spec)
    if not args.no_restrict_universe:
        panel, universe = _restrict_to_universe(panel, universe, f"{asset}: ")
    return lake, panel, universe, spec.name


#: Seed briefs, **per asset class**, because a forced trader belongs to a
#: market. The first night this ran, all three crypto briefs were self-killed
#: by the memo with the same correct objection: balanced-fund rebalancing,
#: quarter-end window dressing and wash-sale tax-loss selling name payers who
#: trade equities and bonds. No 60/40 mandate rebalances into altcoins, and
#: crypto has no wash-sale rule. The briefs were wrong, not the answers — and
#: sending a mechanism to a market whose participants it does not describe
#: wastes a memo to learn something that was knowable when the list was
#: written.
CRYPTO_BRIEFS = [
    # These two were killed twice at "no transmission into the traded
    # instrument" — correctly, because they asked whether funding is a signal
    # about the spot price, which is the one sentence the bar refuses. They now
    # name the cash-and-carry arbitrageur, who must BUY spot to put the trade on
    # and SELL spot to take it off, and let the memo judge that link on the
    # merits. Naming a transmission is not asserting one; both are still to be
    # killed if it does not hold.
    "Cash-and-carry arbitrageurs hold long spot against short perpetual and collect the funding "
    "the levered longs pay. They are the mechanical link between the two books: putting the trade "
    "on means buying spot, taking it off means selling spot. When funding collapses from a high "
    "level the carry stops paying and the inventory is unwound — forced selling in the spot book "
    "by a trader whose obligation is to their own hedge, not to a view on price. Is that "
    "unwinding visible in spot, and does a position sized against it survive 7.5bps a side?",
    "The same link read the other way. Sustained high funding pays the carry trade to exist, so "
    "the arbitrageurs\' spot inventory is large and growing while it lasts — spot buying that has "
    "nothing to do with anyone\'s opinion of the asset. The pairs where the carry has paid most "
    "for longest are the ones where the most spot has been bought for a reason that is not "
    "conviction. Does a cross-sectional tilt on that carry anything in spot, and is it more than "
    "three times its round-trip cost?",
    "A leveraged position that hits its maintenance margin is closed by the exchange, not by "
    "its owner — the most literally forced trade there is, and it clusters. Is the aftermath of "
    "a liquidation cascade tradeable?",
    "Quarterly futures and options on CME and Deribit expire on the last Friday of the quarter. "
    "Hedges must be rolled or unwound on a date fixed years in advance. Does the expiry window "
    "differ from an ordinary week in spot?",
    "Token unlocks put a seller on a date chosen at fundraising, years before anyone knew what "
    "the price would be. Is the window before or after an unlock tradeable?",
    "CME bitcoin futures close for the weekend while spot does not, so hedging flow that would "
    "have gone to futures has nowhere to go until Monday. Is the weekend different, and is the "
    "Monday open different?",
    "Market makers must quote continuously and cannot choose to stand aside when inventory runs "
    "one way. Where does inventory pressure show up in a spot book that trades all night?",
]

#: The same generating question, aimed at the market that actually has these
#: payers. The ETF basket is twelve funds including SPY, TLT, LQD and HYG —
#: precisely what a 60/40 mandate holds and must rebalance.
ETF_BRIEFS = [
    "Balanced funds and target-date funds must rebalance to fixed weights at month end, selling "
    "what rose and buying what fell, in size, regardless of price. Is there a tradeable "
    "imbalance in the days into or out of that date?",
    "Quarter end carries more mandates, more reporting and more window dressing than an ordinary "
    "month end. Does the quarter-end window differ?",
    "December tax-loss selling is a deadline and the wash-sale rule makes the repurchase wait "
    "31 days, so the seller cannot simply buy back. Is the December window different from any "
    "other month?",
    "Salary, pension contributions and coupon payments arrive at the turn of the month and much "
    "of it is invested mechanically, on a schedule nobody chooses. Is the turn of the month "
    "different?",
    "Index reconstitution forces every tracking fund to buy an addition and sell a deletion on "
    "the same day, at whatever price clears. Is that visible in the funds themselves?",
    "A bond fund facing redemptions must sell to meet them, and sells what is liquid rather than "
    "what it would choose. Does redemption pressure show up in credit ETFs?",
]

BRIEFS_BY_ASSET = {"crypto": CRYPTO_BRIEFS, "etf": ETF_BRIEFS, "etf-ls": ETF_BRIEFS}


def _costs_sentence(costs: CostModel) -> str:
    """One line a memo can reason about, not the full parameter dump.

    `CostModel.describe()` returns every field, including the ones that are
    zero for this venue. A prompt is not a manifest: what a mechanism memo has
    to know is how much a round trip costs and whether a per-order floor
    punishes small orders.
    """
    d = costs.describe()
    parts = []
    if d["linear_bps_per_side"]:
        parts.append(f"{d['linear_bps_per_side']:.1f} bps per side (fee plus half-spread)")
    if d["per_share_usd"]:
        parts.append(f"${d['per_share_usd']:.4f} per share")
    if d["min_commission_usd"]:
        parts.append(
            f"a ${d['min_commission_usd']:.2f} per-order minimum, which on this account is the "
            "cost that decides whether an idea survives"
        )
    if costs.borrow_bps_per_year:
        parts.append(f"{costs.borrow_bps_per_year:.0f} bps/yr borrow on shorts")
    return f"{d['name']}: " + ", ".join(parts) + ". Impact is not charged."


def _market_description(asset: str, panel, costs: CostModel, equity: float | None) -> str:
    """What the memo generator is trading, in the words it needs to hear.

    Without this the model infers a market from the feature registry, which
    talks about perpetual funding and the crypto Fear & Greed index — so the
    first ETF night produced seven memos about crypto, each correctly killing
    an equity payer for having no route into an altcoin. The universe is listed
    by name rather than described, because twelve tickers ending in SPY and TLT
    cannot be mistaken for a Binance pair list.
    """
    symbols = list(panel.symbols)
    shown = ", ".join(symbols[:40]) + (f", … ({len(symbols)} in all)" if len(symbols) > 40 else "")
    if asset == "crypto":
        instrument = (
            "Binance **spot** pairs. Long only, no leverage, no margin, no derivatives. "
            "You cannot trade the perpetual, collect funding, or short."
        )
    elif asset == "etf-ls":
        instrument = (
            "US-listed **ETFs** through Interactive Brokers, long and short. "
            "No options, no futures, no single stocks."
        )
    else:
        instrument = (
            "US-listed **ETFs** through Interactive Brokers. Long only — the account is too "
            "small to be allowed a short book. No options, no futures, no single stocks."
        )
    account = f"${equity:,.0f}" if equity else "$1,000"
    return (
        f"**Instrument.** {instrument}\n\n"
        f"**Universe.** {shown}\n\n"
        f"**Costs.** {_costs_sentence(costs)}\n\n"
        f"**Account.** {account}. Retail, no prime broker, no securities lending revenue."
    )


def cmd_autopilot(args) -> int:
    """The overnight loop: memo, kill test, quota, pre-register, twelve gates.

    Every exit is recorded in the trial log, so the morning's question — what
    happened and why — is answered from the chain rather than from scrollback.
    """
    from qr.data.sandbox import SandboxRedeclared, require as require_sandbox
    from qr.research import mechanism
    from qr.research.autopilot import promoter, run_night
    from qr.research.policy import PolicyBreach, require as require_policy

    log = TrialLog(paths(args.root).ensure().trial_log)
    try:
        policy = require_policy(log)
    except PolicyBreach as exc:
        print(str(exc), file=sys.stderr)
        return 2

    market = "/".join(ASSET_PARTITION[args.asset])
    try:
        sandbox = require_sandbox(log, market)
    except SandboxRedeclared as exc:
        print(str(exc), file=sys.stderr)
        return 2

    briefs = list(BRIEFS_BY_ASSET[args.asset])
    if args.briefs_file:
        text = Path(args.briefs_file).expanduser().read_text(encoding="utf-8")
        briefs = [b.strip() for b in text.split("\n\n") if b.strip()]
    if args.brief:
        briefs = list(args.brief)
    if args.limit:
        briefs = briefs[: args.limit]

    lake, panel, universe, _ = _asset_panel(args, args.asset)
    long_short = args.asset == "etf-ls"
    etf = args.asset.startswith("etf")
    costs = (
        CostModel.etf_long_short() if long_short
        else CostModel.etf_trial() if etf
        else CostModel.trial()
    )
    # The account the kill test prices orders against. Without this the ETF
    # side ran the per-order-floor question at `run_backtest`'s $10,000 default
    # while the trial itself is priced at $1,000 — asking whether an edge
    # survives a floor, in an account ten times too large to feel it.
    equity = args.equity or (
        LONG_SHORT_TRIAL_EQUITY if long_short else ETF_TRIAL_EQUITY if etf else None
    )

    promote = None
    if not args.no_promote:
        promote = promoter(
            log,
            panel,
            sandbox,
            policy,
            costs=costs,
            universe=universe,
            reports_dir=paths(args.root).reports,
            prereg_dir=Path("docs/prereg"),
            manifest_hash=lake.manifest_hash(),
            equity=equity,
            permutations=args.permutations,
            progress=_progress,
        )

    night = run_night(
        briefs,
        log,
        policy,
        sandbox,
        panel,
        costs=costs,
        universe=universe,
        equity=equity,
        market=_market_description(args.asset, panel, costs, equity),
        asset=args.asset,
        propose=(lambda brief, **kw: mechanism.propose(brief, model=args.model, **kw)),
        promote=promote,
        progress=_progress,
    )

    print("\n# The night\n")
    print(table(night.frame()))
    if night.stopped_early:
        print(f"\nstopped early: {night.stopped_early}")
    promoted = night.promoted()
    print(f"\n{len(promoted)} promoted, {len(night.blocked())} blocked on data, "
          f"{len([o for o in night.outcomes if o.outcome == 'killed'])} killed at triage.")
    shopping = night.shopping_list()
    if shopping:
        print("\n## Data the night ran into\n")
        print("Counted across every candidate that named it, killed ones included — whether")
        print("an idea survives and whether its data exists are different questions.\n")
        for item, count in shopping.items():
            print(f"  {count}x  {item}")
    print("\nEvery line above is in the trial log; `qr trial show` has the detail.")
    return 0


def cmd_policy(args) -> int:
    """Declare or report the research budget an unattended run may not exceed."""
    from qr.research.policy import PolicyBreach, ResearchPolicy, budget, current, declare

    log = TrialLog(paths(args.root).ensure().trial_log)

    if args.policy_cmd == "declare":
        policy = ResearchPolicy(
            max_promotions_per_week=args.per_week,
            max_promotions_per_quarter=args.per_quarter,
            max_variants_per_family=args.max_variants,
            min_cost_multiple=args.min_cost_multiple,
            max_candidates=args.max_candidates,
            note=args.note or "",
        )
        try:
            record = declare(log, policy, force=args.force)
        except PolicyBreach as exc:
            print(str(exc), file=sys.stderr)
            return 2
        declared = current(log)
        print(table(pd.DataFrame([declared.describe()])))
        print(f"\ndeclared as record {record.seq}, counting candidates from seq {declared.counts_from}")
        print(
            "The nine families that already failed are before this point and do not count "
            "against the stopping rule; they had no mechanism, which is the diagnosis."
        )
        return 0

    # show
    if current(log) is None:
        print(
            "no research policy declared. An unattended run has no budget and no stopping rule "
            "until one exists:\n  qr policy declare",
            file=sys.stderr,
        )
        return 2
    state = budget(log)
    print(table(pd.DataFrame([state])))
    if state["stopping_rule_reached"]:
        print(
            "\nThe stopping rule has been reached. The finding is that no edge is accessible "
            "at this account size with this data. Write it up, stop, hold an index fund."
        )
    return 0


def cmd_sandbox(args) -> int:
    """Declare, show or query a market's discovery/validation boundary."""
    from qr.data.sandbox import (
        SandboxRedeclared,
        SandboxSpec,
        current,
        declare,
    )

    log = TrialLog(paths(args.root).ensure().trial_log)

    if args.sandbox_cmd == "declare":
        spec = SandboxSpec(
            market=args.market,
            mode=args.mode,
            symbol_fraction=args.symbol_fraction,
            period_end=args.period_end,
            salt=args.salt,
            note=args.note or "",
        )
        try:
            record = declare(log, spec, force=args.force)
        except SandboxRedeclared as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(table(pd.DataFrame([spec.describe()])))
        print(f"\ndeclared as record {record.seq}, fingerprint {spec.fingerprint()[:16]}…")
        if args.force:
            print(
                "this SUPERSEDED an existing boundary. The log records that it moved and when; "
                "any result that predates the move should be read knowing it."
            )
        return 0

    if args.sandbox_cmd == "show":
        rows = []
        for record in log.records(kind="sandbox"):
            spec = record.payload.get("spec", {})
            rows.append(
                {
                    "seq": record.seq,
                    "market": spec.get("market"),
                    "mode": spec.get("mode"),
                    "symbol_fraction": spec.get("symbol_fraction"),
                    "period_end": spec.get("period_end"),
                    "fingerprint": (spec.get("fingerprint") or "")[:12],
                    "superseded": bool(record.payload.get("supersedes")),
                    "declared": record.ts[:19],
                }
            )
        if not rows:
            print(
                "no sandbox declared. Nothing may be explored until one exists:\n"
                "  qr sandbox declare --market binance/spot",
                file=sys.stderr,
            )
            return 2
        print(table(pd.DataFrame(rows)))
        return 0

    # check
    spec = current(log, args.market)
    if spec is None:
        print(f"no sandbox declared for {args.market}", file=sys.stderr)
        return 2
    rows = [{"symbol": s, "side": spec.assign(s)} for s in args.symbols]
    print(table(pd.DataFrame(rows)))
    return 0


def cmd_account_size(args) -> int:
    """Step 0 of `docs/10_NEXT.md`: every family, re-scored at three account sizes.

    A sensitivity analysis on one cost parameter. It writes no `run` record, so
    the trial count gate 4 deflates against is untouched, and it produces
    readings rather than verdicts — see `qr.research.account_size`.
    """
    from qr.research.account_size import ACCOUNT_SIZES, SizeSweep, run_size_sweep
    from qr.research.families import (
        BY_ID,
        ETF_FAMILIES,
        LONG_SHORT_FAMILIES,
        TRIAL_FAMILIES,
    )

    groups = {
        "crypto": TRIAL_FAMILIES,
        "etf": ETF_FAMILIES,
        "etf-ls": LONG_SHORT_FAMILIES,
    }
    chosen = list(groups) if args.asset == "all" else [args.asset]
    only = set(args.only or [])
    if only - set(BY_ID):
        print(f"unknown hypothesis id(s): {', '.join(sorted(only - set(BY_ID)))}", file=sys.stderr)
        return 2
    sizes = tuple(args.sizes) if args.sizes else ACCOUNT_SIZES
    if len(sizes) < 2:
        print("an account-size sweep needs at least two sizes to compare", file=sys.stderr)
        return 2

    log = TrialLog(paths(args.root).ensure().trial_log)
    before = log.trial_count()
    sweep = SizeSweep(sizes=sizes)
    for asset in chosen:
        families = [f for f in groups[asset] if not only or f.hypothesis_id in only]
        if not families:
            continue
        lake, panel, universe, universe_name = _asset_panel(args, asset)
        for spec in families:
            print(f"\n### {spec.hypothesis_id} — {spec.summary}", file=sys.stderr)
            sweep.runs.extend(
                run_size_sweep(
                    spec,
                    panel,
                    universe,
                    universe_name,
                    asset,
                    trial_log=log,
                    manifest_hash=lake.manifest_hash(),
                    sizes=sizes,
                    calendar="xnys" if asset in ("etf", "etf-ls") else "continuous",
                    progress=_progress,
                )
            )

    if not sweep.runs:
        print("nothing to run", file=sys.stderr)
        return 2

    print("\n# Account-size sensitivity — not a verdict\n")
    print(table(sweep.frame()))
    print("\n## Readings\n")
    print(table(sweep.readings()))

    after = TrialLog(paths(args.root).trial_log).trial_count()
    print(
        f"\ntrial count {before} -> {after}. This sweep re-scored known families with one "
        f"cost parameter changed; it searched nothing and is charged nothing."
    )
    if after != before:
        print("the trial count moved, which it must not — the log was written to", file=sys.stderr)
        return 1
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        sweep.frame().to_csv(out, index=False)
        print(f"wrote {out}")
    return 0


def _parse_grid(pairs: list[str] | None) -> dict:
    """`--grid lookback=[30,60,90]` -> {"lookback": [30, 60, 90]}."""
    out: dict[str, object] = {}
    for item in pairs or []:
        key, _, value = item.partition("=")
        parsed = json.loads(value)
        out[key] = parsed if isinstance(parsed, list) else [parsed]
    return out


def cmd_site(args) -> int:
    """Render the reports directory and the trial log as one HTML file."""
    from qr.site import collect, write_site

    p = paths(args.root)
    runs = collect(p.reports)
    if not runs:
        print(
            f"no gate reports in {p.reports}. Run `qr families` first — the page is built "
            f"from what the runs wrote, not from the lake.",
            file=sys.stderr,
        )
        return 2
    out = Path(args.out).expanduser() if args.out else p.root / "site" / "index.html"
    written = write_site(p.reports, TrialLog(p.trial_log), out)
    print(f"wrote {written} ({len(runs)} hypotheses, {written.stat().st_size / 1024:.0f} KB)")
    print(f"open it with: open {written}" if sys.platform == "darwin" else f"open {written}")
    return 0


def cmd_backtest(args) -> int:
    from qr.research import crosscheck
    from qr.research.runner import leakage_probe, run_backtest
    from qr.strategies import library

    lake = _lake(args)
    panel = _load_panel(lake, args.interval, args.start, args.end)
    spec = UniverseSpec(n=args.n, lookback=args.lookback, min_history=args.min_history)
    universe = membership(panel, spec)
    strategy = _family_class(args.family)(**_parse_params(args.param))
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


def _family_class(name: str):
    """The strategy class behind a `FAMILIES` entry.

    Programme 1's families all live in `qr.strategies.library`; Programme 2's
    carry family lives beside the carry unit in `qr.strategies.carry`, which
    imports helpers from the library and so cannot be imported *by* it.
    """
    from qr.strategies import auction, carry, intraday, library

    cls_name = FAMILIES[name]
    for module in (library, carry, auction, intraday):
        if hasattr(module, cls_name):
            return getattr(module, cls_name)
    raise KeyError(f"no strategy class {cls_name!r} for family {name!r}")


def _costs(args) -> CostModel:
    """The trial's verified model unless the tier or the BNB switch is overridden.

    `--costs carry` prices a carry unit: the spot model plus the Binance
    perp regular-user model, both legs taker (`CostModel.carry_pair`).
    """
    if getattr(args, "costs", "spot") == "carry":
        spot = CostModel.trial(half_spread_bps=args.spread)
        return CostModel.carry_pair(spot, CostModel.binance_perp())
    if getattr(args, "costs", "spot") == "alpaca":
        return CostModel.alpaca_zero()
    if args.tier.upper() == TRIAL_FEE_TIER and args.bnb == TRIAL_BNB_DISCOUNT:
        return CostModel.trial(half_spread_bps=args.spread)
    return CostModel.binance_spot(tier=args.tier, bnb_discount=args.bnb, half_spread_bps=args.spread)


#: Named fixed baskets a run may use instead of a ranked universe.
BASKETS = {"nasdaq31": "qr.data.auction:NASDAQ31", "qqq": "qr.data.intraday:QQQ_ONLY"}


def _basket_symbols(name: str) -> tuple[str, ...]:
    module, _, attr = BASKETS[name].partition(":")
    import importlib

    return tuple(getattr(importlib.import_module(module), attr))


def _universe_for(panel, spec: UniverseSpec, basket: str | None):
    """A ranked universe, or a named fixed basket when the run asks for one."""
    from qr.data.universe import fixed_basket

    if basket:
        return fixed_basket(panel, _basket_symbols(basket))
    return membership(panel, spec)


def _source_of(market: str) -> str:
    """Which vendor a lake market comes from; Databento for the auction panel."""
    return "databento" if market in ("auction-xnas", "intraday-xnas") else "binance"


def _universe_spec(args, market: str) -> UniverseSpec:
    """The universe for the market the panel came from.

    The carry-unit panel's volatility floor reads the spot leg, and its name
    says what it is so the trial log never records a carry run under the
    spot universe's name.
    """
    extra = {"vol_lookback": args.vol_lookback} if getattr(args, "vol_lookback", None) else {}
    basket = getattr(args, "basket", None)
    if basket:
        return UniverseSpec(n=len(_basket_symbols(basket)), name=basket, min_annual_vol=0.0)
    if market == "carry-um":
        return UniverseSpec(
            n=args.n,
            lookback=args.lookback,
            min_history=args.min_history,
            vol_field="spot_close",
            name=f"carry_top{args.n}",
            **extra,
        )
    return UniverseSpec(n=args.n, lookback=args.lookback, min_history=args.min_history, **extra)


def _build_grid(cls, grid_args: list[str] | None, param_args: list[str] | None) -> list:
    """The variants a run sweeps: `--grid` axes crossed with `--param` fixed values.

    Until 2026-09-16 `--param` was silently ignored whenever `--grid` was
    present, so a pre-registered `--param rebalance=24` beside a grid ran at
    the class default (1). A fixed parameter is now a one-value axis, and a
    name given both ways is refused rather than resolved.
    """
    fixed = _parse_params(param_args)
    if not grid_args:
        return [cls(**fixed)]
    ranges = _parse_grid(grid_args)
    clash = sorted(set(ranges) & set(fixed))
    if clash:
        raise SystemExit(f"{', '.join(clash)} given both as --grid and --param; choose one")
    ranges.update({k: [v] for k, v in fixed.items()})
    return cls.grid(**ranges)


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
        p.add_argument(
            "--vol-lookback", type=int, default=None, dest="vol_lookback",
            help="bars behind the universe's volatility floor (default 90; 2160 on hourly bars)",
        )

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

    fund_pull = data.add_parser(
        "funding-pull", help="perp funding + metrics -> local mirror (needs network)"
    )
    flows = data.add_parser(
        "flows-collect",
        help="record today's ETF share counts (needs network; built for cron)",
    )
    flows.add_argument("--url", default=None, help="override the issuer endpoint")
    flows.add_argument("--out", help="where to append; defaults to the lake")
    flows.add_argument("--dump", help="save the raw response here before parsing")
    flows.add_argument("--dry-run", action="store_true", help="show what would be recorded")
    flows.add_argument(
        "--force",
        action="store_true",
        help="record even if today already has a reading",
    )
    flows.add_argument(
        "--print-launchd",
        action="store_true",
        help="print a macOS launchd agent that runs this every 30 minutes",
    )
    flows.set_defaults(func=cmd_data_flows_collect)
    fund_pull.add_argument("--symbols", nargs="*")
    fund_pull.add_argument("--limit", type=int, help="first N symbols, alphabetically")
    fund_pull.add_argument("--start")
    fund_pull.add_argument("--end")
    fund_pull.add_argument(
        "--metrics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also pull open interest (daily files; many more of them)",
    )
    fund_pull.add_argument("--force", action="store_true", help="re-download files already mirrored")
    fund_pull.set_defaults(func=cmd_data_funding_pull)

    carry = data.add_parser("carry-build", help="spot + futures/um + funding -> carry-unit panel (market carry-um)")
    carry.add_argument("--symbols", nargs="*")
    carry.add_argument("--interval", default="1d")
    carry.set_defaults(func=cmd_data_carry_build)

    auction = data.add_parser(
        "auction-build",
        help="Databento XNAS daily bars + closing-cross snapshots -> overnight-return panel (market auction-xnas)",
    )
    auction.add_argument("--symbols", nargs="*")
    auction.set_defaults(func=cmd_data_auction_build)

    intra = data.add_parser("intraday-build", help="xnas minute bars -> two bars a session, the day so far and the last half hour (market intraday-xnas)")
    intra.add_argument("--symbols", nargs="*", default=["QQQ"])
    intra.add_argument("--decision", default="15:30")
    intra.set_defaults(func=cmd_data_intraday_build)

    rf = data.add_parser("riskfree-pull", help="FRED DTB3 3-month T-bill rate -> lake (needs network, no key)")
    rf.add_argument("--series", default="DTB3")
    rf.add_argument("--dump", help="save the raw CSV here before parsing")
    rf.set_defaults(func=cmd_data_riskfree_pull)

    fund_ingest = data.add_parser("funding-ingest", help="funding mirror -> lake, as daily features")
    fund_ingest.add_argument("--symbols", nargs="*")
    fund_ingest.add_argument(
        "--metrics", action=argparse.BooleanOptionalAction, default=True,
        help="include open interest if it was pulled",
    )
    fund_ingest.set_defaults(func=cmd_data_funding_ingest)

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
    qa.add_argument(
        "--asset",
        choices=("crypto", "etf"),
        default="crypto",
        help="which corner of the lake to check: Binance klines or the Tiingo ETF bars",
    )
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
    verify = trial.add_parser(
        "verify", help="check the hash chain and that pre-registrations still match their stamps"
    )
    verify.add_argument("--prereg-dir", help="where the documents live (default docs/prereg)")
    verify.set_defaults(func=cmd_trial_verify)
    show = trial.add_parser("show", help="recent records")
    show.add_argument("--kind", choices=["prereg", "run", "gate", "holdout", "forward", "note"])
    show.add_argument("--hypothesis")
    show.add_argument("--tail", type=int, default=20)
    show.set_defaults(func=cmd_trial_show)

    fwd = sub.add_parser(
        "forward", help="the live paper record that gate 10 reads"
    ).add_subparsers(dest="subcommand", required=True)
    obs = fwd.add_parser("observe", help="record one bar of the live run")
    obs.add_argument("hypothesis")
    obs.add_argument("--date", required=True, help="the bar's date, e.g. 2026-09-13")
    obs.add_argument("--net-return", type=float, required=True, help="realised net return, e.g. 0.0031")
    obs.add_argument("--cost", type=float, default=0.0, help="realised cost as a fraction of equity")
    obs.add_argument("--expected-cost", type=float, help="what the cost model said this bar would cost")
    obs.add_argument("--weights", help='the book actually held, as JSON: \'{"SPY": 0.5}\'')
    obs.add_argument(
        "--expected-weights",
        help="what the research code says the book should have been; without it gate 10 "
        "cannot tell a decayed strategy from a mis-wired one",
    )
    obs.set_defaults(func=cmd_forward_observe)
    fstat = fwd.add_parser("status", help="how far each incubation has to run")
    fstat.add_argument("--hypothesis")
    fstat.add_argument("--periods-per-year", type=float, default=365.0)
    fstat.set_defaults(func=cmd_forward_status)

    doctor = sub.add_parser("doctor", help="paths, versions and the manifest hash")
    doctor.set_defaults(func=cmd_doctor)

    site = sub.add_parser("site", help="render every gate report as one readable page")
    site.add_argument("--out", help="where to write it (default <root>/site/index.html)")
    site.add_argument("--title", default="Trial Record")
    site.set_defaults(func=cmd_site)

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
    gt.add_argument(
        "--market",
        default="spot",
        help="which lake market the panel comes from: spot (default), or carry-um for the carry unit",
    )
    gt.add_argument("--tier", default=TRIAL_FEE_TIER)
    gt.add_argument("--bnb", action=argparse.BooleanOptionalAction, default=TRIAL_BNB_DISCOUNT)
    gt.add_argument("--spread", type=float, default=2.0)
    gt.add_argument(
        "--costs",
        choices=("spot", "carry", "alpaca"),
        default="spot",
        help="spot: the trial's Binance spot model; carry: spot plus Binance perp, both legs taker; "
        "alpaca: $0 commission, 2 bps half-spread, 1 bp slippage, whole shares",
    )
    gt.add_argument(
        "--basket",
        choices=tuple(BASKETS),
        default=None,
        help="use a named fixed basket as the universe instead of the ranked top-n",
    )
    gt.add_argument("--equity", type=float, default=None, help="account equity the book is sized and costed at (whole shares, per-order floors)")
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
    gt.add_argument("--upto", type=int, default=11, help="highest gate to run")
    gt.add_argument("--all-gates", action="store_true", dest="all_gates", help="do not stop at the first FAIL")
    _add_benchmark_args(gt)
    gt.set_defaults(func=cmd_gates)

    fam = sub.add_parser("families", help="run the four registered trial families through the gates")
    _add_benchmark_args(fam)
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
        choices=("crypto", "etf", "etf-ls"),
        default="crypto",
        help=(
            "which trial: the Binance crypto families, the long-only ETF basket, "
            "or the long-short ETF family (shorts, so it carries a borrow fee and "
            "is priced at $10,000 — a $1,000 account may not short at all)"
        ),
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
    fam.add_argument("--upto", type=int, default=11)
    fam.add_argument("--all-gates", action="store_true", dest="all_gates")
    fam.add_argument(
        "--skip-prereg-check",
        action="store_true",
        dest="skip_prereg_check",
        help="run without pre-registrations; gate 0 will fail them, which is the point",
    )
    fam.set_defaults(func=cmd_families)

    size = sub.add_parser(
        "account-size",
        help="Step 0: re-score every family at $1k/$10k/$100k (a sensitivity, not a search)",
    )
    size.add_argument(
        "--asset",
        choices=("all", "crypto", "etf", "etf-ls"),
        default="all",
        help="which trial's families to re-score (default: all nine)",
    )
    size.add_argument("--only", nargs="*", help="hypothesis ids to re-score (default: all in --asset)")
    size.add_argument(
        "--sizes",
        nargs="*",
        type=float,
        default=None,
        help="account sizes in dollars (default: 1000 10000 100000)",
    )
    size.add_argument("--interval", default="1d")
    size.add_argument("--start")
    size.add_argument("--end")
    add_universe_args(size)
    size.add_argument(
        "--no-restrict-universe",
        action="store_true",
        dest="no_restrict_universe",
        help="keep every symbol in the lake in the panel (slower)",
    )
    size.add_argument("--out", help="write the per-size table to this CSV")
    size.set_defaults(func=cmd_account_size)

    sb = sub.add_parser(
        "sandbox",
        help="the discovery sandbox: where looking is free and nothing is reportable",
    )
    sbsub = sb.add_subparsers(dest="sandbox_cmd", required=True)

    sbd = sbsub.add_parser("declare", help="draw a market's boundary. Once.")
    sbd.add_argument("--market", required=True, help="e.g. binance/spot or tiingo/etf")
    sbd.add_argument(
        "--mode",
        choices=("symbols", "period", "both"),
        default="symbols",
        help="split by symbol (734 pairs can spare a quarter), by date (twelve ETFs cannot), or both",
    )
    sbd.add_argument("--symbol-fraction", dest="symbol_fraction", type=float, default=0.25)
    sbd.add_argument("--period-end", dest="period_end", help="the sandbox gets bars up to this date")
    sbd.add_argument("--salt", default="qr-sandbox-v1", help="fixes the hash that assigns symbols")
    sbd.add_argument("--note", help="why this boundary, in one line")
    sbd.add_argument(
        "--force",
        action="store_true",
        help="supersede an existing boundary. Recorded in the log as a supersession, loudly.",
    )

    sbs = sbsub.add_parser("show", help="every boundary ever declared")

    sbc = sbsub.add_parser("check", help="which side these symbols fall on")
    sbc.add_argument("--market", required=True)
    sbc.add_argument("symbols", nargs="+")

    sb.set_defaults(func=cmd_sandbox)

    pol = sub.add_parser(
        "policy",
        help="the research budget: promotion quota, kill-test bar and stopping rule",
    )
    polsub = pol.add_subparsers(dest="policy_cmd", required=True)

    pold = polsub.add_parser("declare", help="fix the rules before any unattended run. Once.")
    pold.add_argument("--per-week", dest="per_week", type=int, default=2)
    pold.add_argument("--per-quarter", dest="per_quarter", type=int, default=5)
    pold.add_argument("--max-variants", dest="max_variants", type=int, default=250,
                      help="widest grid one family may sweep; gate 4 deflates against the real count")
    pold.add_argument("--min-cost-multiple", dest="min_cost_multiple", type=float, default=3.0,
                      help="stage 3's bar: gross effect as a multiple of round-trip costs")
    pold.add_argument("--max-candidates", dest="max_candidates", type=int, default=8,
                      help="the stopping rule: mechanisms tested before the project stops")
    pold.add_argument("--note", help="why these numbers, in one line")
    pold.add_argument("--force", action="store_true",
                      help="supersede the policy in force. Recorded in the log, loudly.")

    polsub.add_parser("show", help="what is left of the budget")

    pol.set_defaults(func=cmd_policy)

    auto = sub.add_parser(
        "autopilot",
        help="the overnight loop: memo, kill test, quota, pre-register, twelve gates",
    )
    auto.add_argument("--asset", choices=("crypto", "etf", "etf-ls"), default="crypto")
    auto.add_argument("--brief", action="append", help="one brief; repeatable, overrides the defaults")
    auto.add_argument("--briefs-file", dest="briefs_file", help="briefs separated by blank lines")
    auto.add_argument("--limit", type=int, help="consider at most this many briefs tonight")
    auto.add_argument("--model", default="claude-opus-5", help="model that writes the memos")
    auto.add_argument("--equity", type=float, default=None)
    auto.add_argument("--permutations", type=int, default=200)
    auto.add_argument(
        "--no-promote",
        action="store_true",
        dest="no_promote",
        help="stop at the sandbox: write memos and kill tests, register nothing",
    )
    auto.add_argument("--interval", default="1d")
    auto.add_argument("--start")
    auto.add_argument("--end")
    add_universe_args(auto)
    auto.add_argument("--no-restrict-universe", action="store_true", dest="no_restrict_universe")
    auto.set_defaults(func=cmd_autopilot)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
