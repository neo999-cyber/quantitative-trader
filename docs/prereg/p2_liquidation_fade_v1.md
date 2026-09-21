# Pre-registration: `p2_liquidation_fade_v1` — the kill test for C3, the liquidation-cascade fade

*Drafted 18 September 2026 from the plan's C3 row (`docs/20` §5) and the
outside reviews' Q4 (`docs/29`): run the event study as soon as the
recorded sample is adequate, not on a calendar date — but register it
first. The counts below are of liquidation *events only*, read to size
the sample; **no price path was looked at.** Registered on the owner's
yes of 18 September.*

## Mechanism

A liquidation is a forced trade: the venue's engine sells a long (or
buys back a short) at whatever the book offers, with no price sensitivity
and no timing. A burst of liquidations in one direction pushes the price
through the levels that would have absorbed a patient seller, and the
overshoot reverts once the engine is done — minutes, not days. The
opposite side of that flow is the trade; the forced trader is the
liquidation engine itself, which cannot wait.

## What this document registers

**A kill test, not a family.** An event study on recorded bursts with
horizons and a decision rule fixed here. Only if it passes is a trading
family (entry, exit, sizing, costs) registered separately, under the
counter rule, with its own gates. The kill test counts as one trial.

## Data

- **Liquidation events**, recorded forward on the Hetzner box since 15
  September 2026 11:02 UTC (`scripts/record_liquidations.py`; mirrored
  under `mirror/liquidations/{okx,bybit}/`): OKX `liquidation-orders`
  (every SWAP; `sz` is in *contracts* — notional uses the instrument's
  `ctVal`, to be read from OKX's public instruments endpoint and stored
  with the events) and Bybit `allLiquidation` (USDT linear, `v` in coins).
  Binance's stream sends nothing to the host, so **the signal is OKX and
  Bybit liquidations; the price path and any trade are on Binance** — a
  cross-venue read the memo states plainly. In three days: 88,662 events
  on 750 symbols; 36,004 on the twenty symbols the tape covers.
- **Price path**: the Binance top-of-book tape (`mirror/tape/binance/book`,
  since 17 September 07:31 UTC; twenty symbols: BTC ETH SOL XRP HYPE ZEC
  DOGE ADA ENA BEAT NEAR LINK 1000PEPE CL XAUT WLD SUI UNI ONDO BNB), mid =
  (bid + ask)/2 at the nearest update before each stamp. Events before the
  tape starts are not used.
- Point-in-time by construction (both recorded forward).

## Universe

The tape's twenty symbols **excluding BTC and ETH** (the mechanism is a
thin-book overshoot; the majors absorb $250k in a minute hundreds of times
a day — 471 and 335 such windows in three days — and are the control, §
"Controls"). Eighteen names, of which ten showed a $250k-minute in the
first three days.

## Event definition (frozen)

For each venue *v*, symbol *s*, direction *d* ∈ {sell-liquidations (longs
forced out), buy-liquidations (shorts forced out)}: bin liquidation
notional into 60-second windows. A **burst** is a window whose notional is
(a) at least **$50,000** and (b) at least **5 standard deviations above
the trailing 24-hour median** of that venue-symbol-direction's non-empty
windows (rolling, past only). Consecutive qualifying windows are one
event, stamped at the **end** of the last qualifying window (nothing is
known before the burst is over). An event on both venues within 60 s is
one event. Three days gave 134 windows at z ≥ 5 across all twenty
symbols; BTC/ETH removed, and merged, the expectation is 20–40 events a
day.

## Measurement (frozen)

Signed return of the Binance mid from the event stamp *t₀* to *t₀ + h*,
for **h ∈ {1, 5, 15, 60} minutes**, with the sign chosen so that a
reversion is positive: after sell-liquidations, +(mid_h / mid₀ − 1); after
buy-liquidations, −(mid_h / mid₀ − 1). Also recorded: the move *into* the
burst (mid at the burst's first window start → mid₀), the burst's notional
in dollars and in σ, hour of day, venue, symbol.

Statistics: mean and median reversion per horizon with HAC standard
errors clustered by symbol-hour; the same for BTC/ETH (control); the same
for a **placebo** set of stamps — the same symbols at the same times of day
on the same days with no burst — matched one-to-one by symbol and hour.

## Decision rule (frozen)

**Minimum sample: 300 merged events on the eighteen names**, at which
point the study runs once. At the 15-minute horizon the mean reversion
must be **≥ +8 bps** (a taker round trip on Binance USDⓈ-M is ~13 bps
with spread; the maker study's 8 bps is the cost a family would be
registered against), with **t ≥ 3**, and the placebo mean must be within
±3 bps of zero. If BTC/ETH revert as much as the eighteen, the effect is
"any large print" and not a thin-book overshoot; that is a fail of the
mechanism even if the numbers pass. If the 1-minute reversion is ≥ +8 bps
and the 15-minute is not, the effect exists but only at a speed this
account cannot trade (docs/24: a maker order rests minutes); that is
recorded as such and the family is not registered.

**Passes** → a family (`p2_liquidation_fade_v2`) is drafted for the
owner's yes: entry post-only at the mid after the burst, hold to the
horizon that passed, maker exit, cash benchmark, the full gates.
**Fails** → C3 is closed, and the recorders keep running only if some
other use is named.

## Controls

BTC and ETH (deep-book, same test); the placebo stamps; and the mirror
horizon: the return from *t₀ − 5 min* to *t₀* must be *negative* in the
reversion's sign (there must be an overshoot to revert from). A sample
where the pre-move is flat is a sample of noise.

## What would falsify the mechanism

- Reversion ≤ 0 at every horizon.
- Placebo reversion indistinguishable from the events'.
- BTC/ETH revert as much as the mid-caps.
- Reversion present at 1 minute only.

## Prior

Liquidation-cascade fades are a known professional trade at seconds-to-a-
minute horizons on the venue where the liquidation prints; this study
asks whether anything survives to the 15-minute horizon, on a *different*
venue, after a $50k burst. Expected: a reversion of a few bps at 1
minute, decaying to noise by 15; the honest prior is that C3 fails on
horizon, not on sign.
