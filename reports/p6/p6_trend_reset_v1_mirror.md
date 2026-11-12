# Hypothesis Report — `p6_trend_reset_v1_mirror`

## Verdict: **FAIL**

stopped at gate 1 (data integrity): QA failed for AAPL, AMZN, AVGO, BKNG, GOOG, which this strategy holds

| | |
|---|---|
| Strategy | `trend_reset_controlmirror_hold63_near_zero0p25_roc21_was_high1` (family `trend_reset`) |
| Parameters | `{'roc': 21, 'was_high': 1.0, 'near_zero': 0.25, 'hold': 63, 'control': 'mirror'}` |
| Universe | 31 symbols, 2019-07-01 00:00:00+00:00 → 2025-08-29 00:00:00+00:00 |
| **Trials counted** | **4** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `alpaca_us_equity_zero_commission_fractional` at 3 bps/side, fees verified 2026-09-15 (commission and cls rule; spread and slippage unmeasured) |
| Generated | 2026-11-12T14:25:56+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:15:35 |
| 1 | Data integrity | **FAIL** | QA failed for AAPL, AMZN, AVGO, BKNG, GOOG, which this strategy holds |
| 2 | Cost survival | PASS | 98% of gross survives; Sharpe 0.88 at 2x costs; capacity about $30,000,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 2.37 |
| 4 | Multiple-testing deflation | WARN | DSR = 0.94 — **UNJUSTIFIED** |
| 5 | Selection overfitting | **FAIL** | PBO = 0.21 over 12870 splits of 4 variants; selection is arbitrary but stays profitable out of sample (2% losing) — the variants are interchangeable; SPA p = 0.740 vs exposure-matched buy-and-hold (86% invested) — no variant beats holding the universe at its own size |
| 6 | Permutation | **FAIL** | bar permutation p = 0.891 (11th percentile, re-optimised over 4 of 4 variants); random entry p = 0.443; volatility-preserving null p = 0.970 (3th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | PASS | median path Sharpe 0.81 = 91% of in-sample; 100% of 9 paths positive; WFE 0.62 |
| 8 | Robustness and regime | **FAIL** | alpha t = 0.95 against beta 0.60 to equal_weight: this is the market, not the strategy |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.9371 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.8138 |
| Probability of backtest overfitting (gate 5) | 0.2095 |
| Bar-permutation p (gate 6) | 0.8905 |
| …with volatility preserved (reported, not binding) | 0.9701 |
| HAC t-statistic (gate 3) | 2.369 |
| Probabilistic Sharpe (gate 3) | 0.9859 |
| Net / gross return (gate 2) | 0.9847 |
| In-sample net Sharpe (the backtest number) | 0.8974 |
| cagr | 0.1937 |
| ann vol | 0.226 |
| max drawdown | -0.3459 |
| ann turnover | 10.53 |
| round trips | 130 |
| time in market | 0.9729 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.05741 | 0.9486 |
| beta to equal_weight | 0.6031 | — |
| information ratio | 0.3502 | — |
| R² | 0.474 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | ad606c656456edb56d674245883912940ee4de077de748902f3f6461ac23b032 |
| registered_at | 2026-11-12T14:15:35.196343+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_trend_reset_v1_mirror.md |
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
| gross_annual_return | 0.2059 |
| impact_budget_annual | 0.02059 |
| impact_coef | 1 |
| median_participation_at_capacity | 2.122e-18 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0 |
| impact_drag_at_1e+04 | 0 |
| impact_drag_at_3e+04 | 2.206e-07 |
| impact_drag_at_1e+05 | 4.712e-05 |
| impact_drag_at_3e+05 | 0.0004081 |
| impact_drag_at_1e+06 | 0.001699 |
| impact_drag_at_3e+06 | 0.004052 |
| impact_drag_at_1e+07 | 0.00873 |
| impact_drag_at_3e+07 | 0.01631 |
| impact_drag_at_1e+08 | 0.03113 |
| cost_share_commission | 0 |
| cost_share_spread | 1 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.9113 |
| net_sharpe | 0.8974 |
| net_over_gross | 0.9847 |
| ann_turnover | 10.53 |
| cost_drag_ann | 0.003158 |
| sharpe_at_2x_costs | 0.8835 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 2.369 |
| hac_pvalue | 0.01783 |
| hac_lags | 7 |
| psr | 0.9859 |
| sharpe_ci_lower | 0.1675 |
| sharpe_ci_upper | 1.711 |
| min_track_record_length | 872.1 |
| observations | 1,551 |
| skew | -0.4599 |
| kurtosis | 7.079 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 4 |
| trials_raw | 4 |
| trials_effective | 2 |
| sharpe_variance | 0.0002643 |
| deflation_benchmark_per_period | 0.0171 |
| dsr | 0.9371 |
| haircut_sharpe_bhy | 0.5472 |
| adjusted_p_bhy | 0.07429 |
| min_backtest_length_years | 3.443 |
| sample_years | 6.167 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.2095 |
| median_logit | 0.4055 |
| splits | 1.287e+04 |
| variants | 4 |
| blocks | 16 |
| degradation_slope | -0.9472 |
| prob_oos_loss | 0.01958 |
| median_is_sharpe | 0.05997 |
| median_oos_sharpe | 0.04818 |
| is_oos_rank_correlation | 0.4 |
| benchmark | exposure |
| benchmark_exposure | 0.8562 |
| spa_p_consistent | 0.74 |
| spa_p_lower | 0.54 |
| spa_p_upper | 0.74 |
| spa_models | 4 |
| spa_benchmark | exposure_matched |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | -0.002884 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.9113 |
| bar_permutation_p_value | 0.8905 |
| bar_permutation_percentile | 11 |
| bar_permutation_null_median | 1.164 |
| bar_permutation_null_95th | 1.496 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.9113 |
| random_entry_p_value | 0.4428 |
| random_entry_percentile | 56 |
| random_entry_null_median | 0.9 |
| random_entry_null_95th | 1.102 |
| random_entry_permutations | 200 |
| reoptimised_over | 4 |
| grid_size | 4 |
| bar_permutation_vol_preserved_observed | 0.9113 |
| bar_permutation_vol_preserved_p_value | 0.9701 |
| bar_permutation_vol_preserved_percentile | 3 |
| bar_permutation_vol_preserved_null_median | 1.363 |
| bar_permutation_vol_preserved_null_95th | 1.751 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | FAIL |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.8974 |
| median_path_sharpe | 0.8138 |
| worst_path_sharpe | 0.6661 |
| best_path_sharpe | 0.8357 |
| share_paths_positive | 1 |
| median_over_is | 0.9068 |
| walk_forward_efficiency | 0.6177 |
| walk_forward_efficiency_pooled | 0.8441 |
| walk_forward_windows | 5 |
| purge_bars | 63 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 2 |
| constructor_parameters | 5 |
| round_trips | 130 |
| neighbourhood_peak_sharpe | 0.8974 |
| neighbourhood_n_neighbours | 0 |
| neighbourhood_retention | — |
| years | 7 |
| share_profitable_years | 0.8571 |
| sharpe_without_best_year | 0.762 |
| sharpe_without_best_5_trades | 0.4829 |
| sharpe_without_best_5_bars | 0.7144 |
| sharpe_in_low_vol | 1.612 |
| sharpe_in_mid_vol | 0.7283 |
| sharpe_in_high_vol | 0.5082 |
| alpha_annual | 0.05741 |
| alpha_tstat | 0.9486 |
| alpha_pvalue | 0.3428 |
| r_squared | 0.474 |
| information_ratio | 0.3502 |
| residual_vol_annual | 0.1639 |
| n_obs | 1,550 |
| beta_equal_weight | 0.6031 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 4 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
