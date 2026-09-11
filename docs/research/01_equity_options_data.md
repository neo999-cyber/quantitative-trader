# Historical & Fundamental Data for Equities and Options — Vendor Landscape, September 2026

**Research constraints (read first).** The sandbox's egress proxy blocks direct fetches of every vendor domain (databento.com, massive.com, tiingo.com, eodhd.com, norgatedata.com, thetadata, orats, sec.gov, data.nasdaq.com, etc.) and most review sites; only GitHub/PyPI-style hosts were fetchable. Pricing below therefore comes from (a) search-engine-indexed vendor pages, (b) directly fetched GitHub/PyPI pages for client-library status, and (c) the QuantConnect documentation repository on GitHub. Anything not confirmed against a current page is marked **[unverified]**; treat those as "check before paying."

---

## 0. One-table summary (US equities focus)

| Vendor | Best for | Granularity / depth | 2026 price (individual) | Delisted stocks | PIT index members | PIT fundamentals | Python client | Budget verdict |
|---|---|---|---|---|---|---|---|---|
| **Databento** | Raw exchange-grade tick/L2/L3, OPRA | MBO/MBP/trades/1s/1m/1d; XNAS.ITCH from 2018; OPRA now ~10+ extra yrs | $199/mo Standard; or pay-per-GB; $125 free credits | Yes (raw feed, symbology) | No | No | Excellent (Apache-2.0, DBN, py3.10+) | Best per-dollar intraday; needs own adjustments |
| **Massive (ex-Polygon)** | Broad REST API, unlimited calls, options trades/quotes | 1-min/sec aggs, trades, quotes; 5/10/20+ yrs by tier | Stocks $29/$79/$199; options tiers similar [unverified] | Yes (tickers `active=false`, delisted_utc) | No | Partial (XBRL-derived financials) | Good (`massive` 2.8.0, MIT) | Good general-purpose mid tier |
| **Tiingo** | Cheapest reliable adjusted EOD | Daily EOD (many tickers to 1962), IEX intraday | Power $30/mo non-commercial; $50 commercial | Partial (keeps many delisted tickers) | No | Weak (add-on, not PIT) | Good (community, MIT) | Best <$50 daily source |
| **EODHD** | Global EOD + fundamentals in one bill | EOD 70+ exchanges, intraday, fundamentals, options | All-In-One $99.99/mo ($83.33/yr) | Yes (claims) | Yes, S&P 500 from Apr 2012 | No (snapshot) | Official lib stale (Dec 2024) | Good for global breadth, weak PIT |
| **Alpaca** | Broker + SIP minute bars | 1-min SIP bars since 2016; OPRA options | Free (IEX, 200 rpm) / $99 Algo Trader Plus | Patchy | No | No | Excellent (`alpaca-py` 0.44, Aug 2026) | Supplement, not a research DB |
| **Norgate** | Survivorship-bias-free daily DB + constituents | Daily; delisted from 1950 (25k+) | Platinum ~$52.50/mo (12-mo $630); Diamond $787.50/yr | Yes (best-in-class) | Yes (S&P/Russell/Nasdaq etc.) | Partial (200+ fields, not full history) | Good but **Windows-only** | Best value for daily backtests |
| **FirstRate Data** | One-time 1-min/tick bundles | 1-min from 2000; 16,302 tickers incl 7,000+ delisted | ~$300–1,000+ one-time; updates $59–99/mo | Yes | No (S&P bundle = ever-members) | No | None (CSV) | Good one-off intraday archive |
| **Kibot** | One-time 1-min/tick archives | 1-min from 1998; 18,000+ symbols incl delisted | $3,000 All-Stocks 1-min; $139/mo Premium | Yes | No | No | None (CSV/API) | Pricier than FirstRate |
| **Sharadar (Nasdaq Data Link)** | PIT fundamentals + prices + SP500 table | Daily since ~1998; SF1 fundamentals w/ filing dates | "Low hundreds/mo" bundle [exact price unverified] | Yes | Yes (SP500 table) | **Yes** (datekey, ARQ/ART vs MRQ/MRT) | Stale official client (Aug 2022) but works | Best PIT fundamentals under $300 |
| **QuantConnect** | Survivorship-free LEAN data, cloud/local | Tick→daily since 1998 (Algoseek) | $0.05/ticker-day minute; Security Master $600/yr; bulk minute $11,760/yr | Yes (map/factor files) | ETF constituents dataset | Coarse/Morningstar | LEAN CLI | Good if you live in LEAN |
| **Twelve Data** | Global multi-asset API | Daily full; intraday ~2 yrs | Grow $29 / Pro $99 | Weak | No | No | OK (MIT) | Not for US backtests |
| **Finnhub** | Free quotes/news/basic fundamentals | Candles now paid for US [unverified] | Free 60/min; premium ~$12–100 | Weak | No | No | Official (Jun 2026) | Skip for history |
| **Alpha Vantage** | Free small pulls; LISTING_STATUS | Daily/intraday; 25 req/day free | $49.99–$249.99/mo by rpm | LISTING_STATUS lists delisted | No | No | Many wrappers | Skip beyond free |
| **FMP** | Cheap broad fundamentals API | 30+ yrs statements; 300–3,000 rpm | Starter/Premium/Ultimate (approx $22–139/mo annual) [unverified] | Yes-ish | Historical constituents endpoint | No true PIT (has acceptedDate) | `fmpsdk` rebuilt Aug 2026 | Useful, but verify data |
| **yfinance** | Prototyping only | Daily/intraday (limited) | Free; Yahoo ToS personal-only | No (survivorship-biased) | No | No | 1.7.0 Aug 2026; rate-limit waves | Never for production research |
| **Stooq** | Free global daily CSV | Daily (some intraday) | Free, daily hit quota | No | No | No | pandas-datareader | Sanity checks only |
| **Intrinio** | Institutional-lite | Delisted prices from 2007 | From ~$250/mo | Yes | No | Standardized + as-reported | Official SDK | Over budget |
| **Barchart OnDemand** | Enterprise | Tick/min/EOD | From $500/mo; Excel add-in $69.95 | — | — | — | — | Over budget |
| **Xignite** | Acquired by QUODD (Feb 2023) | Enterprise | Quote-based | — | — | — | — | Reference only |
| **CRSP/Compustat (WRDS)** | Academic gold standard | Daily since 1925; delisting returns | Institutional only | Yes | Yes (Compustat index constituents) | Compustat Snapshot/PIT | `wrds` | Reference/academic |
| **Bloomberg / LSEG** | Reference | Everything | ~$25–30k/yr terminal | Yes | Yes | Yes | blpapi / LSEG Data Library | Reference only |

---

## 1. Price data vendors

### 1.1 Databento
- **Provides:** Raw, exchange-normalized US equities (XNAS.ITCH, XNYS.PILLAR, EQUS/DBEQ bundles, consolidated), OPRA options, CME futures. Schemas: MBO (L3), MBP-1/10, trades, TBBO, OHLCV-1s/1m/1h/1d, definitions, statistics, status. Nasdaq TotalView-ITCH history starts May 2018; the DBEQ/EQUS "free-to-license" bundle is newer. OPRA got "10 more years" of history in 2025.
- **2026 pricing:** Standard plan **$199/mo**: unlimited full-history OHLCV-1s/1m, definitions, statistics, status for US equities, plus 12 months of L0/L1 and 1 month of L2. **Usage-based historical (per-GB by schema) remains** and is the cheapest way to pull, e.g., a year of 1-min bars for a universe. **$125 free credits** for new accounts (6-month expiry; card required). Live OPRA usage-based pricing ended June 3, 2025.
- **License:** Unusually permissive: derived-use license with venues; DBEQ bundle carries $0 exchange license fees. Good for building a product later.
- **Python client:** `databento` (Apache-2.0, Python ≥3.10), DBN binary format, `to_df()`, live + historical clients; `Historical.metadata.get_cost()` prices a query before paying.
- **Quality reputation:** Widely regarded as the cleanest raw feed at retail prices; the price of that is *you* do symbology mapping and corporate-action adjustment (unadjusted exchange prints).
- **Verdict:** Best intraday/tick source for a solo quant; budget the $125 credits + per-GB pulls rather than the $199 plan unless you need continuous L1.

### 1.2 Massive (formerly Polygon.io)
- **Status:** Rebranded to Massive.com on **Oct 30, 2025**; APIs, keys and pricing continuous. Python package is now `massive` (v2.8.0, May 2026, MIT); legacy `polygon-api-client` still works.
- **Provides:** Stocks (aggregates, trades, quotes, snapshots, splits, dividends, tickers incl. delisted with `delisted_utc`, XBRL-derived financials), Options (contracts, aggregates, trades since 2016, quotes since 2022, chain snapshots with greeks/IV), indices, forex, crypto, futures.
- **2026 pricing (stocks):** Starter **$29/mo** (unlimited calls, 5 yrs, 15-min delayed); Developer **$79/mo** (10 yrs, second aggregates, trades); Advanced **$199/mo** (20+ yrs, real-time, quotes). Options tiers **[verify on massive.com/pricing]**.
- **License:** Individual plans are personal/non-commercial and prohibit redistribution [unverified for 2026].
- **Quality reputation:** Solid on aggregates; caveats: delisted-ticker coverage thins before ~2003; adjusted aggregates are split-adjusted only (apply dividends yourself); ticker-symbol reuse can bite.
- **Verdict:** Best "one API for everything" at $29–79; not survivorship-bias-free out of the box.

### 1.3 Tiingo
- **Provides:** Adjusted EOD for ~80k+ tickers (US history back to 1962 for long-lived names), IEX intraday, news, US fundamentals (add-on), crypto/FX. Keeps many delisted tickers.
- **2026 pricing:** Free tier (~50 req/hr); **Power $30/mo or $300/yr** (non-commercial); **Commercial $50/mo or $499/yr**.
- **Python:** `tiingo-python` (community, MIT, actively maintained).
- **Verdict:** The best sub-$50 daily-bar source; pair with a constituent history and a delisted list.

### 1.4 EODHD
- **Provides:** EOD for 70+ exchanges (150k+ tickers), intraday, fundamentals, dividends/splits, options, bulk downloads, index constituents with **point-in-time S&P 500 membership from April 2012**.
- **2026 pricing:** **All-In-One $99.99/mo ($999.90/yr)**; 100,000 calls/day, 1,000/min; personal-use only.
- **Python:** Official `eodhd` last released Dec 2024.
- **Verdict:** Best if you need *global* EOD in one bill; do not use its fundamentals for factor backtests without your own lag/restatement handling.

### 1.5 Alpaca Market Data
- **Provides:** SIP-consolidated minute/daily bars (from 2016), trades, quotes, snapshots, news, OPRA options, corporate actions.
- **2026 pricing:** **Basic free** (IEX-only real-time, 200 rpm); **Algo Trader Plus $99/mo** (full SIP real-time, OPRA, 10,000 rpm, 7+ years minute bars).
- **Python:** `alpaca-py` 0.44.0 (Aug 2026), Apache-2.0, Pydantic models — high quality.
- **Verdict:** Excellent for live/paper execution and cheap minute bars; not a backtest master.

### 1.6 Norgate Data
- **Provides:** US stocks & ETFs (plus AU/CA), daily only, **delisted securities since 1950 (25,000+)**, historically accurate index constituents (S&P 500/400/600, Russell 1000/2000/3000, Nasdaq 100, Dow), capital-event and total-return adjustment options, 200+ fundamental fields (snapshot), classifications. Delisted symbols get suffixes like `JAVA-201001`.
- **2026 pricing:** **Platinum** 12 mo $630 (≈$52.50/mo); **Diamond** $787.50/yr. Delisted + historical constituents require Platinum or above.
- **Python:** `norgatedata` 1.0.77 (Jul 2026), `price_timeseries`, `index_constituent_timeseries`, `capital_event_timeseries`. **Requires the Norgate Data Updater (Windows-only)**; Mac/Linux users run a Windows VM.
- **Reputation:** The de-facto standard for retail survivorship-bias-free daily backtests; complaints are the Windows dependency and daily-only granularity.
- **Verdict:** If you can tolerate Windows, this is the single best purchase under $60/mo.

### 1.7 FirstRate Data
- **Provides:** 1-min (and some tick) bundles; Complete Bundle covers **16,302 US stocks incl. 7,000+ delisted, from Jan 2000**. Unadjusted and adjusted files.
- **2026 pricing:** Per-bundle one-time purchases (S&P 500 components from $299.95; Russell 3000 from $399.95); then **$59–99/mo** for daily updates.
- **Verdict:** Cheapest way to own a delisted-inclusive 1-min archive; buy once, refresh with Databento pulls.

### 1.8 Kibot
- All Stocks 1-min (18,000+ symbols incl. delisted since 1998) **$3,000 one-time**; Premium subscription ~**$139/mo**. Verdict: only for pre-2000 minute history.

### 1.9 Nasdaq Data Link (Sharadar)
- **Provides:** SEP (equity prices incl. delisted, since ~1998), SF1 (Core US Fundamentals with `datekey` filing date and dimensions ARQ/ARY/ART vs MRQ/MRY/MRT), DAILY (market cap, EV, ratios), TICKERS (delisted flags), ACTIONS, **SP500 (historical membership)**, EVENTS (8-K), SF2 insiders, SF3 institutions.
- **2026 pricing:** "low hundreds of dollars per month" for the Core US Equities bundle **[exact figure unverified]**.
- **Python:** `nasdaq-data-link` 1.0.4 (Aug 2022) — old but stable; `get_table('SHARADAR/SF1', paginate=True)`; bulk export supported.
- **Verdict:** The only sub-$300 vendor with genuinely point-in-time fundamentals plus an S&P 500 membership table; the core of a "serious" stack.

### 1.10 QuantConnect data library (LEAN)
- Algoseek-sourced US equities tick→daily since 1998 with map files and factor files — survivorship-free when used through LEAN. **Pricing (verified from QC docs repo):** tick $0.06 and second/minute $0.05 per ticker-day file, hour $3 and daily $1 per ticker-year; **US Equity Security Master $600/yr**; bulk minute universe **$11,760/yr**. Verdict: excellent quality; bulk pricing is institutional; per-ticker daily files reasonable for a few hundred names.

### 1.11–1.16 Twelve Data, Finnhub, Alpha Vantage, FMP, yfinance, Stooq
- **Twelve Data:** Grow $29 / Pro $99; daily full history, intraday ~2 yrs; weak delisted coverage. Not for US backtests.
- **Finnhub:** free 60/min quotes/news/basic fundamentals; US historical candles moved behind paid access [unverified]. Skip for history.
- **Alpha Vantage:** free 25 req/day; **`LISTING_STATUS`** endpoint returns active and delisted symbols with dates — one of the few free delisting lists. Buy nothing.
- **FMP:** Free 250/day; Starter/Premium/Ultimate ~$22/$69/$139 [unverified]; legacy v3/v4 endpoints pulled; `fmpsdk` rebuilt Aug 2026. Fundamentals have `acceptedDate` but are restated snapshots. Validate against EDGAR.
- **yfinance:** 1.7.0 (Aug 2026); 2025 waves of `YFRateLimitError`; Yahoo ToS personal-only; no delisted tickers; silent adjustment backfill and price "repair". Prototyping only.
- **Stooq:** free daily CSV, daily hit quota; sanity checks only.

### 1.17 Intrinio, Barchart, Xignite, LSEG/Bloomberg
- Intrinio from ~$250/mo; Barchart OnDemand from $500/mo; Xignite acquired by QUODD (2023); Bloomberg/LSEG are the reference benchmarks. All over budget.

---

## 2. Survivorship bias, delisted stocks, point-in-time constituents, corporate actions

| Source | Delisted price history | PIT index constituents | Corporate actions | Cost |
|---|---|---|---|---|
| Norgate Platinum/Diamond | Since 1950, 25k+ names | Yes: S&P, Russell, Nasdaq, Dow | Yes | ~$52–66/mo |
| Sharadar (SEP + TICKERS + SP500 + ACTIONS) | Since ~1998 | S&P 500 only | ACTIONS table | low hundreds/mo [unverified] |
| QuantConnect/Algoseek | Since 1998 (map/factor files) | ETF-constituents dataset | Factor files | $600/yr master + per-file |
| FirstRate / Kibot | Since 2000 / 1998 | Only "ever-member" bundles (not dated) | Adjusted + unadjusted | One-time |
| Massive | `tickers?active=false`, ~20+ yrs on Advanced | No | Splits/dividends endpoints | $29–199/mo |
| EODHD | Claims delisted coverage | S&P 500 PIT from Apr 2012 | Splits/dividends | $99.99/mo |
| CRSP (WRDS) | Since 1925 with delisting returns | Via Compustat | Full | Institutional |
| Free: fja05680/sp500 | n/a | 1996→ (reliable from ~2001) | n/a | $0 |
| Free: hanshof/sp500_constituents | n/a | 1996→ daily snapshots (Wikipedia-derived) | n/a | $0 |
| Free: riazarbi/sp500-scraper | n/a | iShares 2006→, Wikipedia 2007→, queried daily | n/a | $0 |
| Alpha Vantage LISTING_STATUS | List only (dates) | n/a | n/a | $0 |

**Adjusted prices:** Tiingo, EODHD, Norgate, Sharadar, FirstRate/Kibot deliver adjusted series; Massive aggregates are split-adjusted only; Databento and Alpaca-raw are unadjusted.

---

## 3. Point-in-time fundamentals

- **Sharadar SF1** — the only retail-priced dataset built around the filing date (`datekey`) with as-reported (ARQ/ARY/ART) vs most-recent-restated (MRQ/MRY/MRT) dimensions. Always join on `datekey` (+1 day) with AR* dimensions; MR* leaks restatements.
- **FMP** — `acceptedDate` gives availability, but values are restated snapshots; lag by `acceptedDate` at minimum.
- **EODHD** — snapshots; not PIT.
- **Compustat/CRSP (WRDS)** — institutional only.
- **SEC EDGAR XBRL APIs (free):** `submissions`, `companyfacts` (every tagged fact per CIK with `filed`, `accn`, `fy`, `fp`, `form`, `frame`), `companyconcept`, `frames` (last-filed value — not PIT). Rate limit **10 requests/s**, mandatory User-Agent, nightly `companyfacts.zip` bulk file. Structured XBRL only from 2009 (smaller filers 2011); tags vary by company.
- **Open-source EDGAR tools:** **edgartools** 5.57.0 (Sept 2026), MIT, XBRL-standardized statements, rate limiter, MCP server — the clear winner. **sec-edgar-api** thin wrapper. **secedgar** downloader only. **OpenEDGAR** abandoned (2018).

---

## 4. Options history

| Vendor | Depth / granularity | Greeks / IV | 2026 price | Verdict |
|---|---|---|---|---|
| **ORATS** | EOD since 2007 for 5,000+ symbols; 1-min from Aug 2020; ticks from Sep 2022 | Yes — smoothed IV surfaces, greeks, earnings-adjusted | Data API from $99/mo; historical-inclusive $199–299/mo; **$2,000 one-time bulk 2015→** | Best historical IV-surface source under $300 |
| **Theta Data** | Options Value **$40** (4 yrs, 1-min), Standard **$80** (8 yrs, tick), Pro **$160** (12 yrs, full tick); free 30-day EOD | Computed on request | Requires local Theta Terminal (Java); new `thetadata` 1.0.10 (Aug 2026) | Best raw options history per dollar |
| **Massive options** | Trades since 2016, quotes since 2022 | Live snapshots only | ~$29/$79/$199 [unverified] | Good tape; build your own IV |
| **Databento OPRA** | ~10+ extra years; MBO recent | None (raw) | Standard $199/mo or per-GB | Best full-depth tape; expensive by volume |
| **CBOE DataShop** | EOD summary/quotes, intraday | Optional Calcs | EOD ad-hoc ~$400 per exchange-month; **academic discount** | Authoritative but pricey per pull |
| **OptionMetrics IvyDB** | 1996→, smoothed surface | Yes | Institutional via WRDS | Reference |

---

## 5. Free tiers and rate limits

| Source | Free tier | Rate limit |
|---|---|---|
| Databento | $125 credits (6 mo) | Bandwidth-bound |
| Massive | Free: 5 calls/min, 2 yrs history | Unlimited on paid |
| Tiingo | ~50 req/hr | Power ~5,000/hr commercial |
| EODHD | ~20 calls/day | 1,000/min, 100k/day paid |
| Alpaca | Free IEX + historical | 200 rpm free, 10,000 rpm paid |
| Twelve Data | 8 credits/min, 800/day | Grow 55/min, Pro 610/min |
| Finnhub | 60/min | 300/min paid |
| Alpha Vantage | 25/day | 75–1,200 rpm paid |
| FMP | 250/day | 300–3,000 rpm |
| SEC EDGAR | Unlimited free | 10 req/s, User-Agent required |
| Theta Data | 30 days EOD | Tier-dependent |
| Nasdaq Data Link | Free datasets only | ~300/10 s, 50k/day |

---

## 6. Recommended stacks

### Budget (<$50/mo)
1. **Tiingo Power ($30/mo)** — adjusted EOD, keeps most delisted names.
2. **SEC EDGAR via edgartools (free)** — build your own PIT fundamentals keyed on `filed`.
3. **fja05680/sp500 + riazarbi/sp500-scraper (free)** — S&P 500 membership from 1996/2006; cross-check the two.
4. **Alpha Vantage LISTING_STATUS (free)** — delisting dates to mask the universe.
5. **Databento $125 credits** — one-off 1-min pulls for a shortlist.
6. **Massive free tier** — splits/dividends/delisted flags for reconciliation.
*Stretch:* swap 1+3+4 for **Norgate Platinum (~$52.50/mo)** if you run Windows — strictly better.

### Serious ($100–300/mo)
1. **Norgate Platinum (~$52.50)** — survivorship-free daily universe + dated constituents.
2. **Sharadar Core US Equities bundle (~$100–150, verify)** — PIT fundamentals, SP500 table, ACTIONS.
3. **Theta Data Options Standard ($80)** — 8 yrs of tick options; or **ORATS Data API ($99–199)** for historical IV surfaces.
4. **Massive Stocks Starter ($29)** — unlimited-call reference API and 1-min bars for the last 5 years.
Total ≈ $260–300. Replace Massive with **Databento Standard ($199)** only if you need continuous intraday L1/L2.

### No-compromise (solo)
- **Databento** pay-per-GB full-depth equities + OPRA. **Norgate Diamond** + **Sharadar full bundle**. **ORATS + $2,000 bulk history**; **Theta Pro ($160)**. **QuantConnect Security Master ($600/yr)** as an independent cross-check of adjustments. If academically affiliated: **WRDS** as ground truth.

---

## 7. Survivorship and look-ahead traps by recommended source

- **Tiingo:** universe misses some delisted and early-history tickers; build your universe from a dated constituent list. Adjusted close is backfilled as dividends arrive, so cache raw close + adjustment factors.
- **Norgate:** fundamentals are current snapshots — not for factor backtests. Total-return adjustment (default) embeds dividends — switch to CAPITAL when modeling cash dividends explicitly.
- **Sharadar:** use AR* dimensions and `datekey`, never MR* or `calendardate`; lag SP500 membership one day; SEP starts ~1998.
- **Massive:** split-adjusted only; key on `composite_figi`/CIK not ticker; delisted history thins pre-2003; financials are restated snapshots.
- **Databento:** raw prints → you apply splits/dividends and symbol changes; XNAS.ITCH only from 2018; single-venue datasets under-report consolidated volume.
- **SEC EDGAR / edgartools:** `frames` is last-filed, not PIT; always filter `companyfacts` by `filed <= as_of`; coverage begins 2009/2011; amendments change values with later `filed` dates.
- **fja05680 / hanshof constituents:** Wikipedia-derived; first ~5 years unreliable; symbols are as-of-today spellings — map to historical symbols before joining prices.
- **Theta Data:** history depth is tier-gated (4/8/12 yrs); contracts that expired before tier depth are absent.
- **ORATS:** smoothed surfaces are model outputs, not tradable quotes; 1-min only from Aug 2020.
- **EODHD:** S&P 500 PIT membership only from April 2012; fundamentals restated.
- **FMP:** restated snapshots with `acceptedDate`; endpoint churn — pin `fmpsdk` ≥ 20260824.
- **QuantConnect:** survivorship-free only through LEAN's map/factor files; daily files are built from minute data.
- **yfinance / Stooq:** survivorship-biased by construction; never a system of record.

---

## Sources
- https://databento.com/pricing · https://databento.com/docs/faqs/usage-pricing-and-data-credits · https://databento.com/datasets/XNAS.ITCH · https://databento.com/datasets/OPRA.PILLAR · https://github.com/databento/databento-python
- https://massive.com/blog/polygon-is-now-massive · https://massive.com/pricing · https://massive.com/docs/rest/options/overview · https://github.com/massive-com/client-python
- https://www.tiingo.com/about/pricing · https://www.tiingo.com/documentation/ · https://github.com/hydrosquall/tiingo-python
- https://eodhd.com/pricing · https://eodhd.com/financial-apis-blog/sp-500-historical-constituents-data · https://pypi.org/project/eodhd/
- https://alpaca.markets/data · https://docs.alpaca.markets/us/docs/market-data-faq · https://pypi.org/project/alpaca-py/
- https://norgatedata.com/stockmarketpackages.php · https://norgatedata.com/data-content-tables.php · https://alvarezquanttrading.com/blog/norgate-data-review/ · https://concretumgroup.com/how-to-construct-a-survivorship-bias-free-database-in-norgate-using-python/ · https://pypi.org/project/norgatedata/
- https://firstratedata.com/ · https://firstratedata.com/about/FAQ
- https://www.kibot.com/buy.html · https://www.kibot.com/subscribe.html
- https://data.nasdaq.com/databases/SFA · https://data.nasdaq.com/databases/SEP · https://www.quantrocket.com/pricing/data/sharadar/ · https://github.com/Nasdaq/data-link-python
- https://www.quantconnect.com/docs/v2/lean-cli/datasets/quantconnect/download-by-ticker/costs · https://www.quantconnect.com/pricing/ · https://github.com/QuantConnect/Documentation
- https://twelvedata.com/pricing · https://finnhub.io/pricing · https://www.alphavantage.co/premium/ · https://site.financialmodelingprep.com/pricing-plans · https://pypi.org/project/fmpsdk/
- https://github.com/ranaroussi/yfinance · https://github.com/ranaroussi/yfinance/issues/2480
- https://intrinio.com/pricing · https://www.barchart.com/ondemand/api · https://a-teaminsight.com/blog/quodd-acquires-xignite-enhances-cloud-native-market-data-offering/
- https://github.com/fja05680/sp500 · https://github.com/hanshof/sp500_constituents · https://github.com/riazarbi/sp500-scraper · https://robotwealth.com/how-to-get-historical-spx-constituents-data-for-free/
- https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/center-for-research-in-security-prices-crsp/ · https://github.com/wharton/wrds
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces · https://github.com/dgunning/edgartools · https://github.com/jadchaar/sec-edgar-api · https://github.com/sec-edgar/sec-edgar · https://github.com/LexPredict/openedgar
- https://orats.com/data-api · https://docs.orats.io/ · https://www.thetadata.net/pricing · https://docs.thetadata.us/Articles/Getting-Started/Subscriptions.html · https://pypi.org/project/thetadata/
- https://datashop.cboe.com/option-eod-summary · https://datashop.cboe.com/academic-discount · https://optionmetrics.com/united-states/

**Verify on the live vendor pages before purchase:** Sharadar bundle price; Massive options tier prices and license text; EODHD single-purpose plans; FMP tiers; Finnhub candle access; Databento OPRA plan composition and per-GB rates; CBOE DataShop per-symbol pricing.
