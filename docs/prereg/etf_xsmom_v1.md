# Pre-registration: `etf_xsmom_v1` — cross-sectional rotation across asset classes

*Written 12 September 2026, before any ETF data was pulled.*

## Mechanism

Hold the strongest few of the twelve and skip the rest. Where the time-series
family asks "is this asset trending?", this one asks "which of these is
trending *most*?" — a relative rather than absolute judgement, and a materially
different bet on a basket that spans asset classes rather than one that spans
thirty correlated coins.

The mechanism is the same slow diffusion of macro information, expressed as
rotation: when duration is repricing, bonds lead for months; when it is a
growth scare, gold and treasuries lead together; when it is a risk rally, small
caps and emerging markets lead. A rotation strategy is a bet that these regimes
persist long enough to be ridden after they are visible.

## Predicted sign and size

**Net annualised Sharpe of 0.2 to 0.6** at $1,000, gross 0.5 to 0.9.

**Predicted beta to SPY: 0.3 to 0.6**, and here is the specific worry, recorded
in advance: holding the top 3 of 12 concentrates rather than diversifies, and
the equity sleeve (SPY, QQQ, IWM, EFA, EEM) is five of the twelve names and
tends to lead together. So this family can easily collapse into "long equities,
sometimes", which is the crypto trial's failure mode transplanted. Predicted
alpha t-statistic: **1 to 2** — below the bar, and I am saying so before the run.

Gate 1's shuffled-ticker placebo is the test that decides whether that worry is
real. If attaching this strategy's weights to random tickers does about as
well, the rotation carries nothing and the family is market timing in
cross-sectional clothing. For this family a high placebo p is **damning**, not
expected — unlike the time-series family, where it would be normal.

## Universe

`etf_basket_12`, identical to the other three families and fixed before the
run. Deliberately identical: families that ran on different universes would not
be comparable. Dividend- and split-adjusted, for the reason given in
`etf_tsmom_v1.md`.

## Horizon

Daily bars, monthly rebalance. The 12-1 skip-month convention used in the
crypto family is **dropped** here: it exists to avoid the one-month reversal
documented in individual equities, and there is no evidence for that effect in
broad asset-class ETFs. Carrying it over would be cargo-culting a control for a
bias this universe does not have.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` | 60, 120, 180, 252 (4 values) | yes |
| `n_long` | 3, 4, 6 (3 values) | yes |
| `vol_lookback` | 60 (fixed) | no |
| `vol_target` | 0.10 (fixed) | no |

**12 variants.** Minimum backtest length at 12 trials and a Sharpe of 0.5 is
`2·ln(12)/0.25` ≈ 20 years. Smaller than the time-series grid because the
prediction is weaker and the sample must support the search, not the other way
round.

## What would falsify this

- Gate 1: shuffled-ticker placebo p above 0.50 — the symbol selection carries
  nothing, which for this family is fatal rather than expected.
- Gate 2: net/gross below 0.50. Rotation turns over more than trend does, so
  the $0.35 minimum bites harder here.
- Gate 5: SPA p above 0.50 against holding the equal-weighted basket.
- Gate 8: alpha t below 2 against SPY.

## Prediction about the others

I expect this family to have the **worst chance of the four at gate 1's
placebo** and a better chance than the control at everything else. On crypto I
predicted xsmom would do best at gate 8 and worst at gate 2, and got it exactly
backwards — gate 2 passed at 94% and gate 8 gave alpha t of 0.21. That error is
why the prediction here is about the placebo, which is the test that actually
separates rotation from direction.
