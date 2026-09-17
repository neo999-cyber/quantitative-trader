# Independent review brief — Programme 2 engine changes, 15–16 September 2026

*For a fresh session on a model that did not write the code (Codex, or Claude
Opus 5 if unavailable), per `docs/20` "Sessions and models" and the `docs/16`
pattern: the reviewer gets observations and questions, not the engine's
formulas, and reports what the numbers say before reading the code.*

## What to review

Ten defects were found by the first Programme 2 runs and fixed the same day,
each with a test; the independent review of 17 September 2026 (`docs/25`)
added four more (held-position masking, overnight round trips, intraday
minute stamps, the StepM stop) — fixed with tests the same day — and one
open: the per-leg position/cash ledger. "Verdicts unchanged" is an open
question, answered per family in `docs/25`, not an assumption. The reviewer's job is (a) to confirm each fix from its
test and a hand computation, (b) to say whether any fix could have moved a
Programme 1 verdict, and (c) to look for what the fixes missed.

| # | Where | What was wrong | Test |
|---|---|---|---|
| 1 | `qr/data/carry.py` | carry unit's high/low equalled its close while its open did not → `Panel.tradable()` rejected nearly every bar | `test_a_unit_whose_open_differs_from_its_close_is_still_a_tradable_bar` |
| 2 | `qr/data/carry.py` | unit `volume` was the thinner leg's coin count, so quote ≠ volume × price → gate 1 QA failed every unit | `test_a_units_volume_is_its_quote_volume_in_its_own_price_space` |
| 3 | `qr/validate/permutation.py` | permuted panels dropped every field outside OHLC/volume (funding gone) | `test_a_permuted_carry_panel_keeps_its_funding_with_the_bars` |
| 4 | `qr/validate/permutation.py` | global permutation filtered to each symbol's live window destroyed cross-symbol correlation on staggered listings (0.63 → 0.03) | `test_a_permuted_panel_keeps_cross_symbol_correlation_across_staggered_listings` |
| 5 | `qr/strategies/base.py`, `qr/research/runner.py` | scheduled books grown by the bar they were held *over* (one-bar look-ahead, ~½σ² a bar); the reference loop in the tests had the same defect | `test_the_drifted_book_is_grown_by_the_bars_it_was_held_through_not_the_one_it_is_held_over` |
| 6 | `qr/strategies/carry.py` | when fewer than `n_max` units qualified, the NaN tail of `sort_values` filled the book with alphabetically-first non-qualifying units | `test_a_bar_with_fewer_qualifying_units_than_room_holds_only_those_units` |
| 7 | `qr/cli.py` | `--param` silently dropped whenever `--grid` was present | `test_fixed_params_apply_to_every_grid_variant_and_a_clash_is_refused` |
| 8 | `qr/data/imbalance.py` | Databento side code `A` (ask = sell imbalance) mapped as `S`; every sell imbalance read as zero | `test_databento_side_codes_are_bid_buy_and_ask_sell` |
| 10 | `qr/data/panel.py`, `qr/validate/permutation.py` (17 Sep) | 24 perp bars (19 pairs, five dates in 2023) with quote volume ~1.5× the bar's range: QA flagged them, `Panel.tradable()` served them, gate 1 failed the C5 book for bars it had read. Now withheld (VWAP outside [low·0.95, high·1.05]); permuted panels carry quote volume as a ratio to close | `test_a_bar_whose_quote_volume_implies_a_vwap_outside_its_range_is_not_tradable` |
| 9 | `qr/validate/spa.py` (closed 17 Sep) | SPA raised "zero-size array to reduction operation maximum" on the C1 v2 hourly run: arch 8.0.0's `StepM.compute` stops on the latest round's count, not the cumulative survivors, and re-runs SPA on an empty selection when every model leaves over successive rounds. StepM is now computed in-house with the cumulative stop | `test_stepm_survives_every_model_being_removed_over_successive_rounds` |

Also new and worth a second pair of eyes: `benchmark=exposure`
(`qr/validate/spa.py::exposure_benchmark`), `CostModel.alpaca_zero` and the
runner's whole-share flooring (`runner.whole_share_weights`), the
two-bars-a-session instrument (`qr/data/intraday.py`), the overnight
instrument (`qr/data/auction.py`), the external-results gate script
(`scripts/external_gates.py`), and the `void_seq` note in the trial count.

## Questions, in order

1. Defect 5: on a synthetic panel of iid returns with a weekly-rebalanced
   half-invested book, what is the gap between weekly and daily rebalancing
   before and after the fix? (Observed: 4.8%/yr with t = 15 before; 0.35%/yr
   with t = 1.2 after.) Is the residual the rebalancing premium?
2. Defect 4: after the fix, what share of a late-listed symbol's bars keep
   their cross-sectional alignment, and is that the honest ceiling?
3. Programme 1: which of the nine families used `rebalance_on` (monthly or
   weekly books), and by how much did defect 5 flatter their gross Sharpe?
   None passed; does any verdict move? (Expected: no.)
4. C1 v1's gate-1 ceiling (gross Sharpe 9.7 on daily closes, 3.6 on hourly
   bars): is the 8.0 plausibility test the right instrument for a unit
   whose price barely moves, or should the ceiling scale with the unit's
   realised volatility?
5. E5's external gates: with the runner unavailable, are gates 2–5 and 7
   computed from series alone comparable to the engine's own, and what
   does the missing gate 1 (lag probe) cost in confidence?
6. What would you test next that the nine tests do not?

## Raw observations to hand over

`~/qr/lake/reports/*.json` and `*_variant_returns.parquet` for
`p2_funding_carry_v1`, `p2_funding_carry_v2`, `p2_auction_imbalance_v1`,
`p2_late_day_momentum_v1`, `p2_insider_cluster_v1_external`; the trial log
(`qr trial verify`); `docs/20` week log; the tests named above.
