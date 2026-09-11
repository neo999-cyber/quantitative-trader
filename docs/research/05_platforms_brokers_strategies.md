# Platforms, Brokers, Strategy Sources and AI Workflows for a Solo Quant (September 2026)

**Method and honesty note.** The sandbox egress proxy blocked most vendor domains (quantconnect.com, quantrocket.com, norgatedata.com, interactivebrokers.com, alpaca docs, quantpedia.com, SSRN, arXiv). GitHub and PyPI were reachable. Pricing/status facts come from (a) search-result snippets of official pages and 2026 reviews, and (b) directly fetched GitHub/PyPI pages. Prior knowledge that could not be re-verified is marked **[unverified]**. Verify every price before paying.

---

## TOPIC A — Hosted platforms vs self-hosting

| Platform | Good at | Cost (2026) | Lock-in | Data quality | Solo-quant verdict |
|---|---|---|---|---|---|
| QuantConnect (cloud) | Multi-asset event-driven backtests, 20+ live brokers, huge dataset library | Free (512 MB node); Researcher $60/mo; Quant Trader $120/mo; Institution $1,080/mo; add-on nodes $24–$1,000/mo | Medium: LEAN is Apache-2.0 and runs locally, but the cheap clean data lives in their cloud | Good (survivorship-bias-free equities); local data costs extra | Best "buy" option; use LEAN CLI locally to keep an exit |
| LEAN CLI (local) | Same engine, Docker, local live to IBKR/Alpaca/Tradier/OANDA/Binance/Bybit/Kraken/Coinbase/Schwab/TradeStation… | Free (Docker); data via QC Data Library (paid) or Polygon/IBKR/ThetaData/Databento/CoinAPI | Low | Depends on your feed | Strong self-host core if you like LEAN's abstractions |
| QuantRocket | Docker-based, IBKR-centric, Zipline + Moonshot, survivorship-free US bundle | From ~$19.99/mo; free tier = 2007–2011 sample only | Medium | Good, US-centric | Fine if IBKR-first; smaller community |
| Blueshift (QuantInsti) | Free Python research/backtest, India-heavy | Free | High (cloud only) | Moderate | Skip unless trading NSE |
| Composer | No-code daily-rebalance logic | $40/mo | Very high | Daily closes only; 1 bp default slippage | Not a research platform |
| TradingView (Pine) | Charting, quick prototyping | Alerts need Essential+; Bar Magnifier needs Premium | High (Pine non-portable) | Backtester snapshots intrabar, not tick | Eyeballing, not validation |
| TradeStation / EasyLanguage | Mature desktop backtester, REST+FIX API | Free with funded account **[unverified]** | High | Decent | Only if you already trade there |
| MultiCharts | EasyLanguage-compatible desktop | $97/mo or $1,497–$1,997 lifetime; no data | High | Bring your own feed | Niche |
| NinjaTrader | Futures-first; C#; Kraken-owned ($1.5B, closed May 2025) | Free / $99 mo / $1,499 lifetime | High | Futures tick OK | Futures-only and Windows |
| MetaTrader 5 | Forex/CFD standard; MQL5 tester "every tick based on real ticks"; `MetaTrader5` PyPI 5.0.6180 (Sep 2026), Windows-only | Free from broker | High (MQL5); Python bridges the live terminal, not the tester | Tick quality broker-dependent | Forex execution/data tap only |
| cTrader | Open API (protobuf, MIT `OpenApiPy`), demo endpoints, Python cBots; FAQ now titled "Open API / MCP" | Free via Pepperstone, IC Markets | Medium | Broker tick/candle history | Better API story than MT5 for Python forex |
| AmiBroker + Norgate | Fastest desktop portfolio backtester; Norgate = delisted stocks + PIT index membership | AmiBroker Pro $369 one-time; Norgate ~$630/yr Platinum; Windows + NDU required | Medium | Excellent for daily US/AU equities | The classic swing-trader stack; cheapest high-quality daily-equity research rig |
| WealthLab 8 | C#/.NET, portfolio-level | $39/mo, $299–399/yr | Medium-high | Provider-dependent | OK for .NET people |
| RealTest (Marsten Parker) | Portfolio-level, multi-strategy, very fast, Norgate integration | $389 one-time + optional $159/yr | Medium | Norgate-grade | Best value desktop tool for daily-bar equity systems |
| Portfolio123 | PIT fundamentals screens + rolling backtests | Free; Screener $25/mo; Pro $83/mo | High (no raw export) | High | Fundamental-factor ideas you then re-test yourself |
| Numerai | Obfuscated-feature tournament; new staking from Jul 2026 | Free; stake NMR | None | N/A | Side income / ML practice |
| WorldQuant BRAIN | Alpha-expression simulator; IQC 2026 ($100k pool) | Free | Total (alphas belong to WQ) | Institutional | Learning tool; nothing transfers |
| CrunchDAO | DataCrunch: 60,000 USDC/yr prize pool | Free | None | Provided | Same category as Numerai |

**Self-hosting frameworks verified this session** (GitHub): NautilusTrader (28.8k stars, v2.0.0-rc, adapters for IBKR, Binance, Bybit, OKX, Coinbase, Kraken, dYdX, Deribit, Hyperliquid, Databento, Tardis); vectorbt (9.1k, optional Rust engine); zipline-reloaded; Qlib (48.5k); freqtrade (54.3k); Jesse (MIT, 8.4k); Hummingbot (20k+); pysystemtrade (GPL-3, moved to `pst-group` Jan 2026, last update Jul 2026; IBKR via ib_async); Lumibot (2.1k).

---

## TOPIC B — Execution / brokers with good APIs

### Stocks/options (US)

| Broker | API | Paper | Rate limits | Fees | 2025–26 changes |
|---|---|---|---|---|---|
| **Interactive Brokers** | TWS API (Python via **ib_async 2.1.0**, Dec 2025; IBKR docs say migrate from ib_insync); **Web API** (REST+WebSocket, OAuth 2.0); community `ibind` | Yes | Web API: 10 req/s; TWS: 50 msg/s **[unverified]** | ~$0.005/share, $1 min | **Official MCP** (Jul 28, 2026): `https://api.ibkr.com/v1/api/mcp-public`; works with Claude Code, Cursor, etc. Tool surface is *order instructions* (staged), alerts, watchlists, positions, price history — not autonomous execution. |
| **Alpaca** | REST + WebSocket; `alpaca-py` 0.44.0 (Aug 2026); official **Alpaca MCP server** (paper on by default) | Yes, free | Free: 200 req/min; Algo Trader Plus $99/mo: 10,000 req/min + SIP + OPRA | $0 stocks/options; crypto ~0.25% taker | Options incl. multi-leg; 52+ crypto pairs |
| **Tradier** | REST + streaming | Sandbox (15-min delayed) | 120 req/min | $0 stocks; $0.35/contract; Pro $10/mo | Cheap options-API broker |
| **TradeStation** | REST + FIX; simulator | Yes | Per-category quotas | Commission-free stocks | LEAN target |
| **Schwab (ex-TDA)** | Trader API, OAuth 2.0; `schwab-py` | **No paper trading** | 120 calls/min | Free | App approval takes days |
| **Robinhood** | Official **Crypto Trading API only** | No | n/a | Spread-based | No stocks/options API |
| **Webull** | OpenAPI; new `webull-openapi-python-sdk` (Apache-2.0); old SDK archived Jun 2026 | Test env referenced | Not published | Same as app | Thin docs |

### Crypto
- **CCXT**: 104+ exchanges, built-in rate limiter, `set_sandbox_mode(True)`; near-weekly releases; CCXT Pro (WebSockets) bundled.
- Exchange sandboxes: Binance/Bybit/OKX testnets; Coinbase sandbox; Kraken demo via support. Fees **[unverified]**: Binance 0.10%/0.10%, Coinbase Advanced ~0.40/0.60% lowest tier, Kraken Pro 0.25/0.40%, Bybit 0.10/0.10%, OKX 0.08/0.10%. US persons: Binance.US only; Bybit/OKX restricted.
- Self-hosted execution: freqtrade, Jesse, Hummingbot, NautilusTrader.

### Forex
- **OANDA v20**: free with practice account; community `oandapyV20` is what people use; streaming preferred over polling.
- **IG**: REST + Lightstreamer; `trading-ig`; DEMO intermittently unreliable.
- **FXCM**: no US retail; do not build on it.
- **Dukascopy**: JForex Strategy API is Java; free historical tick downloads via `dukascopy-python`, `duka`, `TickVault`.
- **Pepperstone/cTrader**: Open API + `OpenApiPy`, demo endpoints, Python cBots.
- **MT5 Python**: Windows-only; orders and history from the live terminal; not a backtester bridge.

---

## TOPIC C — Where validated ideas come from

| Source | What it is | Cost / status |
|---|---|---|
| Quantpedia | Encyclopedia of ~1,000 academic strategies with backtests | Paid tiers (~$499/yr **[unverified]**) |
| Papers With Backtest | `awesome-systematic-trading` (14.2k stars; claims **4,843 backtested strategies**; "median replication Sharpe 0.37, 48% clear t=1.96; median test window 34 yrs; need ≈(1.96/Sharpe)² years"), `pwb-toolbox` (MIT; datasets via HuggingFace or PWB API key), `pwb-alphaevolve` | Free code; paid API for parquet data |
| Open Source Asset Pricing (Chen & Zimmermann) | ~300 cross-sectional signals with code and returns | Free (`OpenSourceAP/CrossSection`) |
| JKP Global Factor Data | 150+ factors, 90+ countries | Free (jkpfactors.com / WRDS) |
| awesome-quant | 29.5k-star directory | Free |
| pysystemtrade (Carver) | Reference implementation of *Systematic Trading*: EWMAC 8/32, 32/128, carry, forecast scaling, vol targeting; docs show single-rule Sharpe 0.51, full system ≈0.53 | GPL-3, active |
| freqtrade-strategies / jesse example-strategies | Educational, "not ready to use" | Free |
| Hudson & Thames | mlfinlab (closed since 2023), arbitragelab, portfoliolab | Mixed |
| Sov.ai | open-investment-datasets, panel-ML; commercial datasets | Free + paid |
| SSRN, arXiv q-fin, Alpha Architect, Robot Wealth, QuantStart, Quantocracy, Quant SE, r/algotrading, AQR/Man research, López de Prado, Ernie Chan, Clenow, Connors, Masters | Blocked this session; from memory: Quantocracy and Alpha Architect remain active aggregators; Robot Wealth pivoted to a paid community; Chan runs PredictNow.ai; Masters's books remain the best sources for statistical validation. |

### Which classic anomalies still work post-publication (figures from memory **[unverified]**, canonical papers)

| Family | Post-publication status | Evidence |
|---|---|---|
| Cross-sectional momentum (12-1) | Alive but crash-prone; premium roughly halved OOS | McLean & Pontiff (JF 2016): ~26% lower OOS, ~58% post-publication; Daniel & Moskowitz (2016) crashes; JKP (JF 2023): most factors replicate, decay but don't vanish |
| Time-series momentum / trend following (futures, FX, crypto) | Alive; low Sharpe per market (~0.3–0.5), diversification does the work | Moskowitz–Ooi–Pedersen (2012); Hurst–Ooi–Pedersen "A Century of Evidence"; pysystemtrade docs (verified 0.51) |
| Crypto momentum / trend | Alive with fat tails; 1–4 week momentum and size factors | Liu, Tsyvinski & Wu (NBER w25882) |
| Short-term reversal (1-week/1-month) | Statistically alive, mostly *not tradable after costs* for retail; survives in liquid large caps with limit orders | Novy-Marx & Velikov (2016) |
| Connors-style RSI-2 / 3-down-days on index ETFs | Positive expectancy in ETF backtests; thin, regime-dependent; no peer-reviewed support | Practitioner backtests only; a flavor of short-term reversal in indices |
| Post-earnings-announcement drift | Decayed in large caps; persists in small/illiquid names and in revision momentum | Martineau (2021) "Rest in Peace PEAD" |
| Insider buying (opportunistic vs routine) | Alive for *opportunistic* clustered purchases in small caps | Cohen, Malloy & Pomorski (JF 2012) |
| Low volatility / BAB | Alive risk-adjusted; raw underperformance 2019–24 | Blitz & van Vliet (2007), Frazzini & Pedersen (2014) |
| Value | Deep drawdown 2018–20, strong 2021–22, mixed since | AQR |
| Quality / profitability | Among the most robust in JKP replication | Novy-Marx (2013), JKP |

Decayed/dead for retail: calendar effects, pure size premium, dividend-capture, simple pairs trading in US large caps, most single-indicator TA rules.

---

## TOPIC D — AI-assisted quant workflows in 2026 (kept honest)

**What practitioners actually use LLMs for (verified artefacts):**
- **Broker/data MCP servers**: IBKR official MCP (instruction-staging, alerts, watchlists, price history; single-account authorization); Alpaca official MCP (paper by default, explicit warning "this server can place real trades"); `financial-datasets/mcp-server` (MIT, 2.3k stars); Jesse MCP; cTrader "Open API / MCP"; QuantConnect docs `skills/` and "AI Assistance" section.
- **Code generation / research automation**: Microsoft RD-Agent(Q) (NeurIPS 2025) — LLM-proposed factors scored by Qlib backtests, with an explicit "not ready for any investment" disclaimer. `pwb-alphaevolve` applies evolutionary code search to strategies. vectorbt positions itself "for AI-driven trading workflows".
- **Agentic decision-making**: TradingAgents' own README: runs are non-deterministic, "backtest results are not guaranteed to match any published figure", and social/news inputs "reflect current time, not historical conditions" — the framework admits its backtests leak the future.
- **Everyday uses**: transcript/filings summarisation, literature triage, boilerplate for data loaders and backtest harnesses, converting Pine/AFL/EasyLanguage into Python, writing unit tests for signal code.

**Failure modes (ranked by damage):**
1. **Look-ahead in generated code**: same-bar close used for entry, `shift()` in the wrong direction, resampling that peeks at the period end, current index constituents.
2. **Look-ahead in the model itself**: an LLM "predicting" 2021 sentiment already knows 2021 outcomes (Sarkar & Vafa; Glasserman & Lin **[unverified]**); use anonymised text or models with cutoffs before the test window.
3. **Hallucinated data/APIs**: never let an LLM be a data source; only a code author against a real, versioned dataset.
4. **Overfitting at agent speed**: an agent iterating 200 variants on the same test set is p-hacking; needs a locked holdout, deflated Sharpe / permutation tests, and a strategy-count log.
5. **Non-determinism and silent drift** in agent decisions.
6. **Yahoo/yfinance dependence**: "intended for personal use only"; not a foundation for a live system.
7. **Security**: MCP servers holding live keys — paper accounts, scoped keys, read-only tokens; IBKR's staged-instruction design is the sane pattern.

---

## Recommendations

### Build vs buy per layer

| Layer | Recommendation | Why |
|---|---|---|
| **Data** | **Buy**, store locally in Parquet/DuckDB. Equities daily: Norgate. Intraday/futures/options: Databento and/or ThetaData; Massive as cheaper alternative. Crypto: exchange bulk + CCXT + Tardis for L2. FX: Dukascopy free ticks for research, broker feed for live. | Data is where hosted platforms lock you in |
| **Research** | **Build** on Python: Polars + vectorbt + own factor pipeline; Portfolio123/Quantpedia/PWB as *idea* feeds only | Research code is your IP |
| **Backtest** | **Adopt open source**: NautilusTrader (event-driven, same code for live) or LEAN CLI; RealTest ($389) as an independent second opinion for daily equity portfolios; never trust a single engine | Two engines that agree catch most look-ahead bugs |
| **Execution** | **Buy the broker, build thin adapters**: ib_async, alpaca-py, CCXT; or let NautilusTrader/LEAN own the adapters | Brokers change APIs |
| **Monitoring/ops** | Build small: Docker on a VPS, Telegram alerts, daily reconciliation vs broker statements (IBKR Flex) | Cheap and essential |

### Broker per asset class (solo trader)
- **US stocks/options**: Interactive Brokers (global reach, TWS + Web API + official MCP, real paper accounts). Alpaca as a second/simpler venue. Tradier if options-heavy. Avoid Schwab (no paper), Robinhood (no stock API), Webull (thin docs).
- **Futures/trend following**: IBKR (pysystemtrade-native).
- **Crypto**: Kraken or Coinbase Advanced (US-friendly) via CCXT/Nautilus; Binance/Bybit/OKX outside the US; Hyperliquid/dYdX for perps via Nautilus/Hummingbot.
- **Forex**: OANDA v20 (simplest REST, free practice) or a cTrader broker through Open API; IG for indices/CFDs too.

### Ten strategy families to test first (ranked by evidence × tradability)
1. **Diversified time-series momentum / trend following on futures and crypto** — century-long evidence; open reference implementation (pysystemtrade); low capacity constraints.
2. **Cross-sectional momentum with crash control** — robust in JKP replication; halved but positive post-publication; needs Norgate constituents.
3. **Quality/profitability tilts combined with momentum** — highest replication rates; slow turnover.
4. **Futures/FX carry and crypto funding-rate carry** — pysystemtrade carry rule; crypto basis is the same idea with a fatter left tail.
5. **Opportunistic insider-buying clusters** — Form 4 data is free; small-cap, event-driven, low correlation with 1–3.
6. **Low-volatility / BAB long-only sleeve** — portfolio ballast, not the main engine.
7. **Index/ETF short-term mean reversion (Connors RSI-2 / n-down-days)** — thin but persistent in liquid ETFs; test with realistic slippage and limit-order entries only.
8. **Earnings/revision momentum + call-transcript NLP** — classic PEAD decayed in large caps, but revision drift and small-cap PEAD persist; use pre-cutoff models.
9. **Crypto cross-sectional momentum and size** (weekly rebalance, top-50 by liquidity) — beware exchange listing survivorship.
10. **Statistical arbitrage / pairs in futures spreads and crypto** (not US large-cap equity pairs) — only with own L2 data and cost model.

Stop-lists: calendar effects, single-indicator TA rules, unfiltered short-term reversal in individual stocks, anything an LLM "found" without a locked holdout and a permutation test.

---

## Sources (selected)
- https://github.com/QuantConnect/Lean · https://github.com/QuantConnect/lean-cli · https://www.quantconnect.com/pricing/ · https://github.com/quantrocket-llc/quantrocket-client · https://www.quantrocket.com/pricing/
- https://github.com/QuantInsti/blueshift-demo-strategies · https://help.composer.trade/article/78-slippage-and-fees · https://www.tradingview.com/support/solutions/43000669285-what-is-bar-magnifier-backtesting-mode/
- https://ninjatrader.com/news/kraken-to-acquire-ninjatrader-introducing-the-next-era-of-professional-trading/ · https://www.multicharts.com/purchase/ · https://pypi.org/project/MetaTrader5/ · https://www.mql5.com/en/blogs/post/762517 · https://github.com/spotware/OpenApiPy
- https://brokersdb.com/learn/amibroker-review · https://pypi.org/project/norgatedata/ · https://norgatedata.com/realtest.php · https://www.mhptrading.com/ · https://enlightenedstocktrading.com/realtest-vs-ninjatrader/ · https://www.wealth-lab.com/Software/SubscriptionPlans · https://www.liberatedstocktrader.com/portfolio123-review/
- https://github.com/numerai/docs · https://www.worldquant.com/brain/iqc/ · https://docs.crunchdao.com/competitions/teams/rewards
- https://www.interactivebrokers.com/en/general/about/mediaRelations/7-28-26.php · https://pypi.org/project/ib-async/ · https://github.com/Voyz/ibind · https://www.interactivebrokers.com/campus/ibkr-api-page/webapi-doc/
- https://pypi.org/project/alpaca-py/ · https://github.com/alpacahq/alpaca-mcp-server · https://alpaca.markets/data · https://docs.tradier.com/docs/rate-limiting · https://api.tradestation.com/docs/fundamentals/rate-limiting/ · https://github.com/alexgolec/schwab-py · https://robinhood.com/us/en/newsroom/robinhood-crypto-trading-api/ · https://github.com/webull-inc/webull-openapi-python-sdk
- https://github.com/ccxt/ccxt · https://developer.oanda.com/rest-live-v20/best-practices/ · https://github.com/ig-python/trading-ig · https://github.com/fxcm/ForexConnectAPI · https://pypi.org/project/dukascopy-python/
- https://github.com/paperswithbacktest/awesome-systematic-trading · https://github.com/paperswithbacktest/pwb-toolbox · https://github.com/OpenSourceAP/CrossSection · https://github.com/bkelly-lab/ReplicationCrisis · https://github.com/wilsonfreitas/awesome-quant · https://github.com/robcarver17/pysystemtrade · https://github.com/pst-group · https://github.com/freqtrade/freqtrade-strategies · https://github.com/jesse-ai/example-strategies · https://github.com/hudson-and-thames · https://github.com/sovai-research
- https://github.com/financial-datasets/mcp-server · https://github.com/microsoft/RD-Agent · https://github.com/TauricResearch/TradingAgents · https://github.com/ranaroussi/yfinance
- Canonical papers (from memory): McLean & Pontiff 2016 JF; Jensen, Kelly & Pedersen 2023 JF; Chen & Zimmermann 2022; Daniel & Moskowitz 2016; Moskowitz, Ooi & Pedersen 2012; Hurst, Ooi & Pedersen; Liu, Tsyvinski & Wu NBER w25882; Cohen, Malloy & Pomorski 2012; Novy-Marx & Velikov 2016; Martineau 2021; Blitz & van Vliet 2007; Frazzini & Pedersen 2014.
