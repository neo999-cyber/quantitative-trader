# quantitative-trader — context for Claude Code sessions

Read these first, in order:
1. `docs/01_ONE_WEEK_TRIAL.md` — current decisions and the agreed next step (a one-week, $0, crypto-spot trial judged by validation gates, not P&L). **STATUS: GO (11 Sept 2026). The user approved the build. Start at Day 1 of the plan without asking for confirmation.**
2. `docs/PLAN.md` — the full platform plan (7 layers, data tiers, the 11-gate validation engine, roadmap).
3. `docs/00_STATE_OF_THE_REPO.md` — honest inventory of what exists (`centaur/`: a discretionary swing-trading assistant, 55 tests, never run on live data).
4. `docs/research/` — five research reports with sources (data vendors, engines, statistical rigor, platforms/brokers/strategies).

Conventions
- Python 3.11+, `pip install -e ".[dev,ai]"`, `pytest -q` (55 tests, synthetic data, no network).
- Never use yfinance as a system of record; it is prototyping-only.
- Every backtest run must be counted in the trial log (once it exists). Every LLM output enters as a point-in-time feature, never as a trade.
- Anthropic model default for code in this repo: `claude-opus-5`; catalyst summariser uses structured outputs and server-side refusal fallbacks.
- Commit author must use the GitHub noreply address (`neo999-cyber@users.noreply.github.com`); pushes with the private email are rejected.

Build instructions (one-week trial)
- Package name: `qr` (placeholder; rename later). Keep `centaur/` untouched.
- Day 1–2: Binance bucket loader (daily + 1h klines, top-30 pairs by quote volume, listing/delisting dates from the bucket listing, microsecond timestamps from 2025-01-01), Parquet lake + DuckDB manifest, QA checks, Fear & Greed ingestor, `Strategy` interface, cost model (Binance spot: user's verified tier is VIP 0 with BNB discount ON → maker 0.075%, taker 0.075%; use taker 0.075% = 7.5 bps per side, plus spread; do not ask again), vectorbt runner, append-only hash-chained trial log.
- Day 2–3: gates 1–9 on arch / statsmodels / skfolio (or purgedcv) / jsharpe plus own CSCV and permutation code; synthetic self-test (noise searched over 200 variants must FAIL at gate 4/5; planted edge must PASS). Hypothesis Report generator with the factor-decomposition row (beta to BTC, alpha t-stat).
- Day 4–5: four families through all gates: TSMOM (vol-targeted), cross-sectional momentum (12-1 skip-month convention), weekly reversal, and the existing 3-down-day RSI setup as a control.
- The cloud sandbox cannot reach Binance or Hugging Face; write loaders against local fixtures in the bucket's exact CSV format and ask the user to run `qr data pull` on the laptop.
- Commit after every stage. Run `pytest -q` before each commit. Keep responses short; the user is watching token spend.
- Reviews of repos/sites/guides live in `docs/research/06_repo_reviews.md`, `08_websites_from_socials.md`, `09_hft_stack_vs_ours.md`; two adopted additions: Fear & Greed feature (trial) and DropsTab token-unlock events (Phase 5).

User context
- MacBook Air M2 16 GB (research), Hetzner CX23 shared with other projects (ops later), budget path first, ~$1,000 available after the trial verdict, no new hardware for now.
- Dubai-based; holds Binance and Interactive Brokers accounts. Crypto trial models Binance spot; IBKR for equities later.
- Model guidance from the user: build sessions on Claude Opus 5; Fable 5.1 only for reviewing the gate mathematics and the final Hypothesis Reports; Sonnet 5 for small fixes. Keep context small: do not paste media into build sessions.
