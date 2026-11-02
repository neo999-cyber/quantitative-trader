# P5 — `p5_forecastability_tsfm_v1` — insample 2023-01-01 → 2026-05-31

Arms: timesfm3, timesfm3_cov, timesfm25; backend mlx; 33111 forecasts in 13362 s.

| pair | score | permuted control | extra-lag control | bar |
|---|---|---|---|---|
| `direction:timesfm3` | n 1227, accuracy 0.494, base_rate_accuracy 0.492, t_vs_base 0.071, brier_skill -0.004, t_brier -1.171 | n 1227, accuracy 0.509, base_rate_accuracy 0.491, t_vs_base 0.804, brier_skill 0.005, t_brier 1.982 | n 1227, accuracy 0.499, base_rate_accuracy 0.494, t_vs_base 0.216, brier_skill 0.002, t_brier 0.78 | fail |
| `direction:timesfm3_cov` | n 1227, accuracy 0.509, base_rate_accuracy 0.492, t_vs_base 0.897, brier_skill -0.005, t_brier -1.067 | n 1227, accuracy 0.517, base_rate_accuracy 0.491, t_vs_base 1.329, brier_skill 0.001, t_brier 0.141 | n 1227, accuracy 0.48, base_rate_accuracy 0.494, t_vs_base -0.742, brier_skill -0.013, t_brier -2.55 | fail |
| `direction:timesfm25` | n 1227, accuracy 0.478, base_rate_accuracy 0.492, t_vs_base -0.68, brier_skill -0.009, t_brier -1.913 | n 1227, accuracy 0.52, base_rate_accuracy 0.491, t_vs_base 1.439, brier_skill 0.005, t_brier 1.267 | n 1227, accuracy 0.517, base_rate_accuracy 0.494, t_vs_base 1.075, brier_skill 0.001, t_brier 0.318 | fail |
| `ret7:timesfm3` | n 1227, oos_r2 -0.012, dm_t_vs_zero -1.273 | n 1221, oos_r2 -0.005, dm_t_vs_zero -0.871 | n 1227, oos_r2 -0.011, dm_t_vs_zero -1.152 | fail |
| `ret7:timesfm3_cov` | n 1227, oos_r2 -0.04, dm_t_vs_zero -2.611 | n 1221, oos_r2 -0.028, dm_t_vs_zero -3.374 | n 1227, oos_r2 -0.042, dm_t_vs_zero -2.763 | fail |
| `ret7:timesfm25` | n 1227, oos_r2 -0.01, dm_t_vs_zero -0.599 | n 1221, oos_r2 0.003, dm_t_vs_zero 0.253 | n 1227, oos_r2 -0.014, dm_t_vs_zero -0.89 | fail |
| `logrv:timesfm3` | n 1227, qlike_model 0.439, qlike_dvol 0.473, qlike_garch 0.525, dm_t_vs_dvol 0.789, dm_t_vs_garch 1.906 | n 1227, qlike_model 0.664, qlike_dvol 0.473, qlike_garch 0.525, dm_t_vs_dvol -4.248, dm_t_vs_garch -2.775 | n 1227, qlike_model 0.769, qlike_dvol 0.475, qlike_garch 0.528, dm_t_vs_dvol -5.305, dm_t_vs_garch -4.15 | fail |
| `logrv:timesfm3_cov` | n 1227, qlike_model 0.479, qlike_dvol 0.473, qlike_garch 0.525, dm_t_vs_dvol -0.148, dm_t_vs_garch 1.037 | n 1227, qlike_model 0.651, qlike_dvol 0.473, qlike_garch 0.525, dm_t_vs_dvol -4.117, dm_t_vs_garch -2.603 | n 1227, qlike_model 0.798, qlike_dvol 0.475, qlike_garch 0.528, dm_t_vs_dvol -5.416, dm_t_vs_garch -4.334 | fail |
| `logrv:timesfm25` | n 1227, qlike_model 0.448, qlike_dvol 0.473, qlike_garch 0.525, dm_t_vs_dvol 0.54, dm_t_vs_garch 1.609 | n 1227, qlike_model 0.668, qlike_dvol 0.473, qlike_garch 0.525, dm_t_vs_dvol -4.202, dm_t_vs_garch -2.772 | n 1227, qlike_model 0.777, qlike_dvol 0.475, qlike_garch 0.528, dm_t_vs_dvol -5.624, dm_t_vs_garch -4.391 | fail |

Money test (`timesfm25` pairs above their bar only): {"direction:timesfm3": {"skipped": "research-only licence: a pass is a finding, not a trade"}, "direction:timesfm3_cov": {"skipped": "research-only licence: a pass is a finding, not a trade"}, "direction:timesfm25": {"skipped": "below its statistical bar"}, "ret7:timesfm3": {"skipped": "research-only licence: a pass is a finding, not a trade"}, "ret7:timesfm3_cov": {"skipped": "research-only licence: a pass is a finding, not a trade"}, "ret7:timesfm25": {"skipped": "below its statistical bar"}}

Gates: {"n_trials": 9, "money_tested": []}

Verdict: {"statistical_passes": [], "research_findings_no_money_test": [], "money_passes": [], "covariates_beat_univariate": {"direction": false, "ret7": false, "logrv": false}, "PASS": false}
