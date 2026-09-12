# Pre-registration: `etf_buyhold_v1` — the equal-weighted basket (**the control**)

*Written 12 September 2026, before any ETF data was pulled.*

## What this is for, and why the control changed

The crypto trial's control was the 3-down-day RSI setup, ported from the
Centaur rulebook and pre-registered to fail. It did fail — but it failed for
the wrong reason (I predicted a shortage of trades; it produced 173 and died on
significance), and more importantly it tested the wrong thing. It asked "can
the engine reject a bad strategy?", and by the time it ran, the engine had
already rejected three.

The question that actually needs a control on this trial is different, and the
crypto trial made it unmissable. **Gate 5's SPA test found that not one of 425
crypto configurations beat buy-and-hold.** That was the single cleanest finding
of the whole week. If holding the basket is the thing to beat, then holding the
basket is what belongs in the trial as a named, pre-registered, fully gated
hypothesis — not as a benchmark computed inside gate 5 where it never has to
face gate 3, gate 6 or the holdout itself.

So the control here is: **buy the twelve ETFs in equal weight, rebalance
monthly, and run it through all ten gates like anything else.**

## Mechanism

None claimed. That is the point. This is the risk premium of owning a
diversified basket of assets, which is not an anomaly, not a discovery, and not
something a search could overfit — there is exactly one variant.

## Predicted sign and size

**Net annualised Sharpe of 0.5 to 0.9.** A 60/40-ish multi-asset portfolio has
run around 0.6 over the last two decades and this basket is a reasonable
approximation of one.

Specific prediction, recorded so the mechanism can be checked and not just the
verdict:

> **It will pass gates 2, 3 and 9 and fail gate 8 on beta.** Alpha against SPY
> will be indistinguishable from zero — because there is no alpha here, only
> beta, and gate 8 is the gate designed to say so. Predicted beta to SPY: 0.5
> to 0.8. Predicted alpha t-statistic: **−1 to +1**.

Gate 2 should pass easily despite $1,000 of equity: one monthly rebalance of a
drifting equal-weight book has very low turnover, which is precisely the
property the two momentum families lack.

## Universe and horizon

`etf_basket_12`, identical to the other three. Daily bars, monthly rebalance to
equal weight. Dividend- and split-adjusted.

## Parameter ranges

**One variant.** No sweep, no search, nothing for gate 4 to deflate. This is
the cleanest available reading of what the deflation gates do when there is
genuinely nothing to correct for: if gate 4 or 5 flags a single-variant
strategy, the engine has a bug.

## What would falsify this

- **Gate 8 passing on alpha** would mean either the basket genuinely has alpha
  against SPY — plausible, since it holds duration and gold that SPY does not —
  or that the factor decomposition is mis-specified by using SPY alone as the
  benchmark. The second is more likely and the report must say which. A
  multi-asset portfolio's "alpha to SPY" is mostly just its bond sleeve.
- **Gate 4 or 5 failing a one-variant hypothesis** would be an engine bug, not
  a finding, and blocks the trial until explained.

## What this control is really testing

Two things, only one of which is about the market.

1. Whether any of the three real families beats simply owning the basket —
   which is the question the crypto trial answered with "no, 425 times".
2. Whether the gates behave sensibly on a hypothesis with **no search behind
   it**. Every other run in this project has had a grid. This one has not, and
   the deflation gates should be silent.
