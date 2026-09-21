# Pre-registration: `p3_threshold_wedge_v2_intraday` — the same wedge, on the recorded intraday book

*Drafted 21 September 2026 after v1's in-sample fail (`docs/31` §9), from
the owner's choice of "the intraday version", and **registered the same
day on the owner's yes** to this text, before any line of the Polymarket
or Deribit recording was read for a wedge. What v1 showed and is therefore
known: the daily wedge is +2.6 points a share at k = 5 (t 2.0), one-sided
(the mirror loses), not reproduced by realised vol (the placebo loses),
concentrated in BTC `reach`/`above` markets and in 2026, and negative on
`dip` markets. This memo changes the **data resolution and the fill
model**; it keeps the mechanism, the model and the controls.*

## Mechanism

Unchanged from v1: retail buyers of BTC/ETH/SOL threshold contracts pay
above the options-implied probability; a maker sells the overpricing. The
paper's wedge has a 4.2-hour half-life, so a daily print sees only what
is left of it at the end of the day; the recorded book sees it as it
forms.

## Predicted sign and size

**Positive.** Per filled share, mean net edge **≥ 3 points** at k = 5,
clustered t **≥ 3**; the mirror < half of it; the placebo (realised vol)
clearly below the family; the naive short beaten per share. Book net
Sharpe above 1.0 on the $200 sleeve. An edge above 15 points or a fill
rate above 90% is a leak (a fill rule that fills where no taker was).

## Data (frozen)

- **Polymarket book recording**: `qr-pm-polymarket` on the Hetzner box
  from 21 September 2026 04:25 UTC — `book`, `price_change` (YES side,
  compacted as documented in `scripts/record_polymarket.py`),
  `last_trade_price` for every active BTC/ETH/SOL threshold market
  (horizon ≥ 7 d, the v1 exclusions), list refreshed hourly.
- **Deribit recording**: `qr-pm-deribit` — DVOL BTC/ETH and price indices
  BTC/ETH/SOL at the venue's cadence, same start.
- **Window**: 21 September → 26 October 2026 (five weekly settlement
  cycles), read once on 27 October. **Minimum sample, stated now:** at
  least **30 asset × settlement-date clusters** with a fill, else the run
  is deferred to 30 November and this memo is not touched.
- **Resolutions**: from Gamma at read time (a market that has not resolved
  by the read is dropped and counted).

## Model (frozen, as v1)

Φ(d₂) terminal; reflection-principle touch; σ = the latest DVOL print at
or before the decision time (SOL: BTC DVOL × the past-only 30-day
realised-vol ratio); S = the Deribit price index at the decision time; τ
to the market's end in years.

## Rule and fill model (frozen)

Decision times: **every hour on the hour** UTC. At each, per market:
`wedge = best_bid − p_model` (the bid, because a maker sale is worth what
the buyer will pay). If no position and `wedge ≥ k`, **post a sell of YES
at the best ask** (joining, never improving). The resting order is
**filled only when a `last_trade_price` prints at or above our ask after
the post** (price-through; the queue ahead is assumed to fill first, as in
the maker-fill study's stage 0), within a `TTL` of 4 hours; else cancelled.
Exit: when `wedge ≤ x` at a decision time, post a buy at the best bid with
the same fill rule; if unfilled after TTL, **cross** at the best ask (the
one taker fee, crypto tier 0.07 × p(1−p)); or settlement at 0/1; or `T`
days after the fill, crossing. One position per market; one market per
asset × end date (largest wedge); ≤ 5 open; $25 per market on the $200
sleeve. Fills at the same prices for the per-share population and the
book.

| Parameter | Range | Swept? |
|---|---|---|
| `k` (entry wedge, points) | 5, 8 | yes |
| `T` (max hold, days) | 3, to resolution | yes |
| `x` (exit wedge) | 2 | fixed |
| `TTL` (hours) | 4 | fixed |

**4 variants.** Fees: maker 0; taker fee only on a forced cross; rebates
and liquidity rewards ignored.

## Controls (as v1)

Mirror (buy the under-priced side, posted at the best bid); placebo (σ =
30-day realised vol from the Deribit index, past-only); naive short of
every YES with best bid ≤ 20¢ at first sight, held to resolution; gate 6's
permutation of decision times within a market.

## Statistics

Per-share edge, SE clustered by asset × end date; DSR over 4; the book's
hourly P&L aggregated to days for Sharpe. Fill rate reported per variant
and side.

## What would falsify this

- Edge < 3 points at k = 5, or clustered t < 3; the placebo matching;
  the mirror within half; the naive short not beaten; DSR < 0.90.
- A fill rate below 30%: then the wedge is quoted but not sellable, and
  the finding is "the ask never trades", which is a result too.
- **Holdout**: the recording from 27 October → 30 November, read once,
  only if the in-sample passes.

## Prior

The daily data gave 2.6 points against a 3-point bar with the placebo
clearly below; the intraday version can add the part of the wedge that
decays before the daily print, or it can show that the sellable part is
the daily residue. Five weeks is a short sample; the cluster minimum is
the guard. Honest expectation: the per-share edge rises, the t does not
clear 3 in five weeks, and the December read decides.
