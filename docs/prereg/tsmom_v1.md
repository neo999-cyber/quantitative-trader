# Pre-registration: `tsmom_v1` — time-series momentum, vol-targeted

*Written 11 September 2026, before the first run. Register with `qr trial prereg tsmom_v1 --file docs/prereg/tsmom_v1.md`.*

## Mechanism

Trends persist because information is absorbed gradually and because flows are autocorrelated: funds rebalance on a schedule, leveraged positions are liquidated in sequence rather than at once, and retail participation follows price with a lag. In crypto specifically, the absence of a fundamental anchor means price *is* the information, so the feedback loop is shorter and less damped than in equities.

This is the oldest and most widely replicated systematic effect in any asset class, which cuts both ways: it is unlikely to be spurious, and it is unlikely to be undiscovered. The expectation is a small edge, not a large one.

## Predicted sign and size

**Positive.** Annualised net Sharpe of **0.5 to 1.0** after the frozen cost model, with an annualised volatility near the 20% target and a maximum drawdown in the 25–40% range.

A net Sharpe above 1.5 on this family over this sample would be a reason to look for a bug, not to celebrate — see gate 1's implausibility check.

Beta to BTC is expected to be substantial (0.3–0.7): this is a long-only spot strategy in a market with one dominant factor. The claim that matters is therefore the **alpha t-statistic**, not the Sharpe. Predicted alpha t-statistic: **above 2**, and I expect this to be the binding constraint.

## Universe

`binance_spot_top30`: the top 30 USDT pairs by trailing 30-bar median quote volume, ranked point-in-time from the Binance bucket listing, rebalanced monthly, with a 180-bar minimum history. Delisted pairs are included for as long as they traded and leave the book at their last close.

Fixed before the run. Not to be narrowed to "the liquid ones" after seeing the result.

## Horizon

Daily bars. Positions are set at each bar's close and held over the next bar; effective holding periods run from weeks to months depending on the lookback.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` | 10 to 205 in steps of 5 (40 values) | yes |
| `skip` | 0, 2, 5, 10, 20 (5 values) | yes |
| `vol_target` | 0.20 | fixed |
| `vol_lookback` | 30 | fixed |
| `max_leverage` | 1.0 | fixed |

**200 variants.** This is the trial count gate 4 deflates against, and it is deliberately at the edge of what the sample supports: at an annual Sharpe of 1, the minimum backtest length for 200 trials is 2·ln(200) ≈ 10.6 years. The crypto sample is shorter than that, so gate 4 is expected to warn on minimum backtest length even if the deflated Sharpe clears. That warning is anticipated here rather than explained away later.

Widening either range after seeing results is a new hypothesis with a new id.

## Cost model

`CostModel.trial()`: Binance spot VIP0 with the BNB discount (7.5 bps taker), plus a 2 bps half-spread — **9.5 bps per side, 19 bps a round trip**. Fee tier verified against the account's own fee panel on 11 September 2026.

Gate 2 additionally requires the edge to survive `stressed(2.0)`: 38 bps a round trip.

## Out-of-sample period

**The final 12 months of the available sample**, opened exactly once, after gates 1–8 are complete. The trial log records the opening; a second open is refused.

## What would falsify this

- Net Sharpe below 0.25, or negative at 2× costs → gate 2 or 3.
- Deflated Sharpe below 0.90 over the 200 variants → gate 4. Given the sample length this is a live possibility.
- Alpha t-statistic below 2 against BTC → gate 8. **This is the outcome I consider most likely**: that the family earns its return by holding coins while coins went up, and has no alpha of its own.
- Median CPCV path Sharpe below 40% of in-sample → gate 7.
- Holdout Sharpe negative or below half the deflated Sharpe → gate 9.

## Prior

I expect this family to be the **most likely of the four to pass gates 1–7 and to fail gate 8 on beta**. That prediction is recorded here so that a pass on gate 8 is surprising rather than retrospectively obvious.

---

## Amendment, 12 September 2026 — the universe definition

**Made before any run of this hypothesis. Nothing had been backtested when this was written.**

The first real `qr data universe` over the full Binance bucket showed that ranking USDT pairs by quote volume promotes **stablecoins, fiat and tokenised commodities**. Over eight years USDCUSDT held a top-30 seat for 2,433 days, BUSDUSDT 1,354, EURUSDT 1,339, TUSDUSDT 1,037, FDUSDUSDT 943. On 2026-08-31 six of the thirty slots were pegs, fiat or gold. Binance's now-delisted leveraged tokens (`BTCUPUSDT`, `BTCDOWNUSDT`, `ETHUPUSDT`) also qualified.

They rank high because they are conversion rails, not because anyone speculates on them. A crypto strategy holding USDC is holding cash, and leaving those pairs in would hand this family a spurious risk-off skill — rotate into the peg during a drawdown and the equity curve flatters itself — that is an artifact of the universe rather than a property of the strategy.

`binance_spot_top30` therefore gains two filters, both fixed here before any result exists:

| Filter | Value | Why |
|---|---|---|
| Minimum annualised volatility | **15%**, over a trailing **90 bars**, point-in-time | Mechanical and self-maintaining. A peg runs near 1%, EUR near 8%; Bitcoin's calmest 90-day stretches still run 25–30%, so the threshold sits in a wide empty gap rather than just above what it excludes. |
| Excluded by name | `PAXGUSDT`, `XAUTUSDT`; any `*UP/DOWN/BULL/BEARUSDT` | Tokenised gold runs ~17% annualised and would clear the volatility floor, so no mechanical rule catches it. Leveraged tokens are daily-rebalanced derivatives with decay, not spot assets. |

Everything else in this document — mechanism, predicted sign and size, horizon, swept ranges, cost model, holdout, falsification criteria — is unchanged.

The volatility window is 90 bars rather than the 30 the volume ranking uses because a 30-bar estimate of an 8%-volatility asset reads above 10% often enough to admit EURUSDT for a month at a time, which it did on the first attempt.

This amendment is recorded rather than applied silently: the trial log will show two registrations for this hypothesis with different document hashes and **no run between them**. Gate 0 now fails any hypothesis re-registered *after* a run, and verifies that the registered hash still matches the document on disk.
