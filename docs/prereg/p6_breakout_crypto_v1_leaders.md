# `p6_breakout_crypto_v1_leaders` — the momentum-leaders control of `p6_breakout_crypto_v1`

*Registered 12 November 2026 beside the family's memo (`docs/prereg/p6_breakout_crypto_v1.md`), before any return was
computed. This document names the sweep so gate 0 can find it; it is a control, never a candidate.*

**What it is.** **2 variants** (`base` = 5 and `tight` = 2.0 fixed, as they do not enter; `trail` ∈ {10, 20}; `control = leaders`): enters on any bar a name is an eligible leader in trend under the market filter — no base, no breakout, no volume — with the rule's exits. Condition (2): the rule's median variant must beat it, volatility-matched, at a t ≥ 2.

Run (with `QR_ROOT=~/qr/lake`):

    qr gates --family momentum_breakout --hypothesis p6_breakout_crypto_v1_leaders --market spot --n 100 --costs spot \
      --benchmark exposure --risk-free fred --start 2018-01-01 --end 2025-04-30 \
      --param base=5 --param tight=2.0 --grid 'trail=[10,20]' --param control=leaders --all-gates --upto 8
