# Hypothesis Report — `p6_breakout_crypto_v1_nofilter`

## Verdict: **FAIL**

stopped at gate 3 (single-strategy significance): HAC t = 2.25

| | |
|---|---|
| Strategy | `momentum_breakout_base5_controlnofilter_tight2p5_trail10` (family `momentum_breakout`) |
| Parameters | `{'base': 5, 'tight': 2.5, 'trail': 10, 'control': 'nofilter'}` |
| Universe | 371 symbols, 2018-01-01 00:00:00+00:00 → 2025-04-30 00:00:00+00:00 |
| **Trials counted** | **8** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `binance_spot_vip0_bnb_taker` at 9.5 bps/side, fees verified 2026-09-11 |
| Generated | 2026-11-12T19:06:40+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:46:23 |
| 1 | Data integrity | WARN | 44 held symbols with QA warnings; no lag spike (-10.2 standard errors over its neighbours) — **UNJUSTIFIED** |
| 2 | Cost survival | PASS | 95% of gross survives; Sharpe 0.89 at 2x costs; capacity about $30,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 2.25 |
| 4 | Multiple-testing deflation | PASS | DSR = 0.982 over 8 trials (effective rank 2), haircut Sharpe 0.26 |
| 5 | Selection overfitting | **FAIL** | PBO = 0.69 over 12870 splits of 8 variants; the in-sample winner loses out of sample 12% of the time; SPA p = 0.083 vs exposure-matched buy-and-hold (21% invested) |
| 6 | Permutation | **FAIL** | bar permutation p = 0.169 (84th percentile, re-optimised over 8 of 8 variants); random entry p = 0.005; volatility-preserving null p = 0.015 (99th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | WARN | median path Sharpe 0.69 = 74% of in-sample; 100% of 9 paths positive; WFE -0.15 — **UNJUSTIFIED** |
| 8 | Robustness and regime | **FAIL** | profitable in only 50% of years; alpha t = 1.95 against beta 0.16 to BTCUSDT: the factors explain only 4% of it, so this is neutral around nothing rather than market exposure |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.9822 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.6918 |
| Probability of backtest overfitting (gate 5) | 0.6937 |
| Bar-permutation p (gate 6) | 0.1692 |
| …with volatility preserved (reported, not binding) | 0.01493 |
| HAC t-statistic (gate 3) | 2.252 |
| Probabilistic Sharpe (gate 3) | 0.9964 |
| Net / gross return (gate 2) | 0.9533 |
| In-sample net Sharpe (the backtest number) | 0.9407 |
| cagr | 0.4272 |
| ann vol | 0.5136 |
| max drawdown | -0.6207 |
| ann turnover | 24.91 |
| round trips | 366 |
| time in market | 0.4677 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.4052 | 1.949 |
| beta to BTCUSDT | 0.1563 | — |
| information ratio | 0.8061 | — |
| R² | 0.04256 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | cd023465033a4692f9877debab63f374864a04b6b6a61a74712cf13c7c922f65 |
| registered_at | 2026-11-12T14:46:23.651736+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_breakout_crypto_v1_nofilter.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 0 |
| qa_warnings | 44 |
| qa_failures_traded | 0 |
| qa_failed_symbols | [] |
| qa_failures_on_raw_bars | 1 |
| qa_bars_excluded | 9 |
| lag0_gross_sharpe | 4.748 |
| lag1_gross_sharpe | 0.9863 |
| lag2_gross_sharpe | 0.8755 |
| lag1_price_sharpe | 0.9863 |
| carry_share_of_gross | — |
| peek_ratio | 4.814 |
| spike_ratio | 0.2077 |
| spike_z | -10.19 |
| sharpe_standard_error | 0.3693 |
| placebo_observed | 0.9863 |
| placebo_p_value | 0.0198 |
| placebo_percentile | 99 |
| placebo_null_median | 0.3146 |
| placebo_null_95th | 0.7938 |
| placebo_permutations | 100 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 3e+04 |
| capacity_usd_pessimistic | 1,000 |
| capacity_usd_optimistic | 1e+05 |
| gross_annual_return | 0.5068 |
| impact_budget_annual | 0.05068 |
| impact_coef | 1 |
| median_participation_at_capacity | 2.276e-05 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0.005397 |
| impact_drag_at_1e+04 | 0.02594 |
| impact_drag_at_3e+04 | 0.04875 |
| impact_drag_at_1e+05 | 0.09353 |
| cost_share_commission | 0.7895 |
| cost_share_spread | 0.2105 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.9863 |
| net_sharpe | 0.9407 |
| net_over_gross | 0.9533 |
| ann_turnover | 24.91 |
| cost_drag_ann | 0.02367 |
| sharpe_at_2x_costs | 0.8949 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 2.252 |
| hac_pvalue | 0.02434 |
| hac_lags | 8 |
| psr | 0.9964 |
| sharpe_ci_lower | 0.1049 |
| sharpe_ci_upper | 1.669 |
| min_track_record_length | 1,005 |
| observations | 2,677 |
| skew | 2.399 |
| kurtosis | 30.6 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 8 |
| trials_raw | 8 |
| trials_effective | 2 |
| sharpe_variance | 5.361e-05 |
| deflation_benchmark_per_period | 0.01068 |
| dsr | 0.9822 |
| haircut_sharpe_bhy | 0.2628 |
| adjusted_p_bhy | 0.2647 |
| min_backtest_length_years | 4.7 |
| sample_years | 7.334 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.6937 |
| median_logit | -0.6931 |
| splits | 1.287e+04 |
| variants | 8 |
| blocks | 16 |
| degradation_slope | -1.006 |
| prob_oos_loss | 0.1216 |
| median_is_sharpe | 0.05638 |
| median_oos_sharpe | 0.03885 |
| is_oos_rank_correlation | 0.2381 |
| benchmark | exposure |
| benchmark_exposure | 0.207 |
| spa_p_consistent | 0.083 |
| spa_p_lower | 0.083 |
| spa_p_upper | 0.083 |
| spa_models | 8 |
| spa_benchmark | exposure_matched |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | 0.3885 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.9863 |
| bar_permutation_p_value | 0.1692 |
| bar_permutation_percentile | 83.5 |
| bar_permutation_null_median | 0.6449 |
| bar_permutation_null_95th | 1.182 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.9863 |
| random_entry_p_value | 0.004975 |
| random_entry_percentile | 100 |
| random_entry_null_median | 0.5531 |
| random_entry_null_95th | 0.6109 |
| random_entry_permutations | 200 |
| reoptimised_over | 8 |
| grid_size | 8 |
| bar_permutation_vol_preserved_observed | 0.9863 |
| bar_permutation_vol_preserved_p_value | 0.01493 |
| bar_permutation_vol_preserved_percentile | 99 |
| bar_permutation_vol_preserved_null_median | 0.3189 |
| bar_permutation_vol_preserved_null_95th | 0.8643 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | PASS |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.9407 |
| median_path_sharpe | 0.6918 |
| worst_path_sharpe | 0.6526 |
| best_path_sharpe | 0.8533 |
| share_paths_positive | 1 |
| median_over_is | 0.7355 |
| walk_forward_efficiency | -0.1483 |
| walk_forward_efficiency_pooled | 0.9906 |
| walk_forward_windows | 5 |
| purge_bars | 0 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 3 |
| constructor_parameters | 4 |
| round_trips | 366 |
| neighbourhood_peak_sharpe | 0.9407 |
| neighbourhood_n_neighbours | 1 |
| neighbourhood_retention | 0.9775 |
| neighbourhood_worst_retention | 0.9775 |
| neighbourhood_share_above_70pct | 1 |
| years | 8 |
| share_profitable_years | 0.5 |
| sharpe_without_best_year | 0.4117 |
| sharpe_without_best_5_trades | 0.4504 |
| sharpe_without_best_5_bars | 0.6866 |
| sharpe_in_low_vol | 1.028 |
| sharpe_in_mid_vol | 0.1394 |
| sharpe_in_high_vol | 1.423 |
| alpha_annual | 0.4052 |
| alpha_tstat | 1.949 |
| alpha_pvalue | 0.05131 |
| r_squared | 0.04256 |
| information_ratio | 0.8061 |
| residual_vol_annual | 0.5027 |
| n_obs | 2,676 |
| beta_BTCUSDT | 0.1563 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 8 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
