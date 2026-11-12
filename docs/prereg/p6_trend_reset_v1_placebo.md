# `p6_trend_reset_v1_placebo` — the random-name placebo of `p6_trend_reset_v1`

*Registered 12 November 2026 beside the family's memo (`docs/prereg/p6_trend_reset_v1.md`), before any return was
computed. This document names the sweep so gate 0 can find it; it is a control, never a candidate.*

**What it is.** **8 variants** (the candidate's grid, `control = placebo`, seed 20261112): on each bar as many positions as the rule opened, in names drawn at random among those in an uptrend and not held. Condition (3): the rule's median variant must beat it at a t ≥ 2.

Run (with `QR_ROOT=~/qr/lake`):

    qr gates --family trend_reset --hypothesis p6_trend_reset_v1_placebo --market trend-xnas --basket nasdaq31 \
      --costs alpaca_frac --equity 1000 --benchmark exposure --risk-free fred --start 2019-07-01 --end 2025-08-31 \
      --grid 'roc=[21,63]' --grid 'was_high=[1.0,1.5]' --grid 'near_zero=[0.25,0.5]' --param hold=63 --param control=placebo --all-gates --upto 8
