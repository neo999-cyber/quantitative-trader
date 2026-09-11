# Quantitative Research & Hypothesis Platform — Plan

*Prepared 11 September 2026. Sources: the five research reports in `docs/research/` and the repo inventory in `docs/00_STATE_OF_THE_REPO.md`.*

---

## 1. Straight talk first

You said the aim is to make money and there is no excuse on that part. Then the tool has to be built around the one fact the research is unanimous on: **the main way retail quants lose is by trading edges that were never real.** Backtested Sharpe explains less than 2.5% of live Sharpe (Quantopian's own study). Published anomalies lose 26–58% of their return after publication. Alpha Architect's review of 215 systematic strategies found a median 73% Sharpe deterioration live versus backtest. With five years of daily data, trying more than about 45 configurations virtually guarantees an in-sample Sharpe of 1 with an expected out-of-sample Sharpe of 0.

So the "state of the art" is not a better indicator or a smarter AI. It is a platform that (1) runs on survivorship-free, point-in-time data, (2) charges realistic costs, (3) refuses to promote an idea until it survives multiple-testing deflation, permutation tests and a locked holdout, (4) sizes with math that assumes the edge is smaller than it looks, and (5) runs the identical code from backtest to paper to live so nothing is lost in translation. That is what compounds: small real edges, taken at the right size, for years. Anything that skips those steps is a slot machine with extra steps.

What was built so far (the Centaur v0.1) is a disciplined discretionary swing-trading assistant. It is worth keeping as the human execution layer. It is not the research platform. Details in `docs/00_STATE_OF_THE_REPO.md`.

---

## 2. Target architecture

Seven layers. Each is replaceable; data and the validation engine are the two that matter most.

| # | Layer | Choice | Why (from research) |
|---|---|---|---|
| 0 | **Data lake** | Parquet files, hive-partitioned, queried by DuckDB and Polars; immutable raw + manifest table with source, hash, ingest time | Zero infrastructure at 10–500 GB, ASOF joins for point-in-time, every backtest tied to an exact data version. QuestDB only if live tick ingest with concurrent readers is ever needed. |
| 1 | **Ingestors + reference tables** | One module per source (Binance bucket, Bybit bucket, Kraken CSV, CCXT delta; Dukascopy, TrueFX, OANDA; Tiingo or Norgate, Sharadar, Databento; FRED/ALFRED; SEC EDGAR via edgartools; FINRA) writing to `raw/`. Reference tables: instruments, listing/delisting dates, index membership, corporate actions, calendars, FX rates | Free tiers evaporate (CryptoCompare May 2026, Dune Sept 2026, X, pytrends) so every vendor must be swappable and every raw pull cached locally. |
| 2 | **Features and signals** | Polars expressions; TA-Lib 0.7 wheels; pandas-ta-classic for the long tail; features written to `features/{set}/{version}/` with a decision-time timestamp | Point-in-time joins by construction. Foundation time-series models only as volatility/volume features, never as the signal. |
| 3 | **Research engine** | vectorbt 1.x (Rust engine) for parameter sweeps across many symbols; zipline-reloaded Pipeline + alphalens for cross-sectional equity factors; PyBroker for ML with built-in walk-forward; Optuna 5 for search; MLflow for every run | Fast iteration where it is safe (screening) and disciplined out-of-sample where it matters. |
| 4 | **Validation engine** (the product) | The 11-gate hypothesis pipeline (§4) on `arch` + `statsmodels` + `skfolio`/`purgedcv` + `jsharpe` + own CSCV/permutation code; an immutable, hash-stamped **trial log** that counts every variant ever run | This is what separates a real edge from noise. No comparable open tool exists; the closest (Lacuna, factor-qc) are weeks old and single-author. |
| 5 | **Execution simulation + live** | NautilusTrader (pin 1.231.0 until 2.0 is stable; migrate Q1 2027): fill models with partial fills and slippage probability, maker/taker fees, margin accounts, perp funding; adapters for IBKR (ib_async), Binance/Bybit/Kraken/Coinbase, OANDA via its own API. Same strategy code in backtest, paper and live. | Two engines that agree (vectorized then event-driven) catch most look-ahead bugs. Nautilus is the only open engine with production-grade execution realism and a live path across all three asset classes. |
| 6 | **Portfolio, sizing, risk** | skfolio (CV-aware allocation) and Riskfolio-Lib; volatility targeting; fractional Kelly from *deflated* Sharpe with the 1% rule kept as a hard per-trade cap; drawdown-constrained sizing (Busseti–Ryu–Boyd, cvxpy) | The 1% rule is roughly quarter-Kelly for a typical system; it is a good cap and a bad estimator. |
| 7 | **Ops and the human layer** | cron first, Prefect 3 when there are more than five jobs; MLflow local server; marimo notebooks (plain `.py`, testable); Telegram alerts; daily reconciliation against broker statements; **the existing Centaur rulebook/gauntlet and journal stay as the discretionary execution gate** | Cheap, owned, auditable. |

**AI's place in this architecture.** Claude is a code author, a document reader and an idea generator, never a data source and never the final judge. Concretely: transcript and filing extraction into timestamped features; RD-Agent-style factor proposals that a deterministic backtester scores; code generation for loaders and tests; the evening/morning briefs. Every LLM output enters the pipeline as a point-in-time feature and passes the same 11 gates. LLM "trading agents" (TradingAgents, ai-hedge-fund) are excluded: their own changelogs document look-ahead leaks and non-determinism.

**Repository layout (target).**
```
quantitative-trader/
  lake/                 # Parquet data lake (git-ignored), layout per docs/research/03
  qr/                   # the platform package (working name; rename freely)
    data/               #   ingestors, reference tables, QA checks, DuckDB catalog
    features/           #   feature sets with versioning and decision-time stamps
    strategies/         #   Strategy interface + library (the 10 families)
    research/           #   vectorbt/zipline/PyBroker adapters, Optuna, MLflow
    validate/           #   the 11 gates, trial log, hypothesis report
    execution/          #   Nautilus configs, cost models, broker adapters, reconciliation
    portfolio/          #   allocation, sizing, risk
  centaur/              # existing: rulebook, journal, briefs (the human gate)
  docs/                 # this plan + research
```

---

## 3. Data: what to buy, per asset class and budget

The research produced three tiers per asset class. Recommendation: **start at $0 with crypto**, because Binance's public bucket is the single best free dataset anywhere (spot and perp 1-minute bars since 2017, trades, funding since 2020, open interest and long/short since 2020, depth snapshots since 2023) and it lets the whole pipeline be validated end to end before a dollar is spent. Add equities second (this is where survivorship bias bites hardest and where paid data is non-negotiable), forex third.

### Crypto
| Tier | Stack | ≈ $/mo |
|---|---|---|
| Budget | Binance S3 bulk + Bybit bucket + Kraken quarterly CSV (2013+) + CCXT for daily deltas + Coin Metrics Community (daily fundamentals, no key) + CoinGecko Demo for listing/delisting dates | 0 |
| Serious | + Coinglass entry tier (cross-exchange funding/OI/liquidations) + CoinGecko Basic/Analyst + a one-off Tardis CSV bundle for the 2–3 perps you trade + CoinAPI pay-as-you-go for delisted pairs | 150–300 |
| No-compromise | Tardis Professional (L2 replay) + Coin Metrics Pro or Kaiko + Glassnode Pro + Amberdata | 1.5k–5k+ |

Traps: build the universe from the bucket's historical listing (delisted pairs remain there), never from today's `exchangeInfo`; Binance spot timestamps switched to microseconds on 2025-01-01; backtest on the venue you will execute on and store mark, index and last prices separately; always charge funding on perps.

### Equities (US first)
| Tier | Stack | ≈ $/mo |
|---|---|---|
| Budget | Tiingo Power ($30, adjusted EOD, keeps most delisted names) + SEC EDGAR via edgartools (free point-in-time fundamentals) + free S&P 500 membership histories (fja05680/sp500, riazarbi/sp500-scraper) + Alpha Vantage LISTING_STATUS (free delisting dates) + Databento's $125 signup credits for one-off minute pulls | 30 |
| Serious | Norgate Platinum (~$52.50, survivorship-free daily universe with dated index constituents since 1950; **Windows only**) + Sharadar Core US bundle (~$100–150, the only retail point-in-time fundamentals with filing dates) + Theta Data Standard ($80, 8 years of options ticks) or ORATS ($99–199, IV surfaces) + Massive Starter ($29, unlimited-call reference API) | 260–300 |
| No-compromise | Databento pay-per-GB full depth + OPRA; Norgate Diamond; Sharadar full; ORATS + $2,000 bulk; QuantConnect Security Master ($600/yr) as an independent adjustment cross-check | 500+ |

Traps: yfinance is prototyping-only (Yahoo ToS, rate-limit bans, no delisted names, silent price "repair"); Massive aggregates are split-adjusted only; join Sharadar on `datekey` with as-reported dimensions, never on `calendardate`; EDGAR's `frames` endpoint is last-filed, not point-in-time.

### Forex
| Tier | Stack | ≈ $/mo |
|---|---|---|
| Budget | Dukascopy ticks (bid/ask, UTC, ~2003+) via dukascopy-python/TickVault + TrueFX monthly ticks (bank-aggregated, 2009+) + OANDA practice v20 for NY-17:00-aligned bars + HistData M1 as a third opinion + ECB/FRED fixings | 0 |
| Serious | + Databento CME FX futures (6E/6J/6B…, exchange-quality prints, usage-based) + Twelve Data Grow ($29) + Trading Economics Standard ($149) for a historical consensus calendar | 100–300 |
| No-compromise | LSEG Tick History or LMAX L2 + full CME depth + Econoday | 1k–10k+ |

Traps: store everything in UTC and derive NY-close daily bars with a DST-aware rollover; keep bid and ask, never mid only; never fill weekend bars; retail quotes are broker-specific.

### Macro and alternative (all tiers)
FRED with **ALFRED vintages** (latest-vintage GDP/NFP/CPI is look-ahead), DBnomics, US Treasury, ECB/BoE. SEC Form 4 insider trades and 13F via edgartools. FINRA short interest (free, bi-monthly). Finnhub free news/sentiment, GDELT. First paid alt-data dollars: Quiver Trader ($75, cleaned insiders/13F/WSB) or the Unusual Whales API (~$100+, the only retail-priced options-flow API). Historical Reddit/X sentiment is effectively unavailable to a solo quant now; do not plan around it.

---

## 4. The validation engine: eleven gates, in order

Every idea runs this, in this order, and stops at the first FAIL. A WARN needs a written justification in the trial log. This is the product; everything else is plumbing.

| # | Gate | What runs | Pass | Fail |
|---|---|---|---|---|
| 0 | Pre-registration | Mechanism, predicted sign and size, universe, horizon, parameter *ranges*, cost model, OOS period written and hash-stamped before any run; every variant increments the trial count | Document exists | No doc: exploratory only |
| 1 | Data integrity | Point-in-time fundamentals, delisted names included, decision-time alignment; one-switch leakage test (lag signal +1 bar: smooth degradation; lead −1 bar: if Sharpe explodes there is a leak); shuffled-ticker placebo | Clean | Any leak |
| 2 | Cost survival | Gross vs net with spread + fees + square-root impact + borrow/funding; capacity at intended size | Net ≥ 60% of gross; positive at 2× costs | Net/gross < 50% |
| 3 | Single-strategy significance | HAC t-stat; Probabilistic Sharpe; stationary-bootstrap 95% CI (≥2,000 draws); T vs Minimum Track Record Length | t ≥ 3.0; PSR ≥ 0.95; CI excludes 0 | t < 2.5 |
| 4 | Multiple-testing deflation | Effective trial count from clustering the trial log; Deflated Sharpe; Harvey–Liu haircut (Holm, BHY); Minimum Backtest Length | DSR ≥ 0.95; haircut SR > 0 | DSR < 0.90 |
| 5 | Selection overfitting | CSCV Probability of Backtest Overfitting over the full variant matrix; IS-vs-OOS degradation; Hansen SPA and Romano–Wolf StepM vs buy-and-hold and a random-entry baseline | PBO < 0.10; SPA p < 0.05 | PBO > 0.20 |
| 6 | Permutation | Masters bar-permutation with re-optimisation (≥1,000); signal shuffle; random-entry percentile | p < 0.05; above 95th percentile of random | p > 0.10 |
| 7 | Cross-validated OOS distribution | Combinatorial purged CV (8–10 groups, k=2) giving a distribution of path Sharpes; walk-forward efficiency as a second view | Median path SR > 0.5× IS; ≥ 90% of paths > 0; WFE ≥ 50% | Median < 40% of IS |
| 8 | Robustness and regime | ±25% parameter neighbourhood keeps ≥ 70%; ≤ 5 free parameters, 50–100 trades each; profitable in ≥ 2/3 of years; per-regime Sharpe (HMM/changepoints); drop best 5 trades and best year, still positive | All | Spike surface or single-year dependence |
| 9 | True holdout | One untouched period (≥ 12 months or ≥ MinTRL) opened exactly once | Holdout SR ≥ 50% of deflated SR, same sign | Negative |
| 10 | Incubation | Paper or minimal-size live for 3–6 months; sequential comparison of live vs expected; plan on 40–60% decay | Trending to expectation, no unexplained cost gap | Cost gap > 2× model |
| 11 | Sizing | Fractional Kelly (¼–½) from the *holdout* Sharpe; volatility target; drawdown constraint P(DD > 25%) ≤ 5–10%; 1% rule as the hard cap | — | — |

Minimums to remember: SR 0.5 needs ~11 years of daily data to be 95% distinguishable from zero, SR 1.0 needs ~2.7 years; ≥100 trades for a t-test; ≥100–200 independent events for a 1% catalyst effect.

Output of the engine: a **Hypothesis Report** (Markdown + JSON) with the eleven rows, PASS/WARN/FAIL, the trial count at the time, the data manifest hash, and the tear sheet. The Centaur "candidate" schema gains a required `hypothesis_report_id`; the gauntlet's Rule 2 (confluence) gets a new signal category, `validated`, that only a passing report can supply.

---

## 5. Roadmap

> **Update 11 Sept 2026:** phases 0–3 are replaced for the first pass by the one-week, $0, crypto-spot trial in `docs/01_ONE_WEEK_TRIAL.md` (Claude builds continuously; the pipeline is mostly glue around existing libraries). The phases below remain the shape of the full build after the trial verdict.

Weeks are estimates for one person working most days with Claude as pair. Every phase ends with tests, a runnable command, and a short doc.

### Phase 0 — Decide and set up (week 1)
- Decisions from §6 (OS, budget tier, first asset class, brokers, style).
- Accounts: Binance (public bucket needs none), Dukascopy (none), FRED key, SEC user-agent, Tiingo or Norgate, Databento (claim the $125 credits), IBKR paper, Alpaca paper, OANDA practice, Binance/Bybit testnet.
- Machine: Python 3.12, `uv`, a workstation or VPS with NVMe and ≥64 GB RAM if possible; `lake/` on fast disk.
- **Done when:** `qr doctor` prints every credential and data path as OK.

### Phase 1 — Data lake v1 (weeks 1–3)
- Parquet layout, DuckDB catalog, manifest table, QA checks (gaps, duplicates, timezone, split sanity, volume outliers).
- Crypto ingestors: Binance bucket (klines, aggTrades, fundingRate, metrics), Bybit, Kraken CSV, CCXT delta. Universe from bucket listing with listing/delisting dates.
- Forex ingestors: Dukascopy ticks → UTC bars; OANDA bars; TrueFX cross-check; DST-aware NY-close daily bars.
- Equities ingestors: Tiingo (or Norgate), free constituent histories, LISTING_STATUS; EDGAR companyfacts and Form 4 via edgartools.
- Macro: FRED/ALFRED with vintages.
- Retire the yfinance path in `centaur` to a read-through of the lake.
- **Done when:** one command refreshes every source idempotently and a QA report shows zero unexplained gaps for BTCUSDT, EURUSD and SPY over ten years.

### Phase 2 — Strategy abstraction and vectorized research (weeks 3–5)
- `Strategy` interface: signals → target positions; cost model (spread + fees + √-impact + borrow/funding) as a first-class object; vectorbt adapter; Optuna sweeps; MLflow logging; **the trial log** (append-only, hashed) starts counting from the first run.
- Port the existing 3-down-day/RSI setup as strategy #1 and run it honestly across crypto, forex and equities with costs.
- **Done when:** a sweep over 500 symbols × 1,000 parameter sets completes in minutes and every run is in MLflow with its data manifest hash.

### Phase 3 — Validation engine (weeks 5–8)
- Gates 1–8 implemented on arch/statsmodels/skfolio (or purgedcv)/jsharpe plus own CSCV and permutation code; gate 9 holdout registry that physically withholds the period; Hypothesis Report generator.
- Unit tests against synthetic data with known answers (a true edge must pass; pure noise with 200 variants must fail at gate 4 or 5).
- **Done when:** the pipeline correctly rejects a noise strategy that "found" Sharpe 1.2 by searching, and correctly passes a synthetic strategy with a planted edge.

### Phase 4 — Execution realism and paper trading (weeks 8–11)
- Nautilus data catalog from `clean/`; fill and fee models; margin and funding; broker adapters; reconciliation against statements; Telegram alerts.
- Any strategy that passed gate 8 gets re-run in Nautilus (gate 9 data) before paper trading (gate 10).
- The Centaur gauntlet becomes the manual gate between a paper-validated strategy's signal and a live order.
- **Done when:** the same strategy file runs in vectorbt, Nautilus backtest and Nautilus paper with reconciled results within the cost model's tolerance.

### Phase 5 — Strategy library and portfolio (weeks 11–14)
- Implement the ten families from the research, in evidence order: trend following (futures/crypto), cross-sectional momentum with crash control, quality + momentum, carry and crypto funding carry, opportunistic insider clusters, low-vol sleeve, ETF short-term reversal, revision momentum + transcript features, crypto cross-sectional momentum and size, spread stat-arb.
- Run each through all eleven gates; allocate across survivors with skfolio; size per §4 gate 11; marimo dashboard for the whole book.
- **Done when:** at least two families pass gate 9 and are in paper incubation with a written expectation of live decay.

### Phase 6 — AI research loop and maintenance (ongoing)
- Claude proposes factor candidates (RD-Agent pattern) into the same pipeline with the trial log incremented; transcript/filing/news extraction into point-in-time features; monthly re-validation and decay monitoring for every live strategy; quarterly data-vendor review.

---

## 6. Decisions needed before Phase 1

> **Resolved 11 Sept 2026** (details in `docs/01_ONE_WEEK_TRIAL.md`): macOS research + Linux ops, so Norgate is out; budget path first; crypto spot first; no new hardware; existing CX23 + Volume for ops, hourly CX53 for bursts. Still open: residency (venue), brokers, package name.

1. **Operating system.** Norgate (the best-value equity data) requires Windows for its updater. Mac/Linux means Tiingo + free constituents at budget, or Sharadar at serious tier, or a Windows VM.
2. **Budget tier** per asset class (§3). Recommendation: $0 crypto now, ~$130/mo equities (Tiingo → Norgate/Sharadar) from Phase 1, forex at $0 until a forex strategy passes gate 8.
3. **First asset class.** Recommendation: crypto, for the reasons in §3.
4. **Brokers.** Recommendation: IBKR (stocks, futures, and its official MCP is already connected in this workspace) + Kraken or Coinbase Advanced (crypto, US-friendly; Binance/Bybit if outside the US) + OANDA (forex). Alpaca paper as a simple second stock venue.
5. **Trading style and horizon.** Daily/swing (days to weeks) is what the data tiers above support cheaply and what the evidence favours for a solo account. Intraday requires Databento-class data and moves the budget to the serious tier immediately.
6. **Name.** `centaur` stays for the human layer; the platform package needs a name (`qr` is a placeholder).

---

## 7. What this will cost

| Item | Budget path | Serious path |
|---|---|---|
| Data | $30/mo (Tiingo) | ~$300–400/mo across the three classes |
| Compute | your machine | $50–150/mo VPS or a one-off workstation |
| Software | $0 (all open source; vectorbt PRO optional at ~$20/mo) | + RealTest $389 one-off as an independent equity engine |
| Claude API | $10–50/mo for transcript extraction and code help | $50–200/mo with factor-proposal loops |
| Time | ~14 weeks to Phase 5 | same |

---

## 8. Non-goals and risks

- **Not** high-frequency or market making (hftbacktest exists if that ever changes).
- **Not** an LLM that trades. Not a hosted platform (QuantConnect would be the buy option; the research says lock-in is in the data, and the validation engine does not exist there either).
- **Risk: data cost creep.** Mitigation: raw cache, vendor-agnostic ingestors, decide tiers per phase.
- **Risk: Nautilus 2.0 migration.** Mitigation: pin 1.231.0, wrap its API behind our own thin layer.
- **Risk: p-hacking by an eager human or an eager AI.** Mitigation: the trial log is append-only and every report prints the trial count; the holdout is physically withheld by the data layer.
- **Risk: expecting backtest numbers live.** The plan's own expectation is 40–60% of deflated Sharpe. Size for that.
