# Maker-fill study, stage 1 — the build scope (18 September 2026)

*Two documents from Codex arrived on 17 September: a complete "trading
platform build pack" (spec, reference core, 41 offline tests) and, after
the owner's push-back (drafted here, sent by the owner), a revised scope
that keeps only what `docs/24`'s stage 1 needs. This file records the
assessment of the first and adopts the second, with three details frozen
and one correction to our own protocol. Nothing was run; no code beyond
`docs/24`'s fee line and this file changed. The pack itself is kept
outside the repo (`~/Documents/Codex/2026-09-15/…/Trading_Platform_Complete_Build_Pack.zip`).*

## The build pack: what it is and is not

It specifies the layer this project does not have — order identity, a
state machine with UNKNOWN handling, reservations, reconciliation, kill-
switch levels, an approval bound to an exact intent, a research assistant
that explains candidates and says "no trade today" — and it is careful
and honest about the layer it does not touch: it states five times that it
contains no strategy and reclassifies no failed family. Its reference core
reproduces our review-22 hand ledgers independently in Decimal (cash
drift, short liability, six fills for three nights, whole shares), and its
41 tests pass on this machine.

**Taken:** its four criticisms of `qr/research/ledger.py` — all correct
for an execution ledger and all deliberate research conventions: (1) "no
valid price → sell at the last close" must become "keep the holding, mark
NAV uncertain"; (2) adjusted units are not real shares, dividends and
splits are cash and quantity events; (3) perp margin must be *reserved*
against buying power, not recorded as a line; (4) a live fill is at the
next executable quote, not the decision bar's close. These become an
**execution mode** beside the research mode, compared on the cases where
they must agree. Also taken: the fixed-cost hurdle ($15/month = 18%/yr on
$1,000), the AI boundary (read-only, cited, no credentials — our existing
rule), and the opportunity-card contract as the output format for any
candidate that ever passes gates 0–9.

**Not taken, and why:** its three research templates (ETF 126-day trend
over a 200-day average; stock catalyst with price confirmation including
insider clusters; crypto 20-bar breakout) are Programme 1's ETF trend and
TSMOM and Programme 2's E4 and E5 — all gated and failed (`docs/18`,
`docs/23`). An assistant built on them would honestly show "no trade
today" and a track record not distinguishable from zero. It does not
shorten the time to a validated edge, which is this project's only
bottleneck. Its effort (264–448 engineering hours plus 24–40 of review)
cannot pay back from a $1,000–2,000 account; the pack says so. Its first-
release scope (long-only US stocks, unlevered) defers exactly the two
things still live here — carry and the perp short — to "later releases".
The product shortlist (TrendSpider/Sidekick, Trade Ideas/Holly) has no
verifiable after-cost record and costs 60–240%/yr of the account under
the pack's own table: not bought.

## The revised scope, adopted

Build only what stage 1 of `docs/24` needs, and only after stage 0 passes
its registered rule (≥ 70% fills in 15 minutes, median adverse mark
< 2 bps, read on/after 1 October) **and** the owner's separate yes to the
live configuration:

| Ticket | Minimal implementation | Acceptance |
|---|---|---|
| B10 | Local SQLite event journal: real perp quantities, fees, funding, collateral reservations, cash by venue and currency | Restart/replay reproduces state; a missing price never invents a liquidation |
| B11 | Stable client IDs, durable submit state, reservations, partial-fill and cancel handling, UNKNOWN → broker reconciliation, never a blind resend | A timeout after acceptance creates no duplicate; competing intents cannot exceed the aggregate cap |
| B12 | Deterministic study limits counting pending orders: < $10 an order, ≤ $50 gross open across both venues, ≤ 1× leverage, fixed expiry and closing rules | Unsafe entries rejected; a reducing exit cannot reverse the position |
| B13 | Terminal preview and an authenticated local start of the mandate, bound to account IDs, config hash, symbols, caps and session expiry | Wrong account / config / expired session cannot start; no dashboard |
| B14 | Binance USDⓈ-M and Bybit linear adapters only; verified post-only entries and reduce-only closes; filters, lot/tick/min-notional, position mode and fee tier read from the account | Ineligible symbols excluded, caps never enlarged |
| B15 | Broker snapshots and execution reconciliation; the filled quantity always has an exit path; the 60-minute and day-end taker exits | Partial fills, cancel races, rejected exits and manual activity without overselling or double closes |
| B16 | Attended local runner, terminal log, durable pause, reconciliation on restart, local backup | Sleep / disconnect / crash drill pauses entries; the operator can close through the broker UI |

One local coordinator, transactional reservations across both venues. No
subscription, server, dashboard, or unattended operation. Development of
B14 against the venues' testnets; real keys (trade-only, no withdrawal,
IP-restricted) only for the study itself, and never in the journal or any
model context.

## Frozen before any live order (the protocol left these open)

1. **The 60-minute timer runs from the fill**, not the placement. A cancel
   request is not a close; the close is a confirmed reduce-only execution.
2. **The adverse-selection mark is the mid one minute after the fill**,
   the same quantity stage 0 measures, logged beside the mid at placement.
3. **Instruments and attended hours are chosen from stage 0's shape**
   (fill probability by hour and coin) and written down before the first
   stage-1 order; every scheduled attempt is logged, including orders not
   placed and orders rejected, so the denominator is the schedule.
4. The fee arithmetic in `docs/24` is corrected to a single denominator:
   taker ~25 bps → maker ~8 bps per one-leg notional (halve both for
   two-leg gross). The engine already charged it this way; no reported
   figure moves.
5. $25 is the study's spending-and-loss stop, with a stated reserve for
   closing whatever is open when it trips; the $50 cap and the 60-minute
   exit bound *planned* exposure, not a gap or an outage.
6. Every session ends flat with no working entry orders, verified at both
   brokers, not in the journal alone.

## Output and decision (unchanged from `docs/24`)

Matched stage-0 vs stage-1 fill probabilities by day and symbol with
intervals; fill-conditioned adverse selection, wait times, fees, funding,
taker-close frequency and the full-round-trip cost distribution including
failed attempts; `CostModel.maker_measured(...)` with its denominator and
sample size stated. Within 10 points of stage 0 → the model is an input
for the separately registered `_maker` re-registrations of C1 and C2,
same gates, same counter rule. Outside → the maker route is closed.
Passing stage 1 validates a cost input, not a strategy.

## Parked

The assistant, the LLM explainer, every subscription, the dashboard,
PostgreSQL, hosting, US-stock adapters, productisation, automatic
deployment. C6 stays on its research path and is not traded by this
harness. The parked material stays valid as the specification for the
day a candidate passes gates 0–9.

## Sequencing

Nothing here starts before 1 October. B10 and B12 are pure local code
with tests and can be built at any time; B11/B13/B15/B16 follow; B14 is
built on testnet and is the last thing before the owner's stage-1 yes.
The research funnel — C6 (`docs/prereg/p2_unlock_fade_v1.md`, running
the night of 17–18 September), stage 0's read on 1 October, C3's kill
test in late October — remains the thing that decides whether the
execution layer ever carries a strategy.
