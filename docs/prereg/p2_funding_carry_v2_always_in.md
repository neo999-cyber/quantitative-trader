# Control: `p2_funding_carry_v2_always_in` — hold every eligible hourly carry unit

*Registered 16 September 2026, before any run. The always-in control of
`p2_funding_carry_v2`, on the same hourly `carry-um` panel, universe, costs,
benchmark and in-sample end. One variant, no search:*

    FundingCarry(entry=-1.0, exit=-2.0, ceiling=1.0, n_max=40, lookback=168, rebalance=24, percentile_window=365)

Invocation:

    qr gates --family funding_carry --hypothesis p2_funding_carry_v2_always_in \
      --market carry-um --interval 1h --costs carry \
      --n 40 --lookback 720 --min-history 4320 --vol-lookback 2160 \
      --benchmark cash --risk-free fred --end 2025-09-14 \
      --param entry=-1.0 --param exit=-2.0 --param ceiling=1.0 --param n_max=40 \
      --param lookback=168 --param rebalance=24 --param percentile_window=365 \
      --all-gates --upto 8

What it answers: whether v2's entry rule adds anything after its turnover
at hourly resolution. Predicted: positive against cash; a lower Sharpe than
the timed family; gate 6 near its null, as a timing-free book should be.
