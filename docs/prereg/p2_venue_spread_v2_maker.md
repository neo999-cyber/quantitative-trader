# Pre-registration: `p2_venue_spread_v2_maker` — the cross-venue funding spread, re-tested at the maker cost measured live

*Drafted 13 October 2026 on the owner's yes to a C2 re-test, before any
run. Not registered until the owner says so; it opens a new counter of
one. Everything below that is not the cost model is `p2_venue_spread_v1`
verbatim (`docs/prereg/p2_venue_spread_v1.md`, seq 624, FAIL at gates
3–8 on 17 September 2026; on the ledger, seq 932's comparison: net
Sharpe 0.54, gross 1.01, HAC t 1.50, cost drag 1.45%/yr, turnover
11.6×/yr). The unit panel, universe, rule, grid, controls, benchmark and
window are frozen as they were; the holdout stays shut.*

## What changed since v1, and what did not

v1 priced both legs taker: 12.5 bps a side, 25 a round trip, and its
verdict said the spread was real (funding 96% of gross), the selection
mattered (the always-in control lost), and there was not enough of it
after two taker legs: "reopen only with maker fills on both legs — a
different cost model that needs verified rebates and a fill assumption
this engine refuses to make". Stage 1 of the maker-fill study
(`docs/33`) has since **measured** the Binance leg: 1,169 live post-only
orders on the owner's account, 94.2% filled within 15 minutes (weekdays
96.0%, weekends 91.6%), fee 2.00 bps a side, a +1.06 bps adverse mark 60
seconds after the fill. That is the one new input; nothing else is new.
The Bybit leg has **no** measurement, and this memo does not invent one
for the claim.

## Cost model (the only change)

`--costs xvenue_maker` = `CostModel.carry_pair(CostModel.maker_measured(by_dow=True), CostModel.bybit_perp())`:

| leg | fee (bps a side) | spread / adverse (bps) | per side | source |
|---|---|---|---|---|
| Binance, measured maker | 2.17 (= 0.942 × 2.00 + 0.058 × 5.0) | 1.06 (= 0.942 × 1.06 + 0.058 × 1.0) | **3.23** | stage 1 live, `docs/33` |
| Bybit, taker (as v1) | 5.50 | 1.50 | **7.00** | published non-VIP schedule, unverified |
| unit | 7.67 | 2.56 | **10.23** (v1: 12.50) | |

Stress at 2× (20.5 bps a side), as v1's 50 bps was 2× its 25. Funding
gross at the archived rates; impact once on the thinner leg; cash
benchmark at FRED DTB3; capital, universe, horizon as v1.

**Fill-rate haircut.** The measured model carries its fill rate, and the
runner scales the unit's target weights by it — 0.9604 on weekdays,
0.9158 at weekends (`_FillHaircut`, the convention adopted for every
maker-priced family on 12 October; the unit inherits the product of its
legs' rates, 1.0 for the taker leg). It is conservative twice over — the
unfilled share is both not held and charged the taker fee — and is
applied as is.

**Extrapolation, stated.** The measurement is five alt names
(SUI/DOGE/ONDO/XRP/ADA), $10 orders, 15-minute windows, 07:00–15:00 UTC.
This book holds the forty largest names by the thinner leg's volume and
decides daily; the pooled numbers are applied to every name on every day
because that is the measurement that exists, not because the names match.

## Pre-stated sensitivity (one extra run, not the claim)

`p2_venue_spread_v2_maker_both`, `--costs xvenue_maker_both`: both legs
at the measured Binance model (6.46 bps a side; haircut 0.9224 weekdays,
0.8387 weekends). It assumes Bybit fills as Binance did, which nobody
has measured; it **cannot pass on its own** and is run only to answer
one question — whether a Bybit measurement would be worth its own stage.
Same grid, same panel, same controls; counted in the log; reported
beside the claim, never in its place.

## Predicted sign and size

Positive against cash; the predicted ranges are v1's, unchanged (net
return 2–8%/yr, net Sharpe 1–3, funding ≥ 80% of gross, drawdown < 5%).
The arithmetic of the change: cost drag 1.45%/yr × 10.23/12.50 ≈
1.19%/yr, about **+0.3%/yr of net return** over v1 on the ledger; the
sensitivity ≈ 0.75%/yr of drag, +0.7%/yr. The always-in control
`p2_venue_spread_v2_maker_always_in` is re-run at the new cost
(`--param entry=-1.0 --param exit=-2.0 --param ceiling=1.0 --param
n_max=80 --param lookback=7`, one variant).

## Rule, universe, grid, controls, statistics

As v1, verbatim: `FundingCarry` on `xvenue-um`, `carry_top40` (top 80
units), 90-day minimum history, 15% vol floor, lookback {3, 7, 14},
entry {0.05, 0.10, 0.20}, exit = entry/3, n_max {5, 10}, ceiling 1.0,
daily — **18 variants**, gate 4 deflates against them; ledger engine
(the default since 19 September), 2021-01-01 → 2025-08-31, cash
benchmark at FRED DTB3.

    qr gates --family funding_carry --hypothesis p2_venue_spread_v2_maker \
      --market xvenue-um --costs xvenue_maker \
      --n 80 --lookback 30 --min-history 90 --vol-lookback 90 \
      --benchmark cash --risk-free fred --start 2021-01-01 --end 2025-08-31 \
      --grid 'lookback=[3,7,14]' --grid 'entry=[0.05,0.10,0.20]' --grid 'n_max=[5,10]' \
      --param ceiling=1.0 --param rebalance=1 --all-gates --upto 8

## What would falsify this

v1's falsifiers, unchanged: net Sharpe below 0.5, or negative at 2×
costs (gates 2–3); `carry_share_of_gross` below 50%; the always-in
control within 0.3 Sharpe of the best variant; DSR below 0.90 over 18
(gate 4); SPA p > 0.5 against cash (gate 5); and, only if gates 1–8 pass,
the holdout 1 September 2025 → 31 August 2026 opened once, Sharpe
negative or below half the deflated Sharpe (gate 9).

**The hurdle, stated plainly.** Gate 5 compares the book's active return
with the **full** T-bill rate. The book is in the market about 30% of
the time and its idle margin sits on an exchange, where it earns
nothing, so that is the right hurdle for this owner; it is not relaxed
for a low-deployment book. 2021–2025's DTB3 averaged about 3%/yr.

## Prior

The measured cost takes 18% off the drag on the claim and 48% on the
sensitivity. Against v1's ledger numbers that moves net return by +0.3
and +0.7%/yr, net Sharpe from ~0.55 to ~0.65 and ~0.8, and the t from
1.5 towards 2.0 and 2.4. Gate 3 may clear on the sensitivity; gate 4
(DSR over 18) and gate 5 (a 2–3%/yr book against a 3%/yr T-bill, at 1×)
are expected to fail on both. **Honest expectation: FAIL at gates 4 and
5**, with the value of the run being a real number in the "what it
would take" line — whether the spread at this venue pair is short of
the bar by costs (then a Bybit measurement is the next step) or by its
own size (then C2 is closed at 1×, and leverage is a different
registration, not this one). Programme 2's counter goes to twelve
either way.
