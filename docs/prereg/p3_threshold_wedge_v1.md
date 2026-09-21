# Pre-registration: `p3_threshold_wedge_v1` — selling the Polymarket wedge over the options-implied probability

*Drafted 21 September 2026 from `docs/31` §1.3 and **registered the same
day on the owner's yes** to this text, through
`qr trial prereg --file docs/prereg/p3_threshold_wedge_v1.md`, before any
wedge was computed and before the engine script existed. What was read before drafting, and nothing more: the
market catalogue (counts, horizons, volumes, the resolved-YES rate of 38%)
and the DVOL series' length. No market price was compared with any model
probability.*

## Mechanism

Retail bettors on Polymarket buy "Bitcoin reaches $X by date" and "Ethereum
dips to $Y by date" contracts the way they buy lottery tickets: the price
they pay sits above the probability the options market assigns to the same
event. The options market is the better-capitalised, hedged side of the
same bet, so its implied probability is the fair value. The seller of the
Polymarket contract, resting as a maker (fee 0), collects the difference
when the wedge closes or the contract settles. The forced party is the
directional retail buyer; the measured fact is the favourite–longshot
bias (arXiv 2606.19517: +6.3 pp against Binance options, +11 pp against
Deribit, 2,585 observations, persistent with a 4.2-hour half-life).

## Predicted sign and size

**Positive.** Selling YES when the market's price exceeds the model's
probability by `k` points earns, per share, a mean net edge of **at least
3 points** at `k` = 5 with a clustered t **above 3**; the mirror control
(buying YES when *under*-priced) earns **less than half** of it; the
placebo model (realised vol instead of DVOL) earns **less than the family**
by a margin visible in the t-statistic. Net Sharpe of the daily P&L of the
book, pooled across markets, **above 1.0** after the spread haircut. An
edge above 15 points per share, or a t above 10, is a reason to look for a
leak (a look-ahead in the settlement price or the horizon).

## Data and universe (frozen)

- **Markets**: the catalogue built by `qr/data/polymarket.py` on 21
  September 2026 from Gamma `public-search` over fourteen fixed queries
  (`QUERIES`) — **9,048 resolved BTC/ETH/SOL threshold and barrier
  markets**, horizon ≥ 7 days, volume ≥ $10,000, classified by rule from
  the question text (`classify`): `reach` (touch from below, 1,555),
  `dip` (touch from above, 1,379), `above` (terminal, 6,114). Sub-daily,
  dated-hour ("4AM ET"), "Up or Down" and two-strike "which first" markets
  are excluded by rule. 7,818 are weekly (horizon 7 days), 1,117 monthly or
  longer; resolutions run November 2021 → 20 September 2026, 96% of them
  in 2025–26. The catalogue is frozen at
  `mirror/polymarket/catalogue.parquet`; re-running discovery does not
  change the universe of this memo.
- **Prices**: CLOB `prices-history`, `fidelity=1440` (one point a day, the
  last print of the UTC day), per YES token, mirrored under
  `mirror/polymarket/prices/`. A market with no history is dropped and
  counted.
- **Model inputs**: Deribit DVOL daily close for BTC and ETH from
  2021-03-24 (`reference/dvol_BTC`, `reference/dvol_ETH`, 2,008 days);
  Binance spot daily close for BTCUSDT, ETHUSDT, SOLUSDT from the lake. SOL
  uses BTC DVOL scaled by the ratio of 30-day realised vols (SOL/BTC),
  computed past-only; this is an approximation and SOL is reported
  separately.
- **Alignment**: everything on day *t* is known by 00:00 UTC of day *t+1*;
  a decision on day *t* fills at the price recorded on day *t+1* (the
  one-bar shift, as in every other family here).

## Model probability (frozen)

With `S` the spot close, `X` the strike, `σ` = DVOL/100, `τ` = days to the
market's end date / 365, `μ = −σ²/2` (driftless in price):

- `above` (terminal, "above $X on date"): `p = Φ(d₂)`,
  `d₂ = (ln(S/X) + μτ) / (σ√τ)`.
- `reach` (up-barrier touch, "reach/hit $X by date"), `b = ln(X/S) > 0`:
  `p = Φ((−b + μτ)/(σ√τ)) + exp(2μb/σ²) · Φ((−b − μτ)/(σ√τ))`; if
  `S ≥ X` already, `p = 1`.
- `dip` (down-barrier touch), `b = ln(S/X) > 0`: the same with the sign of
  `μ` flipped; if `S ≤ X` already, `p = 1`.

No smile, no term structure, no drift: the same model for every variant
and both controls, so the only thing that differs between the family and
the placebo is the volatility fed in.

## Rule and parameters (frozen)

Per market, per day *t* from the first day with both a price and a model
probability until end − 1: `wedge_t = price_t − p_t`. If no position and
`wedge_t ≥ k`, **sell YES** at the next day's price minus the haircut
(the capital tied is `1 − fill` per share); hold until `wedge ≤ x` (exit at
the next day's price, haircut again), or the market resolves (settlement
at 0 or 1, no haircut), or `T` days. One position per market; at most one
market per asset × end date (the one with the largest wedge at entry —
the strikes of one weekly ladder are one bet); at most 5 open; $25 per
market. Longs never.

| Parameter | Range | Swept? |
|---|---|---|
| `k` (entry wedge, points) | 5, 8 | yes |
| `T` (max hold) | to resolution, 7 days | yes |
| `x` (exit wedge, points) | 2 | fixed |
| haircut per fill (spread proxy, points) | 1 | fixed |
| cap per market / open markets | $25 / 5 | fixed |

**4 variants.** Fees: maker 0 (Fee Structure V2), rebates and liquidity
rewards ignored, taker fee never paid (no taker entries; a forced exit at
expiry is a settlement, not a trade). Gas and bridging ignored at this
stage and added in the cost line of the report ($0 gas on Polygon; one
bridge). The **3× bar**: mean edge per share ≥ 3 × the haircut.

## Controls

- **Mirror** (`_mirror`): buy YES when `p_t − price_t ≥ k`, same exits.
  The bias says the under-priced side is thin; if the mirror earns as much,
  the finding is "any wedge closes" (noise in the daily print), not a
  retail premium.
- **Placebo model** (`_placebo`): the family's rule with `σ` = 30-day
  realised vol of the spot (past-only) instead of DVOL. If it earns the
  same, the edge is "sell lottery tickets", real but not the options
  market's information, and the family is re-scoped as such.
- **Naive short** (`_naive`): sell every YES priced ≤ 20¢ at first sight,
  hold to resolution. The favourite–longshot baseline; the family must beat
  it per share.
- **Gate 6's permutation null**: entry days shuffled within each market.

## Statistics

Per-share edge with standard errors **clustered by asset × end date**
(the markets on one settlement date share the outcome). Gate 4's DSR over
4 variants. Gate 5 against cash (the capital is idle USDC otherwise). The
book P&L is a daily series of the $200 sleeve.

## What would falsify this

- Mean edge per share below 3 points at `k` = 5, or clustered t below 3.
- The mirror within half of the family, or the placebo matching it.
- The family not beating the naive short per share.
- DSR below 0.90 → gate 4.
- **Holdout**: markets ending 1 June 2026 → 20 September 2026, opened once
  after the in-sample verdict.

## What the daily data cannot say, stated now

The paper's wedge decays in hours; a daily print can only see what is left
of it at the end of the day. A pass here means the slow component alone is
worth selling; a fail here does not kill the intraday version — that
needs the book recorder (`docs/31` §4, running from 21 September) and is a
separate memo. Resolution risk (UMA disputes, wording) is inside the
settlement outcomes and therefore inside the edge; it is not modelled
separately.

## Prior

The bias is well measured and the counterparty is named, which is more
than any Programme 2 candidate had. Against it: daily granularity, 96% of
the sample in two years, and the placebo is the honest worry — retail
over-paying for lottery tickets is a fact about *any* vol model. The prior:
the family passes per share on the reach markets, the placebo is close,
and the report says whether DVOL adds anything over realised vol. That
answer decides whether the intraday version is built.

## Engine

`scripts/p3a_wedge.py` (to build): reads the catalogue, the price mirror,
DVOL and spot from the lake, writes the per-trade table and the daily P&L
under `reports/p3/`, and **counts itself in the trial log** through
`SealedTrialLog` like every other run. It writes nothing to the catalogue.
