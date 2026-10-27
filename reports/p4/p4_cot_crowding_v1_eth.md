# Hypothesis Report — `p4_cot_crowding_v1_eth`

## Verdict: **FAIL**

stopped at gate 1 (data integrity): gross Sharpe 8.4 at the honest lag is not a plausible daily edge; the signal is reading the bar it predicts

| | |
|---|---|
| Strategy | `carry_crowding_timer_controlnone_gross1_p95_window52` (family `carry_crowding_timer`) |
| Parameters | `{'p': 95.0, 'window': 52, 'control': 'none', 'gross': 1.0}` |
| Universe | 1 symbols, 2020-01-01 00:00:00+00:00 → 2024-12-31 00:00:00+00:00 |
| **Trials counted** | **6** |
| Data manifest | `a98a8c46ccf20daf8d9c368f40fdbaf9` |
| Cost model | `carry[binance_spot_vip0_bnb_taker+binance_perp_maker_measured_2026-10_all]` at 10.73 bps/side, fees verified 2026-09-11 |
| Generated | 2026-10-27T15:07:22+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-10-27T14:38:17 |
| 1 | Data integrity | **FAIL** | gross Sharpe 8.4 at the honest lag is not a plausible daily edge; the signal is reading the bar it predicts |
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
| cagr | 0.1607 |
| ann vol | 0.01913 |
| max drawdown | -0.01885 |
| ann turnover | 11.8 |
| round trips | 5 |
| time in market | 0.9611 |
| carry share of gross | 1.017 |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 96845f24401ecad4fa9224e5240afa303fb6ebb73c0e2c35e7231100cfc778c5 |
| registered_at | 2026-10-27T14:38:17.853083+00:00 |
| registrations | 1 |
| source | docs/prereg/p4_cot_crowding_v1_eth.md |
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
| lag0_gross_sharpe | 8.435 |
| lag1_gross_sharpe | 8.433 |
| lag2_gross_sharpe | 8.439 |
| peek_ratio | 1 |
| spike_ratio | 0.9993 |
| spike_z | -0.01402 |
| sharpe_standard_error | 0.447 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 6 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
