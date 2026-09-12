# The ETF verdict: all four families fail, and the control fails too

*Written 12 September 2026, after the ETF-basket trial against Tiingo data.*

The crypto trial ended on 12 September with four failures and the rule saying
the next step was the ETF-basket trial, which costs nothing. This is that
trial. **Nothing passed.** Three hypotheses and one control, twelve funds,
sixteen years of dividend-adjusted bars, ten gates each.

The control failing is the finding worth reading. It is not the same kind of
failure as the other three, and separating the two is most of this document.

> ## Correction, 12 September 2026 — the cost figures in this document are wrong
>
> Every family below used a rebalance calendar, and the drift between
> rebalances was computed by the strategy one bar out of phase with the engine
> that consumes it. The engine holds the book from bar *t-1* and drifts it by
> bar *t*'s return; the strategy could only drift its own *t-1* target by
> *t-1*'s return. The two disagreed by one day's move on every bar in between,
> and that disagreement was charged as a trade.
>
> **A book scheduled to rebalance twelve times a year traded on all 365 of
> them.** On a synthetic panel the inflation was 9x: 17.4% of equity a year
> against a correct 1.9%.
>
> So the cost column, `net_over_gross`, every net Sharpe, and gates 2 through 8
> for all four families are computed from costs that are too high by an unknown
> but large factor. **Finding 1 below — that the per-order floor is the binding
> constraint — is exactly the claim this defect would manufacture**, and it is
> withdrawn pending a re-run. Finding 2 (the control cannot clear gate 3) is
> arithmetic about a Sharpe of 0.305 over sixteen years and survives; Finding 3
> (SPA against buy-and-hold) is a comparison between two things costed the same
> way, and its direction survives while its magnitude does not.
>
> The fix is in `Strategy.trades_on` and `run_backtest`, with the engine's
> closed form checked against an explicit loop that is the definition. The
> re-run has not happened yet, and this notice stays until it has.

## What was run

| | |
|---|---|
| Data | Tiingo daily, 12 ETFs, dividend- and split-adjusted, 5,183–8,462 bars each |
| Universe | `etf_basket_12` — SPY, QQQ, IWM, EFA, EEM, TLT, IEF, LQD, HYG, GLD, DBC, VNQ |
| In-sample | 2007-01-01 → 2022-12-31 |
| Holdout | 2023-01-01 onward, not opened (`--upto 8`) |
| Costs | IBKR Tiered: $0.0035/share, $0.35 per-order minimum, 1% cap, plus spread and impact |
| Account | $1,000 — the sum actually available, not a round number chosen for the model |
| Permutations | 100, re-optimised over the grid |
| Manifest | `b9edf573597201e4d…` |
| QA | 11 PASS, 1 WARN (one zero-volume bar in EFA, withheld by `tradable()`) |

## The result

| hypothesis | variants | verdict | stopped at | IS Sharpe | net/gross | round trips |
|---|---|---|---|---|---|---|
| `etf_tsmom_v1` | 30 | **FAIL** | gate 2 | 0.342 | 0.461 | 217 |
| `etf_xsmom_v1` | 12 | **FAIL** | gate 3 | 0.398 | 0.570 | 183 |
| `etf_reversal_v1` | 12 | **FAIL** | gate 2 | 0.073 | 0.127 | 682 |
| `etf_buyhold_v1` (control) | 1 | **FAIL** | gate 3 | 0.305 | 0.589 | 12 |

## Finding 1: at $1,000, the broker's per-order minimum is the whole cost model

A per-share commission with a floor is not reducible to a rate, and at this
account size the floor binds on **every order, at every price**:

| account | notional per leg | cost per leg | in basis points |
|---|---|---|---|
| $1,000 | $83 | $0.35 | **42.0** |
| $10,000 | $833 | $0.35 | 4.2 |
| $100,000 | $8,333 | $0.35 | 0.4 |
| $1,000,000 | $83,333 | $2.92 | 0.3 |

A twelfth of a $1,000 book is $83. At $0.0035 a share that is a third of a
cent of commission, so the $0.35 minimum applies — and it applies whether the
fund trades at $30 or $600, because 100 shares is the break-even and $83 buys
nowhere near that at any price in this basket. **Below roughly $360,000 of
equity, an equal-weighted twelve-fund rebalance pays the floor on every leg.**

That single fact explains the cost column. `etf_reversal_v1` turns the book
over 682 times and keeps 13% of its gross return. `etf_tsmom_v1` turns it over
217 times and keeps 46%, failing gate 2's 50% floor. These are not statements
about the strategies. They are statements about trading a $1,000 account
through a broker that charges per order.

### A prediction of mine, scored wrong twice

`docs/prereg/etf_tsmom_v1.md` originally said a monthly rebalance would cost
"roughly 5% a year in commissions". Measurement said 0.56%, and I filed a dated
correction before the run predicting that **gate 3, not gate 2, would be the
cause of death**.

It died at gate 2. The correction was wrong in the opposite direction to the
original — and worse than that, it contradicted the same document's own
falsification section, which reads *"Gate 2: net/gross below 0.50. Given 42 bps
a leg this is a live possibility."* The prereg had already named the right
number and the right gate. The prediction paragraph I then wrote on top of it
reasoned about commission as a percentage of notional, which is the one thing a
per-order floor is not, and talked itself out of the answer that was sitting
four lines above.

That is worth more than the two wrong predictions. A pre-registration is
supposed to survive its author's later reasoning, and here it did: the
falsification criteria were right when the commentary was not, which is exactly
the asymmetry they exist to create.

## Finding 2: the control could not have passed, and that is a fact about the test

`etf_buyhold_v1` — hold the twelve funds equally, rebalance monthly — scores an
in-sample Sharpe of 0.305 over sixteen years and a HAC *t* of 1.30. Gate 3
requires *t* ≥ 3.0.

For a strategy with a Sharpe of *S*, the *t*-statistic over *n* years is
approximately *S*·√*n*. To reach 3.0 at a Sharpe of 0.305 takes **97 years** of
data. There are 33 years of SPY and 16 in this sample. No long-only
diversified basket can clear gate 3 on any history that exists.

This is not a flaw to be patched by lowering the threshold. It is the battery
correctly refusing to call market exposure an edge, and gate 8 says so in
plainer terms: beta 0.98 to the equal-weighted benchmark. The control *is* the
benchmark. What the trial asked was whether any of these four things is a
tradable edge, and for the control the answer was never going to be yes —
holding a diversified basket is a perfectly reasonable thing to do with money
and is not an edge. The gates are calibrated for the former question.

Two consequences worth stating rather than leaving implicit:

- **Gate 8 for the control is degenerate.** `alpha t = -17.86 against beta
  0.98` is buy-and-hold regressed against itself; the large negative alpha is
  its own trading costs measured against a costless benchmark. It is arithmetic,
  not evidence, and gate 8 can never say anything else about that family.
- **Gate 6 for a single variant is uninformative.** `bar permutation p = 1.000`
  with no re-optimisation means the observed statistic sat at the bottom of its
  own null — expected for a long-only holder in a world where returns have been
  shuffled but the drift preserved.

## Finding 3: the same cleanest finding as the crypto trial

Gate 5 runs Hansen's SPA against buy-and-hold of the same universe:

| family | SPA p |
|---|---|
| `etf_tsmom_v1` | 0.966 |
| `etf_xsmom_v1` | 0.942 |
| `etf_reversal_v1` | 0.509 |

No variant of any family beats simply holding the basket. The crypto trial said
the same thing with p between 0.83 and 0.91 across 425 variants. Two asset
classes, two data vendors, two cost models, 479 variants, one answer.

Gate 8 adds the mechanism: betas of 0.44, 0.45 and 0.53 to the equal-weighted
basket, with alpha *t*-statistics of 0.13, 0.44 and −1.62. The two momentum
families are the market at roughly half exposure, which is what vol-targeting a
long-only basket produces. Their lower drawdowns are not skill; they are less
of the same thing.

## What this trial bought

Five defects in the engine, all found by the ETF data and all of which would
have silently distorted an equity result:

1. **The panel dropped the traded price.** `close_unadjusted` stopped at the
   lake boundary, so share counts — and the commission charged on them — were
   computed from the dividend-adjusted close, a third below the real price for
   SPY in 2007.
2. **Bars per year was hardcoded at 365.** An exchange keeps ~252 sessions;
   annualising by 365 multiplies every Sharpe by 1.20, consistently enough that
   no gate would catch it.
3. **`quote_volume_consistent` compared two price spaces**, failing eleven of
   twelve funds. The one that passed was the only one paying no distribution.
4. **`calendar_gaps` counted weekends as missing bars** — 3,817 for SPY. A
   check that fires on every instrument forever is one the reader learns to skip.
5. **The lake partition was never passed through**, so `--asset etf` read 734
   crypto pairs, found no SPY, and ran the gates over an empty book.

Defect 1 is the one worth dwelling on, because fixing it changed no number in
this table. The floor binds at $1,000 regardless of price, so the commission
was right by accident. I said the cost figures were overstated and would move;
they did not move at all. At $100,000 they would have.

## The decision

**Do not trade any of these four.** Nothing reached the holdout, which remains
unopened for all four families.

The rule from 11 September covered one branch — all crypto families fail, run
the ETF trial — and that branch is now also exhausted. What it did not
anticipate is that the control would fail too, which makes "run the next asset
class" a weaker move than it looks: the battery has now twice concluded that
the thing to beat is buy-and-hold, and twice been unable to certify buy-and-hold
itself, because holding the market is not an edge and the gates test for edges.

Three honest options, in the order I would take them:

1. **Change the question, not the threshold.** Ask what beats the basket
   *risk-adjusted after costs at $1,000*, and make buy-and-hold the benchmark
   in the strategy definition rather than a family competing under the same
   gates. This is a change to `docs/PLAN.md`, not to a number in
   `GateThresholds`.
2. **Raise the account before raising expectations.** Every cost figure here is
   a function of $1,000. At $100,000 the floor stops binding and the cost column
   changes by two orders of magnitude. The trial cannot distinguish "no edge"
   from "no edge at this account size" for the two momentum families, and it
   should say so rather than pretend otherwise.
3. **Test a family whose claim is not market exposure.** Everything run so far
   has been long-only, and long-only in a rising market is beta. A
   market-neutral or cross-sectional-with-shorts family would at least be
   asking gate 8 a question it can answer.

What the trial bought, again, is a no that cost nothing. Two asset classes have
now been searched, 479 variants deep, and the platform has declined every one
of them while finding eleven defects in itself. An engine that had said yes to
`etf_tsmom_v1` — Sharpe 0.342, half of it beta, 54% of the gross eaten by a
$0.35 minimum — would have been worth less than nothing.
