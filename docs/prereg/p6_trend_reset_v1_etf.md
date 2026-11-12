# `p6_trend_reset_v1_etf` — the ETF arm of `p6_trend_reset_v1`

*Registered 12 November 2026 beside the family's memo (`docs/prereg/p6_trend_reset_v1.md`), before any return was
computed. This document names the sweep so gate 0 can find it; it is a control, never a candidate.*

**What it is.** **8 variants** (the candidate's grid, `control = none`) on `trend-etf`, basket `etf12`, in-sample 2007-01-01 → 2022-12-31: the list of names has no hindsight. Condition (5), reported: its gate-8 alpha; a pass without it is labelled survivor-universe only.

Run (with `QR_ROOT=~/qr/lake`):

    qr gates --family trend_reset --hypothesis p6_trend_reset_v1_etf --market trend-etf --basket etf12 \
      --costs alpaca_frac --equity 1000 --benchmark exposure --risk-free fred --start 2007-01-01 --end 2022-12-31 \
      --grid 'roc=[21,63]' --grid 'was_high=[1.0,1.5]' --grid 'near_zero=[0.25,0.5]' --param hold=63 --param control=none --all-gates --upto 8
