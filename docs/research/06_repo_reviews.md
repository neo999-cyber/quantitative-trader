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

## Set 2

### 5. hummingbot/hummingbot — https://github.com/hummingbot/hummingbot
- **What it is:** Open-source market-making and arbitrage runtime. ~20k stars, Apache-2.0, v2.16.0, 40+ CEX and DEX connectors (CLOB and AMM), paper mode, V2 "controllers" backtestable through the Hummingbot dashboard; sustained by the Hummingbot Foundation.
- **Fit with the plan:** none for the trial or the first phases. It is a live execution runtime for quoting both sides of a book; our strategies are daily-bar directional. Market making is a stated non-goal (`PLAN.md` §8) because it needs L2 data, latency engineering and inventory risk management that are a different product.
- **Verdict: SKIP.** REFERENCE only for exchange-connector edge cases (rate limits, order-status quirks) if we write our own Binance adapter instead of using Nautilus's.

### 6. ccxt/ccxt — https://github.com/ccxt/ccxt
- **What it is:** Unified exchange API for 104+ venues in Python/JS/C#/PHP/Go/Java/Rust; near-weekly releases; built-in rate limiter; `set_sandbox_mode(True)` for testnets; CCXT Pro (WebSockets) now bundled. Unified `fetchOHLCV` (with `paginate`), `fetchTradingFees`, `fetchFundingRateHistory`, `createOrder`.
- **Fit with the plan:** three concrete jobs.
  1. **Phase 1, delta pulls:** the bulk history comes from the Binance bucket; CCXT fetches the last day or two each night so the lake is current without re-downloading zips. It is a convenience layer, not an archive (REST trade depth is days, not years).
  2. **Cost model:** `fetchTradingFees()` on your authenticated Binance account returns *your* maker/taker tier, so the cost model uses the real fee rather than the list price.
  3. **Phase 4, execution:** either directly (simple daily-bar orders on Binance spot) or indirectly through NautilusTrader's Binance adapter. Testnet via sandbox mode for the first paper runs.
- **Verdict: ADOPT** (already implied in the plan; now explicit).

### 7. AI4Finance-Foundation/FinRL — https://github.com/AI4Finance-Foundation/FinRL
- **What it is:** Deep reinforcement learning for trading: gym-style environments plus notebooks. 16.3k stars, MIT, last formal release 0.3.5 (June 2022); repo pushed July 2026 but notebook-centric, 312 open issues; the team steers users to FinRL-Meta/FinRL-X and ran contests 2023–2025.
- **Fit with the plan:** none. RL agents trained on a few years of daily prices are the textbook overfitting case: thousands of implicit parameters, reward on in-sample returns, no multiple-testing control, and the published examples use survivorship-biased Yahoo data. Nothing here would survive gates 4–7, and the code quality is educational.
- **Verdict: SKIP.** REFERENCE only for the gym environment interface if an RL experiment is ever pre-registered as a research question, which is not on the roadmap.

**Net effect on `PLAN.md`:** CCXT written into Phase 1 (nightly deltas, fee lookup) and Phase 4 (execution/testnet). hummingbot and FinRL confirm existing non-goals.

## Set 3

### 8. nautechsystems/nautilus_trader — https://github.com/nautechsystems/nautilus_trader
- **What it is:** Rust-core, event-driven backtest and live platform with a Python control plane. 28.8k stars, LGPL-3.0, pushed daily. 1.231.0 (Aug 2026) is the last Cython-era release; 2.0.0rc4 (Sept 2026) is the Rust-only line. Stable adapters include Binance, Bybit, OKX, Coinbase, Kraken, Interactive Brokers, Databento, Tardis, dYdX, Hyperliquid and Polymarket. Fill models with partial fills and slippage probability, maker/taker fee models, margin accounts, perp funding, Parquet data catalog.
- **Fit with the plan:** it *is* layer 5. Both of your venues (Binance and IBKR) have first-party adapters, which is the strongest argument for it over alternatives. Not used in the one-week trial (vectorbt is enough for daily-bar gates); enters in Phase 4 for execution-realistic re-runs and paper/live.
- **Risks:** learning curve; the 2.0 migration is mid-flight, so pin 1.231.0 and wrap its API behind a thin layer of ours.
- **Verdict: ADOPT** (Phase 4, as already planned).

### 9. github.com/polymarket (organisation) — https://github.com/polymarket
- **What it is:** Not a single repo but the org behind the Polymarket prediction market: `py-clob-client` (Python client for its order book), the TypeScript `clob-client`, an `agents` framework for LLM trading bots on Polymarket, and contract repos. Markets are binary outcome shares priced 0–1 on Polygon, settled in USDC.
- **Fit with the plan:** a different asset class with different statistics. Payoffs are binary, so the right metrics are calibration and Brier score rather than Sharpe; liquidity is thin outside headline markets; edges come from information and resolution timing, not price patterns; and the LLM-agent repo has the same look-ahead problem as TradingAgents. NautilusTrader has a Polymarket adapter, so the architecture would not block it later. Jurisdiction: Polymarket geo-restricts some countries (the US among them); UAE access and legality need checking before any account is opened.
- **Verdict: SKIP for the trial and Phases 1–5.** Park as a possible Phase 6 research question ("is there a systematic edge in Polymarket pricing vs resolution?") only after a data source for historical order books is confirmed and legality is verified. Do not use the `agents` repo.

### 10. Lumiwealth/lumibot — https://github.com/Lumiwealth/lumibot
- **What it is:** Python strategy framework with a broker abstraction: Alpaca, Interactive Brokers, Tradier, Schww/Tradovate/TopstepX, Polymarket, CCXT (Coinbase/Kraken/Binance). Backtest data from Yahoo (default), Polygon, ThetaData, Databento, CSV. ~2.1k stars, LICENSE file is GPL-3.0 (README summary says MIT; trust the file), 91 open issues, active pushes, minute-bar simulation only, newer "AI agents" runtime.
- **Fit with the plan:** overlaps NautilusTrader's Phase 4 role with weaker realism (no fill-probability models, no L2, Yahoo as default data) and a copyleft licence. Its one attraction, a simple IBKR paper path for daily-bar strategies, is also covered by IBKR's official MCP for staged orders and by ib_async.
- **Verdict: SKIP.** REFERENCE only for its IBKR connection boilerplate if we write our own thin adapter.

**Net effect on `PLAN.md`:** none. Nautilus confirmed for Phase 4 with both Binance and IBKR adapters; Polymarket parked as a possible Phase 6 question with legality and data caveats.
