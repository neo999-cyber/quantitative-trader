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

## 2. `p6_breakout_crypto_v1` — ran once, FAILED (12 November 2026)

Qullamaggie's momentum breakout (`docs/research/13` §1), made exact for Binance spot and registered as Programme 6's
second hypothesis on the owner's "go with recommendation" (memo `docs/prereg/p6_breakout_crypto_v1.md`, seq 1123;
controls `_leaders` / `_placebo` / `_late` / `_nofilter`, seq 1124–1127). Registered only after the trend chain had
exited, because trial-log appends are not locked between processes. Ran once on the owner's "run it", 18:54–23:06
Dubai, five sweeps chained (`reports/p6/run_p6_breakout.log`); result note seq 1179; `qr trial verify` clean.

| sweep | gate 3 t | gate 4 DSR | gate 5 SPA *p* | gate 6 bar permutation *p* | gate 8 |
|---|---|---|---|---|---|
| candidate (8 variants) | **2.05 FAIL** | 0.957 | WARN (PBO 0.47) | 0.249 FAIL | FAIL: profitable in 50% of years, alpha t 1.73 |
| `_leaders` (no setup) | 1.56 | 0.94 | 0.166 | 0.249 | FAIL |
| `_placebo` (random eligible days) | 2.05 | 0.75 | 0.125 | 0.343 | FAIL |
| `_late` (one day late) | 1.32 | 0.84 | 0.290 | 0.582 | FAIL |
| `_nofilter` (no bitcoin filter) | 2.25 | 0.982 | 0.083 | 0.169 | FAIL |

The registered conditions on the median variants (`reports/p6/p6_breakout_crypto_v1_compare_2026-11-12.md`; the
control scaled to the rule's volatility, Newey–West t, 30 lags):

| the rule against | points a year | t | memo's bar | met |
|---|---|---|---|---|
| owning the momentum leaders | −1.4 | −0.11 | t ≥ 2 | no |
| random eligible days | +3.4 | +0.24 | t ≥ 2 | no |
| buying one day late | +3.8 | +0.48 | not behind | yes |
| the rule without the bitcoin filter (reported) | −10.8 | −0.84 | — | — |

What it says: the book makes money net of costs (95% of gross survives; Sharpe 0.53 on the median variant), but no
more than owning the same momentum leaders through the same exits, and no more than buying them on random eligible
days. The tight base, the breakout and the volume add nothing measurable; the bitcoin filter, if anything, costs.
That is the memo's prediction (a fail at gates 3/4/6, the setup within noise of the leaders control), and it is
Programme 1's crypto momentum result again with his entry and exit path added. Holdout shut. Nothing forward. The
rule is closed on crypto; with §1, the videos' momentum school is answered here.
