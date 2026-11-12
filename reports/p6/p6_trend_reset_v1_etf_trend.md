# Hypothesis Report — `p6_trend_reset_v1_etf_trend`

## Verdict: **FAIL**

stopped at gate 1 (data integrity): QA failed for DBC, EEM, EFA, HYG, IEF, which this strategy holds

| | |
|---|---|
| Strategy | `trend_reset_controltrend_hold63_near_zero0p25_roc63_was_high1` (family `trend_reset`) |
| Parameters | `{'roc': 63, 'was_high': 1.0, 'near_zero': 0.25, 'hold': 63, 'control': 'trend'}` |
| Universe | 12 symbols, 2007-01-03 00:00:00+00:00 → 2022-12-30 00:00:00+00:00 |
| **Trials counted** | **1** |
| Data manifest | `239c32049fe164b1ece233f815c94843` |
| Cost model | `alpaca_us_equity_zero_commission_fractional` at 3 bps/side, fees verified 2026-09-15 (commission and cls rule; spread and slippage unmeasured) |
| Generated | 2026-11-12T14:46:13+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-11-12T14:15:36 |
| 1 | Data integrity | **FAIL** | QA failed for DBC, EEM, EFA, HYG, IEF, which this strategy holds |
| 2 | Cost survival | PASS | 97% of gross survives; Sharpe 0.70 at 2x costs; capacity about $30,000,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | PASS | t = 3.08, PSR = 0.998, CI excludes zero |
| 4 | Multiple-testing deflation | PASS | DSR = 0.998 over 1 trials (effective rank 1), haircut Sharpe 0.72 |
| 5 | Selection overfitting | skip | only one variant was run, so nothing was selected; PBO does not apply |
| 6 | Permutation | PASS | bar permutation p = 0.045 (96th percentile, single variant, no re-optimisation); random entry p = 0.020; volatility-preserving null p = 0.816 (18th percentile, reported, not binding) |
| 7 | Cross-validated OOS distribution | PASS | median path Sharpe 0.72 = 100% of in-sample; 100% of 9 paths positive; WFE 1.19 |
| 8 | Robustness and regime | WARN | alpha t = 2.43 — **UNJUSTIFIED** |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | 0.9978 |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | 0.7225 |
| Probability of backtest overfitting (gate 5) | — |
| Bar-permutation p (gate 6) | 0.04478 |
| …with volatility preserved (reported, not binding) | 0.8159 |
| HAC t-statistic (gate 3) | 3.082 |
| Probabilistic Sharpe (gate 3) | 0.9978 |
| Net / gross return (gate 2) | 0.9673 |
| In-sample net Sharpe (the backtest number) | 0.7225 |
| cagr | 0.06582 |
| ann vol | 0.09442 |
| max drawdown | -0.116 |
| ann turnover | 7.698 |
| round trips | 268 |
| time in market | 0.9826 |


### Factor decomposition

| term | value | t-stat |
|---|---|---|
| alpha (annualised) | 0.04748 | 2.433 |
| beta to equal_weight | 0.2986 | — |
| information ratio | 0.5522 | — |
| R² | 0.1712 | — |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | d2d11681719a7132acf9ca6254714212ee4f56ad18b34abf3e07ec1bc5c4b85e |
| registered_at | 2026-11-12T14:15:36.348167+00:00 |
| registrations | 1 |
| source | docs/prereg/p6_trend_reset_v1_etf_trend.md |
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
| capacity_usd | 3e+07 |
| capacity_usd_pessimistic | 3e+06 |
| capacity_usd_optimistic | 1e+08 |
| gross_annual_return | 0.07052 |
| impact_budget_annual | 0.007052 |
| impact_coef | 1 |
| median_participation_at_capacity | 9.655e-19 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0 |
| impact_drag_at_1e+04 | 6.409e-07 |
| impact_drag_at_3e+04 | 1.069e-05 |
| impact_drag_at_1e+05 | 6.234e-05 |
| impact_drag_at_3e+05 | 0.0002141 |
| impact_drag_at_1e+06 | 0.0005927 |
| impact_drag_at_3e+06 | 0.001386 |
| impact_drag_at_1e+07 | 0.003236 |
| impact_drag_at_3e+07 | 0.006419 |
| impact_drag_at_1e+08 | 0.01274 |
| cost_share_commission | 0 |
| cost_share_spread | 1 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.747 |
| net_sharpe | 0.7225 |
| net_over_gross | 0.9673 |
| ann_turnover | 7.698 |
| cost_drag_ann | 0.002309 |
| sharpe_at_2x_costs | 0.6979 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 3.082 |
| hac_pvalue | 0.002055 |
| hac_lags | 9 |
| psr | 0.9978 |
| sharpe_ci_lower | 0.2232 |
| sharpe_ci_upper | 1.21 |
| min_track_record_length | 1,344 |
| observations | 4,028 |
| skew | -0.5626 |
| kurtosis | 6.784 |


**Gate 4 — multiple-testing deflation**

| statistic | value |
|---|---|
| trials | 1 |
| trials_raw | 1 |
| trials_effective | 1 |
| sharpe_variance | 0.0002483 |
| deflation_benchmark_per_period | 0 |
| dsr | 0.9978 |
| haircut_sharpe_bhy | 0.7225 |
| adjusted_p_bhy | 0.001028 |
| min_backtest_length_years | — |
| sample_years | 15.99 |


**Gate 6 — permutation**

| statistic | value |
|---|---|
| bar_permutation_observed | 0.747 |
| bar_permutation_p_value | 0.04478 |
| bar_permutation_percentile | 96 |
| bar_permutation_null_median | 0.4926 |
| bar_permutation_null_95th | 0.7319 |
| bar_permutation_permutations | 200 |
| random_entry_observed | 0.747 |
| random_entry_p_value | 0.0199 |
| random_entry_percentile | 98.5 |
| random_entry_null_median | 0.448 |
| random_entry_null_95th | 0.6684 |
| random_entry_permutations | 200 |
| reoptimised_over | 1 |
| grid_size | 1 |
| bar_permutation_vol_preserved_observed | 0.747 |
| bar_permutation_vol_preserved_p_value | 0.8159 |
| bar_permutation_vol_preserved_percentile | 18.5 |
| bar_permutation_vol_preserved_null_median | 0.8967 |
| bar_permutation_vol_preserved_null_95th | 1.179 |
| bar_permutation_vol_preserved_permutations | 200 |
| vol_preserved_verdict | FAIL |


**Gate 7 — cross-validated OOS**

| statistic | value |
|---|---|
| paths | 9 |
| splits | 45 |
| groups | 10 |
| k | 2 |
| is_sharpe | 0.7225 |
| median_path_sharpe | 0.7225 |
| worst_path_sharpe | 0.7225 |
| best_path_sharpe | 0.7225 |
| share_paths_positive | 1 |
| median_over_is | 1 |
| walk_forward_efficiency | 1.192 |
| walk_forward_efficiency_pooled | 1.204 |
| walk_forward_windows | 5 |
| purge_bars | 63 |


**Gate 8 — robustness and regime**

| statistic | value |
|---|---|
| free_parameters | 5 |
| constructor_parameters | 5 |
| round_trips | 268 |
| years | 16 |
| share_profitable_years | 0.75 |
| sharpe_without_best_year | 0.6324 |
| sharpe_without_best_5_trades | 0.4992 |
| sharpe_without_best_5_bars | 0.6428 |
| sharpe_in_low_vol | 0.9296 |
| sharpe_in_mid_vol | 0.2824 |
| sharpe_in_high_vol | 0.9565 |
| alpha_annual | 0.04748 |
| alpha_tstat | 2.433 |
| alpha_pvalue | 0.01496 |
| r_squared | 0.1712 |
| information_ratio | 0.5522 |
| residual_vol_annual | 0.08597 |
| n_obs | 4,027 |
| beta_equal_weight | 0.2986 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 1 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
