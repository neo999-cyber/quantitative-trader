# Hypothesis Report — `p4_etf_flow_pressure_v1_placebo`

## Verdict: **FAIL**

stopped at gate 3 (single-strategy significance): HAC t = 2.28

| | |
|---|---|
| Strategy | `etf_flow_pressure_controlplacebo_gross1_hold24h_k0p5_timingt2` (family `etf_flow_pressure`) |
| Parameters | `{'k': 0.5, 'hold': '24h', 'timing': 't2', 'control': 'placebo', 'gross': 1.0}` |
| Universe | 1 symbols, 2024-01-11 00:00:00+00:00 → 2026-06-30 00:00:00+00:00 |
| **Trials counted** | **6** |
| Data manifest | `ce83ccec3bb3a9714c04953ba9415261` |
| Cost model | `binance_perp_maker_measured_2026-10_weekday` at 2.119 bps/side, fees verified 2026-10-11 stage 1 live, Binance USDⓈ-M, 1,169 orders |
| Generated | 2026-10-27T14:14:31+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-10-27T13:54:33 |
| 1 | Data integrity | PASS | no lag spike (+0.1 standard errors over its neighbours) |
| 2 | Cost survival | PASS | 92% of gross survives; Sharpe 1.26 at 2x costs; capacity about $1,000,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 2.28 |
| 4 | Multiple-testing deflation | — | _not reached_ |
| 5 | Selection overfitting | — | _not reached_ |
| 6 | Permutation | — | _not reached_ |
| 7 | Cross-validated OOS distribution | — | _not reached_ |
| 8 | Robustness and regime | — | _not reached_ |
| 9 | True holdout | — | _not reached_ |
| 10 | Incubation | — | _after the trial_ |
| 11 | Sizing | — | _after the trial_ |

## What the numbers were

| metric | value |
|---|---|
| Deflated Sharpe (gate 4) | — |
| Holdout Sharpe (gate 9) | — |
| Median CPCV path Sharpe (gate 7) | — |
| Probability of backtest overfitting (gate 5) | — |
| Bar-permutation p (gate 6) | — |
| …with volatility preserved (reported, not binding) | — |
| HAC t-statistic (gate 3) | 2.283 |
| Probabilistic Sharpe (gate 3) | 0.9853 |
| Net / gross return (gate 2) | 0.9194 |
| In-sample net Sharpe (the backtest number) | 1.382 |
| cagr | 0.4549 |
| ann vol | 0.3049 |
| max drawdown | -0.2607 |
| ann turnover | 174.2 |
| round trips | 182 |
| time in market | 0.3796 |
| carry share of gross | -0.04273 |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 6fa341da4237109ab2816e8d0f191dc79d7f2c7974ee459a3000b97d100e7d9c |
| registered_at | 2026-10-27T13:54:33.533420+00:00 |
| registrations | 1 |
| source | docs/prereg/p4_etf_flow_pressure_v1_placebo.md |
| doc_verified | True |


**Gate 1 — data integrity**

| statistic | value |
|---|---|
| qa_failures | 0 |
| qa_warnings | 0 |
| qa_failures_traded | 0 |
| qa_failed_symbols | [] |
| qa_failures_on_raw_bars | 0 |
| qa_bars_excluded | 1 |
| lag0_gross_sharpe | 1.45 |
| lag1_gross_sharpe | 1.503 |
| lag2_gross_sharpe | 1.134 |
| peek_ratio | 0.9647 |
| spike_ratio | 1.037 |
| spike_z | 0.08333 |
| sharpe_standard_error | 0.6365 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 1e+06 |
| capacity_usd_pessimistic | 3e+05 |
| capacity_usd_optimistic | 3e+06 |
| gross_annual_return | 0.4583 |
| impact_budget_annual | 0.04583 |
| impact_coef | 1 |
| median_participation_at_capacity | 2.371e-19 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0.001176 |
| impact_drag_at_1e+04 | 0.003718 |
| impact_drag_at_3e+04 | 0.006439 |
| impact_drag_at_1e+05 | 0.01176 |
| impact_drag_at_3e+05 | 0.02036 |
| impact_drag_at_1e+06 | 0.03718 |
| impact_drag_at_3e+06 | 0.06439 |
| cost_share_commission | 1 |
| cost_share_spread | 0 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 1.503 |
| net_sharpe | 1.382 |
| net_over_gross | 0.9194 |
| ann_turnover | 174.2 |
| cost_drag_ann | 0.03692 |
| sharpe_at_2x_costs | 1.261 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 2.283 |
| hac_pvalue | 0.02246 |
| hac_lags | 13 |
| psr | 0.9853 |
| sharpe_ci_lower | 0.1851 |
| sharpe_ci_upper | 2.555 |
| min_track_record_length | 1.234e+04 |
| observations | 2.162e+04 |
| skew | 0.4469 |
| kurtosis | 27.12 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 6 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
