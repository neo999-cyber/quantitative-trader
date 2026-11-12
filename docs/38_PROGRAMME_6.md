# Programme 6 — rules from the owner's videos (opened 12 November 2026)

Two candidates, each from a video the owner sent: `p6_trend_reset_v1` (the trend-with-momentum-reset rule from a
clip on trading with AI agents, `docs/research/12`), and `p6_breakout_crypto_v1` (a momentum-breakout method made
exact for Binance spot, registered from a separate session; its own memo and record). This file records the first.

## 1. `p6_trend_reset_v1` — ran once, FAILED (12 November 2026)

Registered on the owner's "register it and run it" with its five control sweeps (seq 1057–1062), then run once,
18:15–18:46 local; outputs in `reports/p6/` (the six gate reports, `p6_compare_2026-11-12.md`, the run log).

| sweep | best net Sharpe | gate 3 t | gate 5 (SPA *p* vs exposure-matched holding) | gate 6 (random entry *p*) | gate 8 alpha t |
|---|---|---|---|---|---|
| candidate, 31 Nasdaq names | 0.99 | 2.63 | FAIL, 0.711 (PBO 0.56) | FAIL, 0.204 | FAIL, 1.18 |
| `_trend` (filter alone) | 0.87 | 2.29 | — | FAIL, 0.537 | FAIL, 0.54 |
| `_mirror` (strength) | 0.90 | 2.37 | FAIL, 0.740 | FAIL, 0.443 | FAIL, 0.95 |
| `_placebo` (random names) | 0.84 | 2.32 | FAIL, 0.781 | FAIL, 0.572 | FAIL, 0.53 |
| `_etf`, twelve ETFs 2007–2022 | 0.83 | 3.45 | WARN, 0.317 | PASS, 0.010 | WARN, 2.85 |
| `_etf_trend` (filter alone) | 0.72 | 3.08 | — | PASS, 0.020 | WARN, 2.43 |

The registered comparison, on each sweep's median variant (Newey–West t on the daily difference in net return):

| the rule against | points a year | t | memo's bar | met |
|---|---|---|---|---|
| its trend filter alone | −6.2 | −0.99 | t ≥ 2 | no |
| the random-name placebo | +1.9 | +0.32 | t ≥ 2 | no |
| buying strength | +2.3 | +0.40 | not behind | yes |
| ETF arm, against its filter alone | −2.4 | −1.77 | reported | — |

**What it says.** On the Nasdaq names the rule is the market: it makes money because the names rose, does not beat
holding them at its own exposure, and picks names no better than chance. **Waiting for the reset adds nothing** —
it trails the plain trend filter on both arms. On the ETFs the trend filter itself carries something (gate 6 passes,
alpha t 2.4–2.9, the known trend premium across asset classes that `etf_tsmom_v1` also found), and the reset again
subtracts from it. The prediction in the memo — a fail at gate 5 — held.

**Gate 1 failed on every sweep, and does not change the verdict.** Its data-quality check rejected the eleven
Nasdaq names with splits and the eleven ETFs that pay dividends. The cause is a convention clash introduced while
building the instruments, not bad prices: `qa.check_klines` expects raw share volume and rescales the implied VWAP by
`close / close_unadjusted`; the instruments restated volume into the adjusted price space (to satisfy
`Panel.tradable`, which applies no factor), so the check adjusted twice. The two engine checks disagree on the price
space of an adjusted frame. **Fixed the same evening on branch `claude/reverent-khayyam-c5f801` (commit `0adbaf8`,
17:53 Dubai, before this run, which therefore ran the old check):** `qa.check_klines` now judges dollars over shares
in the frame's own price space, as `Panel.tradable` does, and the Tiingo ingest states share volume in that space;
measured on the real lake after it, all 12 `etf`, 12 `trend-etf` and 31 `trend-xnas` frames pass. Gates 2–8
ran (`--all-gates`) on the same prices, and the candidate fails gates 5, 6 and 8 and conditions (2) and (3) on
their own. No rerun: one registered run, and its answer does not depend on gate 1.

Holdout shut. Nothing forward. The rule is closed.
