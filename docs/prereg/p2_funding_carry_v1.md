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
and a Binance USDⓈ-M perpetual (471 such symbols in the lake on 15 September
2026, delisted ones included) — ranked point-in-time by trailing 30-bar
median of the **thinner leg's** quote volume, top 40, rebalanced monthly,
180-bar minimum history. The exclusions of `tsmom_v1`'s amendment apply
unchanged, with one stated adaptation: the 15% annualised volatility floor
over 90 bars is measured on the **spot leg's price** (`spot_close`), not on
the unit's price, because the unit is spot / perp and never moves — the floor
exists to keep pegs and fiat out, which is a property of the coin. Tokenised
gold and leveraged tokens are excluded by name as before. A unit whose perp
is delisted leaves the book at its last close.

The exact invocation, in-sample:

    qr gates --family funding_carry --hypothesis p2_funding_carry_v1 \
      --market carry-um --costs carry --n 40 --min-history 180 \
      --benchmark cash --risk-free fred --end 2025-09-14 \
      --grid 'lookback=[3,7,14,30]' --grid 'entry=[0.05,0.10,0.15,0.20]' \
      --grid 'ceiling=[0.95,1.0]' --grid 'n_max=[5,10]' --upto 8

then once, with `--holdout-start 2025-09-15 --upto 11`. The universe name
the trial log records is `carry_top40`.

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

## Controls

Two, run beside the family and reported in the same table:

- **Always-in carry**: every eligible unit held at equal weight with no
  entry or exit rule. If the family does not beat this after its extra
  turnover, the entry rule adds nothing and the finding is "hold the carry,
  do not time it".
- **Hold T-bill**: the cash benchmark itself.

## Capital committed and stress

A unit of weight *w* commits *w* × equity to spot, the perp's initial
margin on the same notional, and an operating reserve of 20% of equity held
back for margin calls. Gate 11 sizes on that sum, so gross unit weight
cannot exceed roughly 0.6 at 5× perp margin. Gate 8 replays: funding
reversal (the rate flips sign for 14 days), basis widening (perp − spot moves
+3% in a day against the short), one leg filled and the other not (the
unmatched leg held for one bar at the coin's realised volatility), exchange
downtime (no exit for 3 days), auto-deleveraging (the short closed at mark
with no exit choice). Exchange failure is a named, unmodelled risk sized
outside the backtest: no more than 50% of equity on one venue.

## Benchmark

**Cash**: `--benchmark cash --risk-free fred`, the FRED DTB3 series
compounded per bar. This family holds nothing the market would; asking it
to beat a rising coin is the question Programme 1 asked of long-only books
and is not the claim here.

## Out-of-sample period

**From 15 September 2025 to the end of the sample** (the lake's last full
bar is 14 September 2026): in-sample is everything up to `--end 2025-09-14`,
the holdout is `--holdout-start 2025-09-15`, opened exactly once, after
gates 1–8 are complete. The trial log records the opening; a second open is
refused. Funding history on Binance's bucket begins in 2019–2020 depending
on the perp, so the in-sample period is roughly five to six years.

## What would falsify this

- Net Sharpe against cash below 0.5, or negative at 2× costs → gates 2–3.
- Deflated Sharpe below 0.90 over the 64 variants → gate 4.
- SPA *p* against cash above 0.5 → gate 5: the best variant did not beat a
  T-bill once the search was paid for.
- Funding received below 80% of gross → the mechanism is not the one named,
  whatever the Sharpe says; recorded as a fail of the prediction.
- Holdout Sharpe negative or below half the deflated Sharpe → gate 9.
- Incubation (gate 10, at least 63 daily observations): realised funding more
  than 5% below modelled, or fills more than 2 bps worse → the cost model was
  fiction.

## Prior

The most likely outcome, written down: **the family passes gates 2–5 and
the return is smaller than the paper's** — the paper's average carry
includes 2021, and the sample in the lake is dominated by years when funding
sat near its floor. A pass with a 3% net return is the expected result, and
the next question would be capacity and the exchange risk, not the edge.

## Amendment, 15 September 2026 — before registration, before any run

Recorded after `qr data carry-build` and the universe read, and before the
hypothesis was registered or run. Three facts were found; none changes the
rule, the ranges, the cost model or the benchmark.

1. **The sample ends on 31 August 2026, not 14 September 2026.** The
   bucket's funding archive is monthly, and its last complete month is
   August 2026, so the carry unit's last bar is 2026-08-31. The holdout is
   therefore 15 September 2025 to 31 August 2026 (about 11.5 months). The
   in-sample end (`--end 2025-09-14`) and the holdout start are unchanged.
2. **A builder defect, fixed before the universe was read.** The first
   `carry_frames` wrote the unit's `high` and `low` equal to its close while
   its `open` was spot-open / perp-open, so `Panel.tradable()`'s bracket
   check rejected nearly every bar and `carry_top40` read empty (median 0
   members a bar). The high and low are now the bracket of the unit's open
   and close, which are the only two prices of the unit that are observed.
   Test: `test_a_unit_whose_open_differs_from_its_close_is_still_a_tradable_bar`.
   The units were rebuilt (manifest hash `b96ecbb9…`) and read again.
3. **The universe read.** 471 units, bars from 2020-01-01. `carry_top40`
   holds 40 members every month from 2021 on (31 on 2021-01-04; 3 median in
   2020, when few perps had 180 bars); 194 symbols were ever members; no
   member-bar had spot volatility under the 15% floor; no peg, fiat,
   tokenised-gold or leveraged token appears. Mean perp funding of members,
   annualised (longs pay when positive): 2020 +23%, 2021 +38%, 2022 −6%,
   2023 +2%, 2024 +12%, 2025 −1%, 2026 (to August) −10%. The in-sample
   period contains both regimes, which is what the entry floor and the exit
   are for; the prior above stands.

No exclusion was added.
