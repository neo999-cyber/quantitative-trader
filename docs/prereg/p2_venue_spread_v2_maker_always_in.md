# Pre-registration: `p2_venue_spread_v2_maker_always_in` — control for `p2_venue_spread_v2_maker`

*Drafted 13 October 2026 with the parent. One variant, no search. Not
registered until the owner says so, with the parent.*

The always-in cross-venue book at the measured maker cost: every unit in
the universe with a positive 7-day trailing spread, no entry floor, no
ceiling (`FundingCarry(lookback=7, entry=-1.0, exit=-2.0, ceiling=1.0,
n_max=80, rebalance=1)`), on the same `xvenue-um` panel, `carry_top40`
universe rule (top 80 units), `--costs xvenue_maker` (the Binance leg at
stage 1's measured maker model with its weekday/weekend fill-rate
haircut, the Bybit leg taker), ledger engine, cash benchmark at FRED
DTB3, 2021-01-01 → 2025-08-31. It measures what the mean spread pays
after one measured maker leg and one taker leg; the parent's claim is
that the selection by `entry` beats it by at least 0.3 Sharpe. On v1's
cost it lost outright (ledger: net −5.13, the daily re-hedging of a
near-zero gross).
