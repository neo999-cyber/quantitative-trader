# Control: `p2_oi_reversal_v1_unconditioned` — the same reversal without the OI condition

*Registered by the night chain beside `p2_oi_reversal_v1`, before any run.
One variant (the family's central setting with `oi_min=-1`, so every member
qualifies): weekly long the bottom 5 / short the top 5 by trailing 7-bar
return in ranks 31–150. If it earns as much as the family, OI adds nothing.*

    qr gates --family oi_reversal --hypothesis p2_oi_reversal_v1_unconditioned \
      --market futures/um --costs perp --n 150 --rank-min 31 --min-history 90 \
      --benchmark cash --risk-free fred --start 2021-12-01 --end 2025-08-31 \
      --param lookback=7 --param oi_lookback=7 --param oi_min=-1 --param n_side=5 \
      --param rebalance_on=W --all-gates --upto 8
