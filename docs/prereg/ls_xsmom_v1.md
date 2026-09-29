# Pre-registration: `ls_xsmom_v1` — long-short cross-sectional momentum

*Written 12 September 2026, after the ETF verdict and before this family has
been run on any data.*

## Why this family exists

Both completed trials ended at the same sentence. Gate 8 on crypto: *"this is
the market, not the strategy."* Gate 8 on ETFs: the same words, with betas of
0.44, 0.45 and 0.53 and alpha *t*-statistics of 0.13, 0.44 and −1.62. Nine
families across two asset classes, every one of them long-only, every one of
them a repackaging of being long a market that rose.

That is not nine independent failures. It is one structural fact about the
things tested, and it makes gate 8 unanswerable in a useful direction: a
long-only book *is* beta, so the gate can only ever confirm it. This family is
the first whose claim is not market exposure, which is the only way to find out
whether the gates have been rejecting bad strategies or rejecting a category.

## Mechanism

Rank the twelve funds on the same 12-1 momentum signal `etf_xsmom_v1` used —
the return from `lookback + skip` sessions ago to `skip` sessions ago — hold
the top `n_side` long and the bottom `n_side` short, equally weighted, gross
exposure 1.0 and net exposure 0.0, rebalanced monthly.

The claimed mechanism is the same slow diffusion of macro information, but the
bet is different in kind. Long-only rotation profits when the leaders keep
leading. This profits when the *spread* between leaders and laggards persists —
which can be true in a falling market, a rising one, or a flat one, and is the
reason a cross-sectional factor is supposed to be uncorrelated with the market
it is drawn from.

`CrossSectionalMomentum` documents why it is long-only: *"the short leg of the
academic factor is not available, and half a factor is a different strategy
with a different expected return."* That was a statement about Binance spot. A
US margin account can borrow these funds, so this is the other half.

## Predicted sign and size

**Net annualised Sharpe of 0.0 to 0.4** at $10,000, gross 0.1 to 0.5.

**Predicted beta to the equal-weighted basket: −0.15 to +0.15.** Not a
prediction about skill — it is what dollar-neutrality means, and if the
realised beta lands outside that band something is wrong with the construction
rather than interesting about the market.

**Predicted alpha t-statistic: 0.5 to 1.5.** Below the bar, and recorded before
the run. My honest expectation is that this family fails, and the reason it is
worth running anyway is that it fails *differently*: a long-only family that
dies at gate 8 tells you nothing you did not know when you wrote it, while a
dollar-neutral family that dies at gate 3 tells you the spread itself carries
no information in this basket.

## Three things this family faces that no previous one did

**A short leg costs money to hold, not only to trade.** Borrow accrues daily on
short notional whether or not the book moves, so a monthly rebalance still pays
every day. `CostModel.borrow_cost` expresses this for the first time; at 50 bps
a year on roughly half the gross it is a small number here, and it is the
*shape* that is new — a cost with no turnover behind it.

**It cannot be traded in the account the trial models.** A US margin account
may not short below $2,000 of equity, and the ETF trial was priced at $1,000.
The cost model is therefore frozen at **$10,000**, and a pass here is a
research finding, not a trade to place. Saying so in advance matters because
the temptation after a pass is to quietly reprice it down.

**Dollar-neutral is not risk-neutral.** A dollar of TLT against a dollar of EEM
is a volatility-mismatched bet, not a hedge, and the vol-targeting overlay
scales the whole book without touching the mismatch. This is left deliberately
unfixed: beta-neutralising or vol-weighting the legs is a second hypothesis,
and bolting it on now would make a failure impossible to attribute to either.

## What is being run

**12 variants**, the same scale as the other ETF families and inside what
sixteen years can support (`2·ln(12)/0.6² ≈ 14` years at a Sharpe of 0.6):

| parameter | values |
|---|---|
| `lookback` | 60, 120, 180, 252 |
| `n_side` | 2, 3, 4 |
| `skip` | 21 |
| `rebalance_on` | `MS` (first session of the month) |
| `vol_target` / `vol_lookback` / `max_leverage` | 0.10 / 60 / 1.0 |

Universe `etf_basket_12`, in-sample 2007-01-01 → 2022-12-31, holdout from
2023-01-01 untouched. Below `2 · n_side` eligible funds the book stands flat
rather than letting a fund fill both sides — HYG lists in April 2007, inside
the sample, so this is a real bar and not a hypothetical.

## What would falsify this

- Gate 2: net/gross below 0.50. Less likely than for the long-only families —
  six legs monthly at $10,000 is about 6 bps a leg rather than 42 — but the
  borrow fee is new and unverified.
- Gate 3: HAC *t* below 2.5.
- Gate 5: SPA *p* above 0.50 against buy-and-hold, which would repeat the one
  finding both previous trials agree on.
- Gate 8: **beta outside ±0.15**, which falsifies the construction rather than
  the hypothesis and should be treated as a bug to find, not a result to
  report. Or alpha *t* below 2 with beta inside the band, which is the honest
  failure: neutral, and neutral around nothing.
- Gate 9: out-of-sample Sharpe at or below zero on the 2023-onward holdout,
  which is opened once and never again.

## The multiple-testing problem this document cannot solve

This is the **fifth** family run against these sixteen years of these twelve
funds. Gate 4 deflates on the trial count *within* a family — 12 variants here
— and nothing anywhere deflates on the fact that the sample has now been
searched 66 variants deep across five pre-registered hypotheses, or that the
trial log holds 1,450 counted trials in total.

The pre-registrations make each family's search honest. They do not make the
sequence of families honest, and a fifth hypothesis tested on the same data has
a materially higher chance of clearing any fixed bar than the first did. If
this family passes, that is the first thing to hold against it, and the holdout
from 2023 is the only evidence that would not suffer from it.

Recorded here so that a pass is read with this in front of it rather than
discovered afterwards.
