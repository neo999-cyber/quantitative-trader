# Pre-registration: `p2_funding_carry_v1` — funding carry, delta-neutral, benchmarked to cash

*Drafted 15 September 2026, before any run. Register with
`qr trial prereg p2_funding_carry_v1 --file docs/prereg/p2_funding_carry_v1.md`
only after `qr data carry-build` has written the `carry-um` panel and the
universe listing has been read — and before any backtest of this family.*

## Mechanism

A perpetual has no expiry, so it is tied to spot by a payment: every eight
hours the side the market is crowded on pays the other. When the levered crowd
is long, longs pay. That payer is real, the obligation is contractual, and the
trade that collects it — long one unit of spot, short one unit of the perp —
carries no directional exposure to the coin. What it earns is the funding,
less the change in the basis it gave up to enter, less two legs' costs. BIS
Working Paper 1087 (Schmeling, Schrimpf, Todorov, "Crypto carry") measures the
carry at over 10% a year on average and finds its profit is mostly the
funding; it also finds that a *high* carry predicts crashes and margin spikes.
Both halves of that finding are in this family: a floor to enter, and a
ceiling not to.

Programme 1 killed forty crypto memos on transmission because the payer paid
on the perpetual and the book was spot. This is the first family in this
repository that holds the perpetual.

## Predicted sign and size

**Positive against cash.** Net of the frozen cost model, at $1,000 of
equity, over the in-sample period:

- annualised net return **3% to 8%**, annualised volatility **3% to 6%**,
  net Sharpe **0.8 to 1.5** against the 3-month T-bill;
- the funding received explains **at least 80%** of gross return (the
  `carry` series against `gross` in the backtest result); a family earning
  its return from the basis instead has a different mechanism and has not
  confirmed this one;
- maximum drawdown **under 10%**, excluding what the backtest cannot see:
  exchange failure and forced deleveraging. Those are named risks, not
  modelled ones, and gate 11 sizes with that written down.

A net Sharpe above 3 on this family would be a reason to look for a leak
(most likely a funding timestamp that is not point-in-time), not to
celebrate.

## Universe

`carry_top40`: the carry units — symbols with both a Binance USDT spot pair
and a Binance USDⓈ-M perpetual — ranked point-in-time by trailing 30-bar
median of the **thinner leg's** quote volume, top 40, rebalanced monthly,
180-bar minimum history, with the stablecoin, fiat, tokenised-gold and
leveraged-token exclusions of `tsmom_v1`'s amendment applied unchanged. A
unit whose perp is delisted leaves the book at its last close.

Fixed before the run. Not to be narrowed after seeing which coins paid.

## Horizon

Daily bars; decisions daily; a unit is held from the day its trailing
funding clears the entry floor until the day it falls below the exit floor,
so effective holding periods run from days to months.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` (days of funding averaged) | 3, 7, 14, 30 | yes |
| `entry` (annualised funding to open) | 0.05, 0.10, 0.15, 0.20 | yes |
| `exit` | entry / 3 | tied |
| `ceiling` (trailing-year percentile above which not to open) | 0.95, 1.00 | yes |
| `n_max` | 5, 10 | yes |
| `rebalance` | 1 | fixed |
| `percentile_window` | 365 | fixed |

**64 variants.** This is the trial count gate 4 deflates against, on top of
the 1,541 already in the log. Widening any range after seeing results is a
new hypothesis with a new id.

## Cost model

`CostModel.carry_pair(CostModel.trial(), CostModel.binance_perp())`: the
spot leg's 7.5 bps fee and 2 bps half-spread plus the perp leg's 4.5 bps fee
and 1 bp half-spread — **15 bps a side, 30 bps a round trip**, both legs
taker. Gate 2 additionally requires the edge to survive `stressed(2.0)`: 60
bps a round trip. The perp fee is the public regular-user schedule and is
**unverified** against the account's own panel; the sandbox's 3× cost bar
is applied to the unverified number, which is the safe direction.

Funding is settled in gross at the archived daily sum; nothing here assumes
a rate that was not published.

## Benchmark

**Cash**: `--benchmark cash --risk-free fred`, the FRED DTB3 series
compounded per bar. This family holds nothing the market would; asking it
to beat a rising coin is the question Programme 1 asked of long-only books
and is not the claim here.

## Out-of-sample period

**The final 12 months of the available sample**, opened exactly once, after
gates 1–8 are complete. The trial log records the opening; a second open is
refused.

## What would falsify this

- Net Sharpe against cash below 0.5, or negative at 2× costs → gates 2–3.
- Deflated Sharpe below 0.90 over the 64 variants → gate 4.
- SPA *p* against cash above 0.5 → gate 5: the best variant did not beat a
  T-bill once the search was paid for.
- Funding received below 80% of gross → the mechanism is not the one named,
  whatever the Sharpe says; recorded as a fail of the prediction.
- Holdout Sharpe negative or below half the deflated Sharpe → gate 9.
- Forward incubation (gate 10) realised funding more than 5% below modelled,
  or fills more than 2 bps worse → the cost model was fiction.

## Prior

The most likely outcome, written down: **the family passes gates 2–5 and
the return is smaller than the paper's** — the paper's average carry
includes 2021, and the sample in the lake is dominated by years when funding
sat near its floor. A pass with a 3% net return is the expected result, and
the next question would be capacity and the exchange risk, not the edge.
