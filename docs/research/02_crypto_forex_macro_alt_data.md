# Historical Data for Crypto, Forex, Macro and Alternative Data — Solo Quant Research Platform (Sept 2026)

**Verification note.** The sandbox's egress proxy blocked direct fetches of most vendor domains (tardis.dev, coingecko.com, coinapi.io, glassnode.com, dune.com, kraken docs, okx.com, polygon.io, twelvedata.com, databento.com, finnhub.io, FMP, unusualwhales.com, quiverquant, ortex, tiingo, tradingeconomics, finra.org, fred.stlouisfed.org). Figures for those come from search-engine snippets of the vendor pages and from 2026-dated secondary reviews; they are tagged **(secondary)** below and should be re-checked on the vendor page before you pay. Items tagged **(verified)** were fetched directly (Binance S3 bucket, GitHub READMEs, PyPI).

---

## 1. CRYPTO

### 1.1 Exchange-native APIs and bulk downloads

#### Binance — `data.binance.vision` (verified via S3 listing)
- **What is there (verified by listing the bucket):**
  - `data/` → `spot/`, `futures/` (`um/` USD-M, `cm/` COIN-M), `option/`.
  - **Spot daily/monthly:** `aggTrades`, `klines`, `trades`. BTCUSDT 1m monthly klines start **2017-08**. Kline intervals 1s…1mo. Spot timestamps are **microseconds from 2025-01-01** onward (a parsing trap).
  - **UM futures daily:** `aggTrades`, `bookDepth`, `bookTicker`, `indexPriceKlines`, `klines`, `markPriceKlines`, `metrics`, `premiumIndexKlines`, `trades`. **UM monthly** adds `fundingRate` (BTCUSDT `fundingRate` files run **2020-01 → 2026-08**).
  - `metrics` (open interest, OI value, top-trader and global long/short ratios, taker buy/sell volume, 5-min sampling) for BTCUSDT starts **2020-09-01** and is current through **2026-09-10**.
  - `bookDepth` (aggregated depth snapshots) for BTCUSDT starts **2023-01-01**.
  - **CM futures daily** additionally has `liquidationSnapshot`; the UM `liquidationSnapshot/BTCUSDT/` prefix returned no files in Sept 2026 (UM liquidation snapshots appear to have been discontinued — treat as gap).
  - **Option:** `BVOLIndex`, `EOHSummary` (end-of-hour options summaries) only; no per-contract options trades.
- Daily files appear next day; monthly files update the first Monday of the month; every zip has a SHA256 `.CHECKSUM`; official helper scripts in Python/shell (`binance-public-data` repo). Third-party downloaders: `binance-historical-data` (PyPI), `ltftf/binance-historical-data`.
- **REST API:** klines max 1000/request, aggTrades paginatable from id 0; the docs themselves point to data.binance.vision for bulk history.
- **License:** public, no key; Binance ToS governs. **Data-quality issues:** delisted symbols simply vanish from the "current symbol" lists but their historical zips *remain* in the bucket — use the S3 listing (not `exchangeInfo`) to build a point-in-time universe. Microsecond timestamp switch (2025). Binance.US/Binance.com split.
- **Verdict:** The single best free crypto dataset on earth for a solo quant — spot + perp OHLCV, trades, funding, OI/long-short, depth snapshots since 2017/2020/2023 at $0.

#### Bybit — `public.bybit.com` (secondary; domain blocked)
- Bucket folders: `trading` (perp tick trades), `spot`, `kline_for_metatrader4`, `premium_index`, `spot_index`. Third-party downloaders: `bybit-history` (PyPI), `Quantweb3-com/bybit-data-dump`, `nssanta/Bybit-Download-OrderBook-Trades-Klines` (adds order-book + Parquet), `ryu878/bybit_history_downloader`.
- REST v5 `market/kline` (up to 1000 candles/request per docs), `market/funding/history`, `market/open-interest`.
- **Verdict:** Second-best free perp tick-trade archive; use for cross-exchange perp research with Binance.

#### Kraken (secondary; docs blocked)
- **Bulk CSV (official support article):** OHLCVT zips for every pair from market inception, intervals 1/5/15/30/60/240/720/1440 min, hosted on Google Drive (main archive >7 GB, blocks automated download), **quarterly incremental updates**. Time-and-sales (trade) CSV archive also offered.
- **REST:** `OHLC` returns only the most recent ~720 candles — for deep history use the `Trades` endpoint paginated from `since=0` (full history back to 2013) and rebuild bars, or use the CSVs. `freqtrade` issues #4343/#8982 document converting the Kraken CSV format.
- **Verdict:** Best free *long-history* (2013+) spot archive for BTC/ETH majors; slow to refresh (quarterly).

#### Coinbase Advanced Trade / Exchange (secondary)
- Candles: Exchange API caps at **300 candles/request**; Advanced Trade `product_candles` caps at 350. No bulk archive; history available back to product listing; gaps where no ticks occurred (no empty candles). Wrappers: `cbhist`, `coinbase-advancedtrade-python`.
- **Verdict:** Fine for US-regulated spot reference prices; slow to backfill; no free tick archive.

#### OKX (verified endpoint constants; docs blocked)
- `python-okx` `consts.py` confirms: `/api/v5/market/history-candles`, `index-candles`, `mark-price-candles`, `/api/v5/public/funding-rate-history` (100 rows/request), `/api/v5/rubik/stat/contracts/open-interest-history`, `/api/v5/market/history-trades`. OKX changelog notes some public endpoints being throttled to 1 req/3 s.
- **Verdict:** Good for OKX-specific perps/options via REST; no bulk archive; paginate patiently.

### 1.2 CCXT (verified wiki manual)
- Unified `fetchOHLCV(symbol, timeframe, since, limit, params)`; exchange feature map exposes `fetchOHLCV: {paginate: true, limit: 1000}` style capabilities; set `params={'paginate': True}` (with `paginationCalls`/`maxEntriesPerCall`) for automatic backfill. Unified `fetchFundingRateHistory`, `fetchOpenInterestHistory`, `fetchTrades`, `fetchLiquidations` exist where the exchange supports them. `enableRateLimit=True` and per-exchange `rateLimit` override.
- **Known issues:** pagination quirks per exchange (issues #26252, #25285); some venues ignore `since`; `fetchTrades` depth is whatever the exchange REST gives (often days, not years). History depth = exchange's REST depth, so CCXT is a *convenience layer*, not an archive.
- **Verdict:** Use CCXT for incremental daily top-ups and small venues; use bulk buckets (Binance/Bybit/Kraken CSV) for the initial multi-year load.

### 1.3 Commercial crypto data vendors

| Vendor | Coverage / granularity | History | 2026 cost (as found) | Python | Verdict ($0–300/mo) |
|---|---|---|---|---|---|
| **Tardis.dev** (secondary) | Tick-level trades, L2 (and L3 where available) book updates, derivative ticker (funding/OI/mark/index), liquidations, options chains; 50+ exchanges | Varies by exchange (many from 2019–2020) | Reports conflict: "Starter $199/mo (3 exchanges, 10 symbols, 90-day history), Professional $599/mo" vs docs snippet "minimum order $300"; range $50–$900/mo | `tardis-dev` (replaces deprecated `tardis-client`); replay + CSV dataset download, local cache | Best L2 replay for the money but only *just* fits $300 for a narrow scope; buy a one-off historical CSV bundle for the specific exchange/symbols you need rather than a subscription. |
| **Kaiko** (secondary) | L1/L2 tick, aggregates, reference rates, 100+ exchanges, 35k pairs | Deep | $9.5k–55k/yr; L1 aggregations from $1,000/mo | REST/CSV | Out of budget; institutional only. |
| **Coin Metrics Community** (secondary + PyPI verified) | Free v4 endpoints: daily asset network/market metrics, reference rates, market candles/trades for a subset of exchanges | Daily metrics to asset genesis | Free, **no key**, 10 req / 6 s per IP; non-commercial CC license | `coinmetrics-api-client` 2026.9.2 (auto-pagination, pandas/polars) | Best free daily on-chain/market fundamentals; use for universe construction and reference rates. |
| **CoinDesk Data (ex-CryptoCompare/CCData)** (secondary) | 300+ exchanges, aggregated CCCAGG index, minute/hour/day histories, news, social | Long | **Free tier retired 21 May 2026**; all plans sales-led | REST | Migrate away; don't build on it. |
| **CoinGecko** (secondary) | 15k+ coins, exchange-aggregated prices/market cap/volume; OHLC granularity auto-scaled | Demo 1 yr; Basic 2 yr; Analyst+ to 2013 | Demo free (10k calls/mo), Basic $35/mo, Analyst $129/mo, Lite $499 | Community `pycoingecko` | Good for *universe/market-cap/listing dates* (survivorship control), not for backtest price series — aggregated, no exchange-specific fills. |
| **CoinAPI** (secondary) | 380+ exchanges, trades/quotes/L2/OHLCV; Flat Files (S3-style CSV, hourly partitions since 2026-06-09) | Deep | Usage-based; $25 free credits | REST + flat files | Reasonable pay-per-GB for filling gaps (small venues, delisted pairs); watch data-transfer bills. Their blog documents delisted-market listing for survivorship-free universes. |
| **Amberdata** (secondary) | Spot/derivatives/options/vol surfaces, on-chain | Deep | Quote only | REST | Out of budget for API. |
| **Glassnode** (secondary) | On-chain + market + derivatives metrics | Standard free = basic metrics; Advanced $49/mo (**Light API 50 calls/day**); Professional ≈$999/mo | `glassnode` REST | Advanced's 50-call/day API is unusable for pipelines. Use Coin Metrics community for daily on-chain instead. |
| **Dune** (secondary) | SQL over decoded chains | — | Free tier became **view-only from 10 Sept 2026**; Analyst $65/mo annual, Plus $349/mo annual (API) | `dune-client` | Only if you need DEX/DeFi microdata; otherwise skip. |
| **Coinglass** (secondary) | Aggregated funding OHLC, OI OHLC, liquidations, long/short, ETF flows across 30+ exchanges; API v4 | Multi-year per plan | Tiered API (entry tiers historically ~$29–$79/mo) | REST | Convenient *cross-exchange* funding/OI history; cheaper to rebuild from Binance/Bybit/OKX buckets for the big three. |

**Funding / open-interest history, free route:** Binance `fundingRate` (monthly, 2020→) + `metrics` (5-min OI, 2020-09→); Bybit `premium_index`; OKX `funding-rate-history` + `rubik` OI history; CCXT `fetchFundingRateHistory` for incremental.

**Survivorship in crypto universes.** Binance ran three delisting phases in April 2026 (17 tokens) and delisted six more on 17 Aug 2026. Secondary estimates put survivorship inflation at 5–15%/yr. Remedies: build the universe from the **S3 bucket listing** of historical zips (delisted pairs remain), from CoinGecko/CoinMarketCap *inactive* coin lists (one dataset cites 18,622 active vs 29,230 inactive coins), or CoinAPI's delisted-symbol metadata; record listing/delisting dates and only include a symbol from its listing date +N days.

---

## 2. FOREX

### 2.1 Free tick/minute sources

| Source | Coverage | Granularity | History | Cost / license | Python | Quality issues | Verdict |
|---|---|---|---|---|---|---|---|
| **Dukascopy** (bi5 tick files) | 1,000+ instruments: FX, metals, indices CFDs, stocks, ETFs, crypto CFDs | Tick (bid/ask + volume), any resampling | Majors typically to ~2003 | Free, no account; expect 429/503 throttling | `duka`, `dukascopy-python` (UTC index, bid/ask side), `TickVault` (resume, gap detection, backoff), Node `dukascopy-node` | Swiss ECN/retail quotes; "volumes" are Dukascopy-book volumes; UTC timestamps; occasional gaps | **Best free FX tick source**; the default for a solo quant. |
| **HistData.com** | 60+ instruments | Tick (bid/ask, no volume) and M1 | 15+ years | Free (manual per-month download; scripted downloaders exist) | community scrapers | **Timezone = EST without DST** (fixed UTC-5 all year) — must convert; M1 gaps | Good cross-check; not tick-quality. |
| **TrueFX** | 15–16 majors | Tick, ms timestamps, bid/ask | From 2009 | Free registration; monthly CSV | `tickterial`, curl scripts | Aggregated from bank/ECN feed; no volume | Best *interbank-style* free tick feed for majors; reconcile Dukascopy vs bank quotes. |

### 2.2 Broker/vendor APIs

- **OANDA v20** (secondary): `instruments/candles` returns up to **5000 candles/request** (S5→M), bid/ask/mid, `dailyAlignment`/`alignmentTimezone` params let you build NY-17:00-close daily bars; practice account is enough for data; `oandapyV20` with `InstrumentsCandlesFactory` auto-chunks. **Verdict:** best free *API* for FX bars aligned to a real broker's rollover; not tick.
- **FXCM** (secondary; status unresolved): could not verify 2026 REST availability for new retail accounts. **Verdict:** do not build on it.
- **Massive (formerly Polygon.io; rebranded early 2026)** (secondary): Currencies product = forex + crypto, 1,000+ pairs; pricing "in transition" during rebrand. FX from a single aggregator feed, minute bars. **Verdict:** convenient if you already pay Massive for stocks; not worth it for FX alone.
- **Twelve Data** (secondary): Basic free (8 req/min, ~800/day), Grow from $29/mo; 20+ years of daily FX even on free. **Verdict:** cheapest "one API for stocks+FX+crypto daily bars"; FX intraday depth limited on low tiers.
- **Databento** (secondary): **No spot FX dataset.** FX exposure is via **CME Globex MDP3 (`GLBX.MDP3`)** — 6E/6J/6B/6A/6C/6S/6N/6M futures and options, full MBO/MBP-10/trades/OHLCV; usage-based per-GB pricing with free signup credits. **Verdict:** the *no-compromise* way to get exchange-quality, timestamped FX price discovery (futures) for $0–100/mo of usage.
- **Finnhub** (PyPI verified): `forex_candles('OANDA:EUR_USD', ...)`, `crypto_candles('BINANCE:BTCUSDT', ...)` on the free tier (60 calls/min). Good secondary sanity check.

### 2.3 Structural FX pitfalls
- **Interbank vs retail quotes:** Dukascopy/OANDA/HistData are dealer or ECN-retail quotes; TrueFX is bank-aggregated; EBS/LSEG Matching/LMAX are the real interbank venues (expensive). Spreads widen sharply 16:30–17:15 ET around rollover and on Sunday open; backtests on one broker's ticks are broker-specific. CME FX futures (Databento) give exchange-consolidated prints as a neutral reference.
- **Weekend gaps:** market runs Sun 17:00 ET → Fri 17:00 ET; 10–50-pip Sunday gaps on majors after weekend news; brokers differ in open/close by up to an hour. Never fill weekend bars; model gap risk explicitly for swing holds.
- **Timezone conventions:** Dukascopy = UTC (naive resampling produces a Sunday stub bar and 6 "daily" bars/week); HistData = EST fixed; OANDA lets you set NY 17:00 alignment; MT4 servers often use UTC+2/+3 "NY-close" charts. Store everything in UTC, then derive NY-close daily bars via a rollover offset that follows US DST.

---

## 3. MACRO

| Source | Coverage | Access / limits | Python | Notes / verdict |
|---|---|---|---|---|
| **FRED / ALFRED** | 800k+ series; ALFRED holds every vintage | Free API key; `realtime_start`/`realtime_end`/`vintage_dates` params | `fredapi` (verified: `get_series_first_release`, `get_series_as_of_date`, `get_series_all_releases`, `get_series_vintage_dates`), `pandas-datareader` | **Must** use ALFRED vintages for any macro signal; latest-vintage GDP/NFP/CPI is look-ahead. |
| **BLS API v2** | CPI, CES, LAUS, JOLTS | Free key: 500 queries/day, 50 series/query, 20 yrs/query | wrappers | No vintages — use ALFRED for real-time values. |
| **US Treasury** | Daily par yield curve, bill rates, real yields | CSV/XML per year; Fiscal Data API | `requests`/pandas | Free, authoritative; also in FRED (DGS*). |
| **ECB Data Portal** | Euro-area rates, FX refs, HICP | SDMX 2.1 REST, free | `ecbdata`, `sdmx1` | ECB daily FX reference rates (EXR) are a clean, free FX daily fixing series. |
| **Bank of England IADB** | UK rates, gilts, FX | CSV via parameterised URL | none official | Trivial to wrap. |
| **OECD Data Explorer** | MEI, CLI, QNA | SDMX REST, free | `sdmx1` | Slow API; DBnomics mirror easier. |
| **DBnomics** | Aggregates ECB, IMF, Eurostat, WB, OECD, BLS, INSEE into one API | Free | `dbnomics` 1.2.7 | Best single-key macro fetcher; no vintages for most providers. |
| **Trading Economics** (secondary) | 150+ countries, ~1,600 calendar events/mo with actual/forecast/consensus | Standard $149/mo, Professional $299/mo (billed yearly) | `tradingeconomics` | Only paid calendar with clean historical consensus within budget; some "consensus" is TE's own model forecast — separate the two fields. |
| **Economic calendars with historical surprises** | Finnhub `calendar_economic` (free tier; deep history gated), FMP economic calendar (paid), Econoday (institutional), Investing.com (no API; scrapers break and violate ToS), Forex Factory (no API) | — | — | Prefer TE or Finnhub/FMP, and store *first-reported* actuals with release timestamps yourself going forward. |

---

## 4. ALTERNATIVE DATA (swing-trader relevant)

**Options flow**
- **Unusual Whales** (secondary): platform from $50/mo; **API billed separately** (free 1-week trial; 100+ endpoints: flow alerts, dark pool, GEX, Greeks, congress/insider); historical full-market option trades $250/mo. Verdict: the only retail-priced options-flow *API*; realistic all-in ~$100–300/mo.
- **Cheddar Flow** $85–99/mo, **FlowAlgo** $149/mo — UI products, no public API. Skip for a platform.
- **Quiver Quant API** (verified README + secondary): Hobbyist $30/mo, **Trader $75/mo adds Insider (Form 4), 13F changes, ETF holdings, WSB**; `quiverquant` pip.

**Insider trades**
- Free/authoritative: SEC EDGAR Form 4 XML + `edgartools` 5.57 (Sept 2026; `Company("TSLA").get_filings(form="4")`, handles SEC user-agent/rate limits), sec-api.io structured Form 4 dataset (paid), EODHD insider API (paid). Verdict: parse EDGAR yourself with `edgartools`; buy Quiver Trader only if you want it pre-cleaned.

**Short interest**
- **FINRA Equity Short Interest** (secondary): bi-monthly, free JSON/CSV via `api.finra.org` (free developer account). **Ortex**: Basic $39/mo, Advanced $129/mo (real-time SI, options, insiders). **S3 Partners**: enterprise. Verdict: FINRA free for the bi-monthly print; Ortex Advanced if you need daily borrow/utilisation.

**13F**
- SEC publishes free structured Form 13F data sets; `edgartools` parses `13F-HR` holdings. **WhaleWisdom**: Standard $300/yr (API). Verdict: SEC + edgartools is enough; 45-day filing lag makes 13F a slow signal anyway.

**Earnings-call transcripts**
- **FMP** (secondary): transcripts + dates endpoints on paid plans. **Alpha Vantage** `EARNINGS_CALL_TRANSCRIPT` (premium key). **Quartr**: API is B2B. **Seeking Alpha**: ToS prohibits scraping. Verdict: FMP is the pragmatic transcript API at solo budgets.

**News / sentiment**
- **GDELT 2.0**: free raw 15-minute CSV drops and BigQuery tables; tone scores; global, not ticker-tagged. **Finnhub**: free 60 calls/min company news + `news_sentiment`, ticker-tagged. **Tiingo News**: 3 months queryable history on standard plans. **Benzinga**: free Basic tier (headlines) on AWS Marketplace. **NewsAPI.org**: 1-month history on free tier — useless for backtests.

**Reddit / X**
- **Pushshift**: dead for the public since May 2023; successor **Project Arctic Shift** (monthly dumps). **Reddit Data API**: free 100 QPM personal; commercial ~$12k/mo minimums. **X API**: pay-per-use (Feb 2026), $0.005/read; **full-archive search is Enterprise-only ($42k+/mo)**. Verdict: historical social sentiment is effectively unavailable to a solo quant except via Arctic Shift dumps or Quiver's WSB counts.

**Google Trends**
- `pytrends` archived **17 Apr 2025**. Official Google Trends API is application-gated alpha. Maintained fork: `trendspy`. Trends values are sampled and re-normalised per query window — pull overlapping windows and chain-scale.

---

## 5. Recommended stacks

### Crypto
| Tier | Stack | ≈ Monthly |
|---|---|---|
| **Budget ($0)** | Binance S3 bulk (spot+UM klines/aggTrades/fundingRate/metrics/bookDepth) + Bybit public bucket + Kraken quarterly CSV for 2013+ + CCXT for daily top-ups + Coin Metrics Community + CoinGecko Demo for listing/delisting metadata | $0 |
| **Serious ($100–300)** | Budget stack + Coinglass API entry tier + CoinGecko Basic/Analyst ($35–129) + one-off Tardis CSV bundle for the 2–3 perps you trade + CoinAPI pay-as-you-go for delisted/small-venue gaps | ~$150–300 |
| **No-compromise** | Tardis Professional (L2 replay) + Coin Metrics Pro or Kaiko L1 + Glassnode Professional + Amberdata derivatives | $1.5k–5k+ |

### Forex
| Tier | Stack | ≈ Monthly |
|---|---|---|
| **Budget ($0)** | Dukascopy ticks via `dukascopy-python`/`TickVault` + TrueFX monthly ticks (2009+) + OANDA practice v20 for NY-17:00-aligned daily/H1 bars + HistData M1 as a third opinion + ECB/FRED daily fixings | $0 |
| **Serious ($50–300)** | Budget stack + Databento GLBX.MDP3 CME FX futures (usage-based) + Twelve Data Grow ($29) or Massive Currencies + Trading Economics Standard ($149) for historical consensus calendar | ~$100–300 |
| **No-compromise** | LSEG Tick History / EBS or LMAX historical L2 + Databento full CME FX depth + Econoday/Bloomberg calendar with revision history | $1k–10k+ |

Macro/alt add-ons at any tier: FRED/ALFRED (vintages), DBnomics, FINRA short interest, SEC EDGAR via `edgartools`, Finnhub free news/sentiment, GDELT — all $0. First paid alt-data dollars: Quiver Trader ($75) or Unusual Whales API (~$100+).

---

## 6. Key pitfalls (cross-asset)
1. **Survivorship** — crypto delistings are frequent; build universes from historical bucket listings or inactive-coin lists, never from today's `exchangeInfo`. Same for FX CFDs/exotics removed by brokers.
2. **Exchange-specific prices** — BTC on Binance, Coinbase, Kraken and Bybit differ by bps to % during stress; funding/mark/index prices are venue-defined; aggregates are not tradable. Backtest on the venue you will execute on, and store `mark`, `index` and `last` separately.
3. **Look-ahead in economic calendars** — scraped calendars show *revised* actuals and *final* consensus; store first-print actual, consensus at T−1 and the release timestamp.
4. **Macro vintages** — use ALFRED; NFP, GDP, CPI revisions are large enough to flip signals.
5. **Timestamp/timezone traps** — Binance microseconds since 2025-01-01; HistData fixed EST; Dukascopy UTC; broker NY-close conventions; crypto is 24/7.
6. **Retail vs interbank FX quotes; spread regimes** — keep bid and ask (never mid-only) for FX, and do not fill weekend gaps.
7. **Free tiers evaporate** — CryptoCompare/CoinDesk free API (May 2026), Dune free credits (Sept 2026), X Basic/Pro (2026), pytrends/Pushshift already gone. Architect ingestion so any vendor is replaceable and cache raw pulls locally (Parquet).
8. **Rate limits & ToS** — Coin Metrics 10 req/6 s, BLS 500/day, SEC 10 req/s with user-agent, Dukascopy 429/503.
9. **CCXT is not an archive** — do bulk loads from buckets/CSVs and use CCXT only for the delta.

---

## Sources
- https://github.com/binance/binance-public-data
- https://data.binance.vision/
- https://pypi.org/project/binance-historical-data/
- https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/market-data-requests
- https://pypi.org/project/bybit-history/
- https://github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines
- https://bybit-exchange.github.io/docs/v5/market/kline
- https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data
- https://docs.kraken.com/exchange/guides/general/historical-data
- https://concretumgroup.com/how-to-get-free-full-crypto-intraday-data-2013-2025-from-kraken/
- https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
- https://raw.githubusercontent.com/okxapi/python-okx/master/okx/consts.py
- https://raw.githubusercontent.com/ccxt/ccxt/master/wiki/Manual.md
- https://github.com/ccxt/ccxt/issues/26252
- https://tardis.dev/ · https://docs.tardis.dev/faq/billing-and-subscriptions
- https://www.kaiko.com/products/data-feeds/l1-l2-data
- https://gitbook-docs.coinmetrics.io/packages/coin-metrics-community-data
- https://pypi.org/project/coinmetrics-api-client/
- https://www.coingecko.com/en/api/pricing
- https://www.coinapi.io/products/flat-files/pricing
- https://www.coinapi.io/blog/how-to-eliminate-survivorship-bias-in-crypto-backtesting
- https://data.coindesk.com/blogs/changes-to-coindesk-data-indices-api-free-tier-access
- https://glassnode.com/pricing/studio
- https://cryptobriefing.com/dune-free-plan-view-only-access/
- https://www.amberdata.io/pricing
- https://www.coinglass.com/pricing
- https://en.cryptonomist.ch/2026/08/11/binance-token-delisting-six-tokens/
- https://concretumgroup.com/building-a-survivorship-bias-free-crypto-dataset-with-coinmarketcap-api/
- https://github.com/giuse88/duka · https://pypi.org/project/dukascopy-python/
- https://raw.githubusercontent.com/keyhankamyar/TickVault/main/README.md
- https://www.dukascopy-node.app/
- https://www.histdata.com/f-a-q/data-files-detailed-specification/
- https://www.truefx.com/truefx-historical-downloads-2/
- https://oanda-api-v20.readthedocs.io/en/latest/contrib/factories/instrumentscandlesfactory.html
- https://fxcm-api.readthedocs.io/en/latest/fxcmpy.html
- https://twelvedata.com/pricing
- https://databento.com/catalog/cme/GLBX.MDP3/futures/6E
- https://ftmo.com/en/blog/why-you-should-watch-out-for-weekend-gaps-in-forex/
- https://raw.githubusercontent.com/mortada/fredapi/master/README.md
- https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- https://blsapi.readthedocs.io/en/latest/
- https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rate-archives
- https://data.ecb.europa.eu/help/getting-data-web-services-sdmx
- https://www.bankofengland.co.uk/boeapps/database/help.asp
- https://docs.db.nomics.world/web-api/
- https://tradingeconomics.com/api/pricing.aspx
- https://finnhub.io/docs/api/economic-calendar
- https://site.financialmodelingprep.com/developer/docs/economic-calendar-api
- https://pypi.org/project/investpy/
- https://unusualwhales.com/pricing · https://unusualwhales.com/public-api
- https://api.quiverquant.com/pricing/
- https://pypi.org/project/edgartools/
- https://sec-api.io/datasets/form-4
- https://www.finra.org/finra-data/browse-catalog/equity-short-interest
- https://public.ortex.com/ortex-pricing/
- https://whalewisdom.com/help/api
- https://site.financialmodelingprep.com/developer/docs/stable/search-transcripts
- https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/
- https://finnhub.io/docs/api/news-sentiment
- https://www.tiingo.com/documentation/news
- https://www.redditapis.com/pushshift-alternative
- https://postproxy.dev/blog/x-api-pricing-2026/
- https://github.com/GeneralMills/pytrends · https://pypi.org/project/trendspy/
