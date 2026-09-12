# Four engine defects the first real run exposed

*Written 12 September 2026, after the four-family run against real Binance data
and before the confirmation re-run.*

The first run against real data produced four numbers that meant something
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

## What was checked afterwards

`pytest -q` — 401 tests, including 24 new ones written against these four
defects specifically. The regression tests are the useful part of this: each one
reproduces the original defect with the fix switched off, which is how we know
the fix is the fix and not a coincidence.

The engine's synthetic self-test still holds, which is the property that matters
most: noise searched over 200 variants is still rejected at gates 4 and 5, and
the planted edge still survives all nine. A "fix" that made the engine kinder
would have shown up there.

The confirmation run against real data is in `docs/06_TRIAL_VERDICT.md`,
together with a prediction of what it will say, recorded before it runs.
