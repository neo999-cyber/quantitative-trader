# Hypothesis Report — `p6_trend_reset_v1_trend`

## Verdict: **FAIL**

stopped at gate 1 (data integrity): QA failed for AAPL, AMZN, AVGO, BKNG, GOOG, which this strategy holds

| | |
|---|---|
| Strategy | `trend_reset_controltrend_hold63_near_zero0p25_roc63_was_high1` (family `trend_reset`) |
| Parameters | `{'roc': 63, 'was_high': 1.0, 'near_zero': 0.25, 'hold': 63, 'control': 'trend'}` |
| Universe | 31 symbols, 2019-07-01 00:00:00+00:00 → 2025-08-29 00:00:00+00:00 |
| **Trials counted** | **1** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `alpaca_us_equity_zero_commission_fractional` at 3 bps/side, fees verified 2026-09-15 (commission and cls rule; spread and slippage unmeasured) |
| Generated | 2026-11-12T14:22:45+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:15:34 |
| 1 | Data integrity | **FAIL** | QA failed for AAPL, AMZN, AVGO, BKNG, GOOG, which this strategy holds |
| 2 | Cost survival | PASS | 99% of gross survives; Sharpe 0.86 at 2x costs; capacity about $30,000,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 2.29 |
| 4 | Multiple-testing deflation | PASS | DSR = 0.983 over 1 trials (effective rank 1), haircut Sharpe 0.87 |
| 5 | Selection overfitting | skip | only one variant was run, so nothing was selected; PBO does not apply |
| 6 | Permutation | **FAIL** | bar permutation p = 0.861 (14th percentile, single variant, no re-optimisation); random entry p = 0.537; volatility-preserving null p = 0.955 (4th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | PASS | median path Sharpe 0.87 = 100% of in-sample; 100% of 9 paths positive; WFE 0.58 |
| 8 | Robustness and regime | **FAIL** | alpha t = 0.54 against beta 0.87 to equal_weight: this is the market, not the strategy |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.9833 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.8708 |
| Probability of backtest overfitting (gate 5) | — |
| Bar-permutation p (gate 6) | 0.8607 |
| …with volatility preserved (reported, not binding) | 0.9552 |
| HAC t-statistic (gate 3) | 2.285 |
| Probabilistic Sharpe (gate 3) | 0.9833 |
| Net / gross return (gate 2) | 0.9869 |
| In-sample net Sharpe (the backtest number) | 0.8708 |
| cagr | 0.2273 |
| ann vol | 0.2808 |
| max drawdown | -0.3839 |
| ann turnover | 10.82 |
| round trips | 131 |
| time in market | 0.9865 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.03587 | 0.5399 |
| beta to equal_weight | 0.8656 | — |
| information ratio | 0.2106 | — |
| R² | 0.6323 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | da3b8dea4c57cba208cd559a514cb27bf5bfbe767b64b2cd69dc2d3e019b0d8b |
| registered_at | 2026-11-12T14:15:34.799098+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_trend_reset_v1_trend.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 11 |
| qa_warnings | 0 |
| qa_failures_traded | 11 |
| qa_failed_symbols | ['AAPL', 'AMZN', 'AVGO', 'BKNG', 'GOOG', 'GOOGL', 'ISRG', 'LRCX', 'NFLX', 'NVDA', 'TSLA'] |
| qa_failures_on_raw_bars | 11 |
| qa_bars_excluded | 0 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 3e+07 |
| capacity_usd_pessimistic | 1e+07 |
| capacity_usd_optimistic | 1e+08 |
| gross_annual_return | 0.2478 |
| impact_budget_annual | 0.02478 |
| impact_coef | 1 |
| median_participation_at_capacity | 1.88e-18 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0 |
| impact_drag_at_1e+04 | 0 |
| impact_drag_at_3e+04 | 1.179e-07 |
| impact_drag_at_1e+05 | 7.746e-05 |
| impact_drag_at_3e+05 | 0.0005163 |
| impact_drag_at_1e+06 | 0.001934 |
| impact_drag_at_3e+06 | 0.004459 |
| impact_drag_at_1e+07 | 0.009472 |
| impact_drag_at_3e+07 | 0.0176 |
| impact_drag_at_1e+08 | 0.03348 |
| cost_share_commission | 0 |
| cost_share_spread | 1 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.8823 |
| net_sharpe | 0.8708 |
| net_over_gross | 0.9869 |
| ann_turnover | 10.82 |
| cost_drag_ann | 0.003245 |
| sharpe_at_2x_costs | 0.8593 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 2.285 |
| hac_pvalue | 0.0223 |
| hac_lags | 7 |
| psr | 0.9833 |
| sharpe_ci_lower | 0.08471 |
| sharpe_ci_upper | 1.717 |
| min_track_record_length | 926.8 |
| observations | 1,551 |
| skew | -0.4725 |
| kurtosis | 8.706 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 1 |
| trials_raw | 1 |
| trials_effective | 1 |
| sharpe_variance | 0.0006447 |
| deflation_benchmark_per_period | 0 |
| dsr | 0.9833 |
| haircut_sharpe_bhy | 0.8708 |
| adjusted_p_bhy | 0.01115 |
| min_backtest_length_years | — |
| sample_years | 6.167 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.8823 |
| bar_permutation_p_value | 0.8607 |
| bar_permutation_percentile | 14 |
| bar_permutation_null_median | 1.093 |
| bar_permutation_null_95th | 1.414 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.8823 |
| random_entry_p_value | 0.5373 |
| random_entry_percentile | 46.5 |
| random_entry_null_median | 0.9 |
| random_entry_null_95th | 1.102 |
| random_entry_permutations | 200 |
| reoptimised_over | 1 |
| grid_size | 1 |
| bar_permutation_vol_preserved_observed | 0.8823 |
| bar_permutation_vol_preserved_p_value | 0.9552 |
| bar_permutation_vol_preserved_percentile | 4.5 |
| bar_permutation_vol_preserved_null_median | 1.339 |
| bar_permutation_vol_preserved_null_95th | 1.733 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | FAIL |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.8708 |
| median_path_sharpe | 0.8708 |
| worst_path_sharpe | 0.8708 |
| best_path_sharpe | 0.8708 |
| share_paths_positive | 1 |
| median_over_is | 1 |
| walk_forward_efficiency | 0.584 |
| walk_forward_efficiency_pooled | 0.5671 |
| walk_forward_windows | 5 |
| purge_bars | 63 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 5 |
| constructor_parameters | 5 |
| round_trips | 131 |
| years | 7 |
| share_profitable_years | 0.7143 |
| sharpe_without_best_year | 0.5637 |
| sharpe_without_best_5_trades | 0.3456 |
| sharpe_without_best_5_bars | 0.6644 |
| sharpe_in_low_vol | 1.565 |
| sharpe_in_mid_vol | 0.6232 |
| sharpe_in_high_vol | 0.7187 |
| alpha_annual | 0.03587 |
| alpha_tstat | 0.5399 |
| alpha_pvalue | 0.5893 |
| r_squared | 0.6323 |
| information_ratio | 0.2106 |
| residual_vol_annual | 0.1704 |
| n_obs | 1,550 |
| beta_equal_weight | 0.8656 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 1 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
