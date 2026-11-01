# London Strategic Edge (londonstrategicedge.com) — site review, 1 November 2026

*Asked by the owner on 1 November ("so many layers and data"; "dig deep"; "keep a very broad mind, don't just
dismiss stuff"). Method: every URL in the site's five sitemaps was listed (about 2,700: ~100 product and tool
pages, ~110 glossary entries, ~1,000 directory pages, ~1,500 chart pages); the product pages were read, the
pages that only render in a browser were rendered and read; the API reference, the open-source Python client,
its changelog and its public bug list were read in full; the terms, the Companies House record and the outside
web were checked. No account was created: a key is the owner's to make. Nothing registered, nothing run.*

## 1. What it is, and who

A free market-data archive with a browser trading platform on top: live charts, a form backtester, an ML
studio on the company's GPUs, options chains, a screener, macro and COT pages, an economic calendar, and a
REST/WebSocket data API with an MIT-licensed Python client (`pip install lse-data`, v3.0 of 25 October 2026,
296 GitHub stars) and a desktop "LSE Terminal". Everything on the public site is free; the paid part is two
exchange feeds (CME Globex, Nasdaq TotalView) sold in "Lite" tiers whose prices are not published.

**The company.** London Strategic Edge Ltd, Companies House 16555440, incorporated **2 July 2025**, one
director (the founder, born July 2004 per the register; the team page says LSE Philosophy & Economics and
"Quantitative Trader at Optiver"), £1 of share capital, no share allotments on file, registered office moved
from Wakefield to a City Road mail address in February 2026, one confirmation statement "with no updates". The
team page lists five people (an ex-Two Sigma engineer claim among them) and an institutional form offering
"liquidity provision, Level 3 data, low latency infrastructure, pricing models". The company page says it
"raised £1.5M in November 2025"; the FAQ says "the company is self funded. Revenue comes from enterprise data
services and affiliate partnerships with regulated brokers" (the broker pages are affiliate pages). No filing
supports the raise, and the outside web holds nothing on the company at all: no press, no reviews, no forum
threads, an unclaimed CB Insights stub.

**Claims that disagree with themselves across the site:** 118,000 vs 227,000 datasets; "500 TB" vs "2.5+ PB";
"30+ years" vs "daily back to 2003" (the client changelog: US stocks 2003, FX 2009, crypto 2017; an open issue
shows ETF history starting 27 April 2026); 58 vs 33 cryptocurrencies (the crypto page lists 33); options
across 3,186 vs 592 vs 56 underlyings; 16,000+ vs 76,000+ vs 4,175 instruments.

## 2. The map — every section and what is actually there

| Section | What is there | Read how |
|---|---|---|
| Markets: forex, crypto, stocks, commodities, indices, futures | 62 FX pairs; 33 crypto pairs shown (BTC … USDC, quoted "/USD" on the page, `BTCUSDT` in the API, no venue named); 3,987 US/UK/CA stocks; 23 commodities (`XAUUSD`, `BCOUSD`, `WTICOUSD`: CFD-style symbols); 13–19 indices; 54 "futures" (candles only) | rendered |
| Charts `/chart/{SYMBOL}` | ~1,500 symbol pages, live candles, indicators, drawing tools | sitemap |
| Backtesting | a form builder (indicator conditions, stop, take-profit), a manual bar replay, and "Brue" scripts; equity curve, drawdown, Sharpe, profit factor, win rate, trade table; 50 jobs a day; **no cost model documented** on the site (Brue's own engine: next-bar-open fills, a commission flag, slippage) | pages, GitHub |
| ML Studio | LSTM, XGBoost, CatBoost, LightGBM, random forest, Transformer, ARIMA, Prophet, GARCH, CNN, GAN "and more" on their GPUs; 3 jobs a day; no validation method stated | page |
| ML signals | "PRISM" daily range forecasts, "XGStock" daily bias, sector sentiment, "a 20 model ensemble", refreshed every 15 minutes; **no track record published anywhere** | llms-full.txt |
| Economic calendar | NFP, CPI, FOMC and so on, 20+ countries, consensus and impact ratings; the vault "holds only current events" | page, changelog |
| Macro data | 14,640–18,694 series, 100–220 countries; bond yields 202 series / 120 instruments; a heat-map | page |
| COT | CFTC weekly, **39 instruments**, legacy categories (non-commercial / commercial / non-reportable), including CME bitcoin; dated to the report Tuesday | rendered |
| Options | live chains for US underlyings with IV, delta, volume, OI, max pain, put/call; a flow tape of prints with premium; greeks "computed twice a day"; option candles per contract | rendered, API |
| Order book, L2 order flow | the public pages are shells; the data is the paid Nasdaq TotalView (L2, L3) and CME Globex (L3) tiers | API reference |
| Screener, financial statements, insider trading, dividends | 50+ screener criteria; SEC statements; Form 4 buys and sells (**the rendered table repeats one NVDA transaction 26 times**); dividend and split history | rendered |
| Correlation matrix, model visualisation, Monte Carlo VaR, Kalman, gamma scalping, Avellaneda–Stoikov | interactive teaching tools | pages |
| Ship tracking | AIS vessel map | page |
| News, Research | news aggregation; the research section has **no articles** (two URLs, an empty contributors page) | rendered |
| Directory | ~1,000 SEO pages: brokers, data vendors, exchanges, funds, "trading influencers" | sitemap |
| Reference | ~110 microstructure glossary entries | sitemap |
| Education | 27 ML lessons (supervised to reinforcement learning, risk, portfolio), options lessons | page |
| Brokers, partnership | affiliate pages (Blueberry Markets, VT Markets) | pages |
| Falak thesis | an essay on the falling cost of model tokens; not about markets | page |
| LSE Terminal (GitHub, MIT) | a desktop IDE: Python strategies, walk-forward, Monte Carlo, GARCH/Kalman/HMM/LSTM; an assistant that is their hosted LLM or your own Claude/Codex over MCP; Brue Connect broker adapters, a demo account first | README |
| Brue (GitHub, v0.0.1) | a small trade-entry language: one script for backtest and live, conformance goldens, stdlib engine | README |
| Data API `download.londonstrategicedge.com/v3` | see §3 | reference |

**The API, as documented (docs/api.md in the client repo).** GET under `/v3`, key in `X-API-Key`. Free plan: nine
"included" markets (`us_stocks`, `uk_stocks`, `ca_stocks`, `forex`, `crypto`, `futures`, `indices`,
`commodities`, `us_options`), **candles only on the included markets** (trades, quotes, book and orders answer
`data-unavailable`; forex and commodities have no trade slice at all), 15 timeframes from `tick` to `1mo`,
split-adjusted by default, 60 calls a minute, 50 Mbit/s, one download at a time, a weekly allowance of about
12.5 GiB, exports as Parquet or CSV up to 1,000,000 rows with SHA-256 checksums and resumable jobs. Options:
chain and flow endpoints with IV and greeks (own key required). Macro: observations, releases, yields by
country. Reference: 18 collections (COT, insider trades, dividends, splits, statements, profiles, calendar).
Paid: `cme` and `nasdaq` from a "Lite" tier (candles, trades, quotes, L2, L3 by tier; history depth by tier;
500 Mbit/s). WebSocket: 16 symbols on a free key, four streams, 24-hour replay then live. Terms (19 January
2026): data use "in your own research, trading, models or internal work, including for commercial purposes, is
permitted and free of charge"; no redistribution; "market data is provided as is, without warranty of any
kind"; "use automated systems to access the platform without our permission" is listed as prohibited, so the
API is the permitted automation and page scraping is not.

## 3. Provenance and quality — what decides whether we can use it

- **The data is derived, not recorded.** The data page, in small print: *"Displayed prices are the output of
  our proprietary derivation algorithms, applied to independently sourced inputs."* The FAQ: public sources
  parsed by algorithms, cleaned, with *proxy instruments* where direct redistribution is not available. Forex
  and commodities have no prints because there are none: they are derived series under CFD-style symbols. Crypto
  is quoted in Tether with no venue named. US stocks and options are the one place where real prints are
  claimed (an NVDA Level-3 extract is described with exchange and receive timestamps), and those are behind
  the paid Nasdaq tier for anything below candles.
- **The public bug list of the client (August–October 2026)** reads like a data-quality log: spot tick delivery
  at ~2.5% of normal for three whole sessions; SPY and QQQ equity ticks absent for 78 minutes while option
  ticks flowed; bid and ask always null on option ticks; no same-day-expiry rows and a 500 on the filter;
  expired chains returned despite `min_dte`; a "huge candle" on EUR/USD daily; a volume field missing from a
  release; ETF history starting in April 2026.
- **On the page itself**, the insider table repeats one transaction 26 times and the crypto page shows 33 of
  the "58" coins. The research section is empty. The numbers in the marketing contradict each other (§1).
- **Nobody outside has checked it.** The company is sixteen months old, one director, no filings beyond
  incorporation, no press, no reviews.

**Verdict on provenance:** under this repo's rule (yfinance: prototyping only, never a system of record), LSE
belongs in the same class. It can be read for prototypes, cross-checks and for datasets no other free source
gives us. No registered run reads it as the record.

## 4. What this project can take from it — broad mind, honest value

1. **US options chains and flow with IV, greeks, OI and volume, free.** The only free options source reviewed
   in this project. Three uses, in order of value: (a) if **IBIT and ETHA** are among the underlyings (the
   list is 592 or 3,186 depending on the page; it needs a key to read), their chains are a second implied-vol
   surface for bitcoin and ether from a US-regulated venue, a **control σ** beside Deribit for the Programme 3
   wedge model; (b) **dealer gamma and expiry pinning on IBIT** is a mechanism with a named forced party
   (dealers hedging the retail book), a legitimate Programme 5 memo if the chain and OI data check out;
   (c) cheap event-vol reads for single stocks. Caveat: greeks "computed twice a day", option ticks with null
   quotes, and no dte = 0 rows, per the bug list.
2. **US equities at one minute and tick back to 2003, plus Form 4 insider filings and statements, free.** These
   are the point-in-time equity inputs Programme 2 paid Databento for. Two families become testable at $0 on
   IBKR's $0 commission: the **opportunistic-insider-purchase** family (Cohen, Malloy and Pomorski; filing
   timestamps make it point-in-time by construction) and the built-but-unregistered **index-deletion** family.
   Both need the QA pass in §5 first; both are new counters on the owner's yes.
3. **Forex, 62 pairs at one minute from 2009.** A new instrument class the owner can trade at IBKR; carry and
   momentum families are well studied there. But the FX series are derived, so this is prototype data only;
   IBKR's own history would be the record for anything registered.
4. **COT in one call, 39 markets including CME bitcoin.** We already build the TFF report from the CFTC
   directly (`qr/data/cot.py`); LSE carries the legacy categories only. A cross-check, nothing more.
5. **Macro, 14,640+ series, and sovereign yields.** FRED covers what we use (DTB3). Useful only for non-US
   series, which no current thread needs.
6. **Level 3 order data from Nasdaq TotalView and CME Globex.** The one institutional-grade thing here if it is
   what it says. Paid, price unpublished, outside the $0 rule; the estimate endpoint is open to any key, so the
   shape and size of a day of ES orders can be read before any money question is asked.
7. **The backtester, the ML studio, the signals, the "LLM trained on every backtest".** Nothing for us: no
   pre-registration, no cost model on the site, no gate statistics, no published track record. Our engine is
   stricter by construction, and every project finding so far says the instrument and the costs decide, not
   the model.
8. **LSE Terminal and Brue.** The design (one script for backtest and live, broker adapters, paper first) is
   what the stage-1 harness and the carry session already are; Brue's next-bar-open fill is coarser than the
   ledger. A comparison point, not a tool.
9. **WebSocket with 24-hour replay.** Our recorders capture what we need. If (1) proves out, IBIT option ticks
   could be recorded free on the box, standard library only, like the others.
10. **Education, glossary, directory.** Reading material. Nothing to take.

## 5. What using any of it would take — the stage 0 for a new source

1. The owner creates the free key (email sign-up, no card). It goes in `~/.qr/secrets.env` as `LSE_API_KEY`,
   never in chat; the client reads that variable. Claude never sees the value.
2. A $0, uncounted QA script (`scripts/lse_qa.py`, to be written only if the owner wants the key made):
   BTCUSDT one-minute candles for 13–30 October against the lake's Binance bucket (the system of record):
   coverage, bar-by-bar close differences, missing minutes; AAPL daily against a second source; the options
   underlyings list for IBIT and ETHA and one chain snapshot with its OI; the estimate endpoint on one day of
   ES orders to learn the paid tier's shape. Results appended here as §7.
3. Only after that would any family be drafted, and any family is a new counter on the owner's yes. Stay
   inside the API's limits (60 calls a minute, the weekly allowance); no page scraping.

## 6. Verdict

Not a system of record. A prototyping and cross-check source from a one-director, sixteen-month-old company
whose prices are derived from scraped public inputs with proxies, whose marketing numbers contradict each other,
and whose own bug list records whole-session delivery failures. Two of its datasets are nonetheless things no
other free source reviewed here provides: **US options chains and flow** (and, if IBIT and ETHA are there, a
second bitcoin vol surface and a dealer-hedging mechanism to test) and **US equities at one minute with Form 4
filings**. Worth the free key and the QA pass in §5. Not worth changing any live thread for.
