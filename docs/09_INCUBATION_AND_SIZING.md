# Gates 10 and 11: the last two, and the only ones that move money

> **Reviewed 14 September 2026 — `docs/16_GATE_11_SIZING_REVIEW.md`** found the
> formula correct and the label wrong: it computes the probability of ever
> falling 25% below *launch equity*, not a peak-to-trough drawdown. **This page
> has since been corrected** and the code renamed (`prob_ever_below_launch`,
> `SizingPolicy.loss_from_launch`); read `docs/16` for the derivation, the
> Monte Carlo tables and the finite-horizon numbers, which are not repeated
> here.

Gates 0–9 are an argument about history. They can be run again tomorrow and
they will say the same thing, because the data does not change. These two are
different: gate 10 reads bars that did not exist when the strategy was
written, and gate 11's output is a dollar amount.

They are also the two that were missing, so the engine now runs 0–11.

## Gate 10 — incubation

Three checks, in this order, because they fail for different reasons and only
the last one is about the strategy.

**1. Wiring.** Every bar of the live record can carry the book that was
actually held *and* the book the research code says should have been held.
Gate 10 sums the absolute disagreement over the union of both symbol sets — a
position the live system opened that the research never asked for counts
exactly as much as one it missed — and fails above 2% of gross.

This check is first and it is unconditional. A book that is both mis-wired
and profitable still fails, because the profit belongs to something nobody
validated. The verdict says *"this is a wiring defect, not a decay, and
incubating longer will not fix it"*, since the natural instinct on a bad
number is to wait for more data, and more data is the wrong answer here.

If no bar carries an expectation, the gate does not read that as agreement.
It records the wiring as unchecked and downgrades a pass to a warning.

**2. Cost.** Realised cost against what the cost model predicted, failing
above 1.30x. This threshold is doing more work than it looks like: the cost
model decided gate 2 for every family this project has run, and the
rebalance-phase defect in `docs/08` is what a wrong cost model does to a
verdict. If the real world charges a third more than the model, gate 2 was
scoring a fiction for every family, not just this one.

**3. Decay.** Forward Sharpe as a fraction of in-sample. Below 50% fails,
50–70% warns and buys another month, above 70% passes.

This is the check everyone means by "paper trading" and it is the weakest of
the three. Sixty-three daily observations cannot establish that a Sharpe of
0.7 is real — the standard error is far too wide. They can establish that it
is gone. So the gate is built to refute rather than to bless, and its own
pass text says so: *"consistent with the research, which is the strongest
claim 63 observations can support."* A gate that overstated its evidence here
would undo everything gates 3 and 4 exist to enforce.

The record lives in the same hash-chained trial log as the backtests. This is
not tidiness. The one failure mode of an incubation record is the operator
quietly dropping the fortnight that went badly, and a chain makes that
visible instead of tempting. A second line for a day already recorded is kept
as a correction and does **not** replace the original; only the first counts.

    qr forward observe tsmom_v1 --date 2026-09-13 --net-return 0.0031 \
        --cost 0.0002 --expected-cost 0.0002 \
        --weights '{"SPY": 0.5, "TLT": 0.5}' \
        --expected-weights '{"SPY": 0.5, "TLT": 0.5}'
    qr forward status

## Gate 11 — sizing

**The Sharpe that sets the size must be out-of-sample.** Gate 11 takes the
forward record if the strategy is incubating, otherwise the holdout gate 9
opened, and there is no fallback. A strategy that has not reached gate 9 gets
`SKIP` with the reason spelled out: the only Sharpe available for it is the
one the search maximised, and that is the number least entitled to set an
exposure. This is the most common way a genuine edge still ends in a blown
account, and it is worth a gate that simply refuses.

The size is the **minimum of four caps**, and the verdict always names which
one bound — the same shape as gate 2 naming the dominant cost, for the same
reason. "Trade at 0.4x" is a number; "trade at 0.4x because the drawdown
constraint binds, not the edge" is a direction.

| cap | what it is |
|---|---|
| Fractional Kelly | ¼ of full Kelly `SR/σ` |
| Loss from launch | the largest leverage keeping P(ever 25% below launch equity) ≤ 10% |
| Volatility target | 15% annualised on the book |
| Single-name gap | no one position may cost more than 1% of equity on a 20% adverse gap |

The cap uses `P(ever D below launch) = (1 − D) ** (2m/s²)`, the classical
barrier-crossing probability. Two published anchors pin it — a full-Kelly book
has exactly a 50% chance of ever halving, a half-Kelly book exactly ⅛ — and a
simulation that shares no algebra with the formula reproduces it to Monte
Carlo tolerance. The single anchor this page used to cite was drawn from the
same literature as the formula, which is why it passed while the quantity was
mislabelled; `docs/16` made that point and the test file now says so.

**What it is not.** The peak-to-trough drawdown is a different random
variable: measured from the running peak, reflected at zero, and positive
recurrent. Over the infinite horizon the cap is solved on, P(peak-to-trough
drawdown ever exceeds any depth) = 1 at every leverage. The constraint this
page used to state was therefore unsatisfiable as written, and the code met it
only by computing something else.

### What building it turned up

The plan (§4, gate 11) specifies *"fractional Kelly (¼–½)"* and a loss budget
of *"≤ 5–10%"*. Under this engine those are not two ways of saying the same
thing, and the second is much the tighter:

| Kelly fraction | P(ever 25% below launch) | equivalently, share of life spent >25% under water |
|---|---|---|
| full | 75% | 73% |
| ½ | **42%** | 40% |
| ¼ | **13%** | 13% |
| 0.222 (where the cap lands) | 10% | 9% |
| ⅕ | 7.5% | 7% |

Half Kelly — the conventional "safe" fraction, the one that gets recommended
casually — fails a 10% budget by a factor of four on any reading. Quarter
Kelly is *borderline* rather than clearly out: 13% against a 10% budget, which
is why the cap lands just below it at 0.222.

The second column is the same number read as time rather than probability, and
it is the more useful sentence: **at half Kelly you spend 40% of your life
more than a quarter below your high-water mark.** `docs/16` also gives the
finite-horizon peak-to-trough numbers, which are worse again.

**This is a conjunction, not a contradiction.** An earlier version of this
page said the plan's two constraints disagreed and that the code had caught
something; the review was right that this overstated it. "Fractional Kelly
*and* a loss budget" is what the plan always meant, and the answer is simply
the tighter of the two. That is why sizing is a minimum over caps: not because
the numbers conflict, but because which one binds is information, and it is
reported.

In practice a fifth cap usually binds before any of these: the single-name gap
rule holds leverage near 0.2x. **That is not an account-size result** — the
cap is `1% / (max_weight x 20% gap)` and has no equity term in it at all. An
earlier version of this page attributed it to the $1,000 account because that
matched the ETF trial's story. It does not; it is a statement about position
concentration, and it would say the same thing at $100,000. Step 0
(`docs/11`) is where the account-size question is actually answered.
