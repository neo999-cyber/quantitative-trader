# Backtesting Engines, ML-for-Finance, and the Data/Compute Stack for a Solo Quant (as of 11 Sept 2026)

## 0. Method and caveats

- GitHub star counts, last-push dates, open-issue counts and licenses were pulled live from the GitHub API on 2026-09-11. Release versions/dates come from PyPI and GitHub release pages.
- The sandbox egress proxy blocked several vendor domains (vectorbt.pro, quantconnect.com, lean.io, kx.com, arxiv.org, docs.arcticdb.io, jesse.trade, nautilustrader.io, duckdb.org, huggingface.co). Where a primary source was unreachable the claim is marked **[unverified]**.
- A recent GitHub push does not imply substantive work; where it mattered commit content was checked (e.g., Qlib).

---

## 1. Backtesting and research engines

### 1.1 Master table (GitHub API, 2026-09-11)

| Engine | Lang / style | Stars | Last push | License | Open issues | Latest release |
|---|---|---|---|---|---|---|
| vectorbt (OSS) | Python (NumPy/Numba, optional Rust) / vectorized | 9,062 | 2026-08-02 | Apache-2.0 + Commons Clause | 140 | 1.1.0 (2026-07-05) |
| NautilusTrader | Rust core + Python / event-driven | 28,765 | 2026-09-11 | LGPL-3.0 | 131 | 1.231.0 (2026-08-02); 2.0.0rc4 (2026-09-02) |
| QuantConnect LEAN | C# (+Python) / event-driven | 21,581 | 2026-09-10 | Apache-2.0 | 248 | rolling |
| zipline-reloaded | Python (Cython) / event-driven | ~1.9k | 2026 (PR activity Feb 2026) | Apache-2.0 | — | 3.1.1 (2025-07-19) |
| backtrader | Python / event-driven | 23,232 | 2024-08-19 | GPL-3.0 | issues disabled | none (author considers it complete) |
| Backtesting.py | Python / event-loop over OHLC | 8,956 | 2026-08-05 | AGPL-3.0 | 83 | 0.6.6 (2026-07-22) |
| PyBroker | Python (NumPy/Numba) / hybrid | 3,536 | 2026-09-07 | Apache-2.0 + Commons Clause | 4 | 2.0.1 (2026-08-28) |
| bt | Python / tree of "algos", rebalance-driven | 2,981 | 2026-09-10 | MIT | 14 | 1.2.0 (2026-04-25) |
| QSTrader | Python / schedule-driven | 3,464 | 2024-06-30 | MIT | 16 | v0.3.0 |
| finmarketpy | Python / vectorized FX-macro | 3,806 | 2026-04-16 | Apache-2.0 | 43 | 0.11.19 (2025-03-09) |
| Blankly | Python / event-driven | 2,475 | 2024-12-30 | LGPL-3.0 | 39 | stale (README still lists FTX) |
| freqtrade | Python / event-driven crypto bot | 54,257 | 2026-09-10 | GPL-3.0 | 29 | 2026.8 (2026-08-31) |
| Jesse | Python / event-driven crypto | 8,449 | 2026-09-10 | MIT | 16 | 3.1.3 (2026-09-10) |
| hummingbot | Python (+TS gateway) / live MM bot | 19,963 | 2026-09-10 | Apache-2.0 | 161 | v2.16.0 |
| OctoBot | Python / GUI-configured bot | 6,555 | 2026-09-10 | GPL-3.0 | 167 | 3.0.0-beta2 |
| Lumibot | Python / event-driven | 2,054 | 2026-09-09 | GPL-3.0 (LICENSE file) | 91 | rolling on PyPI |
| hftbacktest | Rust + Python (Numba) / tick-level L2/L3 | 4,665 | 2025-12-23 | MIT | 15 | py 2.4.4 (2025-12-10) |
| Barter-rs | Rust / event-driven | 2,274 | 2026-08-24 | MIT | 89 | barter-macro 0.2.1 (Aug 2026) |
| Kungfu | C++/Python (China) | n/a | main repo no longer public | — | — | — |
| Qlib | Python / ML-factor platform | 48,478 | 2026-09-02 | MIT | 476 | 0.9.7 (2025-08-15) |
| FinRL | Python (notebooks) / RL envs | 16,267 | 2026-07-13 | MIT | 312 | 0.3.5 (2022-06-25) |
| TradingGym (Yvictor) | Python / RL env | 1,920 | 2024-02-11 | MIT | 11 | dormant |
| gym-anytrading | Python / RL env | 2,388 | 2024-03-14 | MIT | 10 | dormant |
| RQAlpha | Python / event-driven (China A-shares/futures) | 6,759 | 2026-09-08 | custom | 32 | active |

### 1.2 Engine-by-engine

**vectorbt (open source) vs vectorbt PRO**
- v1.0.0 (2026-04-22) introduced an **optional Rust engine with auto-dispatch** (`pip install vectorbt[rust]`) — Rust kernels for indicators, portfolio simulation and signal processing with fallback to Numba; v1.1.0 (2026-07-05) added Python 3.14 / pandas 3 support. Python 3.11–<3.15 required.
- License is "fair-code": Apache 2.0 with Commons Clause — free for individuals and firms, but "you may not sell products or services that are primarily this software." Fine for a solo trader trading own capital.
- Design: everything is a broadcasted pandas/NumPy array; thousands of parameter combinations are evaluated simultaneously at Numba/Rust speed. Multi-asset via column broadcasting; portfolio simulation (`Portfolio.from_signals/from_orders`) supports fees, fixed fees, slippage, size types, cash sharing across columns (grouped portfolios), stop orders. Not multi-currency in the accounting sense. Native walk-forward is via manual splitting in OSS.
- PRO: sold by membership, roughly **$20/month or a one-time lifetime fee (~$500)**; members get the private GitHub repo, Discord, private docs; PRO advertises faster large-scale testing, cross-validation splitters, portfolio optimization integration, chunking/parallelization, data providers **[pricing and feature list unverified — vectorbt.pro blocked]**.
- Verdict: **the best screening/parameter-sweep engine in Python**; the 1.x Rust engine is a material 2026 upgrade. Buy PRO only once you hit OSS's ceilings (CV tooling, docs, support).

**NautilusTrader**
- Production-grade Rust-native, deterministic event-driven engine; Python is the control plane; same strategy code runs in backtest and live. 18 integrations marked stable: Binance, Bybit, Coinbase, OKX, Kraken, BitMEX, Deribit, Betfair, Interactive Brokers, Databento, Tardis, dYdX, Hyperliquid, Lighter, Polymarket, etc. Asset classes: crypto CEX/DEX, FX, equities, futures, options, betting.
- 2026 status: 1.231.0 (2026-08-02) is the **final v1.x with the Cython core**; 2.0.0rc3 (2026-08-20) removed the legacy Cython package; 2.0.0rc4 (2026-09-02) added custom Python fee models in backtest configs. v1 now gets only critical security backports. Python 3.12–3.14.
- Realism: 11 built-in fill models (Default, BestPrice, Two/ThreeTier, LimitOrderPartial, SizeAware, CompetitionAware, VolumeSensitive, MarketHours…), `prob_fill_on_limit`, `prob_slippage`, random seed for reproducibility, custom fill models; account types CASH/MARGIN/BETTING; multi-currency starting balances; perpetual funding settlements from `FundingRateUpdate`. Nanosecond timestamps; Parquet data catalog. Borrow/short-financing costs for equities are not modeled out of the box.
- Optimization/walk-forward: not built in — loop backtests externally (Optuna/joblib). Learning curve: high. Verdict: **the engine for validation and live deployment of anything execution-sensitive**; the v2 migration is in RC, so pin versions carefully through Q4 2026.

**QuantConnect LEAN (self-hosted vs cloud)**
- Apache-2.0, C# core with Python algorithms; models for every plug-in point; multi-asset. `pip install lean` gives `lean backtest/research/live` via Docker.
- Cloud plans start at $60/month for live trading with free unlimited backtesting; data add-ons are the main cost driver **[from search summaries]**.
- Self-hosted data costs (from the QuantConnect Documentation repo): by-ticker US Equity **$0.06**/security/day/format (trade and quote separate); Futures **$1.50**/ticker/day/format; Forex and CFD **$0.03**/pair/day. 500 US equities × 252 days × 2 formats ≈ $15k/yr by-ticker at minute resolution — bulk is the only sane route at scale.
- Verdict: **best if you want a fully integrated data+backtest+live product and are willing to pay for data**; poor fit if you want to own your own Parquet lake and vectorized research loop.

**zipline-reloaded (+ Pipeline)**
- Stefan Jansen's fork; Apache-2.0; 3.1.1 (2025-07-19). On life support rather than dead (Feb 2026 PR fixed adjustments/Pipeline bugs).
- Pipeline API is still the cleanest cross-sectional factor-research abstraction in Python. No live bridge. Verdict: **use for US-equity factor research with alphalens/pyfolio; not for crypto/forex or live trading.**

**backtrader** — last push 2024-08-19, issues disabled; "archive mode". Verdict: **learning/prototyping only; do not build a 2026 platform on it.**

**Backtesting.py** — AGPL-3.0, 0.6.6 (2026-07-22). Single-instrument OHLC event loop, SAMBO Bayesian optimizer; no multi-asset portfolio, no live. Verdict: **fastest way to sanity-check a single-instrument rule**.

**PyBroker** — Apache 2.0 + Commons Clause; 2.0.1 (2026-08-28); NumPy/Numba engine, built-in **walk-forward analysis**, bootstrapped metrics, ML model training hooks, Optuna integration, caching, Alpaca live. Only 4 open issues. Verdict: **the most opinionated "ML + walk-forward done right" engine**.

**bt** — MIT, 1.2.0 (2026-04-25), tree-of-strategies, weight-based. Verdict: **good for portfolio-allocation strategies, not trade-level execution research.**

**QSTrader** — stale (2024-06). **finmarketpy** — niche FX/macro toolkit. **Blankly** — dead.

**freqtrade (+FreqAI)** — GPL-3.0, 54k stars, monthly releases. FreqAI: adaptive retraining during live trading, feature engineering, LightGBM/XGBoost/CatBoost/PyTorch and RL models. Verdict: **best turnkey crypto spot/futures bot with an honest ML layer**; opinionated and crypto-only.

**Jesse** — MIT, 3.1.3 (2026-09-10), 300+ indicators, spot/futures, partial fills, Optuna optimization, Monte Carlo, Jesse MCP. Live trading pricing **[unverified]**. Verdict: cleaner API than freqtrade, smaller community, crypto-only.

**hummingbot** — for market making, not research. **OctoBot** — retail bot. **Lumibot** — GPL-3.0 (LICENSE file), pragmatic broker abstraction (Alpaca, IBKR, Tradier, Schwab, Tradovate, CCXT); minute-bar simulation only.

**hftbacktest** — MIT, Rust core with Python bindings; full L2/L3 book reconstruction, latency models, queue-position fill models; latest 2.4.4 (2025-12-10). Verdict: **the only serious open-source tool for market-making/HFT-style research on crypto tick data.**

**Barter-rs** — Rust building blocks with an explicit "not for production" disclaimer. **Kungfu** — closed/China only.

**Qlib (Microsoft)** — MIT, 48k stars; 2026 commits are almost all bug/security fixes; 476 open issues. Strong for ML factor pipelines (Alpha158/360), defaults to China A-share data. Verdict: **heavy, data-provider-shaped, maintenance is reactive.**

**FinRL / TradingGym** — educational RL sandboxes; not platform components.

**Notable 2025–2026 releases**: vectorbt 1.0 Rust engine (Apr 2026); NautilusTrader 2.0 RCs (Aug–Sep 2026); PyBroker 2.0 (Aug 2026); Optuna 5.0 (Sep 2026); Polars 2.0 RC (Sep 2026); DuckDB 1.4 LTS (Sep 2025) and 1.5 (Mar 2026); Chronos-2 (Oct 2025), TimesFM 2.5 (Sep 2025), Moirai 2.0 (Aug 2025).

---

## 2. Analytics and reporting

| Library | Stars | License | Latest | Notes |
|---|---|---|---|---|
| quantstats | 7,625 | Apache-2.0 | 0.0.81 (2026-01-13) | Tear sheets/HTML reports, Monte Carlo |
| pyfolio-reloaded | ~612 | Apache-2.0 | 0.9.9 (2025-06-02) | Most information-dense tear sheet; pairs with zipline |
| alphalens-reloaded | ~644 | Apache-2.0 | 0.4.6 (2025-06-02) | Factor IC/quantile/turnover analysis — still the standard |
| empyrical-reloaded | ~121 | Apache-2.0 | 0.5.12 (2025-06-01) | Metrics backend |
| ffn | 2,676 | MIT | push 2026-09-10 | Lightweight stats/plots; backbone of bt |
| Riskfolio-Lib | 4,492 | BSD-3 | 7.3.0 (2026-05-31) | 26 risk measures, HRP/HERC/NCO, CVXPY |
| PyPortfolioOpt | 6,019 | MIT | 1.6.0 (2026-02-26) | Classic MVO, Black-Litterman, HRP |
| skfolio | 2,376 | BSD-3 | 1.0.6 (2026-09-08) | scikit-learn API: cross-validation, walk-forward, CPCV, entropy pooling, transaction costs, cardinality constraints |
| cvxportfolio | 1,284 | GPL-3.0 | 1.5.1 (2025-07-06) | Multi-period convex optimization + simulator (Boyd et al.) |

skfolio is the most actively developed and the only one designed around out-of-sample model selection.

---

## 3. Feature/indicator and forecasting libraries

**TA-Lib (python wrapper)** — 12,243 stars, BSD-2, 0.7.1 (2026-07-16). The historic install pain is largely gone: pre-built wheels for Linux/macOS/Windows across Python 3.9–3.14. Use 0.6/0.7 with NumPy 2.

**pandas-ta after 2025** — the upstream `twopirllc/pandas-ta` GitHub repo now returns 404; PyPI's latest is 0.4.71b0 (beta, 2025-09-14). The community fork **pandas-ta-classic** (MIT; 0.6.52 on 2026-06-24; 224 indicators + 62 candlestick patterns) is the practical replacement.

**ta (bukosabino)** — pure pandas, slow but simple. **tulipy** — not maintained. **finta** — archived.

**tsfresh** — 0.21.2 (2026-05-31): automatic windowed feature extraction; beware leakage on rolling windows. **sktime** — 1.1.0, breadth over polish. **Nixtla**: statsforecast 2.1.1 and neuralforecast 3.2.2 — best-maintained forecasting stack in Python.

**Foundation models — honest assessment for trading**
- Chronos-2 (Amazon; Oct 2025), TimesFM 2.5 (Google; Sep 2025), Moirai-2.0 (Salesforce; Aug 2025).
- A June 2026 benchmark (arXiv 2606.27100) tested TimeGPT, TimesFM-2.5, Moirai-2.0, Chronos and Chronos-2 on large-cap returns: "gains over the random-walk benchmark are small and sparse," with "limited economic significance in noisy markets." A companion paper (arXiv 2607.05291) finds TSFMs more plausibly useful for realized volatility.
- Verdict: **do not expect zero-shot foundation models to forecast returns.** Reasonable uses: volatility/volume/spread forecasting as features, imputation, and as a baseline to beat.

---

## 4. Storage and compute

### 4.1 Options

| System | Stars | License | Latest | Solo-quant relevance |
|---|---|---|---|---|
| Parquet + DuckDB | 41,147 | MIT | 1.5.5 (2026-07-22); 1.4.0 LTS | Zero-infra SQL over Parquet, larger-than-memory, ASOF joins; Iceberg extension experimental |
| Polars | 39,707 | MIT | 1.44.2 (2026-09-09); 2.0.0-rc.1 | Lazy/streaming DataFrames in Rust; `scan_parquet` + `join_asof` + `group_by_dynamic` cover most bar/tick work |
| ArcticDB (Man Group) | 2,509 | BSL 1.1 → Apache-2.0 after two years | 6.25.0 (2026-09-09) | README: production use requires agreement with Man Group; **read the licensing FAQ before depending on it** |
| QuestDB | 17,315 | Apache-2.0 core | 10.0.x | Explicitly targets tick data/order books; ASOF JOIN, SAMPLE BY; single binary |
| TimescaleDB | 23.5k | Apache-2.0 + Timescale License | 2.30.0 | Postgres + hypertables; fine if you already run Postgres |
| ClickHouse | 49,816 | Apache-2.0 | v26.3 LTS | Best raw scan speed at TB scale; heavier ops |
| InfluxDB 3 Core | 31.7k | MIT/Apache | GA April 2025 | Core "limits query time ranges to approximately 72 hours" — **disqualifying for historical research** |
| kdb+ / KDB-X | — | proprietary | Community Edition announced 2025-07-15 **[terms unverified]** | A q rewrite is not worth it for a Python-centric solo stack |
| Lance | 7.1k | Apache-2.0 | v11.0.0 | Designed for multimodal AI, not tick data |
| Apache Iceberg (PyIceberg) | 1.1k | Apache-2.0 | 0.12.0 | SQLite catalog for local use; metadata-layer transactions on Parquet |

### 4.2 What a solo quant should use at 10–500 GB

- **Bars (daily to 1-minute), all asset classes: Parquet + DuckDB + Polars.** Hive-partition by `asset_class/venue/symbol/year`, ZSTD, row groups ~128k–1M rows, sorted by timestamp. DuckDB for ad-hoc SQL and ASOF joins; Polars for feature engineering. 500 GB on a workstation NVMe stays interactive if queries prune partitions.
- **Tick / L2 (crypto, futures): Parquet partitioned by `symbol/date`; query with DuckDB/Polars; feed hftbacktest/Nautilus from those files.** Only add a server (QuestDB or ClickHouse) if you need concurrent live ingestion + queries from multiple processes.
- **Versioning/point-in-time**: ArcticDB is the most ergonomic (check license); PyIceberg with a SQLite catalog is fully open; simplest is immutable Parquet files with a manifest table in DuckDB.
- **Avoid**: InfluxDB 3 Core, kdb+, Lance, TimescaleDB unless Postgres is already central.
- **Compute**: one 16–32 core box with 64–128 GB RAM and NVMe beats cloud for iterative research; Ray/joblib for parameter sweeps; GPU only for neural models.

### 4.3 Orchestration, experiment tracking, notebooks

| Tool | Latest | Verdict |
|---|---|---|
| cron/systemd | — | Sufficient for nightly data pulls; no lineage/retries |
| Prefect | 3.8.5 (2026-09-03) | Best solo fit; self-hosted server is free |
| Dagster | 1.13.21 | Asset-centric model maps well to a data lake; heavier |
| Airflow | 3.3.1 | Operationally heavy for one person |
| MLflow | 3.16.0 (2026-09-04) | Local tracking server in one command; log every backtest as a run |
| Weights & Biases | — | Nicer UI; data leaves your machine unless self-managed |
| Optuna | 5.0.0 (2026-09-07) | Parameter search with pruning; combine with walk-forward objective, not in-sample Sharpe |
| marimo | 0.24.1 (2026-09-10) | Plain .py notebooks, reactive, importable/testable |

---

## 5. LLM-agent quant projects — are they useful beyond demos?

| Project | Stars | Last push | What it actually does |
|---|---|---|---|
| TradingAgents (Tauric) | 104,594 | 2026-09-07 | LangGraph multi-agent debate; v0.3.1/v0.4.0 added look-ahead filtering and FRED vintage pinning (earlier versions leaked); "designed for research purposes"; 371 open issues |
| ai-hedge-fund (virattt) | 63,332 | 2026-09-03 | Persona agents → portfolio manager; `--backtest` mode; "the system does not actually make any trades" |
| FinRobot | 7,965 | 2026-09-07 | Notebook-based analyst agents tied to FinGPT |
| FinGPT | 21,236 | 2026-09-08 | Fine-tuned financial LLMs (sentiment etc.) |
| RD-Agent(Q) (Microsoft) | 14,579 | 2026-09-04 | LLM agent that mines factors and models on top of Qlib; NeurIPS 2025 paper claims ~2× annualized return vs benchmark factor libraries with 70% fewer factors at <$10/run (on A-share data) |

Honest assessment:
- None of these is a strategy. The persona/debate frameworks produce plausible narratives, and their "backtests" are vulnerable to LLM knowledge-cutoff leakage and look-ahead in data feeds — TradingAgents' own changelog shows both being patched in 2025–26.
- What *is* useful: (1) **RD-Agent's pattern** — an LLM proposes and codes candidate factors that are scored by a deterministic backtester with strict CV; (2) LLMs as **coding/research assistants** and for **unstructured data extraction** (filings, news → structured features), where the output is a feature you can test, not a trade.
- Rule: any LLM output must enter the pipeline as a time-stamped, point-in-time feature and pass the same walk-forward tests as any other signal.

---

## 6. Recommended reference architecture for a solo quant (stocks, crypto, forex)

**Data lake layout:**
```
lake/
  raw/        {source}/{asset_class}/{venue}/{symbol}/{yyyy}/{mm}.parquet   # immutable, as-received
  clean/      bars/{freq}/{asset_class}/{venue}/{symbol}/{yyyy}.parquet     # adjusted, gap-filled, UTC
              ticks/{venue}/{symbol}/{yyyy-mm-dd}.parquet
  reference/  instruments.parquet, corporate_actions.parquet, calendars.parquet, fx_rates/{yyyy}.parquet
  features/   {feature_set}/{version}/{asset_class}/{yyyy}.parquet          # point-in-time, versioned
  results/    mlflow/ (runs, artifacts, tear sheets), optuna.db
  catalog.duckdb
```
Rules: UTC nanosecond timestamps, one row-group sort key (ts), ZSTD, write-once files with a manifest (source, hash, ingest time) so every backtest can be tied to the exact data version.

**Engine choice per use case:**
1. **Fast vectorized screening:** vectorbt 1.x with the Rust engine; Optuna 5 + purged/embargoed walk-forward splits; MLflow. For cross-sectional equity factor screens, zipline-reloaded Pipeline + alphalens-reloaded.
2. **ML strategies with out-of-sample discipline:** PyBroker (walk-forward + bootstrapped metrics) or a Polars → LightGBM pipeline evaluated with skfolio/alphalens.
3. **Event-driven validation with realistic execution:** NautilusTrader (pin to 1.231.0 until 2.0 is stable): fill models with `prob_fill_on_limit` < 1, L2 data where available, maker/taker fee models, MARGIN accounts for perps/forex, funding settlements. Everything that survives step 1 must pass here before live.
4. **Market-making/HFT-style research on crypto:** hftbacktest on L2 data.
5. **Live:** NautilusTrader for crypto/FX/IBKR with the same strategy code; freqtrade if you only trade crypto and want a batteries-included bot.

---

## 7. "Use X for Y"

| Need | Use | Not |
|---|---|---|
| Sweep 10k parameter combos across 500 symbols | vectorbt 1.x (Rust engine) | backtrader, Backtesting.py |
| Single-instrument rule sanity check in 5 minutes | Backtesting.py | anything heavier |
| ML strategy with walk-forward + bootstrap CIs | PyBroker | ad-hoc train/test splits |
| Cross-sectional US-equity factor research | zipline-reloaded Pipeline + alphalens-reloaded | vectorbt |
| Realistic execution simulation | NautilusTrader | vectorbt, bt |
| Order-book / market-making research | hftbacktest | NautilusTrader bar mode |
| Crypto bot with adaptive ML retraining | freqtrade + FreqAI | OctoBot |
| Same code backtest → live across CEX/DEX/IBKR | NautilusTrader | LEAN self-hosted unless you buy its data |
| Fully managed data + cloud backtests + live nodes | QuantConnect cloud | self-hosted LEAN with by-ticker data |
| Portfolio allocation across strategies | skfolio, Riskfolio-Lib, cvxportfolio | PyPortfolioOpt for CVaR/drawdown objectives |
| Tear sheets | quantstats, pyfolio-reloaded | quantstats-reloaded fork |
| Indicators | TA-Lib 0.7 wheels; pandas-ta-classic; Polars expressions | upstream pandas-ta, tulipy, finta |
| Return forecasting with foundation models | don't; use Chronos-2/TimesFM 2.5 for vol/volume features only | zero-shot price prediction |
| Storage: bars up to 500 GB | Parquet + DuckDB + Polars | TimescaleDB, InfluxDB 3 Core |
| Storage: live tick ingest + concurrent queries | QuestDB | kdb+, ClickHouse (unless > 1 TB) |
| Versioned DataFrame store | ArcticDB (check license) or PyIceberg | Lance |
| Parameter search | Optuna 5 with walk-forward objective | grid search on in-sample Sharpe |
| Experiment tracking | MLflow local server | W&B unless you want SaaS |
| Scheduling | cron → Prefect 3 | Airflow |
| Notebooks | marimo | Jupyter (except for ecosystem needs) |
| LLM agents | LLM-generated factor candidates scored by a deterministic backtester; NLP feature extraction | TradingAgents/ai-hedge-fund as a trading system |

---

## Sources
- https://github.com/polakowo/vectorbt · https://pypi.org/project/vectorbt/ · https://vectorbt.pro/features/overview/ (blocked)
- https://github.com/nautechsystems/nautilus_trader · https://github.com/nautechsystems/nautilus_trader/releases · docs/concepts/backtesting/fill-models.md · docs/concepts/backtesting/accounts-and-margin.md
- https://github.com/QuantConnect/Lean · https://github.com/QuantConnect/Documentation · https://www.quantconnect.com/pricing/ (blocked)
- https://github.com/stefan-jansen/zipline-reloaded · https://pypi.org/project/zipline-reloaded/
- https://github.com/mementum/backtrader · https://community.backtrader.com/topic/3702/is-backtrader-dead
- https://github.com/kernc/backtesting.py · https://github.com/edtechre/pybroker · https://github.com/pmorissette/bt · https://github.com/mhallsmoore/qstrader · https://github.com/cuemacro/finmarketpy · https://github.com/blankly-finance/blankly
- https://github.com/freqtrade/freqtrade · https://github.com/jesse-ai/jesse · https://github.com/hummingbot/hummingbot · https://github.com/Drakkar-Software/OctoBot · https://github.com/Lumiwealth/lumibot
- https://github.com/nkaz001/hftbacktest · https://github.com/barter-rs/barter-rs · https://github.com/microsoft/qlib · https://github.com/AI4Finance-Foundation/FinRL · https://github.com/ricequant/rqalpha
- https://python.financial/ · https://quanttradingtools.com/python-backtesting-frameworks/ · https://hasanjaved.me/blog/best-python-backtesting-libraries-2026/ · https://bullalert.ai/blog/best-python-backtest-engines-2026/
- https://github.com/ranaroussi/quantstats · https://github.com/stefan-jansen/pyfolio-reloaded · https://github.com/stefan-jansen/alphalens-reloaded · https://github.com/pmorissette/ffn · https://github.com/dcajasn/Riskfolio-Lib · https://github.com/PyPortfolio/PyPortfolioOpt · https://github.com/skfolio/skfolio · https://github.com/cvxgrp/cvxportfolio
- https://github.com/TA-Lib/ta-lib-python · https://pypi.org/project/pandas-ta/ · https://github.com/xgboosted/pandas-ta-classic · https://github.com/bukosabino/ta · https://github.com/blue-yonder/tsfresh · https://github.com/sktime/sktime · https://github.com/Nixtla/statsforecast · https://github.com/Nixtla/neuralforecast
- https://github.com/amazon-science/chronos-forecasting · https://github.com/google-research/timesfm · https://github.com/SalesforceAIResearch/uni2ts · https://arxiv.org/abs/2606.27100 · https://arxiv.org/pdf/2607.05291
- https://github.com/duckdb/duckdb · https://github.com/pola-rs/polars · https://github.com/man-group/ArcticDB · https://github.com/questdb/questdb · https://github.com/timescale/timescaledb · https://github.com/ClickHouse/ClickHouse · https://github.com/influxdata/influxdb · https://github.com/KxSystems/pykx · https://github.com/lancedb/lance · https://github.com/apache/iceberg-python
- https://github.com/PrefectHQ/prefect · https://github.com/dagster-io/dagster · https://github.com/apache/airflow · https://github.com/mlflow/mlflow · https://github.com/wandb/wandb · https://github.com/optuna/optuna · https://github.com/marimo-team/marimo
- https://github.com/TauricResearch/TradingAgents · https://github.com/virattt/ai-hedge-fund · https://github.com/AI4Finance-Foundation/FinRobot · https://github.com/AI4Finance-Foundation/FinGPT · https://github.com/microsoft/RD-Agent · https://github.com/LLMQuant/awesome-trading-agents
