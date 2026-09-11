# Websites from social media (user-submitted, set 1)

Seven sites from a short-form video. The test for each: does it expose **historical, point-in-time data through an API** we can put in the lake and backtest? A dashboard you can only look at today is a discretionary aid, not platform input. Coinalyze's API docs were blocked from the sandbox; that row is marked verify.

| # | Site | What it is | API / history | Verdict | Where it goes |
|---|---|---|---|---|---|
| 1 | **cryptofundraising.in** (the video's spelling; the database is crypto-fundraising.info) | Database of 5,000+ private funding rounds and 7,000+ investors; paid API "customised per client" | Historical rounds with dates; API is bespoke/paid; no self-serve pricing found | **SKIP for the trial.** Weak, slow signal for spot trading; "VC-backed" is at best a universe filter for alt-coins. Free alternatives exist (DropsTab, CryptoRank) if ever needed | Nowhere now |
| 2 | **dexu.ai** | An AI crypto "intelligence" app with its own DEXU token on Solana; market cap ~$3k, daily volume ~$1 as of mid-2025; no documented API, team or milestones | None | **SKIP.** Token-project marketing, not a data source | Nowhere |
| 3 | **coinalyze.net** | Aggregated crypto futures analytics: open interest, funding, liquidations, long/short ratio across exchanges; public REST API (`api.coinalyze.net/v1`) with history endpoints for OI, funding, liquidations | Free with an API key; history endpoints exist; depth and rate limits **[verify on the doc page — blocked from sandbox]** | **BORROW as a cross-exchange cross-check.** For the trial we already get Binance OI/funding/long-short from the bucket (2020→). Coinalyze adds Bybit/OKX/Deribit aggregates for free if its history goes back far enough | Phase 1 optional ingestor; feature source for a "funding/OI" family later |
| 4 | **coinglass.com** | Same category as Coinalyze, larger, with liquidation heatmaps, ETF flows, exchange reserves; tiered paid API | Already assessed in `02_crypto_forex_macro_alt_data.md`: entry tiers ~$29–79/mo | **DEFER.** Same data as Coinalyze/Binance bucket for the big three venues; pay only if a validated strategy needs its extras (ETF flows, exchange reserves) | Serious tier, if a passing strategy needs it |
| 5 | **alternative.me** | The Crypto Fear & Greed Index (0–100, daily at 00:00 UTC since Feb 2018) built from volatility, volume, social, dominance, trends | **Free, no key, full history in one call** (`api.alternative.me/fng/?limit=0&format=csv`), generous rate limit | **ADOPT as a feature.** Cheap, point-in-time by construction (daily snapshot), 8+ years. Candidate sentiment feature for a contrarian/regime filter on the momentum families. Must pass the gates like any feature; expect at best a modest, regime-dependent effect | Phase 1 ingestor (one file); feature set v1 |
| 6 | **tradingeconomics.com** | Macro data and the economic calendar with historical consensus and actuals; API Standard $149/mo | Already assessed in `02_...`: the only affordable calendar with clean historical consensus | **DEFER.** Not needed for crypto spot daily bars. Becomes relevant for the forex phase or a macro-event family | Serious tier, forex phase |
| 7 | **dropstab.com** | Crypto tracker with **token unlock / vesting schedules**, fundraising rounds, VC portfolios, prices; REST API with `/tokenUnlocks` time series; a free Builders Program for unlock and funding data (competitors gate these behind paid or enterprise plans) | Unlock schedules are forward-looking *and* dated, so they are point-in-time by nature; API free via Builders Program **[confirm terms]** | **ADOPT as an event-data source, later.** Scheduled supply unlocks are a documented negative-drift event; a "pre-unlock short / post-unlock mean reversion" family is a legitimate hypothesis for Phase 5, testable with the event-study machinery (gate methods in `04_statistical_rigor.md` §7). Needs ≥100–200 events, which the alt-coin universe supplies | Phase 5 event family; Phase 1 only if the Builders API is confirmed free |

## Net effect on the plan
- **Two new features/data sources:** Fear & Greed (trial-ready, free) and DropsTab unlock schedules (Phase 5 event family).
- **One cross-check source:** Coinalyze, pending its history depth.
- **Confirms deferrals:** Coinglass and Trading Economics stay in the serious tier where the research already put them.
- **Two skips:** dexu.ai and the fundraising database.

## Rule of thumb for future website lists
Ask three questions before spending a minute on a site: (1) Does it have an API? (2) Does the API return history with timestamps, not just today's values? (3) Was the value available at that timestamp, or is it revised later? "No" to any of the three means it is a discretionary dashboard, which belongs to the Centaur morning review, not to the platform.

## Sources
- https://alternative.me/crypto/api/ · https://alternative.me/crypto/fear-and-greed-index/ · https://pypi.org/project/fear-and-greed-crypto/
- https://api.coinalyze.net/v1/doc/ (blocked from sandbox) · https://coinalyze.net/futures-data/
- https://dropstab.com/products/commercial-api · https://dropstab.com/vesting · https://news.dropstab.com/research/free-crypto-data-api
- https://crypto-fundraising.info/api/ · https://crypto-fundraising.info/
- https://web3.bitget.com/en/dapp/dexu-ai-29705
- Coinglass and Trading Economics: see `02_crypto_forex_macro_alt_data.md`

---

# Datasets from social media (set 2)

### mito0o852/OHLCV-1m — https://huggingface.co/datasets/mito0o852/OHLCV-1m
- **What it is:** 1-minute OHLCV bars for "thousands of US stocks", one Parquet file per month from `ohlcv_1992-01.parquet` to `ohlcv_2025-05.parquet` (the card says 1992–2026), columns timestamp/open/high/low/close/volume/ticker. The card states the data was **sourced from Finnhub.io's bulk historical archives** and re-packed. Same author also publishes `OHLCV-1m-Forex` (Dukascopy 1-minute) and `dukascopy-ticks`.
- **Why it is interesting:** free minute bars for US equities would otherwise cost $300–1,000 one-off (FirstRate) or a Databento subscription. If delisted names are present, it is the missing cheap piece of the equities budget tier.
- **What must be verified on the laptop (Hugging Face is blocked from the sandbox):**
  1. **Survivorship.** Open a 2007 monthly file and check for tickers that no longer exist (LEH, BSC, WM, CFC, GM-old). If they are absent, the set is current-constituents-only and inherits the same bias as yfinance; it would then be usable only for *execution-cost* research, not for strategy validation.
  2. **Adjustment.** Compare a split (AAPL 2014-06-09 7:1, NVDA 2024-06-10 10:1) across the boundary: raw prices jump ⇒ unadjusted (good, we adjust ourselves with a corporate-actions table); no jump ⇒ pre-adjusted with an unknown method.
  3. **Coverage per year.** The 1992 start is implausible for minute data on "thousands" of names; count distinct tickers per year. Expect a handful before ~2000 and a steep ramp later.
  4. **Gaps and quality.** Finnhub's minute history has known holes; count missing regular-session minutes per ticker-day against the exchange calendar, and cross-check daily closes aggregated from these minutes against Tiingo daily for 20 random tickers.
  5. **Licence and persistence.** Finnhub's terms prohibit redistribution, so this repack could be taken down. Mirror whatever passes QA into the lake immediately; never depend on the Hub copy at run time. For personal research use the legal exposure is the uploader's, not ours, but the *reliability* risk is ours.
- **Size warning:** thousands of tickers × 390 minutes × ~250 days × 25 years is on the order of tens to hundreds of GB. Pull months selectively with `huggingface_hub.hf_hub_download`, never `load_dataset(...)` on the whole thing on a 16 GB laptop.
- **Verdict: BORROW, pending QA.** Not for the crypto trial. For the equities phase it becomes: (a) the free source of US minute bars for cost/impact modelling (gate 2) and intraday execution studies; (b) a daily-bar source only if check 1 passes. Tiingo (adjusted daily, delisted names) stays the system of record for daily equity research either way.
- **Companion datasets by the same author:** `OHLCV-1m-Forex` and `dukascopy-ticks` are a shortcut to Dukascopy history without hammering Dukascopy's throttled servers. Same QA applies; the Dukascopy origin is a plus because we already planned to use it.

**Laptop QA script (run in the repo venv; ~10 minutes, downloads two monthly files):**
```
pip install huggingface_hub polars
python - <<'PY'
from huggingface_hub import hf_hub_download
import polars as pl
repo = "mito0o852/OHLCV-1m"
for month in ["2007-09", "2014-06"]:
    p = hf_hub_download(repo, f"data/ohlcv_{month}.parquet", repo_type="dataset")
    df = pl.read_parquet(p)
    print(month, df.shape, df.columns)
    print("  distinct tickers:", df["ticker"].n_unique())
    print("  delisted present:", [t for t in ["LEH","BSC","WM","CFC","GM"] if t in set(df["ticker"].unique())])
    if month == "2014-06":
        a = df.filter(pl.col("ticker")=="AAPL").sort("timestamp")
        print("  AAPL close 6 Jun vs 9 Jun 2014 (7:1 split):",
              a.filter(pl.col("timestamp").dt.date()==pl.date(2014,6,6))["close"].tail(1).item(),
              a.filter(pl.col("timestamp").dt.date()==pl.date(2014,6,9))["close"].head(1).item())
PY
```
If the column names differ from the card, print `df.columns` and adjust; the checks are the point, not the exact code.
