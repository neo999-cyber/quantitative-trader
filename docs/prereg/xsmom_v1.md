# Pre-registration: `xsmom_v1` — cross-sectional momentum, 12-1 convention

*Written 11 September 2026, before the first run.*

## Mechanism

The same gradual-information and flow-autocorrelation argument as time-series momentum, but applied *relatively*: the coins that have outperformed their peers continue to, for as long as the flows chasing them continue.

The cross-sectional version has one structural advantage over the time-series one in this context. It is **dollar-neutral in spirit even when long-only in practice**, because holding the best five of thirty is a bet on dispersion rather than on direction. That should reduce beta to BTC, which is precisely what I expect the time-series family to fail on.

The `skip` window is not decoration. The most recent stretch of any momentum window carries short-term *reversal*, which works against the signal; the standard equity formulation measures twelve months ending one month ago for exactly this reason. Crypto's natural scale is shorter, so `skip` is swept rather than assumed.

## Predicted sign and size

**Positive.** Annualised net Sharpe of **0.4 to 0.9** after costs — lower than the time-series family, because a weekly-rebalanced ranked book trades considerably more.

**Beta to BTC of 0.1 to 0.4**, materially lower than time-series momentum. Predicted alpha t-statistic: **above 2**, and unlike the time-series family I expect this one to have a genuine chance of clearing it.

Turnover is the risk here: ranking thirty names and holding five, rebalanced weekly, is a lot of trading at 19 bps a round trip.

## Universe

`binance_spot_top30`, identical to `tsmom_v1` and fixed before the run. Rebalanced monthly, 180-bar minimum history, delisted pairs included for as long as they traded.

## Horizon

Daily bars, weekly rebalance. The selection is held between rebalances rather than recomputed each bar — rebalancing a ranked book daily multiplies turnover by seven, and at these costs that alone decides the outcome.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` | 30, 60, 90, 120, 180, 252 (6 values) | yes |
| `skip` | 0, 5, 10, 21 (4 values) | yes |
| `n_long` | 3, 5, 8 (3 values) | yes |
| `rebalance` | 7, 14 (2 values) | yes |
| `vol_target` | 0.20 | fixed |
| `vol_lookback` | 30 | fixed |
| `max_leverage` | 1.0 | fixed |

**144 variants**, four swept parameters. Four is under gate 8's limit of five, but only just, and `n_long` and `rebalance` are structural choices rather than fitted ones — if the result depends sharply on either, that is a spike surface and gate 8 should say so.

## Cost model

`CostModel.trial()`: 9.5 bps per side, 19 bps a round trip, fee tier verified 11 September 2026. Gate 2 stress at 2×.

## Out-of-sample period

The final 12 months of the available sample, opened exactly once after gates 1–8.

## What would falsify this

- **Net/gross below 60%** → gate 2. This is the most likely failure mode for this family and the reason gate 2 runs third: a weekly-rebalanced ranked book in the most volatile names is where transaction costs go to eat returns.
- Deflated Sharpe below 0.90 over 144 variants → gate 4.
- PBO above 0.20 *with* the selection losing out of sample more than 10% of the time → gate 5.
- Alpha t below 2 → gate 8.
- Holdout negative → gate 9.

## Prior

I expect this family to have the **best chance of the four at gate 8** and the **worst chance at gate 2**. If it survives its own turnover, it is the most interesting of the four.

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
