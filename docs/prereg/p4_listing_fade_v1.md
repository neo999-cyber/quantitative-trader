# Pre-registration (FILED, never registered — owner's decision 6 October 2026): `p4_listing_fade_v1` — fading new perpetual listings on Binance, market-neutral

*Filed on 6 October 2026: the owner decided not to pursue meme-coin or listing work in this project; no Programme 4 was opened and nothing was run. Kept for the record.*

*Drafted 5 October 2026 at the owner's request ("will these rules work on a meme coin market?" → "write the
memo"). **Not registered.** Registering it opens a fourth programme and a new counter, which is the
owner's decision (§ Programme). What was looked at before drafting, and nothing more: the lake's coverage —
which perpetuals exist, their first and last bar dates, which have funding — and Binance's own category
tags. **No return after any listing was computed for this memo.** One related number had already been seen
and is disclosed in § Prior.*

## Mechanism

A new perpetual on Binance concentrates attention on one day. Retail buyers arrive because the coin is on
the front page; the people who already hold it — airdrop recipients, launch-pool farmers, early investors
whose tokens unlock at the listing — are sellers with a cost basis near zero, and they sell into that
attention over the following days. The listing-day price is set by the buyers who had to act that day; the
following weeks are set by holders who can wait. The trade is the other side of the listing-day buyer:
short the newly listed perpetual a fixed number of days after it lists, hedge the market with a long in
BTC, and close after a fixed holding period. The claim is a *relative* decline against BTC, not a view on
the market.

The owner's question was about meme coins. They are where the lottery-ticket buyer is purest, but the
mechanism is not specific to them and there are too few to test alone (§ Universe); memes are therefore a
**declared subgroup**, not the family.

## Predicted sign and size

**The short earns.** Mean return of the listed coin against BTC over the 7 days after entry: **−3% to −8%**
(so +3–8% to the hedged short before funding and costs), smaller for the later entry. Best variant net
Sharpe **1.0 to 2.0** against cash after costs and funding; the old-coin control earns **less than half**;
the placebo date earns **about nothing**. Predicted for the subgroup: memes fade **at least as much** as
the rest. A net Sharpe above 4, or a mean event return above 20%, is a reason to look for a leak (a listing
date read from a later bar, a survivor-only universe).

## Universe and events (frozen)

- **Events**: every USDT-margined perpetual on Binance USDⓈ-M in the lake (`futures/um`, 864 symbols with
  daily and hourly bars from their first bar) whose **first bar is on or after 2021-01-01** — earlier ones
  are censored by the lake's start. By first-bar year: 2021 59, 2022 26, 2023 99, 2024 131, 2025 242, 2026
  226. The event day `d0` is the UTC day of the first bar.
- **In-sample**: listings 2021-01-01 → 2025-12-31 (about 557 events). **Holdout**: listings 2026-01-01 →
  2026-07-31, opened once after gates 1–8 (the lake ends 2026-08-31; a 30-day hold needs the month after).
- **Exclusions, by rule**: contracts Binance does not class as a coin (`underlyingType` other than `COIN` in
  the mirrored `exchangeInfo` of 5 October 2026 — the TradFi/stock perpetuals of 2026); symbols with fewer
  than `k + H` bars after `d0` are dropped and **counted** (a perpetual delisted inside the window is kept
  to its last bar and closed there).
- **Survivorship check, before the run**: only 31 of the 864 end before the lake does. The symbol list is
  reconciled against Binance's delisting announcements (catalogue 161, public) and any delisted perpetual
  missing from the lake is pulled or named in the report. A missing dead coin understates a short's
  return, so the bias, if any, is against the family.
- **Meme subgroup**: Binance's own tag — `underlyingSubType` contains `Meme` in the mirrored `exchangeInfo`
  (55 live symbols). Delisted symbols carry no tag and are reported as "untagged". No hand-made list.
- **Funding**: gross, from the lake (`futures-um`); 666 of 864 symbols have it today. The remaining
  symbols' funding is pulled from Binance's public bucket before the run; an event whose funding is still
  missing is dropped and counted.

## Rule and parameters (frozen)

A calendar rule: no price enters the decision.

For each event, at the close of day `d0 + k`: open a **short** in the listed perpetual worth **5% of NAV**
and a **long in BTCUSDT** worth the same dollars. Hold `H` days, then close both. If 10 events are already
open, the new one is skipped and counted. **Catastrophe stop, fixed:** an event is closed at the first
daily close at or above **2.5×** its entry close (a daily close: gaps are not protected against, and the
report shows the worst single event). One position per symbol, ever.

| Parameter | Range | Swept? |
|---|---|---|
| `k` (days after the first bar) | 1, 3 | yes |
| `H` (holding days) | 7, 30 | yes |
| weight per event / max concurrent | 5% / 10 | fixed |
| hedge | BTCUSDT, equal dollars | fixed |
| stop | 2.5× entry close | fixed |

**4 variants.** Engine: `--engine ledger`, funding gross on both legs. Costs: `--costs perp` with the
half-spread set to **5 bps** on every leg (new listings quote wide; conservative on the BTC leg).
Benchmark: **cash** (`--benchmark cash --risk-free fred`).

Sizing is chosen so the account can trade it: on the $200 studies bucket 5% is $10, above Binance's $5
minimum. That is a statement about feasibility, not a plan to trade.

## Controls

- **Old-coin control** (`_old`): on every event's entry day, short instead a perpetual drawn at random
  (seed 20261005) from those listed more than 365 days earlier, same size, hedge, hold and stop. Alts have
  bled against BTC for most of this sample; if old coins earn half as much, the finding is "short alts
  against BTC", not a listing effect.
- **Placebo date** (`_d90`): the same symbols, entered at `d0 + 90 + k` instead of `d0 + k`. If the same
  coins fade as much three months later, it is the coin, not the listing.
- **Unhedged** (`_naked`): the short leg alone, reported for the size of the market bet the hedge removes;
  not a pass condition.
- **Gate 6's permutation null** as registered.

## Statistics

Gates 1–8 on the daily book. An event table beside them: per event, the return of the listed coin against
BTC from entry to exit, net of costs and of the short's funding; mean with standard errors **clustered by
listing month** (listings bunch, and a month's listings share a market); the same for memes, non-memes and
untagged; funding paid or received by the short leg reported on its own line.

## What would falsify this

- Best net Sharpe below 1.0 against cash, or mean net event return below **+1.0%** to the short, or its
  clustered t below 3.
- The old-coin control within half of the family, or the placebo date within half.
- Funding taking more than half of the price edge (then the fade exists and the crowd of shorts is already
  paid for it).
- DSR below 0.90 over 4 → gate 4. SPA p above 0.5 → gate 5.
- The holdout reversing the in-sample result.
- **Memes**: reported, not a pass condition — about 50 events cannot carry a verdict. The registered
  prediction (memes fade at least as much) is scored right or wrong in the report.

## Prior

One number was already on the table and is the reason for the predicted sign: in the Launchpool
measurement of 21 September (`docs/31` §11), the 53 stablecoin-pool reward tokens fell a **median 11%
between the listing day's close and day 7** on spot. That is a subset selected for prominence, on spot, not
market-adjusted; it overlaps these events and was seen before this memo was written. Against the idea:
the fade is well known, so the short side of a new listing is crowded and its funding can be deeply
negative; Binance often lists a perpetual for a coin that has traded elsewhere for months (no listing
buyer left); 2023–2025 was a regime in which nearly every alt lost to BTC, which is exactly what the
old-coin control is there to subtract. Honest expectation: the family shows a fade, the old-coin control
shows a good part of it, and the verdict turns on the difference between the two and on funding.

## Programme

Programme 3's three registrations are spent. Registering this memo opens **Programme 4** with its own
counter; the proposal is **two** registrations (this one and one in reserve), under the unchanged rules:
register before any run, every run counted, the 3× bar, controls, holdout once, nothing live without the
owner's yes. A pass here would lead to a paper-then-small live stage with the stage-1 execution harness and
the cost model measured by 11 October; it would not lead to on-chain meme trading, which this memo does not
cover and the project does not propose.

## Build, after registration

`qr/data/listings.py` (the event table from the lake and the mirrored `exchangeInfo`; the delisting
reconciliation), `qr/strategies/listing_fade.py` (family and controls as weights for the ledger), funding
for the missing symbols, fixture tests; then `qr gates --family listing_fade --market futures/um --engine
ledger --costs perp --benchmark cash --risk-free fred`. No event return is computed before the
registration is in the trial log.
