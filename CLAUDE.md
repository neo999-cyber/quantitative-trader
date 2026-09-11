# quantitative-trader — context for Claude Code sessions

Read these first, in order:
1. `docs/01_ONE_WEEK_TRIAL.md` — current decisions and the agreed next step (a one-week, $0, crypto-spot trial judged by validation gates, not P&L). **Build has not started; the user said "wait on build, we are still thinking."**
2. `docs/PLAN.md` — the full platform plan (7 layers, data tiers, the 11-gate validation engine, roadmap).
3. `docs/00_STATE_OF_THE_REPO.md` — honest inventory of what exists (`centaur/`: a discretionary swing-trading assistant, 55 tests, never run on live data).
4. `docs/research/` — five research reports with sources (data vendors, engines, statistical rigor, platforms/brokers/strategies).

Conventions
- Python 3.11+, `pip install -e ".[dev,ai]"`, `pytest -q` (55 tests, synthetic data, no network).
- Never use yfinance as a system of record; it is prototyping-only.
- Every backtest run must be counted in the trial log (once it exists). Every LLM output enters as a point-in-time feature, never as a trade.
- Anthropic model default for code in this repo: `claude-opus-5`; catalyst summariser uses structured outputs and server-side refusal fallbacks.
- Commit author must use the GitHub noreply address (`neo999-cyber@users.noreply.github.com`); pushes with the private email are rejected.

User context
- MacBook Air M2 16 GB (research), Hetzner CX23 shared with other projects (ops later), budget path first, ~$1,000 available after the trial verdict, no new hardware for now.
- Dubai-based; holds Binance and Interactive Brokers accounts. Crypto trial models Binance spot; IBKR for equities later.
- Next input from the user: a list of GitHub repos to assess one by one against the plan (record in `docs/research/06_repo_reviews.md`).
