# Response to the independent review of brief 22 (Codex, 17 September 2026)

*Written the same day on Claude Fable 5.1, the model this repo uses for gate
mathematics. Every claim below was re-derived here from the code and the
lake, not taken from the review; the review's own scripts were read but
not run. Numbers from this session are marked; the review's are quoted as
its.*

## Verdict on the review

**Correct on every code claim it makes, and the right next step.** All
seven accounting findings reproduce by inspection or by a test written here;
the StepM diagnosis is exact (arch 8.0.0's loop tests the latest round's
removals against the model count rather than the cumulative set); the
external-gate exposure proxy was indeed 1.0 for every backtest. Two points
of scale the review leaves open are measured below, and one of its
corrections moves a Programme 2 number materially (E5's gate 5).

## What was fixed today, with tests

| Review § | Change | Test |
|---|---|---|
| 1.1 | `Panel.price_valid()` split from `tradable()`; the runner now judges *entry* on the decision bar's tradability (`tradable().shift(lag)`) and *holding* on the bar's price validity only. A corrupt volume field no longer erases a held position's return. A bar with no valid price still liquidates at the last close — kept as a stated convention, not a claim. | `test_a_corrupt_volume_field_on_a_crash_bar_does_not_erase_the_loss_on_a_held_position`, `test_a_new_position_is_refused_when_the_decision_bar_was_not_tradable`; `test_a_strategy_cannot_hold_an_impossible_bar` rewritten |
| 1.4 | `Strategy.round_trip_each_bar` (set on `AuctionFade`): the overnight unit's turnover is entry plus exit on the same bar; consecutive nights are consecutive round trips. | `test_three_consecutive_overnight_signals_are_three_round_trips`; the auction test's turnover expectations corrected |
| 1.6 | `session_split_frames`: the decision reads only minutes stamped *before* 15:30 (Databento stamps the interval start); the session close is the 16:00 auction print (the 16:00 bar's open). | `test_the_decision_reads_only_minutes_completed_by_the_decision_time`; fixture aligned |
| 2 | StepM computed in `qr/validate/spa.py::_stepm` with the cumulative stop; SPA no longer dies with StepM. | `test_stepm_survives_every_model_being_removed_over_successive_rounds` |
| Q5 | `scripts/external_gates.py` reads holdings-based exposure (LEAN's *Exposure* chart, `Equity - Long Ratio`, read for all 20 backtests into `mirror/quantconnect/exposure.json`) and now runs gate 7 (the engine's CPCV + walk-forward) on the variant matrix. | re-scored below (`--no-log`) |
| §4 | Seq 536 and 537 (E5 re-scorings of the same eight backtests) voided by notes 649–650 with the reason and `unique_configurations: 8`; trial count 2,071 → **2,055**; E5 counts 8. | `qr trial verify` |
| 1.3 | `carry.py`'s "exactly" corrected: the ratio return is second-order; measured on 409,715 daily unit-bars: mean +0.13 bps a bar in the ratio's favour, 99th percentile gap 5 bps, exact-pair daily vol 142 bps vs the ratio's 133 (Sharpe read off the ratio ~7% high). | docstring; the per-leg ledger is §"Not done" |
| 1.7 | Split rule checked against the lake: the 40% threshold fired on **zero** nights in the 31-name auction panel, so it is latent, not active. Left as is, documented. | — |

Full suite after the changes: run in this session (count not written down, per CLAUDE.md).

## What the corrections do to Programme 2's numbers (re-scored, not re-run)

Holdings-based exposure of the best variant: E5 0.75 (was assumed 1.00),
E4 0.91, E7 **0.32**. Gates 2–5 and 7 re-scored on the saved equity curves:

| Family | SPA p vs exposure-matched benchmark | best excess /yr | gate 7 (CPCV) | verdict |
|---|---|---|---|---|
| E5 | 0.19 → **0.066** (WARN band, ≤ 0.05 passes) | −1.9% → **+8.7%** | median path = IS 0.69, WFE 0.54 | **still FAIL**: pre-registered falsifier "alpha t below 2 against the market factor" (t 1.31, beta 1.05) and "family − control not distinguishable" (t 1.77) stand; the SPA falsifier (p > 0.5) never fired either way |
| E4 | 0.76 → 0.74 | −0.1% → +0.7% | WFE 0.84 | FAIL, unchanged (t 1.37, DSR 0.76) |
| E7 | 0.88 → **0.52** | −5.7% → +2.6% | WFE 0.56 | FAIL, gate 5 now marginal (falsifier p > 0.5 fires at 0.52); gates 3, 4 and the random-control alpha t 2.49 unchanged |

Note on gate 7 externally: with one variant dominating every split, the
stitched CPCV path *is* the full series, so "median path = in-sample, 100%
positive" is a degenerate reading, the same the engine gives; WFE is the
informative number.

The engine changes above (1.1, 1.4, 1.6) were not re-run on the closed
families. Direction, from the mechanics: E1's costs were *under*-charged
(consecutive nights), so its gate-2 FAIL strengthens; E2's decision had a
one-minute look-ahead in its favour, so its gate-2 FAIL strengthens; C1/C5/C2
are touched only by the 24 VWAP bars and the negative-volume bars (30 bars in
~1.05M), immaterial. A re-run of the frozen grids is the review's step 8 and
is the owner's call, since every run counts.

## Not done, and why

- **The authoritative position/cash ledger (1.2, 1.3, 1.5)** — the review's
  first ticket. **Built on 18 September** (`qr/research/ledger.py`,
  `docs/26`, `docs/20` entry of that date): quantities, cash and NAV with
  weights derived; per-leg fills, fees and funding for the carry and
  cross-venue units; whole shares at the real fill price with a persistent
  count; cash interest at the risk-free rate; `run_backtest(engine="ledger")`
  and `qr gates --engine ledger`, the engine recorded in the trial log and
  the report. Acceptance tests from a hand ledger, and the identity with
  the weight runner at zero cost to 1e-9. Not yet done: the frozen-grid
  re-run (step 8 below) — the chain is written, every run counts, and it
  waits for the owner. The 7% C1 estimate above was of the ratio's
  second-order error only; the ledger also finds the coin's drift the
  ratio hid (turnover 8× on the always-in unit), which the re-run will
  size. It remains the prerequisite for the maker-fill study's stage 1
  and for any re-registration.
- **Q1 (rebalancing premium)** — as the review says, unresolved until the
  ledger exists; the 0.35%/yr, t 1.2 figure is reported as "not
  distinguishable from zero", not as a premium.
- **Q3 (Programme 1 re-run)** — three families (`etf_tsmom_v1`,
  `etf_buyhold_v1`, `ls_xsmom_v1`) carried the `hold_between` look-ahead;
  it flattered them and they failed. Re-running them is step 8.
- **Q2, Q4** — accepted as stated: preservation is partial and null-
  dependent (the docstring says so); the Sharpe-8 ceiling stays a trigger,
  not a policy.

## Corrections to the brief

`docs/22` now says: **eleven defects, ten fixed with a test, one (the
per-leg ledger) open and specified**; "expected unchanged verdicts" is an
open question answered per family above, not an assumption.
