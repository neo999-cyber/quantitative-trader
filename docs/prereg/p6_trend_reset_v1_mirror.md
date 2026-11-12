# `p6_trend_reset_v1_mirror` — the strength mirror of `p6_trend_reset_v1`

*Registered 12 November 2026 beside the family's memo (`docs/prereg/p6_trend_reset_v1.md`), before any return was
computed. This document names the sweep so gate 0 can find it; it is a control, never a candidate.*

**What it is.** **4 variants** (`roc ∈ {21, 63}` × `was_high ∈ {1.0, 1.5}`, `hold = 63`, `control = mirror`): enter when the scaled rate of change is at or above `was_high` today. Condition (4): the rule's median variant must not trail it.

Run (with `QR_ROOT=~/qr/lake`):

    qr gates --family trend_reset --hypothesis p6_trend_reset_v1_mirror --market trend-xnas --basket nasdaq31 \
      --costs alpaca_frac --equity 1000 --benchmark exposure --risk-free fred --start 2019-07-01 --end 2025-08-31 \
      --grid 'roc=[21,63]' --grid 'was_high=[1.0,1.5]' --param hold=63 --param control=mirror --all-gates --upto 8
