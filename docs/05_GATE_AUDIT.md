# Day 6–7: auditing the engine against its own specification

Built on branch `claude/admiring-ptolemy-tfp528`.

Day 6–7 in the plan is "read the four Hypothesis Reports, fix what they expose". The reports from Day 4–5 are on synthetic data, and tuning an engine against a random-number generator is exactly the failure this project exists to prevent. So the day was spent on the one thing that *is* legitimate without real data: checking the implementation against the specification in `PLAN.md` §4, line by line, and closing the gaps.

The trigger was three thresholds in `GateThresholds` that nothing read.

## The audit

| Gate | Specified | Was implemented | Now |
|---|---|---|---|
| 0 | Pre-registration, trial count increments | ✅ | ✅ |
| 1 | Leakage switch | ✅ | ✅ |
| 1 | **Shuffled-ticker placebo** | ❌ | ✅ added |
| 2 | Gross vs net, 2× stress | ✅ | ✅ |
| 2 | **Capacity at intended size** | ❌ | ✅ added |
| 3 | HAC t, PSR, bootstrap CI, MinTRL | ✅ | ✅ |
| 4 | DSR, Harvey–Liu haircut, MinBTL | ✅ | ✅ |
| 4 | **Effective trial count from clustering** | ❌ | ⚠️ measured, deliberately *not* used — see below |
| 5 | CSCV PBO, IS/OOS degradation | ✅ | ✅ |
| 5 | **Hansen SPA, Romano–Wolf StepM** | ❌ | ✅ added |
| 6 | Bar permutation **with re-optimisation** | ⚠️ no re-optimisation | ✅ fixed |
| 6 | Signal shuffle, random-entry percentile | ⚠️ written, partly unwired | ✅ wired |
| 7 | CPCV distribution, walk-forward efficiency | ✅ | ✅ |
| 8 | Neighbourhood, parameters, trades, per-year | ✅ | ✅ |
| 8 | **Per-regime Sharpe** | ❌ | ✅ added |
| 8 | Drop best 5 **trades** | ⚠️ dropped best 5 *bars* | ✅ fixed |
| 9 | Holdout, opened once | ✅ | ✅ |

Three configured thresholds (`max_spa_p`, `max_permutation_p`, `fail_permutation_p`) were read by nothing at all. Gate 6 used the hard-coded defaults inside `PermutationResult.verdict`, so changing the configured value would have had no effect — the kind of bug that makes an engine look more thorough than it is.

## The two biggest fixes

**Gate 6 was not re-optimising.** Masters' test re-runs the *whole search* on each permuted dataset and keeps its best, which asks "is my procedure better than chance". Re-running only the already-chosen variant asks the much weaker "is this variant better than chance", and a strategy that only looks good because 200 variants were tried passes it comfortably. On the noise world the difference is stark:

| | p-value on searched-over noise |
|---|---|
| Before (chosen variant only) | 0.059 — a WARN |
| After (re-optimised over the grid) | **0.782** — an emphatic FAIL |

Because re-optimising over the full grid costs variants × permutations backtests, the search is re-run over an evenly spread subgrid (25 variants by default) and the report states how many. The direction of that approximation is stated too: a subgrid null is weaker than the full-grid null and stronger than none, so the p-value is optimistic relative to a complete Masters test and conservative relative to the naive one.

**SPA was specified and missing.** CSCV asks whether *selecting* the winner tells you anything; SPA asks whether the winner beats buy-and-hold at all once the search is paid for. A family whose variants all merely track the market has a low PBO — the same variant does win every time — and nothing worth trading. Only SPA says so.

Implementing it immediately reproduced the exact mistake this codebase keeps warning about: **arch states SPA in terms of losses, where lower is better.** Passing returns inverted the test, which then reported p ≈ 0.75 for a strategy with a large real edge. Caught by checking it against a planted case before trusting it, which is the only reason it was caught at all.

## Two calibration errors the self-test caught

Both changes were made in good faith, both were wrong, and `qr selftest` failed on both.

**The effective trial count gutted gate 4.** `PLAN.md` §4 asks for deflation against an effective count from clustering, and the estimator works — 200 TSMOM variants have an effective rank near 5, because their return series correlate above 0.95. But feeding that to the Deflated Sharpe **double-discounts the correlation**: E[max] = √V · f(N) already shrinks through **V**, the variance of the trial Sharpes, which is small precisely when the variants are redundant. Discounting N as well let the searched-over noise world sail through gate 4.

So the effective count is now measured, reported, and deliberately not used for deflation. It stays in the report as the diagnostic it should have been: a large gap between raw and effective says the grid is finer than the search.

**SPA's failure band was too tight.** SPA's consistent p-value is conservative when the models are many and correlated, which 200 variants of one family certainly are. On the self-test worlds, a planted edge that genuinely beats buy-and-hold by 15 percentage points a year scores **0.27**, while searched-over noise scores **0.999**. Failing at 0.05 would reject almost everything real. The band is now PASS below 0.05, FAIL above 0.50 — above one half the benchmark beats the best of the search more often than not — and WARN between.

## A finding about the synthetic worlds

The shuffled-ticker placebo revealed something worth stating before anyone reads a cross-sectional result on the test data: **`edge_world` has a time-series edge and no cross-sectional one.** Every symbol gets the same kind of independent AR(1) drift, so a momentum ranker there is choosing between statistically identical coins and its choices carry nothing. The placebo says so correctly.

A related honest result: even in a world where two of twelve symbols carry a genuine 65%-a-year drift, a 90-day momentum ranker picks them only a little more often than chance, because at crypto volatility a 90-day trailing return is mostly noise. That is a limitation of the strategy, not of the test, and it is the sort of thing worth knowing before running `xsmom_v1` on real data and being disappointed.

## Current state

`qr selftest` passes: noise fails gates 3, 4, 5, 6, 7 and 8 with the deflation gates among them; the planted edge passes everything with one WARN at gate 5. The run now takes ~140 seconds rather than 20, because SPA and re-optimisation are real work.

## Still the same gap

None of this has met a real price. `qr data pull` on the laptop remains the blocker (`docs/02_DATA_LAYER.md`), and until then the four Hypothesis Reports describe a random-number generator.

## What the real price found (12 September 2026)

That gap is now closed, and closing it found four more defects that synthetic data could not have surfaced — one of them in gate 1, which this audit had just rewired, and one in the capacity estimate this audit had just added. Both looked correct against fixtures and were wrong against 734 real pairs. See `docs/07_ENGINE_FIXES.md`; the verdict they were found under is `docs/06_TRIAL_VERDICT.md`.

The lesson is the same one twice: an audit against a specification catches what the specification says, and a run against real data catches what the world says. They are not substitutes.
