# The options variance-risk premium as a candidate: the data check (18 September 2026)

*Both outside reviews proposed defined-risk short-volatility on SPY/QQQ
through IBKR (`docs/29` Q5c). Before drafting a memo, the question is
whether a backtest dataset exists at $0. Read-only queries to the owner's
IBKR connector; nothing traded, nothing counted as a backtest — an index
was read, not a strategy run.*

## What IBKR can and cannot supply

- **Expired options: no history.** IBKR's API serves history only for
  listed contracts, and for those it answered "No historical market data
  available" for a live SPY Oct-2026 put without an OPRA subscription.
  There is no way to reconstruct 30–45 DTE condors from 2015 to 2025
  through this connector. A real options backtest needs CBOE DataShop,
  ORATS or OptionMetrics — $100s to $1,000s, against a $0 budget and a
  standing rule of no data spend without a named need.
- **CBOE's strategy benchmark indices: yes.** IBKR serves the index
  histories (`IND`, CBOE): CNDR (S&P 500 iron condor), PUT (put-write),
  BXM (buy-write), BFLY (butterfly), CMBO (combo). Five years weekly
  through the connector; CBOE publishes the full daily files free on
  cboe.com. These are exactly the VRP strategies, computed by the
  exchange with its own rules, **before any retail cost**.

## What the benchmark says, five years weekly (2021-09 → 2026-09)

CNDR, the S&P 500 iron condor index: total **+19.1%**, CAGR **+3.5%**,
annualised vol 6.5%, Sharpe 0.57 against zero, max drawdown −10.1%,
worst week −4.3%. Three-month T-bills averaged roughly 4% a year over the
same window. **The exchange's own condor benchmark earned about cash,
pre-cost, with a 10% drawdown.** Retail costs on top: IBKR $0.65 a
contract, four legs in and out, against a $30–50 credit per condor at
$100–200 max loss; SPY option spreads of 1–3 cents on legs priced in
dollars — several percent of the credit per round trip.

## Verdict

Not registered. The premium the reviews cite is real in the long
literature; over the five years a retail account could have traded it on
IBKR, the exchange's benchmark did not beat cash before costs, and a
$1–2k account trading one condor a month has the "99 days / day 101"
shape at 10–20% of the account per loss. If the owner ever wants it
tested properly, the path is CBOE's free daily index files (PUT since
1986) as a *pre-cost proxy* through the gates against the cash benchmark,
with the retail cost stack layered on; a passing proxy would then justify
paying for contract-level data. On the evidence above that test is
expected to fail gate 5 against cash, so it is filed, not queued.
