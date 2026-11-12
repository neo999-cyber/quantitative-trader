# `p6_trend_reset_v1_trend` — the filter-only control of `p6_trend_reset_v1`

*Registered 12 November 2026 beside the family's memo (`docs/prereg/p6_trend_reset_v1.md`), before any return was
computed. This document names the sweep so gate 0 can find it; it is a control, never a candidate.*

**What it is.** **1 variant** (`control = trend`, `hold = 63`): enter on the trend filter alone, the same five slots, hold and exit. Condition (2) of the memo: the rule's median variant must beat it at a Newey–West t ≥ 2.

Run (with `QR_ROOT=~/qr/lake`):

    qr gates --family trend_reset --hypothesis p6_trend_reset_v1_trend --market trend-xnas --basket nasdaq31 \
      --costs alpaca_frac --equity 1000 --benchmark exposure --risk-free fred --start 2019-07-01 --end 2025-08-31 \
      --param hold=63 --param control=trend --all-gates --upto 8
