# quantitative-trader — context for Claude Code sessions

Read these first, in order:
0. `docs/10_NEXT.md` — **start here.** Current state, the research plan, the stopping rule, and one pending review that has not been run (gate 10/11 mathematics, for Fable 5.1 in its own session — trigger it before any real money is sized). Then `docs/11` (Step 0's verdict), `docs/12`–`14` (sandbox, autonomy, the laptop guide) and `docs/15` (what the first autopilot nights found).
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

Where the project actually is (14 September 2026)
- **The one-week trial is finished and the build below is done.** Nine families ran through gates 0–11; none passed gate 5. Buy-and-hold beat every one across two asset classes.
- **Step 0 is answered: finding ideas, not finding capital** (`docs/11`). Crypto is size-independent to four significant figures; the ETF families get much cheaper with size and still cannot beat the basket at 100x the account. No deposit rescues any of the nine.
- **Stages 1–4 are built**: discovery sandbox, research policy, mechanism memos, kill tests, `qr autopilot`.
- **Three autopilot nights: twelve candidates, twelve self-kills** (`docs/15`). Only two failed because the idea was wrong; ten failed on *access* — the payer trades an instrument this project cannot trade, or the data is not in the lake.
- **Next, and unverified:** `qr data funding-pull` / `funding-ingest` were written where the Binance bucket is unreachable. The first real pull is their verification; both parsers fail loudly and quote the header that actually arrived.

Build instructions (one-week trial — complete, kept for provenance)
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
