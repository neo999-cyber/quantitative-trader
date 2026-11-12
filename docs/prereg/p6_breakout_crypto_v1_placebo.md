# `p6_breakout_crypto_v1_placebo` — the random-day placebo of `p6_breakout_crypto_v1`

*Registered 12 November 2026 beside the family's memo (`docs/prereg/p6_breakout_crypto_v1.md`), before any return was
computed. This document names the sweep so gate 0 can find it; it is a control, never a candidate.*

**What it is.** **8 variants** (the candidate's grid, `control = placebo`, seed 20261112): for each name as many entries as the rule made, on bars drawn at random among its eligible bars, the stop by the same formula, the same exits. Condition (3): the rule's median variant must beat it, volatility-matched, at a t ≥ 2.

Run (with `QR_ROOT=~/qr/lake`):

    qr gates --family momentum_breakout --hypothesis p6_breakout_crypto_v1_placebo --market spot --n 100 --costs spot \
      --benchmark exposure --risk-free fred --start 2018-01-01 --end 2025-04-30 \
      --grid 'base=[5,10]' --grid 'tight=[2.0,2.5]' --grid 'trail=[10,20]' --param control=placebo --all-gates --upto 8
