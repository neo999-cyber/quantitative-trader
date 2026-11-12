# `p6_trend_reset_v1_etf_trend` — the ETF arm's filter-only control of `p6_trend_reset_v1`

*Registered 12 November 2026 beside the family's memo (`docs/prereg/p6_trend_reset_v1.md`), before any return was
computed. This document names the sweep so gate 0 can find it; it is a control, never a candidate.*

**What it is.** **1 variant** (`control = trend`) on the ETF arm's market, basket and window. Reported beside condition (5).

Run (with `QR_ROOT=~/qr/lake`):

    qr gates --family trend_reset --hypothesis p6_trend_reset_v1_etf_trend --market trend-etf --basket etf12 \
      --costs alpaca_frac --equity 1000 --benchmark exposure --risk-free fred --start 2007-01-01 --end 2022-12-31 \
      --param hold=63 --param control=trend --all-gates --upto 8
