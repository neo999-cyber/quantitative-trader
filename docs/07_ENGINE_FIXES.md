# Seven engine defects the real runs exposed, and the sweep for the rest

*Written 12 September 2026, after the four-family run against real Binance data
and before the confirmation re-run.*

The runs against real data produced seven numbers that meant something
other than what they said. None of them changed the verdict — every family
failed gates 3, 4, 5 and 9 independently, and the holdout agreed — which is
precisely why this was the moment to fix them. A threshold moved while a
verdict hangs on it is a threshold nobody can trust again.

## 1. Gate 1 was failing strategies for bars it had already withheld

**Symptom.** All four families reported `stopped_at = 1`, failing on AUDUSDT
and BTTUSDT.

**Cause.** The day before the run, `Panel.tradable()` was taught to exclude
bars whose values cannot be true — Binance's published archive contains five
BTTUSDT bars with negative base volume and one AUDUSDT bar whose high sits
below its own close, six bad prints in roughly 740,000, with verifying
checksums, so the corruption is upstream of this loader. No strategy could read
those bars. Gate 1 nonetheless ran `check_klines` over each symbol's *full*
history, found the same six bars, and failed the strategy for them. The
platform was blaming a strategy for data it had itself refused to serve.

**Fix.** `QAReport.excluding(bars)` re-scores a report over the bars that were
actually available, removing excluded timestamps from every check's offender
list; gate 1 passes it the untradable bars from the panel it ran on. A check
that had offenders and has none left passes. Three things deliberately do not
change:

- a check that failed with *no* offenders — `timezone_utc`, `non_empty` — keeps
  its verdict, because emptiness is not an excuse there;
- `calendar_gaps` reports timestamps absent from the frame altogether, so they
  cannot be in the excluded set and the warning survives: a hole in a listing
  window is a fact about the data whether or not anyone traded through it;
- a defect on a bar the panel *did* let through still blocks. There is a test
  for each.

The raw count is still reported as `qa_failures_on_raw_bars`, so the corruption
does not vanish from the record — it stops being attributed to the strategy.

## 2. Capacity: the square-root law charged for the spread twice

**Symptom.** `tsmom_v1` reported a capacity of **$10,000** against a top-30
universe whose pairs turn over nine figures a day. `xsmom_v1` reported
$1,000,000 for the same universe.

**Cause.** Not a units error and not an inconsistency — the ordering was right,
and it tracks turnover, which differs 7x between those two families. The level
was wrong for all of them. Impact was `coef · σ · √(Q/V)` with no lower bound
on participation. The √-law is an empirical fit to *metaorders* over
participations of roughly 0.1% to 10% of daily volume, and its defining feature
is concavity, so extrapolating it towards zero makes the marginal cost of the
first dollar traded unbounded. At a participation of 1e-5 it still charges
about 2 bps on a 5%/day coin — for an order a thousand times smaller than the
top of book. That is not impact. That is the spread, and `linear_bps` had
already charged it.

**How much of the symptom this explains, measured afterwards: about one ladder
rung.** The confirmation run moved `tsmom_v1` from $10,000 to $30,000 and moved
`xsmom_v1` and `reversal_v1` not at all. The double-count was real and removing
it is right, but the level is governed by `impact_coef`, not by this. The
sentence that used to stand here said the double-count *was* what made the
figure read $10,000; that was an attribution made from the shape of the bug
rather than from a measurement, and the measurement did not support it.

**Fix.** Net the half-spread off the law:

```
impact(p) = max(0, coef · σ · √p − half_spread)
```

Zero for any order small enough to sit inside the quoted spread, continuous and
monotone through the point where it switches on, and asymptotically the √-law
itself once the term matters. It introduces **no new parameter** —
`half_spread_bps` is already named, sourced and used — and it can only ever
lower the charge, so no gate is made easier to pass than the unmodified model
would have it. The maker path keeps the full law, because a maker order did not
pay the spread to begin with.

**What this does not fix**, and the reason capacity is now reported as a band
rather than a number: `impact_coef` is 1.0 because that is the round number the
literature clusters around, not because anything here was fitted to a fill —
this account has never sent an order. `_capacity` now reports the figure at the
assumed coefficient, at twice it and at half it, together with
`capacity_extrapolated`, which says whether the book ever reaches the
participations the law was fitted over. At this account's size it does not, and
the honest reading of the whole figure is then "impact is not the binding
constraint at any size this account will trade", not a dollar amount.

## 3. Gate 6's null is not neutral about volatility targeting

**Symptom.** `tsmom_v1` scored p = 1.000 at the **0th percentile**: every one
of a hundred permuted worlds beat the real one.

**Cause.** Masters' bar permutation destroys serial dependence in the
*direction* of returns, which is what a trend strategy claims. It also destroys
**volatility clustering**, which is not what the strategy claims but is
something a vol-targeted strategy interacts with — scaling down in high-volatility
periods raises a Sharpe ratio with no directional skill whatever, and that
premium needs clustering to exist. All three real families are vol-targeted.
The observed statistic therefore contains a premium that the null has been
stripped of, and "this family has no timing edge" and "vol targeting behaves
differently without clustering" are added together in one number.

**Fix.** A second null decomposes each symbol's returns as
`r_t = μ + σ_t · z_t`, permutes only the standardised residual `z`, and leaves
`μ` and the entire `σ_t` path where they were. It keeps the real volatility
path bar for bar, keeps the unconditional mean in expectation and keeps
cross-sectional correlation, while still destroying any information in the
ordering of direction.

**What the two nulls actually do, measured rather than argued.** Six synthetic
worlds with genuine GARCH clustering and no planted timing edge, vol-targeted
TSMOM, 60 re-optimised permutations each:

| seed | plain p | volatility-preserved p |
|---|---|---|
| 1 | 0.180 | 0.377 |
| 5 | 0.049 | 0.131 |
| 9 | 0.525 | 0.344 |
| 13 | 0.311 | 0.770 |
| 21 | 0.115 | 0.049 |
| 30 | 0.672 | 0.393 |

The p-value moves by about 0.2 on average and **the sign of the move is not
systematic** — preserving volatility raised the null in three of the six and
lowered it in the other three. That is worth stating plainly because it
contradicts two things in turn: the original guess that the plain null was
*advantaged* by losing clustering, and then the opposite guess, made after the
first four seeds came back, that it was systematically disadvantaged. Neither
survived being measured properly. Six seeds is not a proof of no effect either;
what it supports is only the weaker and more useful claim.

**The claim that survives.** Gate 6's p-value for a vol-targeted strategy is
sensitive, by roughly 0.2, to a modelling choice about the null that forms no
part of what the strategy claims. Seed 5 crosses from 0.049 to 0.131 — from
PASS to FAIL — on nothing but that choice. The gap between gate 6's pass band
(0.05) and its fail band (0.10) is smaller than the sensitivity, so for these
families the gate's verdict is fragile in a way its single reported number does
not show. That is the argument for reporting both, and it does not depend on
knowing which direction the bias runs.

It also settles what this does to the trial: nothing. A shift of 0.2 does not
move a p of 1.000, and `tsmom_v1`'s 0th percentile survives either null intact.

**What was deliberately not changed.** The plain Masters null **remains the
binding one**. It is what the four pre-registrations name, and swapping a
decision rule for a better-posed one *after seeing the answer* is the exact
move pre-registration exists to prevent — the quality of the reasoning is not
the point, because if a good argument were sufficient the rule would never bind
at all. The second null is reported as evidence and is there to be
pre-registered by whatever runs next. Run it with `--vol-permutations`; `0`
skips it and halves gate 6's cost.

Three caveats stated rather than discovered later: the unconditional mean is
preserved in expectation rather than exactly, because a leverage effect means a
given draw can land either side of it; the intrabar shape still travels with
its source bar rather than being rescaled to its destination's volatility,
which matters for a strategy reading highs and lows and not for one reading
closes; and each permuted return is clipped to the symbol's own observed range,
because a large residual landing on a high-volatility bar can otherwise fall
below −100% and make the rebuilt price negative.

## 4. Walk-forward efficiency divided by a number passing through zero

**Symptom.** `reversal_v1` reported WFE **13.62** — a strategy thirteen times
better out of sample than in sample.

**Cause.** WFE was the ratio of the *pooled means*: mean out-of-sample
annualised return over mean in-sample annualised return, across six anchored
windows. When the in-sample returns nearly cancel across windows, the
denominator passes through zero and the ratio becomes a number of arbitrary
magnitude and sign. 13.62 was not a finding about `reversal_v1`; it was a
division.

**Fix.** WFE is now the **median of the per-window ratios**. Each window brings
its own denominator, so cancellation across windows cannot happen, and the
median ignores the one window that blew up unless most of them did. Windows
whose in-sample return is not positive are dropped rather than counted as zero
— "how much of the edge survived" is not a question about a window that had no
edge — and `wfe_windows` records how many were left. The pooled figure is still
reported as `wfe_pooled` so the two can be compared, and the per-window ratios
are a column on the returned frame.

## 5. The lag-spike statistic was a ratio of noise to noise

**Symptom.** After fix 1 unblocked gate 1, `rsi_reversal_v1` warned that its
Sharpe *"peaks at the reported lag, 5.88x its neighbours"* — the signature of a
look-ahead, on the one family pre-registered as having no edge. I read it as
possible evidence of a leak in `RSIReversal`.

**`RSIReversal` is clean.** Its indicators are causal at a read — `close.diff()`,
`rolling().sum()`, `volume.shift(1).rolling()` — and the decisive test is
behavioural rather than textual: a look-ahead earns a Sharpe in data with
nothing in it. Over synthetic worlds with no edge planted, `RSIReversal` scores
lag-1 gross Sharpes of +0.41, +0.17 and +0.06. A planted oracle in the same
harness scores far outside that range. There is nothing to find.

**The statistic was the problem.** `spike_ratio` is
`S(1) / max(S(0), S(2))` — a ratio whose denominator is a Sharpe, and a Sharpe
passes through zero. Over the same worlds:

| world | lag-1 Sharpe | neighbours | `spike_ratio` | `spike_z` |
|---|---|---|---|---|
| no edge, seed 0 | +0.41 | +0.42 | 0.98 | −0.0 |
| no edge, seed 1 | +0.17 | +0.08 | 2.07 | +0.2 |
| no edge, seed 2 | +0.06 | −0.22 | **inf** | +0.7 |
| planted bounce, seed 1 | +0.19 | +0.34 | **0.55** | −0.4 |
| planted bounce, seed 2 | +0.25 | +0.03 | **9.92** | +0.5 |

The ratio ranges from 0.55 to infinity across worlds that are qualitatively the
same, and it ranks a world with a *genuine* one-bar edge below one with none.

**Fix.** Stop dividing. What the test asks is whether lag 1 stands above its
neighbours by more than estimation noise, which is a difference in standard
errors:

```
spike_z = (S(1) − max(S(0), S(2))) / sqrt(periods_per_year / n_bars)
```

The denominator is one standard error of an annualised Sharpe of zero over the
sample, so it is never near zero. Gate 1 now warns on `spike_z` above 3 and
`spike_ratio` is kept only as a reported number. Across all six worlds above
`z` stays within ±0.7 — correctly "no spike" — while a planted oracle scores
|z| > 40.

**A first attempt at this was wrong and is worth recording.** I initially kept
the ratio and refused to report it when the *denominator* fell below the noise
floor. That silences the true positive: an oracle's neighbours genuinely do
collapse to nothing, so the case the statistic exists to catch is exactly the
case that has no denominator. The existing `Oracle` test caught it immediately.
A ratio cannot be repaired by guarding it, because it conflates "large
numerator" with "small denominator", and only one of those is the signal.

**This is the second ratio-over-zero in the engine, after walk-forward
efficiency (§4).** Finding the first should have prompted a search for the rest.
It did not, and this one was found only by investigating the strategy it had
wrongly accused.

## 6. Every backtest computed over 734 columns to hold thirty

**Symptom.** Runs took hours. Gate 6 re-optimises 25 variants over 100 permuted
panels, and each of those 2,500 backtests ran over every symbol in the lake.

**Cause.** `load_panel` returns all 734 pairs. The universe admits at most
thirty on any day and 161 over the whole sample; the rest are masked to zero
before anything is summed, so they cost time and contribute nothing.

**Fix.** Restrict the panel to symbols the universe ever admits, after
membership has been decided on the full panel — the ranking has to see
everything that existed on the day, and only what it never chose can be
dropped. Measured on a 734-symbol, 7-year panel: **275 ms → 61 ms per
backtest, 4.5x**, with the net return series **bit-identical** (`max |diff| =
0.000e+00`). Gate 6 falls from about 12 minutes to 3 per family.

One thing it genuinely changes, stated rather than buried: gate 1's
shuffled-ticker placebo reassigns each bar's weights to different columns, so a
smaller column set is a different null. The restricted one is better posed —
that placebo asks whether the strategy picked the right names *among those it
could have held*, and scattering weights onto delisted microcaps it was never
eligible to buy makes the null easier to beat for reasons that have nothing to
do with the strategy. It is a change to a gate's null all the same, which is
why it is a documented default with `--no-restrict-universe` to turn it off,
rather than a silent optimisation.

## 7. The sweep: every other ratio in the engine

Two of the six defects above were the same defect — a ratio dividing by a
quantity that passes through zero — found a day apart, each only after it had
produced a number somebody acted on. That is a bad way to find the third one,
so every division in `qr/` was read.

**Nine were already correct.** `net_over_gross`, `neighbourhood_retention`,
minimum track record length, minimum backtest length, the information ratio,
weight drift, CSCV's logit, CPCV's median-over-in-sample and gate 9's holdout
ratio all guard their denominator. Two of those deserve credit for getting it
right in a way the broken pair did not: CSCV clips `omega` away from both ends
before taking a logit, and `drift` replaces a zero portfolio return with `nan`
rather than dividing by it.

**But `denominator > 0` is not the guard it looks like.** A gross annual return
of 0.1% is positive, clears the check, and still turns the ratio into a number
with no information in it — which gate 2 then compares against a 60% threshold
and can **pass**. The same is true of gate 8's parameter plateau: a peak Sharpe
of 0.02 beside a neighbour at 0.03 is a "retention" of 150%, which reads as a
comfortable plateau and is a flat field of noise. Neither bit during the trial,
because both families had healthy gross returns and peak Sharpes near 0.75 —
they were latent, not harmless.

Both now require their denominator to clear **one standard error of a Sharpe
over the sample**, `sqrt(periods_per_year / n_obs)`, which is now a named
function (`stats.sharpe_standard_error`) rather than three copies of the same
reasoning. It is the same floor the lag-spike test uses.

**A `nan` must never read as a pass.** Gate 2 already had this right — it fails
with "gross return is not positive; there is nothing to survive". Gate 8 did
not: `if np.isfinite(median) and median < threshold` skips a non-measurable
plateau in silence, and a check nobody is told about is indistinguishable from
one that passed. It now says so. Relatedly, gate 8 was discarding *all* its
warnings whenever it failed for some other reason, so a "could not measure
this" could be hidden behind an unrelated failure; warnings now ride along with
the FAIL.

**One ratio is genuinely hard and was left strict.** The two-engine cross-check
measures pointwise relative error against the share ledger's equity, which a
ruinous strategy drives towards zero. Normalising by the curve's peak instead
would remove the zero — and would also hide a ledger that disagrees by half at
low equity, which is a real bug. So the pointwise measure still decides, and
`scale_relative_error` is reported beside it: a large pointwise error with a
tiny scale-relative one means the account is nearly empty, not that the engines
disagree.

## What was checked afterwards

`pytest -q` — 414 tests, including 37 new ones written against these
defects specifically. The regression tests are the useful part of this: each one
reproduces the original defect with the fix switched off, which is how we know
the fix is the fix and not a coincidence.

The engine's synthetic self-test still holds, which is the property that matters
most: noise searched over 200 variants is still rejected at gates 4 and 5, and
the planted edge still survives all nine. A "fix" that made the engine kinder
would have shown up there.

The confirmation run against real data is in `docs/06_TRIAL_VERDICT.md`,
together with a prediction of what it will say, recorded before it runs.
