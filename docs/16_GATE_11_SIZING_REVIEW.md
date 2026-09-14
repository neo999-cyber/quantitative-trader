# Gate 11 sizing mathematics: the independent review

*14 September 2026. The review `docs/10_NEXT.md` asked for, run in a
separate session as `CLAUDE.md` requires. Scope: the mathematics in
`qr/portfolio/sizing.py` and the claims in `docs/09_INCUBATION_AND_SIZING.md`.
Nothing was fixed and no repository code was written; the numbers below come
from a throwaway Monte Carlo that is not part of the codebase. Fixes are
listed at the end for a build session.*

## Verdict in one paragraph

The algebra is right and the number is wrong. Every formula in the module is
correctly derived and correctly coded, and the 75% / 42% / 13% / 7.5% table
reproduces to three figures. But the quantity those formulas compute is
**not the probability of ever drawing down more than 25%**. It is the
probability that equity ever falls 25% below its *launch* value. The
peak-to-trough drawdown the code, the docstrings, the policy comments, the
gate 11 verdict text and `docs/09` all name is a different random variable,
and over the infinite horizon the code sizes to, its probability of exceeding
25% is 100% at every leverage. The two headline conclusions in `docs/09`
survive only partly: half Kelly is indeed incompatible with a 10% budget on any
reading, but quarter Kelly is not "not close" to it, the "contradiction" in the
plan is a conjunction the plan always meant, and the sentence tying the 0.2x
result to the $1,000 account is false because the cap that produces it has
no equity term.

## 1. `drawdown_probability()` — right formula, wrong label

The code sets *m* = *f*·SR·σ − ½(*f*σ)² and *s* = *f*σ, then returns
(1 − *D*)^(2*m*/*s*²).

**The derivation of *m* and *s* is correct.** With SR·σ read as the
arithmetic (simple-return) excess drift of the unlevered book, a book at
leverage *f* under continuous rebalancing has log-wealth drift
*f*μ − ½*f*²σ² and log-wealth volatility *f*σ. The Itô correction is
present and has the right sign. One condition attaches to this: the SR
handed in must be computed from simple returns, which is what
`forward.summarise` and the gate 9 holdout do. Had it been computed from
log returns the correction would be applied twice.

**The expression is the classical barrier-crossing probability.** For a
Brownian motion with drift *m* > 0 and volatility *s*, the probability of
*ever* reaching a level *L* below its starting point is exp(−2*mL*/*s*²).
Substituting *L* = −ln(1 − *D*) gives exactly (1 − *D*)^(2*m*/*s*²). This is
correct, it is textbook, and the Monte Carlo below confirms it as the long
horizon limit.

**But "ever reaching a level *L* below the start" is not a drawdown.** A
drawdown is measured from the running peak. For the same process, the
drawdown *Y*<sub>t</sub> = max<sub>u≤t</sub> *X*<sub>u</sub> − *X*<sub>t</sub>
is a Brownian motion with drift −*m* reflected at zero. It is positive
recurrent: it revisits every level infinitely often. So over the infinite
horizon the module names in its own policy comment ("'Ever' rather than
'this year'"), P(ever draw down more than *D*) = 1 for every *D* < 1 and
every leverage with *m* > 0. The constraint "P(ever DD > 25%) ≤ 10%" as
written in `docs/09` and the gate 11 verdict is unsatisfiable, and the code
satisfies it only by silently computing something else.

What the code does compute is meaningful, and has two exact readings, both
worth more than the label it carries:

- **P(the account statement ever shows a 25% loss against the deposit).**
  A drawdown from the peak *at time zero*. This is plausibly the point at
  which an operator abandons a strategy, and it is the quantity the Kelly
  literature's "probability of ever halving" refers to.
- **The long-run fraction of time spent more than 25% below the high-water
  mark.** The stationary distribution of the reflected drawdown process is
  exponential with rate 2*m*/*s*², so P(*Y*<sub>∞</sub> > *L*) is the same
  expression. "At half Kelly you spend 42% of your life more than a quarter
  below your peak" is true, and rather more damning than the mislabelled
  version.

Monte Carlo, 20,000 paths, daily steps, D = 25%, Sharpe 0.8 (the module's
example). Column A is the code's number. Column B is the exact finite-horizon
form of the same quantity (a reflection-principle formula; the MC agreed
with it to within the daily-step barrier bias). Column C is what the label
promises: peak-to-trough maximum drawdown exceeding 25% within the horizon.
Column E is the stationary time-under-water reading.

| Kelly fraction | A: code | B: below launch by 1y / 3y / 10y | C: max drawdown > 25% by 1y / 3y / 10y / 30y | E: time under water |
|---|---|---|---|---|
| full | 75.0% | 61% / 70% / 74% | 100% / 100% / 100% / 100% | 73% |
| ½ | 42.2% | 28% / 38% / 42% | 69% / 98% / 100% / 100% | 40% |
| ¼ | 13.3% | 5% / 11% / 13% | 11% / 41% / 86% / 100% | 13% |
| 0.222 (the coded cap) | 10.0% | 3% / 8% / 10% | 6% / 29% / 74% / 98% | 9% |
| ⅕ | 7.5% | 2% / 6% / 7% | 4% / 20% / 60% / 95% | 7% |

The same table at Sharpe 0.4, closer to what a marginally passing holdout
would deliver, has identical column A (the code's number depends only on the
Kelly fraction) and a slower column C: at ¼ Kelly, max drawdown > 25% within
1 / 3 / 10 years is 0.3% / 7% / 37%. That dependence on Sharpe and horizon
is the point: the peak-to-trough risk of a fractional-Kelly book is not a
single number, and the code's single number is not it.

Two minor points on the function itself. Returning 1.0 for *m* ≤ 0 is
correct (non-positive drift hits every lower level almost surely). The
`min(1.0, …)` guard is unreachable once *m* > 0 and harmless.

## 2. `_drawdown_cap()` — the algebra is right

With *f* = *c*·SR/σ, 2*m*/*s*² = 2*f*μ/(*f*²σ²) − 1 = 2SR/(*f*σ) − 1
= 2/*c* − 1. Verified. The constraint (1 − *D*)^*q* ≤ tol, with both
logarithms negative, gives *q* ≥ ln(tol)/ln(1 − *D*), and inverting for the
largest *f* gives 2SR/(σ(*q*<sub>needed</sub> + 1)). Verified, and the
test that measures the risk at the cap and gets 0.10 back is a genuine
round-trip. For *D* = 25%, tol = 10%:

| | value |
|---|---|
| *q*<sub>needed</sub> | 8.004 |
| drawdown cap, as a Kelly fraction | 0.2221 |
| ratio of drawdown cap to the ¼-Kelly cap | 0.889 |
| Sharpe above which the 15% volatility target binds instead | 0.675 |

Two consequences the author did not draw. First, the drawdown cap is a
constant multiple of full Kelly, so with `kelly_fraction = 0.25` and this
budget **the Kelly cap can never bind**; it is dead code as a constraint,
and the "drawdown constraint is the binding one" sentence in `docs/09` is
true by construction rather than an empirical finding. Second, the
`needed_q + 1 <= 0` branch cannot be reached (tol is clamped below 1, so
*q*<sub>needed</sub> > 0), and `policy.max_drawdown` is never validated:
a value ≥ 1 raises inside `math.log`, a value ≤ 0 divides by zero or
flips the inequality.

## 3. The full-Kelly halving anchor — right result, weak test

"At full Kelly the probability of ever halving is one half" is Thorp's
result, and it is a statement about falling to half the *initial* capital,
not about a 50% drawdown from the peak. So the anchor is consistent with
what the code computes and inconsistent with what the code says it
computes. It cannot catch the mislabelling because it is stated in the
same terms as the formula.

The code reproduces it structurally, not by coincidence: at *c* = 1,
*q* = 2/*c* − 1 = 1 regardless of Sharpe or volatility, so the expression
collapses to 1 − *D* for every *D*. But that is also why the test is weak.
Any expression (1 − *D*)^*g*(*c*) with *g*(1) = 1 passes it, including
*g*(*c*) = (2/*c* − 1)² or *g* ≡ 1. The fractional-Kelly test in the same
file asserts `p == 0.75**3`, which is the formula re-evaluated inline; it
confirms that the code equals itself. The fractional family *q* = 2/*c* − 1
does match the published result (half Kelly: probability of ever halving is
(½)³ = ⅛), which would have been a stronger anchor, and a simulated barrier
crossing would have been an independent one. None of the tests is
independent of the formula.

## 4. The table in `docs/09` — recomputed

0.75¹ = 0.750, 0.75³ = 0.422, 0.75⁷ = 0.133, 0.75⁹ = 0.075. The table is
arithmetically correct **for the probability of ever trading 25% below
launch equity**, and it is worth stating that this probability depends only
on the Kelly fraction, not on the Sharpe or the asset. As a table of
"P(ever draw down > 25%)" every row should read 100%.

## 5. Do the plan's two constraints contradict each other?

`docs/09` says the plan "specifies fractional Kelly (¼–½) and P(DD > 25%)
≤ 5–10% as if they were two ways of saying the same thing". The plan's
gate 11 row lists four constraints separated by semicolons and names the
1% rule "as the hard cap". That is a conjunction, and a minimum over caps is
the natural reading of it; the code implements exactly that. The plan did
not claim equivalence, so there was no contradiction to discover, only a
question of which member of the conjunction binds. The framing of an
ordinary conjunction as a defect the code exposed is the clearest place the
author's motivation shows.

On the substance, with the corrected reading:

- **Half Kelly against a 10% budget** fails on every reading. Below launch:
  42%. Peak-to-trough within one year at Sharpe 0.8: 69%. There is no
  horizon on which it is close.
- **Quarter Kelly against a 10% budget** is borderline, not "not close".
  Below launch: 13% against 10%. Peak-to-trough within one year: 11% at
  Sharpe 0.8, 0.3% at Sharpe 0.4. The cap the code actually applies is
  0.222 Kelly, 11% below the plan's lower bound.
- The horizon question in the prompt has an answer: the infinite-horizon
  reading is not an artefact, it is the only reading under which the code's
  number is exact, and for the quantity the label names the infinite
  horizon makes the constraint void. A finite horizon is what a
  practitioner means by a drawdown constraint, and on that reading the
  answer depends on horizon and Sharpe (column C above), which no
  fraction-only table can express.

The doc's last paragraph, "at a $1,000 account the single-name gap rule
holds leverage near 0.2x … at this account size the constraint is the
account", is false as written. The single-name cap is
`max_single_name_loss / (max_weight × gap_move)` = 0.05 / max_weight, with
no equity term anywhere. A four-name equal-weight book is capped at 0.2x on
a $1,000 account and on a $1,000,000 account alike. This is consistent with
`docs/11` finding crypto sizing bit-identical across account sizes, and
inconsistent with the sentence that attributes it to the account. The
sentence carries the ETF trial's narrative into a place the arithmetic does
not support.

## 6. Is an infinite-horizon probability the right thing to size on?

No, and not mainly for the reason the prompt suggests.

- **The quantity has to be renamed before the question is meaningful.**
  Sizing on "P(ever DD > 25%)" is sizing on a constant. Sizing on "P(ever
  25% below launch)" or "fraction of time spent 25% under water" is
  coherent, horizon-free, and depends on nothing but the Kelly fraction.
  Those are real virtues for a policy: the number cannot be gamed by the
  choice of horizon, which is precisely the friendlier-number problem the
  policy comment worries about. Either would be a defensible cap if
  labelled honestly.
- **The precision is false either way.** The cap returns a leverage
  *f* = 0.222·SR/σ, linear in the out-of-sample Sharpe estimate. The
  standard error of an annualised Sharpe from *n* years of daily data is
  about √((1 + SR²/2)/*n*): roughly 2.1 from the 63-day forward record gate
  10 accepts, 1.0 from a one-year holdout. A drawdown probability quoted to
  three figures (42.2%) off an input whose one-sigma range spans zero is
  not a risk number. And for every Sharpe below 0.675 the drawdown cap,
  not the volatility target, sets the size, so the apparatus decides
  exactly in the regime where its input is noisiest. A vol target sized
  off realised volatility, which is estimated an order of magnitude more
  precisely than the Sharpe, is the more honest binding constraint at this
  data length.
- **The model is the wrong one for the venue.** Continuous rebalancing,
  Gaussian log returns, constant Sharpe and volatility. Daily crypto
  returns are fat-tailed and the book is rebalanced daily at best, so a
  25% level is crossed by a gap more often than any Brownian formula
  predicts. The single-name cap is the only term that acknowledges this,
  and it is the one that binds.
- **What a practitioner would size on instead**: a finite-horizon
  peak-to-trough probability at the strategy's review horizon (one year is
  the natural one for an incubated strategy), estimated by simulation from
  the strategy's own out-of-sample return distribution rather than a
  closed form, with the Sharpe uncertainty propagated. That is more work
  and less elegant than one line of algebra, which is a reason to suspect
  the one line was chosen for its elegance.

## Where the motivation shows

- A closed form with a known-answer test looks rigorous; the known answer
  was chosen from the same literature as the formula and cannot detect the
  one error present.
- "42%" was promoted to a headline and cited in `docs/10` as already
  informing decisions before anyone checked what it was the probability of.
- The plan's conjunction was recast as a contradiction, which makes the code
  look like it caught something.
- The 0.2x result was attributed to the $1,000 account, matching the ETF
  trial's story, when the cap producing it has no account term.
- The policy comment defends "ever" over "this year" on the grounds that
  the finite horizon gives a friendlier number. For the quantity actually
  computed that is true; for the quantity named it is backwards, since over
  a finite horizon the drawdown probability is smaller than one and over
  the infinite horizon it is one.

None of this changes a trial verdict. Gates 10 and 11 are inert until
something reaches gate 9, and nothing has.

## What a build session should change

Listed for a Sonnet or Opus session; not done here.

1. Rename the quantity everywhere it appears: `drawdown_probability` and
   `_drawdown_cap` in `qr/portfolio/sizing.py`, the `SizingPolicy` field
   comments, the gate 11 verdict string in `qr/validate/gates.py`, and the
   table and text of `docs/09`. "P(ever 25% below launch equity)" or "share
   of time more than 25% under water" are both exact; pick one and say
   which.
2. Correct `docs/09`: the four-row table's heading, the "not close"
   sentence, the "contradiction" framing, and the $1,000-account
   attribution of the single-name cap.
3. Replace the tautological tests with an independent one: a simulated
   Brownian barrier crossing that recovers the closed form to Monte Carlo
   tolerance, plus the published half-Kelly halving probability of ⅛.
4. Either drop `kelly_fraction` from the policy or set it where it can
   bind, and validate `max_drawdown` in (0, 1) at construction.
5. Decide whether gate 11 should add a finite-horizon peak-to-trough
   estimate from the out-of-sample return distribution at the strategy's
   review horizon. If it does, carry the Sharpe standard error into the
   verdict text so the leverage is reported as a range, not a point.
