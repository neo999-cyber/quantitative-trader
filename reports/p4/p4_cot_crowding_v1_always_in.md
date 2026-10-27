# Hypothesis Report — `p4_cot_crowding_v1_always_in`

## Verdict: **FAIL**

stopped at gate 1 (data integrity): gross Sharpe 9.3 at the honest lag is not a plausible daily edge; the signal is reading the bar it predicts

| | |
|---|---|
| Strategy | `carry_crowding_timer_controlalways_in_gross1_p90_window52` (family `carry_crowding_timer`) |
| Parameters | `{'p': 90.0, 'window': 52, 'control': 'always_in', 'gross': 1.0}` |
| Universe | 1 symbols, 2020-01-01 00:00:00+00:00 → 2024-12-31 00:00:00+00:00 |
| **Trials counted** | **1** |
| Data manifest | `a98a8c46ccf20daf8d9c368f40fdbaf9` |
| Cost model | `carry[binance_spot_vip0_bnb_taker+binance_perp_maker_measured_2026-10_all]` at 10.73 bps/side, fees verified 2026-09-11 |
| Generated | 2026-10-27T15:07:15+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-10-27T14:38:16 |
| 1 | Data integrity | **FAIL** | gross Sharpe 9.3 at the honest lag is not a plausible daily edge; the signal is reading the bar it predicts |
| 2 | Cost survival | — | _not reached_ |
| 3 | Single-strategy significance | — | _not reached_ |
| 4 | Multiple-testing deflation | — | _not reached_ |
| 5 | Selection overfitting | — | _not reached_ |
| 6 | Permutation | — | _not reached_ |
| 7 | Cross-validated OOS distribution | — | _not reached_ |
| 8 | Robustness and regime | — | _not reached_ |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | — |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | — |
| Probability of backtest overfitting (gate 5) | — |
| Bar-permutation p (gate 6) | — |
| …with volatility preserved (reported, not binding) | — |
| HAC t-statistic (gate 3) | — |
| Probabilistic Sharpe (gate 3) | — |
| Net / gross return (gate 2) | — |
| In-sample net Sharpe (the backtest number) | — |
| cagr | 0.1348 |
| ann vol | 0.01441 |
| max drawdown | -0.02312 |
| ann turnover | 8.042 |
| round trips | 1 |
| time in market | 0.9995 |
| carry share of gross | 1.009 |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 22a0675acb3d92cd67dec5b3f381c9bc91eb6ccf7b7ff2981033d7708d2f4f92 |
| registered_at | 2026-10-27T14:38:16.759774+00:00 |
| registrations | 1 |
| source | docs/prereg/p4_cot_crowding_v1_always_in.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 0 |
| qa_warnings | 0 |
| qa_failures_traded | 0 |
| qa_failed_symbols | [] |
| qa_failures_on_raw_bars | 0 |
| qa_bars_excluded | 0 |
| lag0_gross_sharpe | 9.343 |
| lag1_gross_sharpe | 9.343 |
| lag2_gross_sharpe | 9.34 |
| peek_ratio | 1 |
| spike_ratio | 1 |
| spike_z | 0 |
| sharpe_standard_error | 0.447 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 1 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
