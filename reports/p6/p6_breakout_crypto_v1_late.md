# Hypothesis Report — `p6_breakout_crypto_v1_late`

## Verdict: **FAIL**

stopped at gate 3 (single-strategy significance): HAC t = 1.32

| | |
|---|---|
| Strategy | `momentum_breakout_base5_controllate_tight2p5_trail10` (family `momentum_breakout`) |
| Parameters | `{'base': 5, 'tight': 2.5, 'trail': 10, 'control': 'late'}` |
| Universe | 371 symbols, 2018-01-01 00:00:00+00:00 → 2025-04-30 00:00:00+00:00 |
| **Trials counted** | **8** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `binance_spot_vip0_bnb_taker` at 9.5 bps/side, fees verified 2026-09-11 |
| Generated | 2026-11-12T18:01:42+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:46:23 |
| 1 | Data integrity | WARN | 39 held symbols with QA warnings; no lag spike (-4.8 standard errors over its neighbours) — **UNJUSTIFIED** |
| 2 | Cost survival | PASS | 91% of gross survives; Sharpe 0.43 at 2x costs; capacity about $10,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 1.32 |
| 4 | Multiple-testing deflation | **FAIL** | DSR = 0.84 over 8 trials (effective rank 2): the best of this search is what noise would give |
| 5 | Selection overfitting | **FAIL** | PBO = 0.81 over 12870 splits of 8 variants; the in-sample winner loses out of sample 24% of the time; SPA p = 0.290 vs exposure-matched buy-and-hold (13% invested) |
| 6 | Permutation | **FAIL** | bar permutation p = 0.582 (42th percentile, re-optimised over 8 of 8 variants); random entry p = 0.751; volatility-preserving null p = 0.308 (70th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | WARN | median path Sharpe 0.28 = 59% of in-sample; 100% of 9 paths positive; WFE 0.24 — **UNJUSTIFIED** |
| 8 | Robustness and regime | **FAIL** | profitable in only 50% of years; the entire result is five trades; alpha t = 0.94 against beta 0.10 to BTCUSDT: the factors explain only 3% of it, so this is neutral around nothing rather than market exposure |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.8358 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.2778 |
| Probability of backtest overfitting (gate 5) | 0.8068 |
| Bar-permutation p (gate 6) | 0.5821 |
| …with volatility preserved (reported, not binding) | 0.3085 |
| HAC t-statistic (gate 3) | 1.317 |
| Probabilistic Sharpe (gate 3) | 0.9019 |
| Net / gross return (gate 2) | 0.915 |
| In-sample net Sharpe (the backtest number) | 0.4686 |
| cagr | 0.1104 |
| ann vol | 0.3579 |
| max drawdown | -0.523 |
| ann turnover | 16.4 |
| round trips | 241 |
| time in market | 0.3127 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.1186 | 0.9434 |
| beta to BTCUSDT | 0.09842 | — |
| information ratio | 0.3372 | — |
| R² | 0.03475 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 8c7b603a79ac7be424388d269af3bad739fd3d5cadd905703097e20e1303e48c |
| registered_at | 2026-11-12T14:46:23.271298+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_breakout_crypto_v1_late.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 0 |
| qa_warnings | 39 |
| qa_failures_traded | 0 |
| qa_failed_symbols | [] |
| qa_failures_on_raw_bars | 1 |
| qa_bars_excluded | 9 |
| lag0_gross_sharpe | 2.283 |
| lag1_gross_sharpe | 0.5118 |
| lag2_gross_sharpe | 0.379 |
| lag1_price_sharpe | 0.5118 |
| carry_share_of_gross | — |
| peek_ratio | 4.46 |
| spike_ratio | 0.2242 |
| spike_z | -4.796 |
| sharpe_standard_error | 0.3693 |
| placebo_observed | 0.5118 |
| placebo_p_value | 0.1485 |
| placebo_percentile | 86 |
| placebo_null_median | 0.2045 |
| placebo_null_95th | 0.6573 |
| placebo_permutations | 100 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 1e+04 |
| capacity_usd_pessimistic | 1,000 |
| capacity_usd_optimistic | 3e+04 |
| gross_annual_return | 0.1833 |
| impact_budget_annual | 0.01833 |
| impact_coef | 1 |
| median_participation_at_capacity | 8.257e-06 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0.00322 |
| impact_drag_at_1e+04 | 0.01601 |
| impact_drag_at_3e+04 | 0.03021 |
| cost_share_commission | 0.7895 |
| cost_share_spread | 0.2105 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.5118 |
| net_sharpe | 0.4686 |
| net_over_gross | 0.915 |
| ann_turnover | 16.4 |
| cost_drag_ann | 0.01558 |
| sharpe_at_2x_costs | 0.4252 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 1.317 |
| hac_pvalue | 0.188 |
| hac_lags | 8 |
| psr | 0.9019 |
| sharpe_ci_lower | -0.2775 |
| sharpe_ci_upper | 1.147 |
| min_track_record_length | 4,335 |
| observations | 2,677 |
| skew | 1.655 |
| kurtosis | 29.23 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 8 |
| trials_raw | 8 |
| trials_effective | 2 |
| sharpe_variance | 1.679e-05 |
| deflation_benchmark_per_period | 0.005979 |
| dsr | 0.8358 |
| haircut_sharpe_bhy | 0 |
| adjusted_p_bhy | 1 |
| min_backtest_length_years | 18.94 |
| sample_years | 7.334 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.8068 |
| median_logit | -0.6931 |
| splits | 1.287e+04 |
| variants | 8 |
| blocks | 16 |
| degradation_slope | -0.9963 |
| prob_oos_loss | 0.2394 |
| median_is_sharpe | 0.02995 |
| median_oos_sharpe | 0.01394 |
| is_oos_rank_correlation | -0.4048 |
| benchmark | exposure |
| benchmark_exposure | 0.1268 |
| spa_p_consistent | 0.29 |
| spa_p_lower | 0.29 |
| spa_p_upper | 0.29 |
| spa_models | 8 |
| spa_benchmark | exposure_matched |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | 0.1097 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.5118 |
| bar_permutation_p_value | 0.5821 |
| bar_permutation_percentile | 42 |
| bar_permutation_null_median | 0.584 |
| bar_permutation_null_95th | 1.128 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.5118 |
| random_entry_p_value | 0.7512 |
| random_entry_percentile | 25 |
| random_entry_null_median | 0.5536 |
| random_entry_null_95th | 0.6395 |
| random_entry_permutations | 200 |
| reoptimised_over | 8 |
| grid_size | 8 |
| bar_permutation_vol_preserved_observed | 0.5118 |
| bar_permutation_vol_preserved_p_value | 0.3085 |
| bar_permutation_vol_preserved_percentile | 69.5 |
| bar_permutation_vol_preserved_null_median | 0.2989 |
| bar_permutation_vol_preserved_null_95th | 0.8711 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | FAIL |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.4686 |
| median_path_sharpe | 0.2778 |
| worst_path_sharpe | 0.1854 |
| best_path_sharpe | 0.3564 |
| share_paths_positive | 1 |
| median_over_is | 0.5928 |
| walk_forward_efficiency | 0.2354 |
| walk_forward_efficiency_pooled | 0.3489 |
| walk_forward_windows | 4 |
| purge_bars | 0 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 3 |
| constructor_parameters | 4 |
| round_trips | 241 |
| neighbourhood_peak_sharpe | 0.4686 |
| neighbourhood_n_neighbours | 1 |
| neighbourhood_retention | 0.7898 |
| neighbourhood_worst_retention | 0.7898 |
| neighbourhood_share_above_70pct | 1 |
| years | 8 |
| share_profitable_years | 0.5 |
| sharpe_without_best_year | 0.3089 |
| sharpe_without_best_5_trades | -0.005372 |
| sharpe_without_best_5_bars | 0.1592 |
| sharpe_in_low_vol | 0.7129 |
| sharpe_in_mid_vol | 0.0926 |
| sharpe_in_high_vol | 0.5369 |
| alpha_annual | 0.1186 |
| alpha_tstat | 0.9434 |
| alpha_pvalue | 0.3455 |
| r_squared | 0.03475 |
| information_ratio | 0.3372 |
| residual_vol_annual | 0.3517 |
| n_obs | 2,676 |
| beta_BTCUSDT | 0.09842 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 8 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
