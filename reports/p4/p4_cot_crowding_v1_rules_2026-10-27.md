# `p4_cot_crowding_v1` — per-variant reading of the counted runs (2026-10-27)

In-sample 2020-01-01 → 2024-12-31 on the BTCUSDT carry unit at the memo's cost (21.5 bps a round trip), from the saved
per-variant net returns; no re-run. `ann_net_pct` is the mean daily net return annualised; `vs_holding_ann_pct` the same
less the always-in holding's; `days_in_share` the share of days the unit was held; the years are net percent each.

## `p4_cot_crowding_v1` — the timer: out while crowded

| variant | total_net_pct | ann_net_pct | net_sharpe | days_in_share | worst_year_pct | best_year_pct | vs_holding_ann_pct | years_ahead_of_holding | years |
|---|---|---|---|---|---|---|---|---|---|
| controlnone_gross1_p80_window26 | 28.93 | 5.78 | 5.93 | 0.652 | 1.48 | 8.88 | -6.88 | 0 | 2020:+8.4 2021:+8.9 2022:+1.5 2023:+4.1 2024:+6.0 |
| controlnone_gross1_p80_window52 | 28.41 | 5.68 | 6.18 | 0.614 | 1.7 | 9.1 | -6.98 | 0 | 2020:+9.1 2021:+8.4 2022:+1.7 2023:+5.0 2024:+4.3 |
| controlnone_gross1_p90_window26 | 38.47 | 7.69 | 6.88 | 0.772 | 1.75 | 15.4 | -4.97 | 0 | 2020:+8.9 2021:+15.4 2022:+1.8 2023:+4.7 2024:+7.7 |
| controlnone_gross1_p90_window52 | 36.71 | 7.33 | 6.76 | 0.736 | 1.48 | 13.48 | -5.33 | 0 | 2020:+9.8 2021:+13.5 2022:+1.5 2023:+5.2 2024:+6.8 |
| controlnone_gross1_p95_window26 | 41.53 | 8.3 | 7.2 | 0.825 | 1.92 | 17.31 | -4.36 | 0 | 2020:+9.5 2021:+17.3 2022:+1.9 2023:+4.8 2024:+8.0 |
| controlnone_gross1_p95_window52 | 46.57 | 9.3 | 7.42 | 0.842 | 1.55 | 21.13 | -3.36 | 0 | 2020:+10.8 2021:+21.1 2022:+1.6 2023:+5.4 2024:+7.7 |

## `p4_cot_crowding_v1_always_in` — the holding, no rule

| variant | total_net_pct | ann_net_pct | net_sharpe | days_in_share | worst_year_pct | best_year_pct | vs_holding_ann_pct | years_ahead_of_holding | years |
|---|---|---|---|---|---|---|---|---|---|
| controlalways_in_gross1_p90_window52 | 63.35 | 12.66 | 8.78 | 0.999 | 3.06 | 27.95 | 0 | 0 | 2020:+14.8 2021:+27.9 2022:+3.1 2023:+6.8 2024:+10.7 |

## `p4_cot_crowding_v1_mirror` — mirror: in only while crowded

| variant | total_net_pct | ann_net_pct | net_sharpe | days_in_share | worst_year_pct | best_year_pct | vs_holding_ann_pct | years_ahead_of_holding | years |
|---|---|---|---|---|---|---|---|---|---|
| controlmirror_gross1_p80_window26 | 24.82 | 4.96 | 4.04 | 0.377 | 0.13 | 16.36 | -7.7 | 0 | 2020:+5.0 2021:+16.4 2022:+0.1 2023:+0.9 2024:+2.5 |
| controlmirror_gross1_p80_window52 | 27.51 | 5.5 | 4.39 | 0.408 | 0.27 | 18.32 | -7.16 | 0 | 2020:+3.6 2021:+18.3 2022:+0.3 2023:+0.9 2024:+4.4 |
| controlmirror_gross1_p90_window26 | 16.56 | 3.31 | 3.06 | 0.252 | 0.21 | 10.94 | -9.35 | 0 | 2020:+4.6 2021:+10.9 2022:+0.2 2023:+0.3 2024:+0.5 |
| controlmirror_gross1_p90_window52 | 18.48 | 3.69 | 3.31 | 0.288 | 0.13 | 12.48 | -8.97 | 0 | 2020:+4.0 2021:+12.5 2022:+0.1 2023:+0.2 2024:+1.7 |
| controlmirror_gross1_p95_window26 | 14.21 | 2.84 | 2.76 | 0.198 | 0.06 | 9.02 | -9.82 | 0 | 2020:+4.4 2021:+9.0 2022:+0.1 2023:+0.2 2024:+0.5 |
| controlmirror_gross1_p95_window52 | 8.81 | 1.76 | 2 | 0.181 | -0.4 | 5.2 | -10.9 | 0 | 2020:+3.4 2021:+5.2 2022:+0.1 2023:-0.4 2024:+0.5 |

## `p4_cot_crowding_v1_placebo` — placebo: the crowded flags in permuted 13-week blocks

| variant | total_net_pct | ann_net_pct | net_sharpe | days_in_share | worst_year_pct | best_year_pct | vs_holding_ann_pct | years_ahead_of_holding | years |
|---|---|---|---|---|---|---|---|---|---|
| controlplacebo_gross1_p80_window26 | 38.16 | 7.62 | 5.51 | 0.655 | 0.5 | 23.52 | -5.04 | 0 | 2020:+7.8 2021:+23.5 2022:+1.0 2023:+0.5 2024:+5.4 |
| controlplacebo_gross1_p80_window52 | 35.42 | 7.08 | 5.37 | 0.617 | 0.65 | 20.04 | -5.58 | 0 | 2020:+7.6 2021:+20.0 2022:+0.7 2023:+2.1 2024:+5.0 |
| controlplacebo_gross1_p90_window26 | 47.89 | 9.57 | 6.58 | 0.773 | 0.92 | 24.56 | -3.09 | 0 | 2020:+13.5 2021:+24.6 2022:+0.9 2023:+1.8 2024:+7.1 |
| controlplacebo_gross1_p90_window52 | 42.8 | 8.55 | 6.2 | 0.737 | 1.34 | 23.52 | -4.11 | 0 | 2020:+8.0 2021:+23.5 2022:+1.3 2023:+3.5 2024:+6.5 |
| controlplacebo_gross1_p95_window26 | 51.92 | 10.37 | 7.05 | 0.826 | 1.11 | 26.16 | -2.29 | 0 | 2020:+13.8 2021:+26.2 2022:+1.1 2023:+2.2 2024:+8.6 |
| controlplacebo_gross1_p95_window52 | 50.87 | 10.16 | 6.99 | 0.843 | 1.06 | 24.56 | -2.5 | 0 | 2020:+13.5 2021:+24.6 2022:+1.1 2023:+4.7 2024:+7.1 |

## `p4_cot_crowding_v1_eth` — the ETH arm

| variant | total_net_pct | ann_net_pct | net_sharpe | days_in_share | worst_year_pct | best_year_pct | years |
|---|---|---|---|---|---|---|---|
| controlnone_gross1_p80_window26 | 71.37 | 14.26 | 7.41 | 0.875 | -0.41 | 34.27 | 2020:+23.9 2021:+34.3 2022:-0.4 2023:+5.0 2024:+8.5 |
| controlnone_gross1_p80_window52 | 72.27 | 14.44 | 7.52 | 0.885 | -0.41 | 34.27 | 2020:+23.9 2021:+34.3 2022:-0.4 2023:+5.6 2024:+8.9 |
| controlnone_gross1_p90_window26 | 72.97 | 14.58 | 7.58 | 0.924 | -0.41 | 34.27 | 2020:+23.9 2021:+34.3 2022:-0.4 2023:+5.4 2024:+9.8 |
| controlnone_gross1_p90_window52 | 73.31 | 14.65 | 7.63 | 0.92 | -0.41 | 34.27 | 2020:+23.9 2021:+34.3 2022:-0.4 2023:+5.6 2024:+9.9 |
| controlnone_gross1_p95_window26 | 73.67 | 14.72 | 7.66 | 0.943 | -0.41 | 34.27 | 2020:+23.9 2021:+34.3 2022:-0.4 2023:+5.6 2024:+10.2 |
| controlnone_gross1_p95_window52 | 74.72 | 14.93 | 7.8 | 0.963 | -0.41 | 34.27 | 2020:+23.9 2021:+34.3 2022:-0.4 2023:+6.0 2024:+11.0 |

