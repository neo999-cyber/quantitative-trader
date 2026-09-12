# Pre-registration: `etf_tsmom_v1` — multi-asset time-series momentum

*Written 12 September 2026, before any ETF data was pulled.*

## Why this family, and why it is not a repeat of the crypto one

Time-series momentum failed on Binance spot: HAC t of 1.93, deflated Sharpe
0.78, SPA p of 0.890, holdout Sharpe −0.55. This is the same effect on a
different asset class, and the literature is explicit that the two are not the
same bet. Moskowitz, Ooi and Pedersen document trend across 58 futures markets
over 25 years; the effect is strongest in **multi-asset** portfolios where
equities, duration and commodities trend at different times, and it is the
diversification across uncorrelated trends — not the trend in any one market —
that produces the Sharpe.

The crypto basket had one factor. Thirty coins with a 0.8 correlation to
Bitcoin is one bet wearing thirty hats, which is exactly what gate 8 found:
beta 0.21 to BTC with an alpha t-statistic of 0.89. A basket of SPY, TLT and
GLD is genuinely three bets. That is the specific reason to expect a different
answer, and if it is wrong this family should fail the same way the crypto one
did.

## Mechanism

Slow-moving capital and under-reaction to persistent macro information.
Pension funds rebalance quarterly, central banks move rates in sequences, and
commodity supply responds to price over years — so an initial move is followed
by more of the same move for weeks to months. It is the most heavily replicated
anomaly in any asset class and also the most heavily traded, which cuts both
ways: unlikely to be spurious, unlikely to be generous.

## Predicted sign and size

**Net annualised Sharpe of 0.4 to 0.8** at $1,000 of equity. Gross before
costs: 0.6 to 1.0.

The gap between those two numbers is the whole point of running this at $1,000
and I am predicting it will be large. At 42 bps a leg, a monthly rebalance of
twelve positions costs roughly 5% a year in commissions alone.

**Predicted beta to SPY: 0.2 to 0.5**, lower than a long-only equity sleeve
because the bond and gold legs are genuinely different exposures. Predicted
alpha t-statistic: **above 2**, and I expect this to be the binding constraint
exactly as it was in crypto.

## Universe

`etf_basket_12`, fixed and named before the run: SPY, QQQ, IWM, EFA, EEM, TLT,
IEF, LQD, HYG, GLD, DBC, VNQ.

**The known bias, stated here rather than discovered later.** These are today's
largest funds in their categories, and choosing them in 2026 is a choice made
with hindsight. No ETF on this list has closed; the ones that closed are absent
because nobody remembers them. The bias is real and smaller than crypto's — all
twelve were among the largest in their categories by 2010, chosen for asset-class
coverage rather than for returns, and none is a thematic or leveraged product —
but it is not zero, and a reader should discount accordingly.

Prices are **dividend- and split-adjusted**. On unadjusted prices TLT and HYG
would appear to be persistent losers and this family would learn to short them,
which would be an artefact of the data and not a property of the market.

## Horizon

Daily bars, monthly rebalance, positions held between rebalances.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` | 60, 90, 120, 180, 252 (5 values) | yes |
| `skip` | 0, 5, 20 (3 values) | yes |
| `vol_lookback` | 30, 60 (2 values) | yes |
| `vol_target` | 0.10 (fixed) | no |
| `max_leverage` | 1.0 (fixed) | no |

**30 variants**, deliberately a sixth of the crypto family's 200. Minimum
backtest length at 30 trials and a Sharpe of 0.6 is `2·ln(30)/0.36` ≈ 19 years,
which is about what this basket has. The crypto trial searched 200 variants
over 7 years and gate 4 was right to reject it; registering a grid that the
sample can actually support is the lesson from that, applied in advance.

The vol target is 0.10 rather than crypto's 0.20 because a multi-asset ETF
basket has roughly half the volatility of a crypto basket and levering it to
20% would require margin this account does not have.

## What would falsify this

- Gate 2: net/gross below 0.50. Given 42 bps a leg this is a live possibility
  and would mean the family is unaffordable rather than edgeless.
- Gate 3: HAC t below 2.5.
- Gate 8: alpha t-statistic below 2 against SPY, which would mean the basket is
  an expensive way to be long equities.
- Gate 9: holdout Sharpe at or below zero.

## Prediction about the others

I expect this family to be the **most likely of the four to pass**, for the
diversification reason above, and the most likely to be killed by gate 2 rather
than by gate 3. That is recorded so a failure at gate 3 is a surprise rather
than retrospectively obvious — which is exactly the mistake I made on crypto,
where I predicted a gate 8 death on beta and got a gate 3 death instead.
