# `p4_etf_flow_pressure_v1` — per-trade reading of the counted runs (2026-10-27)

In-sample 2024-01-11 → 2026-06-30, net of the weekday measured maker cost, from the saved per-variant returns; no re-run.
`mean_net_bps` is the mean net return per entry over its hold; `t_per_trade` its t across entries; `net_sharpe` the
hourly series annualised.

## `p4_etf_flow_pressure_v1` — the family (T + 2)

| variant | k | hold | entries | long | short | mean_net_bps | t_per_trade | hit_rate | total_net_pct | net_sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| controlnone_gross1_holdsession_k0p5_timingt2 | 0.5 | session | 342 | 255 | 87 | -4.97 | -0.47 | 0.477 | -23.96 | -0.44 |
| controlnone_gross1_holdsession_k1_timingt2 | 1 | session | 225 | 184 | 41 | -15.65 | -1.18 | 0.462 | -39.8 | -0.88 |
| controlnone_gross1_holdsession_k1p5_timingt2 | 1.5 | session | 152 | 127 | 25 | -16.86 | -1.07 | 0.454 | -28.72 | -0.77 |
| controlnone_gross1_hold24h_k0p5_timingt2 | 0.5 | 24h | 341 | 255 | 87 | -6.14 | -0.44 | 0.478 | -23.93 | -0.32 |
| controlnone_gross1_hold24h_k1_timingt2 | 1 | 24h | 224 | 184 | 41 | -10.99 | -0.65 | 0.487 | -26.84 | -0.43 |
| controlnone_gross1_hold24h_k1p5_timingt2 | 1.5 | 24h | 151 | 127 | 25 | -1.96 | -0.1 | 0.497 | -4.52 | -0.09 |

## `p4_etf_flow_pressure_v1_t1` — the diagnostic arm (T + 1)

| variant | k | hold | entries | long | short | mean_net_bps | t_per_trade | hit_rate | total_net_pct | net_sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| controlnone_gross1_holdsession_k0p5_timingt1 | 0.5 | session | 343 | 255 | 88 | 3.74 | 0.36 | 0.516 | 5.85 | 0.11 |
| controlnone_gross1_holdsession_k1_timingt1 | 1 | session | 226 | 184 | 42 | 4.86 | 0.36 | 0.518 | 6.4 | 0.14 |
| controlnone_gross1_holdsession_k1p5_timingt1 | 1.5 | session | 153 | 127 | 26 | 7.74 | 0.5 | 0.549 | 8.73 | 0.24 |
| controlnone_gross1_hold24h_k0p5_timingt1 | 0.5 | 24h | 342 | 255 | 88 | 16.82 | 1.3 | 0.535 | 54.55 | 0.73 |
| controlnone_gross1_hold24h_k1_timingt1 | 1 | 24h | 225 | 184 | 42 | 16.83 | 1.03 | 0.52 | 35.6 | 0.57 |
| controlnone_gross1_hold24h_k1p5_timingt1 | 1.5 | 24h | 152 | 127 | 26 | 23.62 | 1.33 | 0.539 | 34.35 | 0.67 |

## `p4_etf_flow_pressure_v1_mirror` — mirror (sides reversed)

| variant | k | hold | entries | long | short | mean_net_bps | t_per_trade | hit_rate | total_net_pct | net_sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| controlmirror_gross1_holdsession_k0p5_timingt2 | 0.5 | session | 342 | 87 | 255 | 0.77 | 0.07 | 0.518 | -4.32 | -0.08 |
| controlmirror_gross1_holdsession_k1_timingt2 | 1 | session | 225 | 41 | 184 | 11.45 | 0.86 | 0.533 | 21.18 | 0.47 |
| controlmirror_gross1_holdsession_k1p5_timingt2 | 1.5 | session | 152 | 25 | 127 | 12.65 | 0.81 | 0.539 | 16.14 | 0.43 |
| controlmirror_gross1_hold24h_k0p5_timingt2 | 0.5 | 24h | 341 | 87 | 255 | 3.58 | 0.26 | 0.51 | 8.85 | 0.12 |
| controlmirror_gross1_hold24h_k1_timingt2 | 1 | 24h | 224 | 41 | 184 | 8.44 | 0.5 | 0.504 | 16.3 | 0.26 |
| controlmirror_gross1_hold24h_k1p5_timingt2 | 1.5 | 24h | 151 | 25 | 127 | -0.7 | -0.03 | 0.49 | -2.99 | -0.06 |

## `p4_etf_flow_pressure_v1_placebo` — placebo (flows permuted within month)

| variant | k | hold | entries | long | short | mean_net_bps | t_per_trade | hit_rate | total_net_pct | net_sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| controlplacebo_gross1_holdsession_k0p5_timingt2 | 0.5 | session | 342 | 255 | 87 | 6.03 | 0.57 | 0.523 | 13.68 | 0.25 |
| controlplacebo_gross1_holdsession_k1_timingt2 | 1 | session | 225 | 184 | 41 | 8.09 | 0.64 | 0.511 | 13.63 | 0.3 |
| controlplacebo_gross1_holdsession_k1p5_timingt2 | 1.5 | session | 152 | 127 | 25 | 13.1 | 0.84 | 0.546 | 16.82 | 0.45 |
| controlplacebo_gross1_hold24h_k0p5_timingt2 | 0.5 | 24h | 342 | 255 | 87 | 31.5 | 2.41 | 0.558 | 104.02 | 1.38 |
| controlplacebo_gross1_hold24h_k1_timingt2 | 1 | 24h | 225 | 184 | 41 | 31.42 | 1.99 | 0.56 | 67.54 | 1.09 |
| controlplacebo_gross1_hold24h_k1p5_timingt2 | 1.5 | 24h | 152 | 127 | 25 | 37.72 | 1.99 | 0.572 | 54.99 | 1.07 |

## `p4_etf_flow_pressure_v1_always_long` — base rate (long every eligible session)

| variant | k | hold | entries | long | short | mean_net_bps | t_per_trade | hit_rate | total_net_pct | net_sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| controlalways_long_gross1_holdsession_k0_timingt2 | 0 | session | 599 | 599 | 0 | -10.14 | -1.28 | 0.489 | -72.93 | -1.02 |
| controlalways_long_gross1_hold24h_k0_timingt2 | 0 | 24h | 598 | 599 | 0 | 0.83 | 0.08 | 0.532 | 1.98 | 0.02 |

