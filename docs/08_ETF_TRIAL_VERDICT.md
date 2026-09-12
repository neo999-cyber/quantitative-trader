# The ETF verdict: five families, none survive

*Written 12 September 2026. **Rewritten the same day** after a defect in the
engine was found to have inflated every cost figure in the first version —
see "What the first version of this document got wrong" at the end, which is
the most useful part of it.*

Five pre-registered families against twelve funds and sixteen years: three
long-only hypotheses, a long-only control, and one dollar-neutral long-short
family added afterwards to test whether the gates were rejecting strategies or
rejecting a category. **Nothing passed.**

## What was run

| | |
|---|---|
| Data | Tiingo daily, 12 ETFs, dividend- and split-adjusted, 5,183–8,462 bars each |
| Universe | `etf_basket_12` — SPY, QQQ, IWM, EFA, EEM, TLT, IEF, LQD, HYG, GLD, DBC, VNQ |
| In-sample | 2007-01-01 → 2022-12-31 |
| Holdout | 2023-01-01 onward, opened once by the first run and not re-opened |
| Costs | IBKR Tiered: $0.0035/share, $0.35 per-order minimum, 1% cap, plus spread; borrow at 50 bps/yr on the short family |
| Account | $1,000, and $10,000 for the long-short family, which may not legally short below $2,000 |
| Permutations | 100, re-optimised over the grid |
| Manifest | `b9edf573597201e4d…` |
| QA | 11 PASS, 1 WARN (one zero-volume bar in EFA, withheld by `tradable()`) |

## The result

| hypothesis | variants | verdict | stopped at | IS Sharpe | net/gross | round trips |
|---|---|---|---|---|---|---|
| `etf_tsmom_v1` | 30 | **FAIL** | gate 5 | 0.678 | 0.733 | 214 |
| `etf_xsmom_v1` | 12 | **FAIL** | gate 3 | 0.398 | 0.570 | 183 |
| `etf_reversal_v1` | 12 | **FAIL** | gate 2 | 0.073 | 0.127 | 682 |
| `etf_buyhold_v1` (control) | 1 | **FAIL** | gate 6 | 0.664 | 0.957 | 12 |
| `ls_xsmom_v1` (long-short) | 12 | **FAIL** | gate 3 | 0.326 | 0.634 | 295 |

## Finding 1: turnover decides affordability, not account size alone

The first version of this document claimed the per-order minimum was "the whole
cost model" at $1,000. With the costs computed correctly, the picture is
sharper and different: the floor binds hard, but only on books that trade a lot.

| family | round trips | net/gross | commission's share of the drag |
|---|---|---|---|
| `etf_reversal_v1` | 682 | 0.127 | 94% |
| `ls_xsmom_v1` | 295 | 0.634 | — |
| `etf_tsmom_v1` | 214 | 0.733 | — |
| `etf_xsmom_v1` | 183 | 0.570 | 98% |
| `etf_buyhold_v1` | 12 | 0.957 | — |

A weekly reversal strategy at $1,000 keeps 13% of its gross return and the
commission is essentially all of it. A monthly momentum book keeps 73% and
passes gate 2 comfortably. The control keeps 96%. **The constraint is real and
it is a constraint on turnover**, which is a design variable, rather than on
the account, which is not.

That distinction only became visible because gate 2 can now name which cost it
was — `CostModel.components` splits the drag into commission, spread, impact
and borrow, and gate 2 reports the culprit when one of them dominates. A
verdict of "costs eat 87% of gross return" is a dead end; the same sentence
ending "94% of it the per-order commission" is a direction.

## Finding 2: `etf_tsmom_v1` is the closest this project has come to a pass

It clears gates 0, 1, 2, 4 and 7, and only warns at 3:

| gate | verdict | |
|---|---|---|
| 2 cost survival | **PASS** | 73% of gross survives; Sharpe 0.43 at 2x costs |
| 3 significance | WARN | HAC *t* = 2.90 against a 3.0 bar |
| 4 deflation | **PASS** | DSR = 0.982 over 30 trials, haircut Sharpe 0.18 |
| 5 selection | FAIL | PBO 0.58; SPA *p* = 0.510 vs buy-and-hold |
| 6 permutation | FAIL | bar permutation *p* = 0.188 |
| 7 cross-validated OOS | **PASS** | median path Sharpe 0.48 = 72% of in-sample, 9 of 9 positive |
| 8 robustness | FAIL | alpha *t* = 1.87 against beta 0.47 |

This is a much more informative failure than "costs ate it". The strategy is
affordable, it survives deflation against its own 30-variant search, and it
holds up across combinatorial purged CV paths. What kills it is that the
variants are interchangeable (PBO 0.58 with **0% of selections losing out of
sample** — arbitrary selection, not overfitting), that a re-optimised bar
permutation reproduces its Sharpe 19% of the time, and that half of it is beta.

Note also gate 4 and gate 5 disagreeing in an interesting way: the deflated
Sharpe ratio says the best of the search is not what noise would give, while
SPA says no variant beats holding the basket. Both can be true — the strategy
is real and it is not better than the benchmark.

## Finding 3: still nothing beats buy-and-hold, but less emphatically

| family | SPA *p* vs buy-and-hold | was, with inflated costs |
|---|---|---|
| `etf_tsmom_v1` | 0.510 | 0.966 |
| `etf_reversal_v1` | 0.509 | 0.509 |
| `ls_xsmom_v1` | 0.875 | 0.956 |
| `etf_xsmom_v1` | 0.942 | 0.942 |

Every *p* is still above one half, so the direction of the crypto trial's
cleanest finding survives across two asset classes and 479 variants. But
`etf_tsmom_v1` moved from 0.966 to 0.510, which is the difference between
"emphatically worse than the benchmark" and "indistinguishable from it". The
strength of that finding was partly an artefact.

## Finding 4: the long-short family was neutral around nothing, exactly as predicted

`ls_xsmom_v1` existed to answer one question — were the gates rejecting bad
strategies, or rejecting long-only investing? Its pre-registration made three
numeric predictions and a fourth about costs. All four landed:

| predicted, before the run | realised |
|---|---|
| beta to the basket, −0.15 to +0.15 | **+0.03** |
| alpha *t*, 0.5 to 1.5 | **1.34** |
| net Sharpe, 0.0 to 0.4 | **0.326** |
| gate 2 less likely to fail than for the long-only families | **PASS**, 63% survives |

The construction works and the answer is clean: **the gates were not rejecting
a category.** A dollar-neutral book faces them on level terms and fails on its
own merits, at gate 3, with a HAC *t* of 1.46. Gate 7 is the plainest reading —
median path Sharpe 0.20, 8 of 9 paths positive, but too small to matter. The
momentum spread in this basket carries a little information and not enough.

Gate 8 now says so correctly: *"the factors explain only 0% of it, so this is
neutral around nothing rather than market exposure."* It used to say "this is
the market, not the strategy" at a beta of 0.03 — the same sentence it printed
at a beta of 0.98.

## What the first version of this document got wrong

Every family here used a rebalance calendar, and the drift between rebalances
was computed by the strategy one bar out of phase with the engine consuming it.
The engine holds the book from bar *t−1* and drifts it by bar *t*'s return; the
strategy could only drift its own *t−1* target by *t−1*'s return. The
disagreement was charged as a trade on every bar in between, so **a book
scheduled to rebalance twelve times a year traded on all 365**.

The damage:

| | first version | corrected | |
|---|---|---|---|
| `etf_tsmom_v1` Sharpe | 0.342 | 0.678 | 1.98x |
| `etf_buyhold_v1` Sharpe | 0.305 | 0.664 | 2.18x |
| `ls_xsmom_v1` Sharpe | 0.152 | 0.326 | 2.14x |
| `etf_tsmom_v1` stopped at | gate 2 | gate 5 | |
| `etf_buyhold_v1` stopped at | gate 3 | gate 6 | |

Three things are worth recording about how this was found and how badly the
first document handled it.

**It was not found by the gates.** Eleven defects in this platform have been
found by its own runs; this one was found only because a sixth family was being
designed *around* the cost structure, which meant counting orders per year and
noticing the engine disagreed with the arithmetic. No gate tests the engine
against a definition of what holding a book means. There is one now, written as
an explicit loop that the closed form must match.

**The first document's triage was itself wrong.** When the defect was found I
withdrew Finding 1 and wrote that Finding 2 — the control cannot clear gate 3 —
"is arithmetic about a Sharpe of 0.305 over sixteen years and survives". It did
not survive. The Sharpe was 0.664, the *t* is 2.91 rather than 1.30, and the
claim built on it (that *no* long-only diversified basket can clear gate 3 on
any history that exists) is false. Arithmetic is only as good as the number
going into it, and I checked the arithmetic rather than the number.

**Three of my predictions were scored as wrong when the engine was at fault.**
The `etf_tsmom_v1` pre-registration predicted gate 3, not gate 2, as the cause
of death; I scored that wrong twice over and wrote a section about how the
falsification criteria had been right where my commentary was not. With the
costs computed correctly the family passes gate 2 and warns at gate 3. The
original prediction was right. Likewise `ls_xsmom_v1`'s cost prediction, which
I recorded as the one of four it got wrong.

The lesson is not that the pre-registrations were vindicated. It is that a
cost figure agreeing with the story I was telling was never once questioned,
across three separate write-ups, while the predictions that disagreed with it
were repeatedly marked wrong. Pre-registration protects against choosing a
hypothesis after the fact. It does nothing about believing a measurement
because it is convenient.

## The decision

**Do not trade any of these five.** The holdout was opened once, by the first
ETF run, and these corrected numbers are a re-score of the same in-sample
period rather than new evidence — the 2023-onward record for these families is
spent and cannot be used to rescue them.

`etf_tsmom_v1` is worth one more thought before it is closed out. A Sharpe of
0.678 that survives cost, deflation and purged cross-validation, and dies on
selection arbitrariness and beta, is the profile of a real but unremarkable
trend-following premium — which is what the literature says multi-asset time
series momentum is. It is not an edge over holding the basket. Whether it is
worth trading anyway, for the drawdown profile rather than the return, is a
portfolio-construction question this battery is not designed to answer and
should not be bent into answering.
