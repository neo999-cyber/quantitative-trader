# Pre-registration: `p2_venue_spread_v1_always_in` — control for `p2_venue_spread_v1`

*Written 17 September 2026 with the parent. One variant, no search.*

The always-in cross-venue book: every unit in the universe with a positive
7-day trailing spread, no entry floor, no ceiling (`FundingCarry(lookback=7,
entry=-1.0, exit=-2.0, ceiling=1.0, n_max=80, rebalance=1)`), on the same
`xvenue-um` panel, `carry_top40` universe rule (top 80 units), `--costs
xvenue`, cash benchmark, 2021-01-01 → 2025-08-31. It measures what the
mean spread pays after two taker legs; the parent's claim is that the
selection by `entry` beats it by at least 0.3 Sharpe.
