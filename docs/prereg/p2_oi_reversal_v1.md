# Pre-registration: `p2_oi_reversal_v1` — OI-conditioned reversal, mid-cap perpetuals, long/short

*Written 16 September 2026 at 21:50 Dubai time, before the open-interest
data finished downloading and before any run. Registration is by the night
chain (`scripts/night4_2026-09-16.sh`) only if the mechanical universe check
(`scripts/c5_universe_check.py`, criteria below) passes; the chain reads no
return before registering. If the check fails, nothing is registered and
the owner reads the printout in the morning.*

## Mechanism

Levered latecomers crowd into a coin that has run: open interest rises with
the price. The unwind — liquidation, deleveraging, funding cost — reverses
the move. Ranks 31–150 by volume only: the March 2026 SSRN post-mortem
(Azka Fayez Junior) finds plain OHLCV and funding sorts on large caps carry
nothing, and the plan (`docs/20` §5, C5) restricts the family to mid-caps
and conditions on OI change for that reason. Perpetuals make the short leg
native; funding is settled gross on both legs.

## Predicted sign and size

**Positive against cash**: gross 6–15% a year at 15–25% volatility on a
dollar-neutral book, net Sharpe **0.3 to 1.0**; the loser leg earns more
than the winner leg loses (the unwind is asymmetric). A net Sharpe above 2
is a reason to look for a leak (an OI stamp ahead of its bar).

## Data and universe

Binance USDⓈ-M daily perp bars (`futures/um`, in the lake) with the daily
open-interest feature (last 5-minute reading of the day, from the bucket's
`metrics` files, available from December 2021) attached by the lake.
Universe `futures_um_ranks31_150`: trailing 30-bar median quote volume,
**ranks 31 to 150**, monthly, 90-bar minimum history, 15% volatility floor,
pegs/fiat/leveraged excluded by the existing rules.

**Mechanical check before registration** (all must hold): median members a
bar ≥ 100; median share of member-bars with an OI reading ≥ 0.8; no peg,
fiat, gold or leveraged token among members; OI observed from no later
than 1 March 2022. Sample: 2022-01-01 → 2025-08-31 in-sample (about 3.7
years, ~190 weekly decisions — short, and stated), holdout 2025-09-01 →
2026-08-31, opened once after gates 1–8.

## Rule and parameters

Weekly (Monday bar). Among members whose OI rose by at least `oi_min` over
the trailing `oi_lookback` bars, rank by the trailing `lookback`-bar
return: long the bottom `n_side` (losers), short the top `n_side` (winners),
equal weight, gross 1.0, net 0, held to the next decision. Fewer than
`2 × n_side` qualifying names → flat.

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` (bars) | 3, 7, 14 | yes |
| `oi_lookback` (bars) | 7 | fixed |
| `oi_min` (OI change to count as crowded) | 0.05, 0.10, 0.20 | yes |
| `n_side` | 5, 10 | yes |
| `rebalance_on` | W | fixed |

**18 variants.**

    qr gates --family oi_reversal --hypothesis p2_oi_reversal_v1 \
      --market futures/um --costs perp --n 150 --rank-min 31 --min-history 90 \
      --benchmark cash --risk-free fred --start 2021-12-01 --end 2025-08-31 \
      --grid 'lookback=[3,7,14]' --grid 'oi_min=[0.05,0.10,0.20]' --grid 'n_side=[5,10]' \
      --param oi_lookback=7 --param rebalance_on=W --all-gates --upto 8

## Cost model, benchmark, controls

`CostModel.binance_perp()` (4.5 bps taker + 1 bp half-spread a side, 11
bps a round trip per leg, funding gross; 2× stressed). Benchmark: cash.
Controls: the same sort **without the OI condition** (`oi_min=-1`,
registered as `p2_oi_reversal_v1_unconditioned`) — if it earns as much,
OI adds nothing and the family is plain weekly reversal, which the
post-mortem says is nothing; and hold-BTC-perp, reported beside it.

## What would falsify this

- Net Sharpe below 0.5 or negative at 2× costs → gates 2–3.
- DSR below 0.90 over 18 → gate 4. SPA p > 0.5 vs cash → gate 5.
- The unconditioned control earning as much → OI is not the driver.
- The loser leg not outperforming the winner leg → the asymmetry the
  mechanism predicts is absent.
- Holdout Sharpe negative or below half the deflated Sharpe → gate 9.

## Prior

Fail at gate 3 or 4: weekly crypto reversal is well arbitraged even in
mid-caps, and 3.7 years is a short sample for 18 variants.
