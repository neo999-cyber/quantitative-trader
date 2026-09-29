# Pre-registration: `p2_venue_spread_v1` — cross-venue funding spread, Binance against Bybit

*Written 17 September 2026, before any run. The unit panel was built and
read (counts, the spread's distribution and persistence, the unit's own
return volatility) before this document; no strategy was run on it.*

## Mechanism

The same levered longs pay funding on every venue, but each venue clears
its own rate from its own order book, so at any time one venue's perp pays
more than another's for the same coin. A position long the perp on the
lower-rate venue and short the perp on the higher-rate venue collects the
difference and carries no directional exposure — both legs are the same
contract on the same coin. The forced trader is the venue-captive long
(retail on one app, an institution restricted to another) who pays the
local rate rather than the cheapest one; what keeps the spread open is
that the arbitrage needs margin on two venues at once. The claim is that
the spread **persists** long enough to be collected net of two taker legs.

## Data and unit

`xvenue-um` (`qr/data/xvenue.py`): Binance USDⓈ-M daily bars and daily
funding (the lake's `futures/um` and `futures-um`), Bybit linear-perp daily
bars and funding from the public REST API (`mirror/bybit`, pulled 16–17
September 2026, 765 symbols). Two units a symbol: `<SYM>-BNBY` (long
Binance / short Bybit) and `<SYM>-BYBN`, exact mirrors, so the long-only
`FundingCarry` family holds whichever side is being paid. The unit's
price is the long leg's close over the short leg's; `perp_funding_rate` is
the spread the unit collects (short leg's rate minus long leg's), summed
per UTC day; `quote_volume` is the thinner leg's.

Read before writing: 471 symbols → 942 units, 2020-03-25 → 2026-08-31,
median 606 days a unit; 123 units live on a median day (94 in 2022, 296 in
2025); one unit fails QA (excluded by gate 1's own rule, not by hand).
The 7-day trailing spread, annualised: 5th/25th/50th/75th/95th percentiles
−15.6% / −1.7% / +0.9% / +5.1% / +20.7%; |spread| exceeds 5%/yr on 13% of
unit-days, 10% on 7%, 20% on 3%. Persistence: correlation of the trailing
7-day spread with the next 7 days' is **0.20** (C1's funding level was
higher). The unit's daily close-to-close vol has median 13 bps (95th
percentile 39 bps); the cross-venue basis is 5 bps in absolute median.

## Predicted sign and size

Positive against cash. Net of two taker legs: annualised net return
**2% to 8%**, volatility **1% to 4%**, net Sharpe **1 to 3**; funding
received **at least 80%** of gross (`carry_share_of_gross`); drawdown
under 5%. The always-in control (every unit with a positive spread, no
floor) earns the mean spread, ~1%/yr, and less than costs.

## Universe

`carry_top40`'s rule on the unit panel: trailing 30-day median of the
thinner leg's quote volume, **top 80 units = 40 symbols** (each symbol's
two sides share a volume), rebalanced monthly, 90-day minimum history, 15%
annualised volatility floor over 90 days on `spot_close` (the Binance perp
close).

## Rule and parameters

`FundingCarry` unchanged: trailing `lookback`-day mean of the unit's
spread, annualised; open a unit when it clears `entry`, keep while above
`exit` = entry / 3, up to `n_max` units, equal weight, daily decisions.
No ceiling (`ceiling = 1.0`): the crash filter belongs to the funding
*level*, and a cross-venue spread is not a crowding signal.

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` (days) | 3, 7, 14 | yes |
| `entry` (annualised spread) | 0.05, 0.10, 0.20 | yes |
| `exit` | entry / 3 | tied |
| `n_max` | 5, 10 | yes |
| `ceiling` | 1.0 | fixed |
| `rebalance` | 1 | fixed |

**18 variants.** Gate 4 deflates against them.

    qr gates --family funding_carry --hypothesis p2_venue_spread_v1 \
      --market xvenue-um --costs xvenue \
      --n 80 --lookback 30 --min-history 90 --vol-lookback 90 \
      --benchmark cash --risk-free fred --start 2021-01-01 --end 2025-08-31 \
      --grid 'lookback=[3,7,14]' --grid 'entry=[0.05,0.10,0.20]' --grid 'n_max=[5,10]' \
      --param ceiling=1.0 --param rebalance=1 --all-gates --upto 8

Control `p2_venue_spread_v1_always_in`: `--param entry=-1.0 --param
exit=-2.0 --param ceiling=1.0 --param n_max=80 --param lookback=7`, one
variant, same panel, universe and costs.

## Cost model, benchmark, capital, stress, falsifiers

`CostModel.carry_pair(binance_perp, bybit_perp)`: Binance regular-user
taker with BNB (4.5 bps) + Bybit non-VIP taker (5.5 bps, published
schedule, unverified) + half-spreads 1 + 1.5 bps = **12.5 bps a side, 25
bps a round trip**; 50 bps stressed. Funding gross at the archived rates.
Cash benchmark at FRED DTB3. Capital committed = both legs' margin + 20%
reserve; the smallest book is $1,000 across two venues, stated.

Falsifiers:
- net Sharpe below 0.5, or negative at 2× costs → gates 2–3;
- `carry_share_of_gross` below 50% → the return is basis noise, not the
  spread;
- the always-in control within 0.3 Sharpe of the best variant → the
  selection is not the driver;
- DSR below 0.90 over 18 → gate 4; SPA p > 0.5 vs cash → gate 5;
- holdout (1 September 2025 → 31 August 2026, opened once after gates
  1–8) Sharpe negative or below half the deflated Sharpe → gate 9.

## Prior

The spread is real but thin and short-lived (persistence 0.20): a 10%/yr
spread pays 2.7 bps a day against a 25 bps round trip, so a unit must be
held nine days to break even and the signal decays faster than that.
Expected: gross positive, net Sharpe below 1, gate 2 or 3 failing; the
mechanism survives only if the top-`entry` tail persists longer than the
average does.
