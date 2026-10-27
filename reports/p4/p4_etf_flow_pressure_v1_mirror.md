# Hypothesis Report — `p4_etf_flow_pressure_v1_mirror`

## Verdict: **FAIL**

stopped at gate 3 (single-strategy significance): HAC t = 0.71

| | |
|---|---|
| Strategy | `etf_flow_pressure_controlmirror_gross1_holdsession_k1_timingt2` (family `etf_flow_pressure`) |
| Parameters | `{'k': 1.0, 'hold': 'session', 'timing': 't2', 'control': 'mirror', 'gross': 1.0}` |
| Universe | 1 symbols, 2024-01-11 00:00:00+00:00 → 2026-06-30 00:00:00+00:00 |
| **Trials counted** | **6** |
| Data manifest | `ce83ccec3bb3a9714c04953ba9415261` |
| Cost model | `binance_perp_maker_measured_2026-10_weekday` at 2.119 bps/side, fees verified 2026-10-11 stage 1 live, Binance USDⓈ-M, 1,169 orders |
| Generated | 2026-10-27T14:14:23+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-10-27T13:54:33 |
| 1 | Data integrity | PASS | no lag spike (-0.3 standard errors over its neighbours) |
| 2 | Cost survival | PASS | 69% of gross survives; Sharpe 0.26 at 2x costs; capacity about $100,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 0.71 |
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
| HAC t-statistic (gate 3) | 0.7106 |
| Probabilistic Sharpe (gate 3) | 0.77 |
| Net / gross return (gate 2) | 0.693 |
| In-sample net Sharpe (the backtest number) | 0.4705 |
| cagr | 0.07162 |
| ann vol | 0.1824 |
| max drawdown | -0.2037 |
| ann turnover | 179.4 |
| round trips | 225 |
| time in market | 0.07283 |
| carry share of gross | 0.05124 |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | acd8b106e46fbb417d7b1d5dcbb8564aaabb36d29034fc421a0e2d6dde82631c |
| registered_at | 2026-10-27T13:54:33.167206+00:00 |
| registrations | 1 |
| source | docs/prereg/p4_etf_flow_pressure_v1_mirror.md |
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
| lag0_gross_sharpe | 0.4877 |
| lag1_gross_sharpe | 0.6791 |
| lag2_gross_sharpe | 0.8414 |
| peek_ratio | 0.7182 |
| spike_ratio | 0.8071 |
| spike_z | -0.255 |
| sharpe_standard_error | 0.6365 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 1e+05 |
| capacity_usd_pessimistic | 3e+04 |
| capacity_usd_optimistic | 3e+05 |
| gross_annual_return | 0.1238 |
| impact_budget_annual | 0.01238 |
| impact_coef | 1 |
| median_participation_at_capacity | 3.591e-20 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0.001123 |
| impact_drag_at_1e+04 | 0.003551 |
| impact_drag_at_3e+04 | 0.00615 |
| impact_drag_at_1e+05 | 0.01123 |
| impact_drag_at_3e+05 | 0.01945 |
| cost_share_commission | 1 |
| cost_share_spread | 0 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.6791 |
| net_sharpe | 0.4705 |
| net_over_gross | 0.693 |
| ann_turnover | 179.4 |
| cost_drag_ann | 0.03802 |
| sharpe_at_2x_costs | 0.2619 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 0.7106 |
| hac_pvalue | 0.4773 |
| hac_lags | 13 |
| psr | 0.77 |
| sharpe_ci_lower | -0.8004 |
| sharpe_ci_upper | 1.696 |
| min_track_record_length | 1.072e+05 |
| observations | 2.162e+04 |
| skew | -0.0351 |
| kurtosis | 92.22 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 6 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
