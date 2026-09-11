"""`centaur` command line - the daily Centaur workflow.

  centaur regime                     macro regime + confidence (Rule 3 input)
  centaur scan                       pattern matcher over the S&P 500 (+ backtest stats)
  centaur flow --tickers AAPL MSFT   unusual call-volume flags
  centaur catalyst --ticker XYZ --transcript call.txt   bullish/bearish + insider cross-ref
  centaur evening                    the AI grind: regime + scan + flow -> briefs/YYYY-MM-DD.md
  centaur morning                    print last brief; scaffold candidate files for the top hits
  centaur gauntlet cand.json         run the 5 veteran rules -> TAKE / ABORT
  centaur size --entry 150 --stop 145   position size from the 1% rule
  centaur journal open|close|list|stats|feedback
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

from .config import load_config, AccountConfig
from .data import YFinanceProvider, CSVProvider, SyntheticProvider, sp500_tickers
from .indicators import atr, swing_levels
from .screens.pattern_matcher import SetupSpec, scan_universe, pooled_stats, backtest_setup
from .screens.regime import assess_regime, fetch_regime_inputs, RegimeAssessment, Regime
from .screens.options_flow import ChainHistoryFlowProvider, UnusualWhalesFlowProvider, scan_flow
from .screens.catalyst import summarize_transcript, summarize_insider_activity, cross_reference, CatalystSummary
from .rules.candidate import TradeCandidate
from .rules.rulebook import run_gauntlet
from .sizing import position_size
from .journal import Journal
from .brief import EveningBrief, candidate_template


# --------------------------------------------------------------------------- #
def _provider(args, cfg: AccountConfig):
    if getattr(args, "csv_dir", None):
        return CSVProvider(args.csv_dir)
    if getattr(args, "synthetic", False):
        return SyntheticProvider()
    return YFinanceProvider(cache_dir=cfg.cache_dir)


def _tickers(args) -> list[str]:
    if getattr(args, "tickers", None):
        return [t.upper() for t in args.tickers]
    if getattr(args, "universe_file", None):
        return sp500_tickers(args.universe_file)
    return sp500_tickers()


def _spec(args) -> SetupSpec:
    return SetupSpec(down_days=args.down_days, volume_multiple=args.volume_multiple,
                     rsi_max=args.rsi_max, horizon=args.horizon)


def _load_regime(path: str | None, provider=None) -> RegimeAssessment | None:
    if path:
        with open(path) as fh:
            d = json.load(fh)
        from .screens.regime import Component
        return RegimeAssessment(
            regime=Regime(d["regime"]), composite=d["composite"], confidence=d["confidence"],
            components=[Component(**c) for c in d.get("components", [])], as_of=d.get("as_of", ""),
            warnings=d.get("warnings", []),
        )
    if provider is not None:
        return assess_regime(fetch_regime_inputs(provider))
    return None


def _latest_brief_json(cfg: AccountConfig) -> Path | None:
    d = Path(cfg.briefs_dir)
    files = sorted(d.glob("*.json")) if d.is_dir() else []
    return files[-1] if files else None


# --------------------------------------------------------------------------- #
def cmd_regime(args, cfg):
    provider = _provider(args, cfg)
    assessment = assess_regime(fetch_regime_inputs(provider, sp500_earnings_yield=args.earnings_yield))
    if args.json:
        print(json.dumps(assessment.to_dict(), indent=2))
    else:
        print(assessment.summary())
    if args.save:
        Path(args.save).write_text(json.dumps(assessment.to_dict(), indent=2))
    return 0


def cmd_scan(args, cfg):
    provider = _provider(args, cfg)
    tickers = _tickers(args)
    spec = _spec(args)
    logging.info("downloading %d tickers (%d years)...", len(tickers), args.years)
    hist = provider.histories(tickers, years=args.years)
    hits = scan_universe(hist, spec, min_avg_dollar_volume=cfg.min_avg_dollar_volume if not args.all else 0.0)
    pooled = pooled_stats(hist, spec)
    if args.json:
        print(json.dumps({"setup": spec.describe(), "pooled": pooled.to_dict(),
                          "hits": [h.to_dict() for h in hits[: args.top]]}, indent=2))
        return 0
    print(f"Setup: {spec.describe()}")
    print(f"Universe: {len(hist)} tickers.  Pooled history: {pooled.summary()}")
    print(f"Firing today: {len(hits)}" + (f" (showing top {args.top})" if len(hits) > args.top else ""))
    for h in hits[: args.top]:
        print(f"  {h.ticker:<6} close {h.close:>9.2f}  RSI {h.rsi:>4.0f}  streak {h.consecutive_down}  rvol {h.relative_volume:.1f}x  "
              f"move {h.drawdown_pct:+.1%}  ADV ${h.avg_dollar_volume/1e6:,.0f}M  | {h.stats.summary()}")
    return 0


def cmd_backtest(args, cfg):
    provider = _provider(args, cfg)
    spec = _spec(args)
    for t in _tickers(args):
        df = provider.history(t, years=args.years)
        print(f"{t}: {backtest_setup(df, spec).summary()}")
    return 0


def cmd_flow(args, cfg):
    tickers = _tickers(args)
    if args.provider == "unusualwhales":
        flow = UnusualWhalesFlowProvider()
    else:
        flow = ChainHistoryFlowProvider(_provider(args, cfg), history_path=Path(cfg.cache_dir) / "option_volume_history.json")
    flags = scan_flow(flow, tickers, threshold=args.threshold, max_dte=args.max_dte)
    if args.json:
        print(json.dumps([f.to_dict() for f in flags], indent=2))
        return 0
    if not flags:
        print("No unusual call flow flagged." + ("" if args.provider == "unusualwhales" else
              " (Free provider needs ~30 daily runs to build a baseline; check baseline_days.)"))
    for f in flags:
        print(f"  {f.ticker:<6} {f.expiration} {f.strike:>8g}C  vol {f.volume:>8,.0f}  avg {f.avg_volume_30d:>8,.0f}  "
              f"{f.ratio:>5.1f}x  {f.days_to_expiry:>2}d  {f.note}")
    return 0


def cmd_catalyst(args, cfg):
    provider = _provider(args, cfg)
    summary: CatalystSummary | None = None
    if args.transcript:
        text = Path(args.transcript).read_text()
        summary = summarize_transcript(args.ticker.upper(), text, model=args.model)
        print(summary.markdown())
        print()
    insiders = summarize_insider_activity(args.ticker.upper(), provider.insider_transactions(args.ticker.upper()), days=args.days)
    print("Insider activity:", insiders.summary())
    for t in insiders.transactions[:10]:
        print(f"  {t['date']}  {t['kind']:<4} {t['insider']} ({t['position']}) {t['shares']:,.0f} sh  ${t['value']:,.0f}")
    xref = cross_reference(summary, insiders)
    print(f"\nCross-reference: {xref['verdict']} - {xref['note']}")
    for s in xref["signals"]:
        print(f"  signal -> {s}")
    if args.save:
        Path(args.save).write_text(json.dumps({"summary": summary.to_dict() if summary else None,
                                               "insiders": insiders.to_dict(), "cross_reference": xref}, indent=2))
    return 0


def cmd_evening(args, cfg):
    provider = _provider(args, cfg)
    tickers = _tickers(args)
    spec = _spec(args)
    today = str(dt.date.today())
    notes: list[str] = []

    logging.info("regime check...")
    regime = assess_regime(fetch_regime_inputs(provider, sp500_earnings_yield=args.earnings_yield))

    logging.info("scanning %d tickers...", len(tickers))
    hist = provider.histories(tickers, years=args.years)
    hits = scan_universe(hist, spec, min_avg_dollar_volume=cfg.min_avg_dollar_volume)
    pooled = pooled_stats(hist, spec)

    flow = []
    if not args.skip_flow and hits:
        try:
            fp = ChainHistoryFlowProvider(provider, history_path=Path(cfg.cache_dir) / "option_volume_history.json")
            flow = scan_flow(fp, [h.ticker for h in hits[: args.top]], threshold=3.0, max_dte=14)
        except Exception as exc:  # flow is a bonus, never block the brief
            notes.append(f"options flow unavailable: {exc}")

    feedback = Journal(cfg.journal_path).feedback_markdown() if Path(cfg.journal_path).is_file() else ""
    brief = EveningBrief(date=today, regime=regime, spec=spec, hits=hits, pooled=pooled, flow=flow,
                         universe_size=len(hist), journal_feedback=feedback, notes=notes)
    md, js = brief.save(cfg.briefs_dir)

    # scaffold candidate files for the morning review
    cand_dir = Path(cfg.briefs_dir) / today / "candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)
    for h in brief.top(args.top):
        df = hist[h.ticker]
        res, _ = swing_levels(df)
        a = float(atr(df).iloc[-1])
        tmpl = candidate_template(h, cfg, resistance=res, next_earnings=provider.next_earnings_date(h.ticker), atr_value=a)
        tmpl.save(cand_dir / f"{h.ticker}.json")

    print(brief.markdown(top_n=args.top))
    print(f"\nSaved brief -> {md}\nCandidate templates -> {cand_dir}/")
    return 0


def cmd_morning(args, cfg):
    js = _latest_brief_json(cfg)
    if js is None:
        print("No evening brief found. Run `centaur evening` first.")
        return 1
    md = js.with_suffix(".md")
    print(md.read_text() if md.is_file() else js.read_text())
    cand_dir = js.parent / js.stem / "candidates"
    if cand_dir.is_dir():
        print("\nCandidate files to review (edit stop/target/catalyst/signals, then `centaur gauntlet <file>`):")
        for p in sorted(cand_dir.glob("*.json")):
            print(f"  {p}")
    return 0


def cmd_gauntlet(args, cfg):
    cand = TradeCandidate.load(args.candidate)
    regime = _load_regime(args.regime)
    if regime is None:
        js = _latest_brief_json(cfg)
        if js is not None:
            regime = _load_regime_from_brief(js)
    if regime is None and not args.offline:
        regime = _load_regime(None, _provider(args, cfg))
    report = run_gauntlet(cand, cfg, regime)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(report.render())
    if args.save:
        Path(args.save).write_text(json.dumps(report.to_dict(), indent=2, default=str))
    return 0 if report.passed else 2


def _load_regime_from_brief(js: Path) -> RegimeAssessment | None:
    from .screens.regime import Component
    try:
        d = json.loads(js.read_text())["regime"]
        return RegimeAssessment(Regime(d["regime"]), d["composite"], d["confidence"],
                                [Component(**c) for c in d.get("components", [])], d.get("as_of", ""), d.get("warnings", []))
    except Exception:
        return None


def cmd_size(args, cfg):
    ps = position_size(cfg.equity, cfg.risk_pct, args.entry, args.stop)
    print(ps.summary())
    if args.target:
        rr = abs(args.target - args.entry) / ps.risk_per_share
        print(f"reward:risk 1:{rr:.2f}" + ("" if rr >= cfg.min_reward_risk else f"  <-- below 1:{cfg.min_reward_risk:g}, invalid"))
    return 0


def cmd_journal(args, cfg):
    j = Journal(cfg.journal_path)
    if args.jcmd == "open":
        gauntlet = None
        if args.gauntlet:
            gauntlet = json.loads(Path(args.gauntlet).read_text())
        e = j.open(args.ticker, args.direction, args.entry, args.stop, args.target, args.shares,
                   ai_thesis=args.ai_thesis, why_taken=args.why, signals=args.signals or [],
                   gauntlet=gauntlet, regime=args.regime or "")
        print(f"opened {e.id}: {e.ticker} {e.direction} {e.shares} @ {e.entry} stop {e.stop} target {e.target}")
    elif args.jcmd == "close":
        e = j.close(args.id, args.exit_price, args.reason, lessons=args.lessons)
        print(f"closed {e.id}: {e.ticker} exit {e.exit_price} ({e.exit_reason})  pnl ${e.pnl:,.2f}  {e.r_multiple:+.2f}R")
    elif args.jcmd == "list":
        for e in j.entries():
            state = "OPEN " if e.is_open else f"{e.r_multiple:+.2f}R"
            print(f"{e.id}  {e.opened}  {e.ticker:<6} {e.direction:<5} {e.shares:>5} @ {e.entry:<8.2f} stop {e.stop:<8.2f} tgt {e.target:<8.2f} {state}")
    elif args.jcmd == "stats":
        print(json.dumps(j.stats(), indent=2))
    elif args.jcmd == "feedback":
        print(j.feedback_markdown(args.last))
    return 0


# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="centaur", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="path to centaur.json")
    p.add_argument("--equity", type=float, help="account equity (overrides config)")
    p.add_argument("--risk-pct", type=float, help="risk per trade as a fraction, e.g. 0.01")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def data_opts(sp):
        sp.add_argument("--csv-dir", help="offline data directory of <TICKER>.csv files")
        sp.add_argument("--synthetic", action="store_true", help="deterministic fake data (dry run)")

    def universe_opts(sp):
        sp.add_argument("--tickers", nargs="+", help="explicit tickers (default: bundled S&P 500 list)")
        sp.add_argument("--universe-file", help="csv/txt of tickers, one per line")

    def setup_opts(sp):
        sp.add_argument("--years", type=int, default=10)
        sp.add_argument("--down-days", type=int, default=3)
        sp.add_argument("--volume-multiple", type=float, default=1.0)
        sp.add_argument("--rsi-max", type=float, default=30.0)
        sp.add_argument("--horizon", type=int, default=5)
        sp.add_argument("--top", type=int, default=5)

    sp = sub.add_parser("regime", help="macro regime: risk-on / risk-off + confidence")
    data_opts(sp)
    sp.add_argument("--earnings-yield", type=float, help="S&P 500 earnings yield, e.g. 0.045")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--save", help="write assessment json here")
    sp.set_defaults(func=cmd_regime)

    sp = sub.add_parser("scan", help="pattern matcher over a universe + historical forward returns")
    data_opts(sp); universe_opts(sp); setup_opts(sp)
    sp.add_argument("--all", action="store_true", help="ignore the liquidity floor")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("backtest", help="historical stats of the setup for specific tickers")
    data_opts(sp); universe_opts(sp); setup_opts(sp)
    sp.set_defaults(func=cmd_backtest)

    sp = sub.add_parser("flow", help="unusual call option volume")
    data_opts(sp); universe_opts(sp)
    sp.add_argument("--provider", choices=["chain", "unusualwhales"], default="chain")
    sp.add_argument("--threshold", type=float, default=3.0, help="volume / 30d avg (3.0 = 300%%)")
    sp.add_argument("--max-dte", type=int, default=14)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_flow)

    sp = sub.add_parser("catalyst", help="earnings-call synthesis + insider cross-reference")
    data_opts(sp)
    sp.add_argument("--ticker", required=True)
    sp.add_argument("--transcript", help="text file with the earnings call transcript (needs ANTHROPIC_API_KEY)")
    sp.add_argument("--model", default="claude-opus-5")
    sp.add_argument("--days", type=int, default=30)
    sp.add_argument("--save")
    sp.set_defaults(func=cmd_catalyst)

    sp = sub.add_parser("evening", help="the AI grind: regime + scan + flow -> brief")
    data_opts(sp); universe_opts(sp); setup_opts(sp)
    sp.add_argument("--earnings-yield", type=float)
    sp.add_argument("--skip-flow", action="store_true")
    sp.set_defaults(func=cmd_evening)

    sp = sub.add_parser("morning", help="print the latest brief and the candidate files to review")
    sp.set_defaults(func=cmd_morning)

    sp = sub.add_parser("gauntlet", help="run the 5 veteran rules on a candidate json")
    data_opts(sp)
    sp.add_argument("candidate")
    sp.add_argument("--regime", help="regime json from `centaur regime --save` (default: latest brief, else live)")
    sp.add_argument("--offline", action="store_true", help="never fetch; fail Rule 3 if no regime is available")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--save")
    sp.set_defaults(func=cmd_gauntlet)

    sp = sub.add_parser("size", help="position size from the 1%% rule")
    sp.add_argument("--entry", type=float, required=True)
    sp.add_argument("--stop", type=float, required=True)
    sp.add_argument("--target", type=float)
    sp.set_defaults(func=cmd_size)

    sp = sub.add_parser("journal", help="trade journal")
    js = sp.add_subparsers(dest="jcmd", required=True)
    o = js.add_parser("open")
    o.add_argument("ticker"); o.add_argument("--direction", default="long", choices=["long", "short"])
    o.add_argument("--entry", type=float, required=True); o.add_argument("--stop", type=float, required=True)
    o.add_argument("--target", type=float, required=True); o.add_argument("--shares", type=int, required=True)
    o.add_argument("--ai-thesis", default=""); o.add_argument("--why", default="")
    o.add_argument("--signals", nargs="*"); o.add_argument("--gauntlet", help="gauntlet report json"); o.add_argument("--regime")
    c = js.add_parser("close")
    c.add_argument("id"); c.add_argument("--exit-price", type=float, required=True)
    c.add_argument("--reason", required=True, choices=["stop", "target", "time", "discretionary", "news", "partial"])
    c.add_argument("--lessons", default="")
    js.add_parser("list"); js.add_parser("stats")
    f = js.add_parser("feedback"); f.add_argument("--last", type=int, default=20)
    sp.set_defaults(func=cmd_journal)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    cfg = load_config(args.config, equity=args.equity, risk_pct=args.risk_pct)
    return args.func(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
