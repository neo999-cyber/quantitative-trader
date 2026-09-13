# Gates 10 and 11: the last two, and the only ones that move money

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
| Drawdown | the largest leverage keeping P(ever draw down > 25%) ≤ 10% |
| Volatility target | 15% annualised on the book |
| Single-name gap | no one position may cost more than 1% of equity on a 20% adverse gap |

The drawdown cap uses `P(ever DD > D) = (1 − D) ** (2m/s²)`. The test for it
is a known answer rather than a plausible one: a full-Kelly book has exactly
a 50% chance of ever halving, and any expression that does not reproduce that
is the wrong expression.

### What building it turned up

The plan (§4, gate 11) specifies *"fractional Kelly (¼–½)"* and *"P(DD >
25%) ≤ 5–10%"* as if they were two ways of saying the same thing. They are
not, and the arithmetic is not close:

| Kelly fraction | P(ever draw down > 25%) |
|---|---|
| full | 75% (and a 50% chance of ever halving) |
| ½ | **42%** |
| ¼ | **13%** |
| ⅕ | 7.5% |

Half Kelly — the conventional "safe" fraction, the one that gets recommended
casually — carries a better-than-even chance of a drawdown deep enough that
most people would abandon the strategy. Even quarter Kelly misses the plan's
own 10% budget.

So the two constraints disagree, and under this engine the **drawdown
constraint is the binding one, not the Kelly fraction**. That is why sizing
is a minimum over caps rather than a single formula: the plan's numbers were
each defensible and their conjunction was not, which is exactly the kind of
thing that stays invisible until someone writes it down as code.

In practice a fifth cap usually binds before any of these. At a $1,000
account the single-name gap rule holds leverage near 0.2x, which is a
restatement of the ETF trial's finding: at this account size the constraint
is the account, and the interesting design variable is turnover.
