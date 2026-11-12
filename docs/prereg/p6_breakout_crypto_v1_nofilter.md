# `p6_breakout_crypto_v1_nofilter` — the rule without the market filter of `p6_breakout_crypto_v1`

*Registered 12 November 2026 beside the family's memo (`docs/prereg/p6_breakout_crypto_v1.md`), before any return was
computed. This document names the sweep so gate 0 can find it; it is a control, never a candidate.*

**What it is.** **8 variants** (the candidate's grid, `control = nofilter`): the rule with BTCUSDT's 10/20-day filter removed. Reported beside conditions (2)–(4): it labels a pass filter-free or not.

Run (with `QR_ROOT=~/qr/lake`):

    qr gates --family momentum_breakout --hypothesis p6_breakout_crypto_v1_nofilter --market spot --n 100 --costs spot \
      --benchmark exposure --risk-free fred --start 2018-01-01 --end 2025-04-30 \
      --grid 'base=[5,10]' --grid 'tight=[2.0,2.5]' --grid 'trail=[10,20]' --param control=nofilter --all-gates --upto 8
