# Pre-registration: `p2_funding_carry_v2` — funding carry on hourly bars

*Written 16 September 2026, before any run of this hypothesis. Successor to
`p2_funding_carry_v1`, whose in-sample run on 15 September 2026 stopped at
gate 1 (gross Sharpe 9.7 on daily closes, above the engine's 8.0
plausibility ceiling) while passing gates 2–8. Nothing in v1's rule, cost
model, benchmark, universe or ranges is loosened here; what changes is the
resolution the unit is priced at, which is the change `docs/20` §2 (cause
5.3) prescribes for the whole programme.*

## Why a v2, stated before the run

The v1 leak hunt found no leak: the three lags agree (9.9 / 9.7 / 9.2),
funding is credited to the day it settled, the large basis prints are real
events. The number is what a daily-close series of spot / perp produces —
a unit whose close-to-close vol is ~1.5% a year against ~10–30% a year of
persistent funding. What daily closes cannot show is the basis moving
inside the day, the eight-hour settlement landing on the bar the position
had to be held for, and the hours where a leg is thin. On hourly bars a
member unit's return vol is ~7% a year (p90 17.5%; read from the hourly
`carry-um` panel on 16 September 2026 before this document was written and
before any strategy was run on it). The test of the mechanism is therefore
re-run at that resolution, with the same rule.

A second reason: v1 ran on a book loop that, whenever fewer than `n_max`
units cleared the entry floor, filled the spare room with the
alphabetically first *non-qualifying* units (found on 16 September while
vectorising the loop; `test_a_bar_with_fewer_qualifying_units_than_room_holds_only_those_units`).
v2 runs on the corrected loop. v1's report stands as recorded; it is not
re-run.

## Mechanism, sign and controls

As `p2_funding_carry_v1` §Mechanism: leveraged longs pay funding; long spot
/ short perp collects it with no directional exposure; a high carry
predicts crashes (BIS WP 1087), hence the entry floor and the ceiling.
Positive against cash. Controls: the always-in carry book
(`FundingCarry(entry=-1.0, exit=-2.0, ceiling=1.0, n_max=40)`) on the same
hourly panel, registered as `p2_funding_carry_v2_always_in`; and hold
T-bill, the benchmark itself.

## Predicted sign and size

Net of the frozen cost model, in-sample:

- annualised net return **4% to 12%**, annualised volatility **3% to 8%**,
  net Sharpe **1 to 3** against the 3-month T-bill;
- gross Sharpe **below 8**; if the hourly unit still reads above the
  engine's ceiling the mechanism has not been shown at this resolution
  either and the family stops there, as v1 did;
- funding received **at least 80%** of gross (`carry_share_of_gross`, now in
  every report);
- maximum drawdown **under 10%**.

## Data and unit

`carry-um` at interval `1h`: spot 1h bars (471 both-leg symbols), USDⓈ-M
perp 1h bars, and funding at settlement level from the bucket's
`fundingRate` files. A settlement at time T is assigned to the bar that
closes at T — the bar a position had to be held over to be paid — and the
other bars carry zero inside the settlement history
(`qr.data.funding.bar_funding`). The unit's price is spot / perp per hour;
high and low bracket its open and close; volume is the thinner leg's quote
volume in the unit's price space. Sample: 2020-01-01 to 2026-08-31 (the
funding archive's last complete month).

## Universe

`carry_top40` as in v1, with the windows in hourly bars: trailing 720-bar
(30-day) median of the thinner leg's quote volume, top 40, rebalanced
monthly, 4,320-bar (180-day) minimum history, 15% annualised volatility
floor over 2,160 bars (90 days) on `spot_close`. Read on 16 September
before this document: 40 members a bar from 2021, 170 ever. No exclusion
added.

## Rule and parameters

Decisions **once a day at 00:00 UTC** (`rebalance=24` bars); the book is
held through the other 23 bars and earns their returns and settlements.
`lookback` is the trailing window of hourly bars whose funding is averaged
and annualised by 8,760; the ceiling's percentile is of the signal at
decision bars over the trailing 365 decisions (v1's daily definition).

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` (hourly bars) | 72, 168, 336, 720 (= v1's 3, 7, 14, 30 days) | yes |
| `entry` (annualised funding to open) | 0.05, 0.10, 0.15, 0.20 | yes |
| `exit` | entry / 3 | tied |
| `ceiling` | 0.95, 1.00 | yes |
| `n_max` | 5, 10 | yes |
| `rebalance` | 24 | fixed |
| `percentile_window` | 365 decisions | fixed |

**64 variants**, the same grid as v1. Gate 4 deflates against them.

Exact invocation, in-sample:

    qr gates --family funding_carry --hypothesis p2_funding_carry_v2 \
      --market carry-um --interval 1h --costs carry \
      --n 40 --lookback 720 --min-history 4320 --vol-lookback 2160 \
      --benchmark cash --risk-free fred --end 2025-09-14 \
      --grid 'lookback=[72,168,336,720]' --grid 'entry=[0.05,0.10,0.15,0.20]' \
      --grid 'ceiling=[0.95,1.0]' --grid 'n_max=[5,10]' \
      --param rebalance=24 --param percentile_window=365 --all-gates --upto 8

then once, `--holdout-start 2025-09-15 --upto 11`, opened only if gates
1–8 pass. The universe name the log records is `carry_top40`.

## Cost model, benchmark, capital, stress, falsifiers

Unchanged from v1: `CostModel.carry_pair` (15 bps a side, 60 bps a round
trip stressed), funding gross at the archived rate; cash benchmark at FRED
DTB3; capital committed = spot notional + perp margin + 20% reserve; the
gate-8 stress list; the falsifiers of v1 with the gross-Sharpe line above
added. The holdout is 15 September 2025 to 31 August 2026.

## Prior

**The family passes gates 1–8 with a net Sharpe between 1 and 3**, and
the interesting number is the drawdown across the March 2020, May 2021,
May 2022 and November 2022 bars, which daily closes smoothed over.
