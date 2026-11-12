# Hypothesis Report — `p6_trend_reset_v1_placebo`

## Verdict: **FAIL**

stopped at gate 1 (data integrity): QA failed for AAPL, AMZN, AVGO, BKNG, GOOG, which this strategy holds

| | |
|---|---|
| Strategy | `trend_reset_controlplacebo_hold63_near_zero0p25_roc21_was_high1p5` (family `trend_reset`) |
| Parameters | `{'roc': 21, 'was_high': 1.5, 'near_zero': 0.25, 'hold': 63, 'control': 'placebo'}` |
| Universe | 31 symbols, 2019-07-01 00:00:00+00:00 → 2025-08-29 00:00:00+00:00 |
| **Trials counted** | **8** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `alpaca_us_equity_zero_commission_fractional` at 3 bps/side, fees verified 2026-09-15 (commission and cls rule; spread and slippage unmeasured) |
| Generated | 2026-11-12T14:33:00+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:15:35 |
| 1 | Data integrity | **FAIL** | QA failed for AAPL, AMZN, AVGO, BKNG, GOOG, which this strategy holds |
| 2 | Cost survival | PASS | 98% of gross survives; Sharpe 0.82 at 2x costs; capacity about $30,000,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 2.32 |
| 4 | Multiple-testing deflation | PASS | DSR = 0.963 over 8 trials (effective rank 2), haircut Sharpe 0.28 |
| 5 | Selection overfitting | **FAIL** | PBO = 0.92 over 12870 splits of 8 variants; selection is arbitrary but stays profitable out of sample (9% losing) — the variants are interchangeable; SPA p = 0.781 vs exposure-matched buy-and-hold (70% invested) — no variant beats holding the universe at its own size |
| 6 | Permutation | **FAIL** | bar permutation p = 0.886 (12th percentile, re-optimised over 8 of 8 variants); random entry p = 0.572; volatility-preserving null p = 0.980 (2th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | WARN | median path Sharpe 0.55 = 65% of in-sample; 100% of 9 paths positive; WFE 0.35 — **UNJUSTIFIED** |
| 8 | Robustness and regime | **FAIL** | alpha t = 0.53 against beta 0.59 to equal_weight: this is the market, not the strategy |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.9634 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.5455 |
| Probability of backtest overfitting (gate 5) | 0.9207 |
| Bar-permutation p (gate 6) | 0.8856 |
| …with volatility preserved (reported, not binding) | 0.9801 |
| HAC t-statistic (gate 3) | 2.319 |
| Probabilistic Sharpe (gate 3) | 0.9796 |
| Net / gross return (gate 2) | 0.9822 |
| In-sample net Sharpe (the backtest number) | 0.8381 |
| cagr | 0.1593 |
| ann vol | 0.2005 |
| max drawdown | -0.2901 |
| ann turnover | 10.14 |
| round trips | 133 |
| time in market | 0.9568 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.02692 | 0.5285 |
| beta to equal_weight | 0.5854 | — |
| information ratio | 0.2041 | — |
| R² | 0.5673 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 4cbaac8f45b6ebaa31bc3630b852cdb8fbce38adf3d4f27bea99863ff2026b7a |
| registered_at | 2026-11-12T14:15:35.579629+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_trend_reset_v1_placebo.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 10 |
| qa_warnings | 0 |
| qa_failures_traded | 10 |
| qa_failed_symbols | ['AAPL', 'AMZN', 'AVGO', 'BKNG', 'GOOG', 'GOOGL', 'ISRG', 'NFLX', 'NVDA', 'TSLA'] |
| qa_failures_on_raw_bars | 10 |
| qa_bars_excluded | 0 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 3e+07 |
| capacity_usd_pessimistic | 3e+06 |
| capacity_usd_optimistic | 1e+08 |
| gross_annual_return | 0.1711 |
| impact_budget_annual | 0.01711 |
| impact_coef | 1 |
| median_participation_at_capacity | 2.337e-18 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0 |
| impact_drag_at_1e+04 | 0 |
| impact_drag_at_3e+04 | 0 |
| impact_drag_at_1e+05 | 5.074e-05 |
| impact_drag_at_3e+05 | 0.0004246 |
| impact_drag_at_1e+06 | 0.001737 |
| impact_drag_at_3e+06 | 0.004107 |
| impact_drag_at_1e+07 | 0.008866 |
| impact_drag_at_3e+07 | 0.01659 |
| impact_drag_at_1e+08 | 0.03169 |
| cost_share_commission | 0 |
| cost_share_spread | 1 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.8533 |
| net_sharpe | 0.8381 |
| net_over_gross | 0.9822 |
| ann_turnover | 10.14 |
| cost_drag_ann | 0.003042 |
| sharpe_at_2x_costs | 0.823 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 2.319 |
| hac_pvalue | 0.02039 |
| hac_lags | 7 |
| psr | 0.9796 |
| sharpe_ci_lower | 0.01227 |
| sharpe_ci_upper | 1.684 |
| min_track_record_length | 1,003 |
| observations | 1,551 |
| skew | -0.5351 |
| kurtosis | 10.05 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 8 |
| trials_raw | 8 |
| trials_effective | 2 |
| sharpe_variance | 2.026e-05 |
| deflation_benchmark_per_period | 0.006568 |
| dsr | 0.9634 |
| haircut_sharpe_bhy | 0.277 |
| adjusted_p_bhy | 0.2217 |
| min_backtest_length_years | 5.92 |
| sample_years | 6.167 |


**Gate 5 — selection overfitting**

| statistic | value |
|---|---|
| pbo | 0.9207 |
| median_logit | -1.253 |
| splits | 1.287e+04 |
| variants | 8 |
| blocks | 16 |
| degradation_slope | -0.9649 |
| prob_oos_loss | 0.08943 |
| median_is_sharpe | 0.06279 |
| median_oos_sharpe | 0.03794 |
| is_oos_rank_correlation | -0.6429 |
| benchmark | exposure |
| benchmark_exposure | 0.7029 |
| spa_p_consistent | 0.781 |
| spa_p_lower | 0.711 |
| spa_p_upper | 0.781 |
| spa_models | 8 |
| spa_benchmark | exposure_matched |
| spa_better_models | 0 |
| stepm_survivors | 0 |
| best_excess_annual | 0.01382 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.8533 |
| bar_permutation_p_value | 0.8856 |
| bar_permutation_percentile | 11.5 |
| bar_permutation_null_median | 1.104 |
| bar_permutation_null_95th | 1.414 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.8533 |
| random_entry_p_value | 0.5721 |
| random_entry_percentile | 43 |
| random_entry_null_median | 0.8708 |
| random_entry_null_95th | 1.087 |
| random_entry_permutations | 200 |
| reoptimised_over | 8 |
| grid_size | 8 |
| bar_permutation_vol_preserved_observed | 0.8533 |
| bar_permutation_vol_preserved_p_value | 0.9801 |
| bar_permutation_vol_preserved_percentile | 2 |
| bar_permutation_vol_preserved_null_median | 1.341 |
| bar_permutation_vol_preserved_null_95th | 1.738 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | FAIL |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.8381 |
| median_path_sharpe | 0.5455 |
| worst_path_sharpe | 0.387 |
| best_path_sharpe | 0.6614 |
| share_paths_positive | 1 |
| median_over_is | 0.6509 |
| walk_forward_efficiency | 0.3475 |
| walk_forward_efficiency_pooled | 0.5019 |
| walk_forward_windows | 5 |
| purge_bars | 63 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 3 |
| constructor_parameters | 5 |
| round_trips | 133 |
| neighbourhood_peak_sharpe | 0.8381 |
| neighbourhood_n_neighbours | 0 |
| neighbourhood_retention | — |
| years | 7 |
| share_profitable_years | 0.7143 |
| sharpe_without_best_year | 0.6093 |
| sharpe_without_best_5_trades | 0.5087 |
| sharpe_without_best_5_bars | 0.6257 |
| sharpe_in_low_vol | 1.32 |
| sharpe_in_mid_vol | 0.956 |
| sharpe_in_high_vol | 0.4414 |
| alpha_annual | 0.02692 |
| alpha_tstat | 0.5285 |
| alpha_pvalue | 0.5971 |
| r_squared | 0.5673 |
| information_ratio | 0.2041 |
| residual_vol_annual | 0.1319 |
| n_obs | 1,550 |
| beta_equal_weight | 0.5854 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 8 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
