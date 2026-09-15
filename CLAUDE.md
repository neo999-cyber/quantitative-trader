# quantitative-trader — context for Claude Code sessions

Read these first, in order:
00. `docs/20_PROGRAMME_2.md` — **start here from 15 September 2026.** Programme 1 (below) is finished; its one-page verdict is `docs/18` and its clinical handover is `docs/19`. Programme 2 changes the instruments (perpetuals, single stocks at $0 commission, micro futures), the resolution (minute bars, funding, auction imbalance), the point-in-time data, and gate 5's comparator (`--benchmark cash` for market-neutral and carry books, exposure-matched for long-only stock selection). Owner's decisions (Dubai, $0 data, no funded evaluation yet), the stopping-rule re-scope, the plain-steps plan, the session/model plan and the week-by-week log are in that file. The real lake is `$QR_ROOT=~/qr/lake` (set in `~/.zshrc`, not inherited by a tool's shell); the checkout's `lake/` is empty and `qr doctor` shows which one a shell is using.
0. `docs/18_THE_VERDICT.md` — **start here.** One page: what was asked, what was found, what to do about it. The research is finished; nothing below is a live task. Then `docs/19_HANDOVER.md` — the clinical version for an outside reader: failure root-cause analysis, what a successor must not redo, and what a serious attempt would require. Then `docs/17` for the one thing still running, `docs/16` for the sizing review, and `docs/10_NEXT.md` / `docs/11`–`15` for the workings.
1. `docs/01_ONE_WEEK_TRIAL.md` — how the trial was framed (a one-week, $0, crypto-spot trial judged by validation gates, not P&L). **Built and run; the verdict is `docs/06` for crypto and `docs/08` for ETFs. Do not start at Day 1.**
2. `docs/PLAN.md` — the full platform plan (7 layers, data tiers, the 11-gate validation engine, roadmap).
3. `docs/00_STATE_OF_THE_REPO.md` — honest inventory of what exists (`centaur/`: a discretionary swing-trading assistant, 55 tests, never run on live data).
4. `docs/research/` — five research reports with sources (data vendors, engines, statistical rigor, platforms/brokers/strategies).

Conventions
- Python 3.11+, `pip install -e ".[dev,qr,gates,ai]"`, `pytest -q` (synthetic data, no network). Do not write the test count down — it goes stale on the next commit and a reader who trusts it is reasoning about the wrong suite.
- Never use yfinance as a system of record; it is prototyping-only.
- Every backtest run must be counted in the trial log; `qr trial verify` prints the count and walks the hash chain. A sensitivity analysis reads it through `SealedTrialLog` and writes nothing. Every LLM output enters as a point-in-time feature, never as a trade.
- Anthropic model default for code in this repo: `claude-opus-5`; catalyst summariser uses structured outputs and server-side refusal fallbacks.
- Commit author must use the GitHub noreply address (`neo999-cyber@users.noreply.github.com`); pushes with the private email are rejected.

Where the project actually is (15 September 2026, Programme 2 week 1) — **read `docs/20`**
- Gate 5 can be pre-registered against cash (`qr gates --benchmark cash --risk-free fred`); `qr data riskfree-pull` stores FRED DTB3. Perp cost models exist (`CostModel.binance_perp`, `CostModel.hyperliquid_perp`, `CostModel.carry_pair`); funding is **gross**, not a cost (`runner.funding_pnl`). The carry unit (`qr data carry-build`, market `carry-um`) and the `FundingCarry` family exist; `qr gates --market carry-um --costs carry` runs it. Two engine defects and two ingest defects were found by the new controls and closed the same day; see the week-1 log.
- Every USDT perpetual's daily bars are in the lake under `futures/um`; funding for the 471 both-leg symbols is being mirrored. OKX and Bybit liquidation recorders run on the Hetzner box. Nothing from Programme 2 has been run through the gates yet and nothing is pre-registered yet.

Where Programme 1 ended Where the project actually is (15 September 2026) — **finished; read `docs/18`**
- **The research is complete and the answer is an index fund.** Nine pre-registered families failed the gates across two asset classes; forty-six mechanism candidates produced one measurable effect (turn-of-month, 4.8 bps a round trip) that is 0.6x its costs at $1,000 and, at every account size up to $100,000, a worse risk-adjusted way to own the basket than holding it.
- **Step 0 is answered: finding ideas, not finding capital** (`docs/11`), for those nine. `docs/15` qualifies it for the one candidate that had an effect: there the account bound the *cost bar* and not the *outcome*.
- **Stages 1–4 are built and were run to exhaustion**: discovery sandbox, research policy, mechanism memos, kill tests, `qr autopilot`. The generator now returns the same two ideas under new titles; the brief space is spent.
- **Done since:** perp funding and open interest are in the lake and verified; the gate 10/11 sizing review ran (`docs/16`) and its fixes are applied — the quantity was mislabelled, and is now `prob_ever_below_launch`.
- **The only live thread:** `scripts/collect_flows_standalone.py` records ETF share counts on the Hetzner box every 30 minutes on weekdays (`docs/17`). It needs nothing. `fund_flows` stays `needs_dataset` in the registry until the file is long enough to test with.
- **Do not start another autopilot night** without a new input. The funnel is gated on data and instruments, not on loop iterations, and re-running re-derives the same answer at API cost.

Build instructions (one-week trial — complete, kept for provenance)
- Package name: `qr` (placeholder; rename later). Keep `centaur/` untouched.
- Day 1–2: Binance bucket loader (daily + 1h klines, top-30 pairs by quote volume, listing/delisting dates from the bucket listing, microsecond timestamps from 2025-01-01), Parquet lake + DuckDB manifest, QA checks, Fear & Greed ingestor, `Strategy` interface, cost model (Binance spot: user's verified tier is VIP 0 with BNB discount ON → maker 0.075%, taker 0.075%; use taker 0.075% = 7.5 bps per side, plus spread; do not ask again), vectorbt runner, append-only hash-chained trial log.
- Day 2–3: gates 1–9 on arch / statsmodels / skfolio (or purgedcv) / jsharpe plus own CSCV and permutation code; synthetic self-test (noise searched over 200 variants must FAIL at gate 4/5; planted edge must PASS). Hypothesis Report generator with the factor-decomposition row (beta to BTC, alpha t-stat).
- Day 4–5: four families through all gates: TSMOM (vol-targeted), cross-sectional momentum (12-1 skip-month convention), weekly reversal, and the existing 3-down-day RSI setup as a control.
- The cloud sandbox cannot reach Binance or Hugging Face; write loaders against local fixtures in the bucket's exact CSV format and ask the user to run `qr data pull` on the laptop.
- Commit after every stage. Run `pytest -q` before each commit. Keep responses short; the user is watching token spend.
- Reviews of repos/sites/guides live in `docs/research/06_repo_reviews.md`, `08_websites_from_socials.md`, `09_hft_stack_vs_ours.md`; two adopted additions: Fear & Greed feature (trial) and DropsTab token-unlock events (Phase 5).

User context
- MacBook Air M2 16 GB (research). Hetzner box at `root@91.98.172.9`, shared with other projects — it runs the flow collector from `~/flows/`, standard library only, deliberately without `qr` installed so nothing else on it can break. Budget path first, ~$1,000 available, no new hardware.
- Dubai-based; holds Binance and Interactive Brokers accounts. Crypto trial models Binance spot; IBKR for equities later.
- Model guidance from the user: build sessions on Claude Opus 5; Fable 5.1 only for reviewing the gate mathematics and the final Hypothesis Reports; Sonnet 5 for small fixes. Keep context small: do not paste media into build sessions.
