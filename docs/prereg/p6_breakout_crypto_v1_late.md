# `p6_breakout_crypto_v1_late` — the one-day-late entry of `p6_breakout_crypto_v1`

*Registered 12 November 2026 beside the family's memo (`docs/prereg/p6_breakout_crypto_v1.md`), before any return was
computed. This document names the sweep so gate 0 can find it; it is a control, never a candidate.*

**What it is.** **8 variants** (the candidate's grid, `control = late`): enters one bar after the rule's signal with the signal bar's stop, the same exits. Condition (4): the rule's median variant must not be behind it.

Run (with `QR_ROOT=~/qr/lake`):

    qr gates --family momentum_breakout --hypothesis p6_breakout_crypto_v1_late --market spot --n 100 --costs spot \
      --benchmark exposure --risk-free fred --start 2018-01-01 --end 2025-04-30 \
      --grid 'base=[5,10]' --grid 'tight=[2.0,2.5]' --grid 'trail=[10,20]' --param control=late --all-gates --upto 8
