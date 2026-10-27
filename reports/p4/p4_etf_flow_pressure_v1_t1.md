# Hypothesis Report — `p4_etf_flow_pressure_v1_t1`

## Verdict: **FAIL**

stopped at gate 3 (single-strategy significance): HAC t = 1.17

| | |
|---|---|
| Strategy | `etf_flow_pressure_controlnone_gross1_hold24h_k0p5_timingt1` (family `etf_flow_pressure`) |
| Parameters | `{'k': 0.5, 'hold': '24h', 'timing': 't1', 'control': 'none', 'gross': 1.0}` |
| Universe | 1 symbols, 2024-01-11 00:00:00+00:00 → 2026-06-30 00:00:00+00:00 |
| **Trials counted** | **6** |
| Data manifest | `ce83ccec3bb3a9714c04953ba9415261` |
| Cost model | `binance_perp_maker_measured_2026-10_weekday` at 2.119 bps/side, fees verified 2026-10-11 stage 1 live, Binance USDⓈ-M, 1,169 orders |
| Generated | 2026-10-27T14:14:15+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-10-27T13:54:32 |
| 1 | Data integrity | PASS | no lag spike (-0.2 standard errors over its neighbours) |
| 2 | Cost survival | PASS | 88% of gross survives; Sharpe 0.64 at 2x costs; capacity about $300,000 before impact takes a further 10% of gross |
| 3 | Single-strategy significance | **FAIL** | HAC t = 1.17 |
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
| HAC t-statistic (gate 3) | 1.175 |
| Probabilistic Sharpe (gate 3) | 0.8756 |
| Net / gross return (gate 2) | 0.8818 |
| In-sample net Sharpe (the backtest number) | 0.7339 |
| cagr | 0.192 |
| ann vol | 0.3011 |
| max drawdown | -0.2938 |
| ann turnover | 139.8 |
| round trips | 156 |
| time in market | 0.3801 |
| carry share of gross | -0.08888 |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 6437ab6afec448fcff1e4255fc32f20e95b3a997d67e90445679e673ca18a84b |
| registered_at | 2026-10-27T13:54:32.798083+00:00 |
| registrations | 1 |
| source | docs/prereg/p4_etf_flow_pressure_v1_t1.md |
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
| lag0_gross_sharpe | 0.9431 |
| lag1_gross_sharpe | 0.8324 |
| lag2_gross_sharpe | 0.8318 |
| peek_ratio | 1.133 |
| spike_ratio | 0.8826 |
| spike_z | -0.174 |
| sharpe_standard_error | 0.6365 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 3e+05 |
| capacity_usd_pessimistic | 1e+05 |
| capacity_usd_optimistic | 1e+06 |
| gross_annual_return | 0.2506 |
| impact_budget_annual | 0.02506 |
| impact_coef | 1 |
| median_participation_at_capacity | 7.095e-20 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0.0009194 |
| impact_drag_at_1e+04 | 0.002907 |
| impact_drag_at_3e+04 | 0.005036 |
| impact_drag_at_1e+05 | 0.009194 |
| impact_drag_at_3e+05 | 0.01592 |
| impact_drag_at_1e+06 | 0.02907 |
| cost_share_commission | 1 |
| cost_share_spread | 0 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.8324 |
| net_sharpe | 0.7339 |
| net_over_gross | 0.8818 |
| ann_turnover | 139.8 |
| cost_drag_ann | 0.02963 |
| sharpe_at_2x_costs | 0.6355 |


**Gate 3 — single-strategy significance**

| statistic | value |
|---|---|
| hac_tstat | 1.175 |
| hac_pvalue | 0.2401 |
| hac_lags | 13 |
| psr | 0.8756 |
| sharpe_ci_lower | -0.5176 |
| sharpe_ci_upper | 1.946 |
| min_track_record_length | 4.399e+04 |
| observations | 2.162e+04 |
| skew | 0.0706 |
| kurtosis | 29.03 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 6 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
