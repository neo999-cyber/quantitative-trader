# Pre-registration: `reversal_v1` — weekly short-term reversal

*Written 11 September 2026, before the first run.*

## Mechanism

A coin that fell hard over a week did so partly because sellers needed liquidity, not only because its prospects changed. Someone has to take the other side of a forced or impatient sale, and the compensation for doing so is the reversal. This is the oldest microstructure argument there is, and it is the one effect on this list whose mechanism is about *market structure* rather than about information.

The mechanism also tells you exactly where it dies: the compensation for providing liquidity is paid in basis points, and the strategy pays basis points to trade. If the round trip costs more than the reversal is worth, there is no strategy — only a transfer to the venue.

## Predicted sign and size

**Positive gross, uncertain net.** Gross annualised Sharpe of **0.5 to 1.2**; net Sharpe of **0 to 0.5** after 19 bps a round trip.

I am explicitly predicting that **net/gross will be the binding number** and may well fall below gate 2's 60% floor. Predicted beta to BTC: near zero or slightly negative — buying the biggest losers is close to a contrarian bet on the market itself.

## Universe

`binance_spot_top30`, identical to the other families and fixed before the run. The liquidity constraint matters more here than anywhere else: this family deliberately buys the names that just moved most, which are the names with the widest spreads at exactly the moment it wants to buy them. The flat 2 bps half-spread in the cost model is therefore **optimistic for this family specifically**, and that is stated here rather than discovered later.

## Horizon

Daily bars, weekly rebalance, holding the selection between rebalances.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` | 3, 5, 7, 10, 14, 21 (6 values) | yes |
| `n_long` | 3, 5, 8 (3 values) | yes |
| `rebalance` | 3, 7, 14 (3 values) | yes |
| `vol_target` | 0.20 | fixed |
| `vol_lookback` | 30 | fixed |
| `max_leverage` | 1.0 | fixed |

**54 variants**, three swept parameters — the smallest grid of the four, because the mechanism specifies a short horizon and there is no honest reason to search long ones.

## Cost model

`CostModel.trial()`: 9.5 bps per side, 19 bps a round trip, fee tier verified 11 September 2026. Gate 2 stress at 2×.

**Caveat recorded in advance:** the 2 bps half-spread is a flat assumption and this family trades the widest-spread moments in the universe. A pass at gate 2 that depends on the spread assumption should be treated as unproven until measured from intrabar data, and that condition is written here so it cannot be forgotten if the result is good.

## Out-of-sample period

The final 12 months of the available sample, opened exactly once after gates 1–8.

## What would falsify this

- **Net/gross below 50%** → gate 2 FAIL. The single most likely outcome.
- Positive gross Sharpe with negative net Sharpe → the mechanism is real and untradable at this size and venue. That is a *finding*, not a failure, and it should be recorded as one.
- Gate 1 spike warning: a one-bar-ahead signal produces the same lag profile as a look-ahead. This family genuinely predicts a short horizon, so a spike warning here is expected and needs a written justification rather than alarm.
- Alpha t below 2 → gate 8.

## Prior

**The most likely of the four to fail, and the most informative failure.** If the gross edge is there and costs eat it, that tells us something concrete about what would be needed to trade it: maker orders, a lower fee tier, or a venue with tighter spreads — all measurable, all in Phase 4's scope.
