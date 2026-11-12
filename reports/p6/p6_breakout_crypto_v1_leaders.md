# Hypothesis Report — `p6_breakout_crypto_v1_leaders`

## Verdict: **FAIL**

stopped at gate 3 (single-strategy significance): HAC t = 1.56

| | |
|---|---|
| Strategy | `momentum_breakout_base5_controlleaders_tight2_trail10` (family `momentum_breakout`) |
| Parameters | `{'base': 5, 'tight': 2.0, 'trail': 10, 'control': 'leaders'}` |
| Universe | 371 symbols, 2018-01-01 00:00:00+00:00 → 2025-04-30 00:00:00+00:00 |
| **Trials counted** | **2** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `binance_spot_vip0_bnb_taker` at 9.5 bps/side, fees verified 2026-09-11 |
| Generated | 2026-11-12T16:06:26+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:46:22 |
| 1 | Data integrity | WARN | 58 held symbols with QA warnings; no lag spike (-8.3 standard errors over its neighbours) — **UNJUSTIFIED** |
| 2 | Cost survival | PASS | 91% of gross survives; Sharpe 0.51 at 2x costs; capacity about $1,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 1.56 |
| 4 | Multiple-testing deflation | WARN | DSR = 0.94 — **UNJUSTIFIED** |
| 5 | Selection overfitting | **FAIL** | PBO = 0.70 over 12870 splits of 2 variants; the in-sample winner loses out of sample 14% of the time; SPA p = 0.166 vs exposure-matched buy-and-hold (39% invested) |
| 6 | Permutation | **FAIL** | bar permutation p = 0.249 (76th percentile, re-optimised over 2 of 2 variants); random entry p = 0.010; volatility-preserving null p = 0.055 (95th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | WARN | median path Sharpe 0.41 = 72% of in-sample; 100% of 9 paths positive; WFE -0.11 — **UNJUSTIFIED** |
| 8 | Robustness and regime | **FAIL** | profitable in only 50% of years; alpha t = 1.04 against beta 0.29 to BTCUSDT: the factors explain only 8% of it, so this is neutral around nothing rather than market exposure |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.9375 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.4129 |
| Probability of backtest overfitting (gate 5) | 0.7021 |
| Bar-permutation p (gate 6) | 0.2488 |
| …with volatility preserved (reported, not binding) | 0.05473 |
| HAC t-statistic (gate 3) | 1.557 |
| Probabilistic Sharpe (gate 3) | 0.9452 |
| Net / gross return (gate 2) | 0.905 |
| In-sample net Sharpe (the backtest number) | 0.5742 |
| cagr | 0.1812 |
| ann vol | 0.6931 |
| max drawdown | -0.7916 |
| ann turnover | 43.97 |
| round trips | 592 |
| time in market | 0.5484 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.2518 | 1.043 |
| beta to BTCUSDT | 0.2927 | — |
| information ratio | 0.3791 | — |
| R² | 0.08195 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | c9b64d51f01f7a4e170bec64f4ca4e376241afa267698a313ffbccf7c1cfb9c7 |
| registered_at | 2026-11-12T14:46:22.503958+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_breakout_crypto_v1_leaders.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 0 |
| qa_warnings | 58 |
| qa_failures_traded | 0 |
| qa_failed_symbols | [] |
| qa_failures_on_raw_bars | 1 |
| qa_bars_excluded | 9 |
| lag0_gross_sharpe | 3.706 |
| lag1_gross_sharpe | 0.6344 |
| lag2_gross_sharpe | 0.5559 |
| lag1_price_sharpe | 0.6344 |
| carry_share_of_gross | — |
| peek_ratio | 5.841 |
| spike_ratio | 0.1712 |
| spike_z | -8.317 |
| sharpe_standard_error | 0.3693 |
| placebo_observed | 0.6344 |
| placebo_p_value | 0.3168 |
| placebo_percentile | 69 |
| placebo_null_median | 0.474 |
| placebo_null_95th | 0.8833 |
| placebo_permutations | 100 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 1,000 |
| capacity_usd_pessimistic | 1,000 |
| capacity_usd_optimistic | 1e+04 |
| gross_annual_return | 0.4398 |
| impact_budget_annual | 0.04398 |
| impact_coef | 1 |
| median_participation_at_capacity | 6.188e-07 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0.0139 |
| impact_drag_at_1e+04 | 0.05936 |
| cost_share_commission | 0.7895 |
| cost_share_spread | 0.2105 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.6344 |
| net_sharpe | 0.5742 |
| net_over_gross | 0.905 |
| ann_turnover | 43.97 |
| cost_drag_ann | 0.04178 |
| sharpe_at_2x_costs | 0.5138 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 1.557 |
| hac_pvalue | 0.1195 |
| hac_lags | 8 |
| psr | 0.9452 |
| sharpe_ci_lower | -0.1277 |
| sharpe_ci_upper | 1.261 |
| min_track_record_length | 2,830 |
| observations | 2,677 |
| skew | 2.031 |
| kurtosis | 25.83 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 2 |
| trials_raw | 2 |
| trials_effective | 1 |
| sharpe_variance | 5.656e-06 |
| deflation_benchmark_per_period | 0.001236 |
| dsr | 0.9375 |
| haircut_sharpe_bhy | 0.3386 |
| adjusted_p_bhy | 0.1793 |
| min_backtest_length_years | 4.205 |
| sample_years | 7.334 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.7021 |
| median_logit | -0.6931 |
| splits | 1.287e+04 |
| variants | 2 |
| blocks | 16 |
| degradation_slope | -1.064 |
| prob_oos_loss | 0.1361 |
| median_is_sharpe | 0.032 |
| median_oos_sharpe | 0.02622 |
| is_oos_rank_correlation | -1 |
| benchmark | exposure |
| benchmark_exposure | 0.3889 |
| spa_p_consistent | 0.166 |
| spa_p_lower | 0.166 |
| spa_p_upper | 0.166 |
| spa_models | 2 |
| spa_benchmark | exposure_matched |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | 0.2202 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.6344 |
| bar_permutation_p_value | 0.2488 |
| bar_permutation_percentile | 75.5 |
| bar_permutation_null_median | 0.4522 |
| bar_permutation_null_95th | 0.8932 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.6344 |
| random_entry_p_value | 0.00995 |
| random_entry_percentile | 99.5 |
| random_entry_null_median | 0.5484 |
| random_entry_null_95th | 0.6044 |
| random_entry_permutations | 200 |
| reoptimised_over | 2 |
| grid_size | 2 |
| bar_permutation_vol_preserved_observed | 0.6344 |
| bar_permutation_vol_preserved_p_value | 0.05473 |
| bar_permutation_vol_preserved_percentile | 95 |
| bar_permutation_vol_preserved_null_median | 0.06116 |
| bar_permutation_vol_preserved_null_95th | 0.6161 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | WARN |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.5742 |
| median_path_sharpe | 0.4129 |
| worst_path_sharpe | 0.3431 |
| best_path_sharpe | 0.5742 |
| share_paths_positive | 1 |
| median_over_is | 0.7191 |
| walk_forward_efficiency | -0.1077 |
| walk_forward_efficiency_pooled | 0.735 |
| walk_forward_windows | 5 |
| purge_bars | 0 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 1 |
| constructor_parameters | 4 |
| round_trips | 592 |
| neighbourhood_peak_sharpe | 0.5742 |
| neighbourhood_n_neighbours | 0 |
| neighbourhood_retention | — |
| years | 8 |
| share_profitable_years | 0.5 |
| sharpe_without_best_year | 0.1698 |
| sharpe_without_best_5_trades | 0.2709 |
| sharpe_without_best_5_bars | 0.2684 |
| sharpe_in_low_vol | 0.9658 |
| sharpe_in_mid_vol | 0.02196 |
| sharpe_in_high_vol | 0.6906 |
| alpha_annual | 0.2518 |
| alpha_tstat | 1.043 |
| alpha_pvalue | 0.2968 |
| r_squared | 0.08195 |
| information_ratio | 0.3791 |
| residual_vol_annual | 0.6642 |
| n_obs | 2,676 |
| beta_BTCUSDT | 0.2927 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 2 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
