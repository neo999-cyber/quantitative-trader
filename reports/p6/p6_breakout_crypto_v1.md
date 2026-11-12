# Hypothesis Report — `p6_breakout_crypto_v1`

## Verdict: **FAIL**

stopped at gate 3 (single-strategy significance): HAC t = 2.05

| | |
|---|---|
| Strategy | `momentum_breakout_base5_controlnone_tight2p5_trail10` (family `momentum_breakout`) |
| Parameters | `{'base': 5, 'tight': 2.5, 'trail': 10, 'control': 'none'}` |
| Universe | 371 symbols, 2018-01-01 00:00:00+00:00 → 2025-04-30 00:00:00+00:00 |
| **Trials counted** | **8** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `binance_spot_vip0_bnb_taker` at 9.5 bps/side, fees verified 2026-09-11 |
| Generated | 2026-11-12T15:50:20+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:46:22 |
| 1 | Data integrity | WARN | 38 held symbols with QA warnings; no lag spike (-8.8 standard errors over its neighbours) — **UNJUSTIFIED** |
| 2 | Cost survival | PASS | 95% of gross survives; Sharpe 0.73 at 2x costs; capacity about $10,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 2.05 |
| 4 | Multiple-testing deflation | PASS | DSR = 0.957 over 8 trials (effective rank 2), haircut Sharpe 0.06 |
| 5 | Selection overfitting | WARN | PBO = 0.47 over 12870 splits of 8 variants; selection is arbitrary but stays profitable out of sample (8% losing) — the variants are interchangeable; SPA p = 0.097 vs exposure-matched buy-and-hold (13% invested) — **UNJUSTIFIED** |
| 6 | Permutation | **FAIL** | bar permutation p = 0.249 (76th percentile, re-optimised over 8 of 8 variants); random entry p = 0.005; volatility-preserving null p = 0.070 (94th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | WARN | median path Sharpe 0.53 = 68% of in-sample; 100% of 9 paths positive; WFE 0.33 — **UNJUSTIFIED** |
| 8 | Robustness and regime | **FAIL** | profitable in only 50% of years; alpha t = 1.73 against beta 0.10 to BTCUSDT: the factors explain only 3% of it, so this is neutral around nothing rather than market exposure |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.9572 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.528 |
| Probability of backtest overfitting (gate 5) | 0.4706 |
| Bar-permutation p (gate 6) | 0.2488 |
| …with volatility preserved (reported, not binding) | 0.06965 |
| HAC t-statistic (gate 3) | 2.052 |
| Probabilistic Sharpe (gate 3) | 0.9861 |
| Net / gross return (gate 2) | 0.9486 |
| In-sample net Sharpe (the backtest number) | 0.7742 |
| cagr | 0.2424 |
| ann vol | 0.3631 |
| max drawdown | -0.4662 |
| ann turnover | 16.04 |
| round trips | 235 |
| time in market | 0.3261 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.2328 | 1.727 |
| beta to BTCUSDT | 0.09689 | — |
| information ratio | 0.6518 | — |
| R² | 0.03272 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 09bcdf74d8a9dff1c3f26e6a9d67ff3f8a731908b2e29e8dab1b2b1f5afab04c |
| registered_at | 2026-11-12T14:46:22.089832+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_breakout_crypto_v1.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 0 |
| qa_warnings | 38 |
| qa_failures_traded | 0 |
| qa_failed_symbols | [] |
| qa_failures_on_raw_bars | 1 |
| qa_bars_excluded | 9 |
| lag0_gross_sharpe | 4.053 |
| lag1_gross_sharpe | 0.8158 |
| lag2_gross_sharpe | 0.679 |
| lag1_price_sharpe | 0.8158 |
| carry_share_of_gross | — |
| peek_ratio | 4.969 |
| spike_ratio | 0.2013 |
| spike_z | -8.768 |
| sharpe_standard_error | 0.3693 |
| placebo_observed | 0.8158 |
| placebo_p_value | 0.1089 |
| placebo_percentile | 90 |
| placebo_null_median | 0.4139 |
| placebo_null_95th | 0.8717 |
| placebo_permutations | 100 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 1e+04 |
| capacity_usd_pessimistic | 1,000 |
| capacity_usd_optimistic | 1e+05 |
| gross_annual_return | 0.2964 |
| impact_budget_annual | 0.02964 |
| impact_coef | 1 |
| median_participation_at_capacity | 7.465e-06 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0.003206 |
| impact_drag_at_1e+04 | 0.01586 |
| impact_drag_at_3e+04 | 0.0299 |
| cost_share_commission | 0.7895 |
| cost_share_spread | 0.2105 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.8158 |
| net_sharpe | 0.7742 |
| net_over_gross | 0.9486 |
| ann_turnover | 16.04 |
| cost_drag_ann | 0.01524 |
| sharpe_at_2x_costs | 0.7326 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 2.052 |
| hac_pvalue | 0.04019 |
| hac_lags | 8 |
| psr | 0.9861 |
| sharpe_ci_lower | 0.06504 |
| sharpe_ci_upper | 1.466 |
| min_track_record_length | 1,498 |
| observations | 2,677 |
| skew | 2.568 |
| kurtosis | 32.26 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 8 |
| trials_raw | 8 |
| trials_effective | 2 |
| sharpe_variance | 3.671e-05 |
| deflation_benchmark_per_period | 0.00884 |
| dsr | 0.9572 |
| haircut_sharpe_bhy | 0.05995 |
| adjusted_p_bhy | 0.4369 |
| min_backtest_length_years | 6.938 |
| sample_years | 7.334 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.4706 |
| median_logit | 0.2231 |
| splits | 1.287e+04 |
| variants | 8 |
| blocks | 16 |
| degradation_slope | -0.7702 |
| prob_oos_loss | 0.07731 |
| median_is_sharpe | 0.04299 |
| median_oos_sharpe | 0.0253 |
| is_oos_rank_correlation | 0.3333 |
| benchmark | exposure |
| benchmark_exposure | 0.1348 |
| spa_p_consistent | 0.097 |
| spa_p_lower | 0.097 |
| spa_p_upper | 0.097 |
| spa_models | 8 |
| spa_benchmark | exposure_matched |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | 0.2195 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.8158 |
| bar_permutation_p_value | 0.2488 |
| bar_permutation_percentile | 75.5 |
| bar_permutation_null_median | 0.5773 |
| bar_permutation_null_95th | 1.16 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.8158 |
| random_entry_p_value | 0.004975 |
| random_entry_percentile | 100 |
| random_entry_null_median | 0.5477 |
| random_entry_null_95th | 0.6307 |
| random_entry_permutations | 200 |
| reoptimised_over | 8 |
| grid_size | 8 |
| bar_permutation_vol_preserved_observed | 0.8158 |
| bar_permutation_vol_preserved_p_value | 0.06965 |
| bar_permutation_vol_preserved_percentile | 93.5 |
| bar_permutation_vol_preserved_null_median | 0.2742 |
| bar_permutation_vol_preserved_null_95th | 0.8359 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | WARN |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.7742 |
| median_path_sharpe | 0.528 |
| worst_path_sharpe | 0.3676 |
| best_path_sharpe | 0.7554 |
| share_paths_positive | 1 |
| median_over_is | 0.682 |
| walk_forward_efficiency | 0.3285 |
| walk_forward_efficiency_pooled | 0.9931 |
| walk_forward_windows | 4 |
| purge_bars | 0 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 3 |
| constructor_parameters | 4 |
| round_trips | 235 |
| neighbourhood_peak_sharpe | 0.7742 |
| neighbourhood_n_neighbours | 1 |
| neighbourhood_retention | 0.7809 |
| neighbourhood_worst_retention | 0.7809 |
| neighbourhood_share_above_70pct | 1 |
| years | 8 |
| share_profitable_years | 0.5 |
| sharpe_without_best_year | 0.5097 |
| sharpe_without_best_5_trades | 0.3469 |
| sharpe_without_best_5_bars | 0.4767 |
| sharpe_in_low_vol | 0.9663 |
| sharpe_in_mid_vol | 0.5488 |
| sharpe_in_high_vol | 0.782 |
| alpha_annual | 0.2328 |
| alpha_tstat | 1.727 |
| alpha_pvalue | 0.08412 |
| r_squared | 0.03272 |
| information_ratio | 0.6518 |
| residual_vol_annual | 0.3572 |
| n_obs | 2,676 |
| beta_BTCUSDT | 0.09689 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 8 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
