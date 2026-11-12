# Hypothesis Report — `p6_breakout_crypto_v1_placebo`

## Verdict: **FAIL**

stopped at gate 3 (single-strategy significance): HAC t = 2.05

| | |
|---|---|
| Strategy | `momentum_breakout_base10_controlplacebo_tight2p5_trail20` (family `momentum_breakout`) |
| Parameters | `{'base': 10, 'tight': 2.5, 'trail': 20, 'control': 'placebo'}` |
| Universe | 371 symbols, 2018-01-01 00:00:00+00:00 → 2025-04-30 00:00:00+00:00 |
| **Trials counted** | **8** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `binance_spot_vip0_bnb_taker` at 9.5 bps/side, fees verified 2026-09-11 |
| Generated | 2026-11-12T17:03:51+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:46:22 |
| 1 | Data integrity | WARN | 31 held symbols with QA warnings; no lag spike (-4.9 standard errors over its neighbours) — **UNJUSTIFIED** |
| 2 | Cost survival | PASS | 96% of gross survives; Sharpe 0.81 at 2x costs; capacity about $10,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 2.05 |
| 4 | Multiple-testing deflation | **FAIL** | DSR = 0.75 over 8 trials (effective rank 6): the best of this search is what noise would give |
| 5 | Selection overfitting | **FAIL** | PBO = 0.33 over 12870 splits of 8 variants; the in-sample winner loses out of sample 20% of the time; SPA p = 0.125 vs exposure-matched buy-and-hold (13% invested) |
| 6 | Permutation | **FAIL** | bar permutation p = 0.343 (66th percentile, re-optimised over 8 of 8 variants); random entry p = 0.005; volatility-preserving null p = 0.109 (90th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | **FAIL** | median path Sharpe 0.03 = 3% of in-sample; 56% of 9 paths positive; WFE 0.51 |
| 8 | Robustness and regime | **FAIL** | neighbours keep only 16% of the peak Sharpe (a spike, not a plateau); alpha t = 1.72 against beta 0.12 to BTCUSDT: the factors explain only 5% of it, so this is neutral around nothing rather than market exposure |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.7474 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.0286 |
| Probability of backtest overfitting (gate 5) | 0.335 |
| Bar-permutation p (gate 6) | 0.3433 |
| …with volatility preserved (reported, not binding) | 0.1095 |
| HAC t-statistic (gate 3) | 2.05 |
| Probabilistic Sharpe (gate 3) | 0.9917 |
| Net / gross return (gate 2) | 0.9593 |
| In-sample net Sharpe (the backtest number) | 0.8484 |
| cagr | 0.2622 |
| ann vol | 0.3419 |
| max drawdown | -0.4338 |
| ann turnover | 12.94 |
| round trips | 189 |
| time in market | 0.3347 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.2316 | 1.719 |
| beta to BTCUSDT | 0.1171 | — |
| information ratio | 0.6964 | — |
| R² | 0.05392 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 7eb16887bd71dbbbd7cd8332e47960f1f697758d7f6d0e15fc9603a3504f01d8 |
| registered_at | 2026-11-12T14:46:22.892554+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_breakout_crypto_v1_placebo.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 0 |
| qa_warnings | 31 |
| qa_failures_traded | 0 |
| qa_failed_symbols | [] |
| qa_failures_on_raw_bars | 0 |
| qa_bars_excluded | 9 |
| lag0_gross_sharpe | 2.678 |
| lag1_gross_sharpe | 0.8842 |
| lag2_gross_sharpe | 0.9784 |
| lag1_price_sharpe | 0.8842 |
| carry_share_of_gross | — |
| peek_ratio | 3.029 |
| spike_ratio | 0.3302 |
| spike_z | -4.858 |
| sharpe_standard_error | 0.3693 |
| placebo_observed | 0.8842 |
| placebo_p_value | 0.07921 |
| placebo_percentile | 93 |
| placebo_null_median | 0.543 |
| placebo_null_95th | 0.9529 |
| placebo_permutations | 100 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 1e+04 |
| capacity_usd_pessimistic | 1,000 |
| capacity_usd_optimistic | 1e+05 |
| gross_annual_return | 0.3024 |
| impact_budget_annual | 0.03024 |
| impact_coef | 1 |
| median_participation_at_capacity | 4.747e-06 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0.004004 |
| impact_drag_at_1e+04 | 0.0175 |
| impact_drag_at_3e+04 | 0.03231 |
| cost_share_commission | 0.7895 |
| cost_share_spread | 0.2105 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.8842 |
| net_sharpe | 0.8484 |
| net_over_gross | 0.9593 |
| ann_turnover | 12.94 |
| cost_drag_ann | 0.0123 |
| sharpe_at_2x_costs | 0.8125 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 2.05 |
| hac_pvalue | 0.04041 |
| hac_lags | 8 |
| psr | 0.9917 |
| sharpe_ci_lower | 0.07379 |
| sharpe_ci_upper | 1.496 |
| min_track_record_length | 1,264 |
| observations | 2,677 |
| skew | 2.071 |
| kurtosis | 26.39 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 8 |
| trials_raw | 8 |
| trials_effective | 6 |
| sharpe_variance | 0.0004825 |
| deflation_benchmark_per_period | 0.03205 |
| dsr | 0.7474 |
| haircut_sharpe_bhy | 0.06319 |
| adjusted_p_bhy | 0.4393 |
| min_backtest_length_years | 5.778 |
| sample_years | 7.334 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.335 |
| median_logit | 0.2231 |
| splits | 1.287e+04 |
| variants | 8 |
| blocks | 16 |
| degradation_slope | -1.014 |
| prob_oos_loss | 0.2045 |
| median_is_sharpe | 0.05405 |
| median_oos_sharpe | 0.02356 |
| is_oos_rank_correlation | 0.2857 |
| benchmark | exposure |
| benchmark_exposure | 0.1252 |
| spa_p_consistent | 0.125 |
| spa_p_lower | 0.105 |
| spa_p_upper | 0.125 |
| spa_models | 8 |
| spa_benchmark | exposure_matched |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | 0.2328 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.8842 |
| bar_permutation_p_value | 0.3433 |
| bar_permutation_percentile | 66 |
| bar_permutation_null_median | 0.776 |
| bar_permutation_null_95th | 1.196 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.8842 |
| random_entry_p_value | 0.004975 |
| random_entry_percentile | 100 |
| random_entry_null_median | 0.5411 |
| random_entry_null_95th | 0.625 |
| random_entry_permutations | 200 |
| reoptimised_over | 8 |
| grid_size | 8 |
| bar_permutation_vol_preserved_observed | 0.8842 |
| bar_permutation_vol_preserved_p_value | 0.1095 |
| bar_permutation_vol_preserved_percentile | 89.5 |
| bar_permutation_vol_preserved_null_median | 0.5269 |
| bar_permutation_vol_preserved_null_95th | 1.025 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | FAIL |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.8484 |
| median_path_sharpe | 0.0286 |
| worst_path_sharpe | -0.3789 |
| best_path_sharpe | 0.8101 |
| share_paths_positive | 0.5556 |
| median_over_is | 0.03372 |
| walk_forward_efficiency | 0.5137 |
| walk_forward_efficiency_pooled | 1 |
| walk_forward_windows | 5 |
| purge_bars | 0 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 3 |
| constructor_parameters | 4 |
| round_trips | 189 |
| neighbourhood_peak_sharpe | 0.8484 |
| neighbourhood_n_neighbours | 1 |
| neighbourhood_retention | 0.1607 |
| neighbourhood_worst_retention | 0.1607 |
| neighbourhood_share_above_70pct | 0 |
| years | 8 |
| share_profitable_years | 0.75 |
| sharpe_without_best_year | 0.5819 |
| sharpe_without_best_5_trades | 0.2747 |
| sharpe_without_best_5_bars | 0.5767 |
| sharpe_in_low_vol | 1.301 |
| sharpe_in_mid_vol | 0.05739 |
| sharpe_in_high_vol | 0.9538 |
| alpha_annual | 0.2316 |
| alpha_tstat | 1.719 |
| alpha_pvalue | 0.08555 |
| r_squared | 0.05392 |
| information_ratio | 0.6964 |
| residual_vol_annual | 0.3326 |
| n_obs | 2,676 |
| beta_BTCUSDT | 0.1171 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 8 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
