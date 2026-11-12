# Hypothesis Report — `p6_trend_reset_v1_etf`

## Verdict: **FAIL**

stopped at gate 1 (data integrity): QA failed for DBC, EEM, EFA, HYG, IEF, which this strategy holds

| | |
|---|---|
| Strategy | `trend_reset_controlnone_hold63_near_zero0p25_roc63_was_high1` (family `trend_reset`) |
| Parameters | `{'roc': 63, 'was_high': 1.0, 'near_zero': 0.25, 'hold': 63, 'control': 'none'}` |
| Universe | 12 symbols, 2007-01-03 00:00:00+00:00 → 2022-12-30 00:00:00+00:00 |
| **Trials counted** | **8** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `alpaca_us_equity_zero_commission_fractional` at 3 bps/side, fees verified 2026-09-15 (commission and cls rule; spread and slippage unmeasured) |
| Generated | 2026-11-12T14:44:18+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:15:35 |
| 1 | Data integrity | **FAIL** | QA failed for DBC, EEM, EFA, HYG, IEF, which this strategy holds |
| 2 | Cost survival | PASS | 96% of gross survives; Sharpe 0.80 at 2x costs; capacity about $10,000,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | PASS | t = 3.45, PSR = 1.000, CI excludes zero |
| 4 | Multiple-testing deflation | PASS | DSR = 0.998 over 8 trials (effective rank 2), haircut Sharpe 0.61 |
| 5 | Selection overfitting | WARN | PBO = 0.44 over 12870 splits of 8 variants; selection is arbitrary but stays profitable out of sample (0% losing) — the variants are interchangeable; SPA p = 0.317 vs exposure-matched buy-and-hold (64% invested) — **UNJUSTIFIED** |
| 6 | Permutation | PASS | bar permutation p = 0.030 (98th percentile, re-optimised over 8 of 8 variants); random entry p = 0.010; volatility-preserving null p = 0.672 (33th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | PASS | median path Sharpe 0.83 = 100% of in-sample; 100% of 9 paths positive; WFE 0.80 |
| 8 | Robustness and regime | WARN | alpha t = 2.85 — **UNJUSTIFIED** |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.998 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.8347 |
| Probability of backtest overfitting (gate 5) | 0.4417 |
| Bar-permutation p (gate 6) | 0.02985 |
| …with volatility preserved (reported, not binding) | 0.6716 |
| HAC t-statistic (gate 3) | 3.449 |
| Probabilistic Sharpe (gate 3) | 0.9995 |
| Net / gross return (gate 2) | 0.9551 |
| In-sample net Sharpe (the backtest number) | 0.8347 |
| cagr | 0.06222 |
| ann vol | 0.07576 |
| max drawdown | -0.08848 |
| ann turnover | 9.915 |
| round trips | 369 |
| time in market | 0.9454 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.04595 | 2.846 |
| beta to equal_weight | 0.2489 | — |
| information ratio | 0.6717 | — |
| R² | 0.1848 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 8515bbdd7c17564d4937243a5d057eee63adf2d9f2a6ed4569d5c059c6d1cb1c |
| registered_at | 2026-11-12T14:15:35.967223+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_trend_reset_v1_etf.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 11 |
| qa_warnings | 0 |
| qa_failures_traded | 11 |
| qa_failed_symbols | ['DBC', 'EEM', 'EFA', 'HYG', 'IEF', 'IWM', 'LQD', 'QQQ', 'SPY', 'TLT', 'VNQ'] |
| qa_failures_on_raw_bars | 11 |
| qa_bars_excluded | 0 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 1e+07 |
| capacity_usd_pessimistic | 3e+06 |
| capacity_usd_optimistic | 3e+07 |
| gross_annual_return | 0.06621 |
| impact_budget_annual | 0.006621 |
| impact_coef | 1 |
| median_participation_at_capacity | 3.658e-19 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0 |
| impact_drag_at_1e+04 | 8.737e-08 |
| impact_drag_at_3e+04 | 7.706e-06 |
| impact_drag_at_1e+05 | 7.127e-05 |
| impact_drag_at_3e+05 | 0.0002741 |
| impact_drag_at_1e+06 | 0.0007758 |
| impact_drag_at_3e+06 | 0.001798 |
| impact_drag_at_1e+07 | 0.004185 |
| impact_drag_at_3e+07 | 0.008355 |
| cost_share_commission | 0 |
| cost_share_spread | 1 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.8739 |
| net_sharpe | 0.8347 |
| net_over_gross | 0.9551 |
| ann_turnover | 9.915 |
| cost_drag_ann | 0.002974 |
| sharpe_at_2x_costs | 0.7954 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 3.449 |
| hac_pvalue | 0.0005627 |
| hac_lags | 9 |
| psr | 0.9995 |
| sharpe_ci_lower | 0.3393 |
| sharpe_ci_upper | 1.325 |
| min_track_record_length | 1,004 |
| observations | 4,028 |
| skew | -0.395 |
| kurtosis | 7.546 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 8 |
| trials_raw | 8 |
| trials_effective | 2 |
| sharpe_variance | 2.07e-05 |
| deflation_benchmark_per_period | 0.006638 |
| dsr | 0.998 |
| haircut_sharpe_bhy | 0.6063 |
| adjusted_p_bhy | 0.006118 |
| min_backtest_length_years | 5.969 |
| sample_years | 15.99 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.4417 |
| median_logit | 0.6931 |
| splits | 1.287e+04 |
| variants | 8 |
| blocks | 16 |
| degradation_slope | -0.8464 |
| prob_oos_loss | 0.001709 |
| median_is_sharpe | 0.05545 |
| median_oos_sharpe | 0.04229 |
| is_oos_rank_correlation | 0.1429 |
| benchmark | exposure |
| benchmark_exposure | 0.6363 |
| spa_p_consistent | 0.317 |
| spa_p_lower | 0.299 |
| spa_p_upper | 0.317 |
| spa_models | 8 |
| spa_benchmark | exposure_matched |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | 0.01936 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.8739 |
| bar_permutation_p_value | 0.02985 |
| bar_permutation_percentile | 97.5 |
| bar_permutation_null_median | 0.567 |
| bar_permutation_null_95th | 0.8325 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.8739 |
| random_entry_p_value | 0.00995 |
| random_entry_percentile | 99.5 |
| random_entry_null_median | 0.448 |
| random_entry_null_95th | 0.6684 |
| random_entry_permutations | 200 |
| reoptimised_over | 8 |
| grid_size | 8 |
| bar_permutation_vol_preserved_observed | 0.8739 |
| bar_permutation_vol_preserved_p_value | 0.6716 |
| bar_permutation_vol_preserved_percentile | 33 |
| bar_permutation_vol_preserved_null_median | 0.941 |
| bar_permutation_vol_preserved_null_95th | 1.196 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | FAIL |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.8347 |
| median_path_sharpe | 0.8347 |
| worst_path_sharpe | 0.6264 |
| best_path_sharpe | 0.8347 |
| share_paths_positive | 1 |
| median_over_is | 1 |
| walk_forward_efficiency | 0.7959 |
| walk_forward_efficiency_pooled | 0.8279 |
| walk_forward_windows | 5 |
| purge_bars | 63 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 3 |
| constructor_parameters | 5 |
| round_trips | 369 |
| neighbourhood_peak_sharpe | 0.8347 |
| neighbourhood_n_neighbours | 0 |
| neighbourhood_retention | — |
| years | 16 |
| share_profitable_years | 0.8125 |
| sharpe_without_best_year | 0.7349 |
| sharpe_without_best_5_trades | 0.6896 |
| sharpe_without_best_5_bars | 0.7483 |
| sharpe_in_low_vol | 0.834 |
| sharpe_in_mid_vol | 0.6543 |
| sharpe_in_high_vol | 1.014 |
| alpha_annual | 0.04595 |
| alpha_tstat | 2.846 |
| alpha_pvalue | 0.00443 |
| r_squared | 0.1848 |
| information_ratio | 0.6717 |
| residual_vol_annual | 0.06842 |
| n_obs | 4,027 |
| beta_equal_weight | 0.2489 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 8 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
