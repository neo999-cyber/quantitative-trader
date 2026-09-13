# Pre-registration: `etf_reversal_v1` — short-term reversal on ETFs

*Written 12 September 2026, before any ETF data was pulled.*

## Mechanism

Buy the worst performers of the last few days, hold for a week. Someone
liquidating a position in size needs immediacy, and the compensation for
supplying it is the reversal. This is the one family on the list whose
mechanism is about **market structure** rather than information, and it is
named in `PLAN.md` §6 as one of the ten families worth testing.

The mechanism also says exactly where it dies, and on this trial it says it
twice. Liquidity provision is paid in basis points. The strategy pays 42 bps a
leg at $1,000 of equity, and it trades weekly rather than monthly. If the
reversal is worth less than the round trip, there is no strategy — only a
transfer to Interactive Brokers.

## Predicted sign and size

**Positive gross, negative net.** Gross annualised Sharpe of 0.4 to 0.9; net
Sharpe of **−0.5 to +0.1**.

This is the most confident prediction in the set and the most specific: I
expect this family to **fail gate 2**, with net/gross below zero — not merely
below the 0.60 floor. A weekly rebalance of a 3-name book at 42 bps a leg is
roughly 13% a year in commissions, against a gross return unlikely to exceed
6%. Predicted beta to SPY: near zero or slightly negative.

On crypto I predicted this family's costs would be binding and was wrong —
net/gross came in at 87.7%, because Binance charges proportionally and 9.5 bps
is cheap on daily bars. The prediction is being made again here for a
structurally different reason: it is not the rate that kills it, it is the
per-order minimum meeting a small account and a weekly turnover.

## Universe

`etf_basket_12`, identical to the other families, dividend-adjusted. The
liquidity constraint matters less here than it did on crypto — these are the
most liquid ETFs in the world and a 1 bp half-spread is if anything
conservative — which isolates the commission as the cause of death if it dies.

## Horizon

Daily bars, weekly rebalance, held between rebalances.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` | 3, 5, 10, 21 (4 values) | yes |
| `n_long` | 2, 3, 4 (3 values) | yes |

**12 variants.**

## What would falsify this

The prediction here is **failure at gate 2 specifically**. It is falsified by:

- net/gross above 0.60, which would mean I have misjudged the commission drag
  twice in two trials and should rebuild the cost model rather than trust it;
- the family passing gates 1–8, which would be a genuine surprise and would
  demand the engine be checked before the strategy is believed.

A failure at gate 3 or 4 instead of gate 2 is **not** a confirmation. It would
mean the family had no gross edge to erode, which is a different finding from
the one predicted here, and the report must distinguish them.
