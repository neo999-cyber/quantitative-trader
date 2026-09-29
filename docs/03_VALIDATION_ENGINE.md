# Day 2–3: the validation engine

Built on branch `claude/admiring-ptolemy-tfp528`. 283 tests, all offline, ~90 seconds.

**The self-test passes.** That is the only headline that matters here, and it means: searched-over noise is rejected by the deflation gates, and a realistic planted edge survives all nine.

```
world          expected  actual  failed_gates       deflation_caught_it  in_sample_sharpe
noise          FAIL      FAIL    [3, 4, 5, 7, 8]    True                 1.058
planted_edge   PASS      WARN    []                 False                1.678
```

Run it yourself: `qr selftest` (20 seconds).

## What now exists

| Module | Gate | What it does |
|---|---|---|
| `qr/research/sweep.py` | 4, 5, 7, 8 | The variant matrix, with the trial count written to the log |
| `qr/validate/stats.py` | 3, 4 | HAC t, PSR, MinTRL, stationary-bootstrap CI, DSR, MinBTL, Harvey–Liu haircuts |
| `qr/validate/cscv.py` | 5 | CSCV → Probability of Backtest Overfitting |
| `qr/validate/permutation.py` | 6 | Masters bar permutation, signal shuffle, random-entry percentile |
| `qr/validate/cpcv.py` | 7 | Combinatorial purged CV with embargo; walk-forward efficiency |
| `qr/validate/factors.py` | 8 | Alpha t-stat against BTC — is this an edge or beta wearing a hat |
| `qr/validate/gates.py` | 0–9 | The pipeline, every threshold in one named dataclass |
| `qr/validate/report.py` | — | Hypothesis Report, Markdown + JSON |
| `qr/validate/selftest.py` | — | The two worlds whose answers are known in advance |

Every formula in `stats.py` is written out rather than imported, and then tested twice: once against its published closed form, once against `jsharpe`, `arch` or `statsmodels`. The conventions differ between implementations — per-period versus annualised Sharpe, excess versus raw kurtosis — and a silent mismatch in a deflation formula is exactly how a dead strategy gets through gate 4.

## The workflow

```bash
qr trial prereg tsmom_v1 --file docs/prereg/tsmom_v1.md    # gate 0, before any run
qr gates --family tsmom --grid "lookback=[20,40,60,90,120]" --grid "skip=[0,5]" \
         --n 30 --hypothesis tsmom_v1 --holdout-start 2024-01-01
qr trial note tsmom_v1 "gate 5: variants are interchangeable, not overfit — see PBO detail"
qr trial verify
```

Gate 0 fails without a pre-registration, and registering one *after* a run is recorded and still fails. An unjustified WARN is counted as a FAIL by the report. Neither is negotiable from the CLI, which is the point.

## What the self-test found

It was written to check the engine and immediately found four real problems, three of them in the engine itself rather than the plumbing. Recording them because each is a trap worth not falling into twice.

**1. Gate 1 was testing the wrong thing.** The original leak test flagged any strategy whose lag-0 Sharpe much exceeded its lag-1 Sharpe. But letting a return-based signal act on the bar it is predicting is an enormous and entirely *expected* advantage — an honest TSMOM scores 4–8× — so the test flagged everything, including the planted edge.

The leak that actually matters is a strategy reaching forward inside its own `target_weights`, where the runner's one-bar shift cannot protect against it. That has the opposite signature: the honest shift aligns the peek exactly onto the bar it predicted, so Sharpe **spikes at the reported lag** and collapses on both sides.

| | lag 0 | lag 1 (reported) | lag 2 |
|---|---|---|---|
| Honest TSMOM | 7.97 | 2.04 | 1.77 |
| Forward-looking | 0.52 | **46.16** | 1.24 |

Gate 1 now blocks on an implausible Sharpe at the reported lag and only *warns* on the shape — because a genuine one-day reversal produces the same shape as a leak, and only magnitude separates them. A real daily edge earns Sharpe 1–2; a leak earns 46.

**2. Gate 5 over-rejected.** A high PBO is damning when the variants disagree about whether an edge exists, and merely uninteresting when they are 200 near-identical parameterisations of a real one — there the in-sample "winner" among near-ties is arbitrary by construction, and any of them would have done. The two cases separate on whether the selection actually *loses* out of sample: 25% of the time for noise, 2% for the planted edge. A high PBO whose selections stay profitable is now a WARN reading "your variants are interchangeable", which is true and worth knowing.

**3. The self-test's own criterion was wrong.** Rejecting noise is not enough — gates 4 **and** 5 must both do it. A noise winner often also trips gate 3 on its raw t-statistic, and an engine relying on that would wave through the next noise winner whose t happened to land above 3. A world expected to fail now always runs every gate, so the criterion can see which ones did the work.

**4. The planted edge was worth Sharpe 21.** Every gate waved it through, so it tested nothing: an engine that only recognises unmissable edges would pass that self-test and still reject everything real. Recalibrated to ~1.7 — good but attainable. At that strength its lag-1 autocorrelation is 0.006, *smaller than what the noise world throws up by chance*. A genuine tradable edge being invisible in the obvious statistic is the whole reason this machinery exists.

Also fixed along the way: `RandomEntry` took 2.8 s per backtest against TSMOM's 14 ms and gate 6 runs hundreds of them (self-test 351 s → 20 s); `haircut_sharpe` returned NaN at p = 0 through an inf/inf; the trial log refused to record a SKIP verdict, which is the verdict most easily mistaken for a pass.

## Thresholds

All in `GateThresholds`, deliberately awkward to change in passing — loosening one to get a pass is the easiest way to make this whole apparatus worthless, so a changed threshold is a visible change to a named default with a git blame.

## Still waiting on you

The laptop data pull (`docs/02_DATA_LAYER.md`). Everything above runs on synthetic data in the bucket's exact format; none of it has met a real price.

## Next (Day 4–5)

Four families through all nine gates: TSMOM (vol-targeted), cross-sectional momentum (12-1), weekly reversal, and the existing 3-down-day RSI setup as a control expected to fail. Each gets a pre-registration document and a Hypothesis Report.
