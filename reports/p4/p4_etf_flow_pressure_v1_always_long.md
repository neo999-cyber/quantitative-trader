# Hypothesis Report — `p4_etf_flow_pressure_v1_always_long`

## Verdict: **FAIL**

stopped at gate 2 (cost survival): gross return is not positive; there is nothing to survive

| | |
|---|---|
| Strategy | `etf_flow_pressure_controlalways_long_gross1_hold24h_k0_timingt2` (family `etf_flow_pressure`) |
| Parameters | `{'k': 0.0, 'hold': '24h', 'timing': 't2', 'control': 'always_long', 'gross': 1.0}` |
| Universe | 1 symbols, 2024-01-11 00:00:00+00:00 → 2026-06-30 00:00:00+00:00 |
| **Trials counted** | **2** |
| Data manifest | `ce83ccec3bb3a9714c04953ba9415261` |
| Cost model | `binance_perp_maker_measured_2026-10_weekday` at 2.119 bps/side, fees verified 2026-10-11 stage 1 live, Binance USDⓈ-M, 1,169 orders |
| Generated | 2026-10-27T14:14:36+00:00 |

## The gates

| # | Gate | Verdict | Detail |
|---|---|---|---|
| 0 | Pre-registration | PASS | registered 2026-10-27T13:54:33 |
| 1 | Data integrity | PASS | no lag spike (+0.0 standard errors over its neighbours) |
| 2 | Cost survival | **FAIL** | gross return is not positive; there is nothing to survive |
| 3 | Single-strategy significance | — | _not reached_ |
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
| HAC t-statistic (gate 3) | — |
| Probabilistic Sharpe (gate 3) | — |
| Net / gross return (gate 2) | — |
| In-sample net Sharpe (the backtest number) | 0.02015 |
| cagr | -0.06907 |
| ann vol | 0.3989 |
| max drawdown | -0.6149 |
| ann turnover | 106.2 |
| round trips | 136 |
| time in market | 0.6642 |
| carry share of gross | -1.416 |


### Per gate

**Gate 0 — pre-registration**

| statistic | value |
|---|---|
| doc_sha256 | 8eb938b4d014d3f510b007420b153e9ca28726398622e39728f628360d711f45 |
| registered_at | 2026-10-27T13:54:33.900363+00:00 |
| registrations | 1 |
| source | docs/prereg/p4_etf_flow_pressure_v1_always_long.md |
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
| lag0_gross_sharpe | 0.03175 |
| lag1_gross_sharpe | 0.07658 |
| lag2_gross_sharpe | 0.04824 |
| peek_ratio | 0.4146 |
| spike_ratio | 1.587 |
| spike_z | 0.04452 |
| sharpe_standard_error | 0.6365 |


**Gate 2 — cost survival**

| statistic | value |
|---|---|
| capacity_usd | 1e+04 |
| capacity_usd_pessimistic | 1,000 |
| capacity_usd_optimistic | 3e+04 |
| gross_annual_return | 0.03055 |
| impact_budget_annual | 0.003055 |
| impact_coef | 1 |
| median_participation_at_capacity | 2.363e-21 |
| capacity_extrapolated | True |
| impact_drag_at_1e+03 | 0.0006993 |
| impact_drag_at_1e+04 | 0.002211 |
| impact_drag_at_3e+04 | 0.00383 |
| cost_share_commission | 1 |
| cost_share_spread | 0 |
| cost_share_impact | 0 |
| cost_share_borrow | 0 |
| gross_sharpe | 0.07658 |
| net_sharpe | 0.02015 |
| net_over_gross | — |
| ann_turnover | 106.2 |
| cost_drag_ann | 0.02251 |
| sharpe_at_2x_costs | -0.03629 |


## How to read this

The in-sample Sharpe is the least informative number here and appears last for that reason. The deflated Sharpe prices the search; the holdout is the only figure computed on data the strategy had never seen. A strategy is worth trading when those two agree with each other, not when the backtest is impressive.

Reproduce: the data manifest hash pins the bytes, the trial log pins the 2 variants that were run, and the cost model above pins the fee schedule. Change any of the three and this report no longer applies.
