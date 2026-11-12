# Hypothesis Report — `p6_trend_reset_v1`

## Verdict: **FAIL**

stopped at gate 1 (data integrity): QA failed for AAPL, AMZN, AVGO, BKNG, GOOG, which this strategy holds

| | |
|---|---|
| Strategy | `trend_reset_controlnone_hold63_near_zero0p5_roc21_was_high1p5` (family `trend_reset`) |
| Parameters | `{'roc': 21, 'was_high': 1.5, 'near_zero': 0.5, 'hold': 63, 'control': 'none'}` |
| Universe | 31 symbols, 2019-07-01 00:00:00+00:00 → 2025-08-29 00:00:00+00:00 |
| **Trials counted** | **8** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `alpaca_us_equity_zero_commission_fractional` at 3 bps/side, fees verified 2026-09-15 (commission and cls rule; spread and slippage unmeasured) |
| Generated | 2026-11-12T14:21:37+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:15:34 |
| 1 | Data integrity | **FAIL** | QA failed for AAPL, AMZN, AVGO, BKNG, GOOG, which this strategy holds |
| 2 | Cost survival | PASS | 99% of gross survives; Sharpe 0.98 at 2x costs; capacity about $30,000,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | WARN | t = 2.63, PSR = 0.99 — **UNJUSTIFIED** |
| 4 | Multiple-testing deflation | PASS | DSR = 0.978 over 8 trials (effective rank 2), haircut Sharpe 0.50 |
| 5 | Selection overfitting | **FAIL** | PBO = 0.56 over 12870 splits of 8 variants; selection is arbitrary but stays profitable out of sample (5% losing) — the variants are interchangeable; SPA p = 0.711 vs exposure-matched buy-and-hold (86% invested) — no variant beats holding the universe at its own size |
| 6 | Permutation | **FAIL** | bar permutation p = 0.751 (25th percentile, re-optimised over 8 of 8 variants); random entry p = 0.204; volatility-preserving null p = 0.955 (4th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | PASS | median path Sharpe 0.69 = 69% of in-sample; 100% of 9 paths positive; WFE 0.58 |
| 8 | Robustness and regime | **FAIL** | alpha t = 1.18 against beta 0.67 to equal_weight: this is the market, not the strategy |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.9776 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.6852 |
| Probability of backtest overfitting (gate 5) | 0.5639 |
| Bar-permutation p (gate 6) | 0.7512 |
| …with volatility preserved (reported, not binding) | 0.9552 |
| HAC t-statistic (gate 3) | 2.626 |
| Probabilistic Sharpe (gate 3) | 0.9921 |
| Net / gross return (gate 2) | 0.9857 |
| In-sample net Sharpe (the backtest number) | 0.9934 |
| cagr | 0.2237 |
| ann vol | 0.2301 |
| max drawdown | -0.3978 |
| ann turnover | 11.03 |
| round trips | 139 |
| time in market | 0.9691 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.06805 | 1.178 |
| beta to equal_weight | 0.6659 | — |
| information ratio | 0.4444 | — |
| R² | 0.5574 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 5ac87fa360581a127f495dcb35e7590ee0dd392c8d7a78bc493f4f2e1c4b1fe6 |
| registered_at | 2026-11-12T14:15:34.418201+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_trend_reset_v1.md |
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
| gross_annual_return | 0.2319 |
| impact_budget_annual | 0.02319 |
| impact_coef | 1 |
| median_participation_at_capacity | 2.365e-18 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0 |
| impact_drag_at_1e+04 | 0 |
| impact_drag_at_3e+04 | 5.091e-08 |
| impact_drag_at_1e+05 | 5.536e-05 |
| impact_drag_at_3e+05 | 0.0004384 |
| impact_drag_at_1e+06 | 0.001844 |
| impact_drag_at_3e+06 | 0.004395 |
| impact_drag_at_1e+07 | 0.009479 |
| impact_drag_at_3e+07 | 0.01772 |
| impact_drag_at_1e+08 | 0.03381 |
| cost_share_commission | 0 |
| cost_share_spread | 1 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 1.008 |
| net_sharpe | 0.9934 |
| net_over_gross | 0.9857 |
| ann_turnover | 11.03 |
| cost_drag_ann | 0.003308 |
| sharpe_at_2x_costs | 0.979 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 2.626 |
| hac_pvalue | 0.008651 |
| hac_lags | 7 |
| psr | 0.9921 |
| sharpe_ci_lower | 0.2255 |
| sharpe_ci_upper | 1.794 |
| min_track_record_length | 719.8 |
| observations | 1,551 |
| skew | -0.5825 |
| kurtosis | 6.968 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 8 |
| trials_raw | 8 |
| trials_effective | 2 |
| sharpe_variance | 5.307e-05 |
| deflation_benchmark_per_period | 0.01063 |
| dsr | 0.9776 |
| haircut_sharpe_bhy | 0.498 |
| adjusted_p_bhy | 0.09405 |
| min_backtest_length_years | 4.215 |
| sample_years | 6.167 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.5639 |
| median_logit | -0.2231 |
| splits | 1.287e+04 |
| variants | 8 |
| blocks | 16 |
| degradation_slope | -0.9616 |
| prob_oos_loss | 0.04569 |
| median_is_sharpe | 0.06785 |
| median_oos_sharpe | 0.04569 |
| is_oos_rank_correlation | -0.4048 |
| benchmark | exposure |
| benchmark_exposure | 0.8566 |
| spa_p_consistent | 0.711 |
| spa_p_lower | 0.585 |
| spa_p_upper | 0.711 |
| spa_models | 8 |
| spa_benchmark | exposure_matched |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | 0.02281 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 1.008 |
| bar_permutation_p_value | 0.7512 |
| bar_permutation_percentile | 25 |
| bar_permutation_null_median | 1.118 |
| bar_permutation_null_95th | 1.434 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 1.008 |
| random_entry_p_value | 0.204 |
| random_entry_percentile | 80 |
| random_entry_null_median | 0.9 |
| random_entry_null_95th | 1.102 |
| random_entry_permutations | 200 |
| reoptimised_over | 8 |
| grid_size | 8 |
| bar_permutation_vol_preserved_observed | 1.008 |
| bar_permutation_vol_preserved_p_value | 0.9552 |
| bar_permutation_vol_preserved_percentile | 4.5 |
| bar_permutation_vol_preserved_null_median | 1.392 |
| bar_permutation_vol_preserved_null_95th | 1.804 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | FAIL |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.9934 |
| median_path_sharpe | 0.6852 |
| worst_path_sharpe | 0.5083 |
| best_path_sharpe | 0.7571 |
| share_paths_positive | 1 |
| median_over_is | 0.6898 |
| walk_forward_efficiency | 0.5833 |
| walk_forward_efficiency_pooled | 0.5804 |
| walk_forward_windows | 5 |
| purge_bars | 63 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 3 |
| constructor_parameters | 5 |
| round_trips | 139 |
| neighbourhood_peak_sharpe | 0.9934 |
| neighbourhood_n_neighbours | 0 |
| neighbourhood_retention | — |
| years | 7 |
| share_profitable_years | 0.8571 |
| sharpe_without_best_year | 0.7451 |
| sharpe_without_best_5_trades | 0.716 |
| sharpe_without_best_5_bars | 0.8259 |
| sharpe_in_low_vol | 2.343 |
| sharpe_in_mid_vol | 0.5912 |
| sharpe_in_high_vol | 0.4012 |
| alpha_annual | 0.06805 |
| alpha_tstat | 1.178 |
| alpha_pvalue | 0.2388 |
| r_squared | 0.5574 |
| information_ratio | 0.4444 |
| residual_vol_annual | 0.1531 |
| n_obs | 1,550 |
| beta_equal_weight | 0.6659 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 8 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
