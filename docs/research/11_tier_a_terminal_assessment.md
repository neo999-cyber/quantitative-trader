# Assessment: the "Tier A" crypto intelligence terminal report (15 October 2026)

*The owner shared a standalone report — "A Free and Open-Source Crypto Intelligence Terminal", a plan to
rebuild 55–65% of Blockworks Intel's visible surface for $0–60 a month on open-source software and free
data tiers — and asked whether it can be built here and used for this project.*

## Can it be built?

Yes. The plan is competent and its stack is ordinary: Next.js, Postgres with TimescaleDB, Dagster, dbt,
CCXT, ECharts, Meilisearch, a Telegram bot, one Hetzner server. Its estimate of 10–14 weeks for one
full-stack developer plus 2–4 hours a week of maintenance is honest; with Claude Code driving, the build
compresses to a few weeks of sessions and the maintenance does not compress at all, because it is feed
breakage, rate limits and metric redefinitions, which arrive on the sources' schedule. Its licensing
section is right: CoinGecko Demo, Reddit, Dune and CryptoRank free tiers are non-commercial, so this is a
personal terminal, not a product.

Pieces of it already exist in this repository, recorded point-in-time for other reasons: DefiLlama yields
and the Binance announcement catalogues (`scripts/record_yields.py`), Binance/Bybit/Hyperliquid/Deribit
market data (the tape, the surface, the asset contexts), Polymarket's order books, FRED, the ETF-flow
series (issuer workbooks and a public table), the CFTC COT history, Coin Metrics on-chain, a Parquet lake
with a DuckDB manifest. What does not exist here is everything the report calls the product: a web app,
news ingestion, LLM summaries, asset metadata, governance alerts, a screener.

One factual correction from our own experience: the report's ETF-flow row relies on scraping Farside and
SoSoValue; both refuse non-browser fetches (403, checked 14 October). The issuers' own fund workbooks are
the working route (`docs/31` §18) and would be the right source for the terminal too.

## Should it be built for this project?

No. The project is a pre-registered research programme whose output is verdicts, and whose rules are $0
data, every run counted, no discretionary trading. A terminal is a consumption surface for discretionary
reading; the report says so itself ("what a visitor sees"). Three specific reasons:

1. **It produces no test.** Nothing on its feature list changes a gate, a cost model or a mechanism memo.
   The data it would add that we do not already hold — governance proposals, exploits, fundraising rounds,
   GitHub activity, Reddit — are event feeds with no forced party behind them that the programme has not
   already tried (token unlocks were C6, FAIL) or with a party that acts before the event is visible (a
   hack is a dump that has happened; a treasury company's purchase is TWAP'd before it is announced).
2. **It costs the one thing the programme is short of.** Not money — $0–60 a month is fine — but build
   and maintenance time and the owner's attention, in a repository whose convention is to keep context
   small. Ten weeks of terminal is ten weeks not spent on the two registrations the data-expansion plan
   actually proposes.
3. **It changes the owner's relationship to the data.** The programme's protection against the "I saw a
   chart" trade is that the owner does not look at charts; a terminal is built to be looked at. That is
   not a moral point, it is the stopping rule (`docs/20`) in another form.

## What is worth taking from it

- **Charts as saved queries** (its §5.7): the same pattern as our reports — a metric is a versioned query
  with a cached result and a source stamp. Already how the lake's reference tables and the stage reports
  work; nothing to change.
- **Feed-health checks that alert when a source goes quiet** (its §8): we have this for the recorders
  (`deploy/surface/recorder_health.sh`); the daily ETF collector and the yield timer should report into
  the same line. A ten-minute change, worth doing.
- **A one-page daily "desk sheet"** generated from the lake with no server and no UI — recorders' health,
  the ladder's current rates, the open decisions, the dated items — would give the owner most of the
  *visibility* a terminal promises at a day's build and zero maintenance. Offered, not built.

## Verdict

Buildable, honestly costed, and the wrong project for this repository. If the owner wants a personal
terminal as a product or a hobby, it should be its own repository and its own sessions, with the report as
its brief; nothing from it should be wired into the research code, and nothing in the research programme
waits on it.
