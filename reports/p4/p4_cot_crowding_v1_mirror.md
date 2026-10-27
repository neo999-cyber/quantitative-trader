# Hypothesis Report — `p4_cot_crowding_v1_mirror`

## Verdict: **FAIL**

stopped at gate 5 (selection overfitting): PBO = 0.03 over 12870 splits of 6 variants; SPA p = 0.542 vs buy-and-hold — no variant beats simply holding the universe

| | |
|---|---|
| Strategy | `carry_crowding_timer_controlmirror_gross1_p80_window52` (family `carry_crowding_timer`) |
| Parameters | `{'p': 80.0, 'window': 52, 'control': 'mirror', 'gross': 1.0}` |
| Universe | 1 symbols, 2020-01-01 00:00:00+00:00 → 2024-12-31 00:00:00+00:00 |
| **Trials counted** | **6** |
| Data manifest | `a98a8c46ccf20daf8d9c368f40fdbaf9` |
| Cost model | `carry[binance_spot_vip0_bnb_taker+binance_perp_maker_measured_2026-10_all]` at 10.73 bps/side, fees verified 2026-09-11 |
| Generated | 2026-10-27T15:07:18+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-10-27T14:38:17 |
| 1 | Data integrity | PASS | no lag spike (-0.1 standard errors over its neighbours) |
| 2 | Cost survival | PASS | 84% of gross survives; Sharpe 3.35 at 2x costs; capacity about $1,000,000,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | PASS | t = 4.61, PSR = 1.000, CI excludes zero |
| 4 | Multiple-testing deflation | PASS | DSR = 1.000 over 6 trials (effective rank 2), haircut Sharpe 3.82 |
| 5 | Selection overfitting | **FAIL** | PBO = 0.03 over 12870 splits of 6 variants; SPA p = 0.542 vs buy-and-hold — no variant beats simply holding the universe |
| 6 | Permutation | — | _not reached_ |
| 7 | Cross-validated OOS distribution | — | _not reached_ |
| 8 | Robustness and regime | — | _not reached_ |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 1 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | — |
| Probability of backtest overfitting (gate 5) | 0.02572 |
| Bar-permutation p (gate 6) | — |
| …with volatility preserved (reported, not binding) | — |
| HAC t-statistic (gate 3) | 4.609 |
| Probabilistic Sharpe (gate 3) | 1 |
| Net / gross return (gate 2) | 0.8366 |
| In-sample net Sharpe (the backtest number) | 4.389 |
| cagr | 0.05641 |
| ann vol | 0.01252 |
| max drawdown | -0.02395 |
| ann turnover | 11.09 |
| round trips | 21 |
| time in market | 0.3963 |
| carry share of gross | 1.009 |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | ec00ba515219321caa1e3e56111ee6b1e6a36bd4e02c9e86cd7b11b6e1c121ab |
| registered_at | 2026-10-27T14:38:17.121477+00:00 |
| registrations | 1 |
| source | docs/prereg/p4_cot_crowding_v1_mirror.md |
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
| lag0_gross_sharpe | 5.37 |
| lag1_gross_sharpe | 5.318 |
| lag2_gross_sharpe | 5.284 |
| peek_ratio | 1.01 |
| spike_ratio | 0.9902 |
| spike_z | -0.1174 |
| sharpe_standard_error | 0.447 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 1e+09 |
| capacity_usd_pessimistic | 1e+09 |
| capacity_usd_optimistic | 1e+09 |
| gross_annual_return | 0.06569 |
| impact_budget_annual | 0.006569 |
| impact_coef | 1 |
| median_participation_at_capacity | 7.528e-17 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0 |
| impact_drag_at_1e+04 | 0 |
| impact_drag_at_3e+04 | 0 |
| impact_drag_at_1e+05 | 0 |
| impact_drag_at_3e+05 | 0 |
| impact_drag_at_1e+06 | 0 |
| impact_drag_at_3e+06 | 7.147e-06 |
| impact_drag_at_1e+07 | 6.555e-05 |
| impact_drag_at_3e+07 | 0.0001828 |
| impact_drag_at_1e+08 | 0.0004811 |
| impact_drag_at_3e+08 | 0.001091 |
| impact_drag_at_1e+09 | 0.002519 |
| cost_share_commission | 1 |
| cost_share_spread | 0 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 5.318 |
| net_sharpe | 4.389 |
| net_over_gross | 0.8366 |
| ann_turnover | 11.09 |
| cost_drag_ann | 0.01073 |
| sharpe_at_2x_costs | 3.346 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 4.609 |
| hac_pvalue | 4.044e-06 |
| hac_lags | 7 |
| psr | 1 |
| sharpe_ci_lower | 1.702 |
| sharpe_ci_upper | 6.907 |
| min_track_record_length | 69.08 |
| observations | 1,827 |
| skew | 1.236 |
| kurtosis | 47.37 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 6 |
| trials_raw | 6 |
| trials_effective | 2 |
| sharpe_variance | 0.002066 |
| deflation_benchmark_per_period | 0.05909 |
| dsr | 1 |
| haircut_sharpe_bhy | 3.823 |
| adjusted_p_bhy | 2.972e-05 |
| min_backtest_length_years | 0.1861 |
| sample_years | 5.005 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.02572 |
| median_logit | 1.792 |
| splits | 1.287e+04 |
| variants | 6 |
| blocks | 16 |
| degradation_slope | -0.8652 |
| prob_oos_loss | 0 |
| median_is_sharpe | 0.2493 |
| median_oos_sharpe | 0.2415 |
| is_oos_rank_correlation | 1 |
| benchmark | buyhold |
| spa_p_consistent | 0.542 |
| spa_p_lower | 0.542 |
| spa_p_upper | 1 |
| spa_models | 6 |
| spa_benchmark | buy_and_hold |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | -0.0716 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 6 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
