# Pre-registration: `xsmom_v1` — cross-sectional momentum, 12-1 convention

*Written 11 September 2026, before the first run.*

## Mechanism

The same gradual-information and flow-autocorrelation argument as time-series momentum, but applied *relatively*: the coins that have outperformed their peers continue to, for as long as the flows chasing them continue.

The cross-sectional version has one structural advantage over the time-series one in this context. It is **dollar-neutral in spirit even when long-only in practice**, because holding the best five of thirty is a bet on dispersion rather than on direction. That should reduce beta to BTC, which is precisely what I expect the time-series family to fail on.

The `skip` window is not decoration. The most recent stretch of any momentum window carries short-term *reversal*, which works against the signal; the standard equity formulation measures twelve months ending one month ago for exactly this reason. Crypto's natural scale is shorter, so `skip` is swept rather than assumed.

## Predicted sign and size

**Positive.** Annualised net Sharpe of **0.4 to 0.9** after costs — lower than the time-series family, because a weekly-rebalanced ranked book trades considerably more.

**Beta to BTC of 0.1 to 0.4**, materially lower than time-series momentum. Predicted alpha t-statistic: **above 2**, and unlike the time-series family I expect this one to have a genuine chance of clearing it.

Turnover is the risk here: ranking thirty names and holding five, rebalanced weekly, is a lot of trading at 19 bps a round trip.

## Universe

`binance_spot_top30`, identical to `tsmom_v1` and fixed before the run. Rebalanced monthly, 180-bar minimum history, delisted pairs included for as long as they traded.

## Horizon

Daily bars, weekly rebalance. The selection is held between rebalances rather than recomputed each bar — rebalancing a ranked book daily multiplies turnover by seven, and at these costs that alone decides the outcome.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` | 30, 60, 90, 120, 180, 252 (6 values) | yes |
| `skip` | 0, 5, 10, 21 (4 values) | yes |
| `n_long` | 3, 5, 8 (3 values) | yes |
| `rebalance` | 7, 14 (2 values) | yes |
| `vol_target` | 0.20 | fixed |
| `vol_lookback` | 30 | fixed |
| `max_leverage` | 1.0 | fixed |

**144 variants**, four swept parameters. Four is under gate 8's limit of five, but only just, and `n_long` and `rebalance` are structural choices rather than fitted ones — if the result depends sharply on either, that is a spike surface and gate 8 should say so.

## Cost model

`CostModel.trial()`: 9.5 bps per side, 19 bps a round trip, fee tier verified 11 September 2026. Gate 2 stress at 2×.

## Out-of-sample period

The final 12 months of the available sample, opened exactly once after gates 1–8.

## What would falsify this

- **Net/gross below 60%** → gate 2. This is the most likely failure mode for this family and the reason gate 2 runs third: a weekly-rebalanced ranked book in the most volatile names is where transaction costs go to eat returns.
- Deflated Sharpe below 0.90 over 144 variants → gate 4.
- PBO above 0.20 *with* the selection losing out of sample more than 10% of the time → gate 5.
- Alpha t below 2 → gate 8.
- Holdout negative → gate 9.

## Prior

I expect this family to have the **best chance of the four at gate 8** and the **worst chance at gate 2**. If it survives its own turnover, it is the most interesting of the four.
