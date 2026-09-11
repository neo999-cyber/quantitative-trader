# Repo reviews (user-submitted)

Verdict scale: **ADOPT** (becomes a dependency) · **BORROW** (take a module or idea, not the package) · **REFERENCE** (read, do not depend on) · **SKIP**.
Status figures are from the 11 Sept 2026 GitHub API pulls in `03_engines_and_storage.md` unless noted.

## Set 1

### 1. TauricResearch/TradingAgents — https://github.com/tauricresearch/tradingagents
- **What it is:** LangGraph multi-agent LLM framework: analyst roles (fundamentals, news, sentiment, technicals) → bull/bear debate → trader → risk team, producing a per-date decision. 104.6k stars, Apache-2.0, v0.4.0 (Aug 2026), 371 open issues.
- **Fit with the plan:** none for research or execution. Its own README says runs are non-deterministic, backtests "are not guaranteed to match any published figure", and news/social inputs "reflect current time, not historical conditions". v0.3.1/v0.4.0 had to add look-ahead filtering and FRED vintage pinning, i.e. earlier results leaked the future. An LLM that has read 2021 already knows 2021 outcomes; no gate in our pipeline can fix that.
- **Verdict: SKIP as a system; BORROW one idea.** The analyst-role decomposition (fundamentals / news / sentiment / technical → bull case / bear case → risk) is a good template for the *evening brief* prompts in `prompts/` (layer 7, human layer). It never touches layers 3–6.

### 2. freqtrade/freqtrade — https://github.com/freqtrade/freqtrade
- **What it is:** The dominant open-source crypto bot. 54.3k stars, GPL-3.0, monthly releases (2026.8), spot and futures on Binance/Bybit/OKX/Kraken and others, dry-run mode, hyperopt, FreqAI (adaptive ML retraining).
- **Fit with the plan:** not as the research engine. It is opinionated (its own strategy class, data format and pairlists), crypto-only, GPL-licensed, and its hyperopt has no multiple-testing correction, so anything it "finds" still has to go through our gates. Two useful pieces:
  1. **Reference for the Binance loader** (Phase 1, days 1–2): `freqtrade download-data` handles pair lists, exchange quirks and feather/parquet OHLCV storage; worth reading before writing ours.
  2. **Alternative live runner for crypto** (Phase 4): if NautilusTrader proves heavier than needed for daily-bar spot strategies on the CX23, a validated strategy can be ported to a freqtrade strategy class and run in dry-run, then live, on Binance. Its Telegram bot and dry-run wallet are mature.
- **Verdict: REFERENCE now; possible ADOPT for live-only in Phase 4.** Never for validation.

### 3. polakowo/vectorbt — https://github.com/polakowo/vectorbt
- **What it is:** Vectorized backtesting on NumPy/Numba with an optional Rust engine since 1.0 (Apr 2026); 1.1.0 (Jul 2026); 9.1k stars; Apache-2.0 + Commons Clause (free for trading your own capital; you may not sell it as a product). PRO edition is paid (~$20/mo or lifetime) with private docs and CV tooling.
- **Fit with the plan:** already the core of layer 3. Thousands of parameter sets across many symbols in seconds on daily bars; fees, slippage, stop orders, grouped portfolios. Not multi-currency, no built-in walk-forward (skfolio/own splits handle that), fills are bar-close approximations (Nautilus handles realism in Phase 4).
- **Verdict: ADOPT** (already in the plan). Buy PRO only if the open edition's CV or documentation becomes the bottleneck.

### 4. mementum/backtrader — https://github.com/mementum/backtrader
- **What it is:** The classic Python event-driven backtester. 23.2k stars, GPL-3.0, **last push 2024-08-19, issues disabled**; the author considers it complete. Community forks exist but are thin.
- **Fit with the plan:** none. Python 3.10+/pandas 2 friction, no maintenance, single-threaded loops that make the permutation and CPCV gates impractical, no live path we would use.
- **Verdict: SKIP.** REFERENCE only if you want to read a clean example of order/broker semantics; NautilusTrader covers that ground for us.

**Net effect on `PLAN.md`:** no changes. vectorbt confirmed; freqtrade noted as a Phase 4 crypto-live alternative and a loader reference; TradingAgents' role decomposition noted for the prompt library.
