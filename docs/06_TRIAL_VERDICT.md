# The verdict: all four families fail

*Written 12 September 2026, after the first run against real Binance data.*

The one-week trial had a decision rule, written on 11 September before any code
existed and before any data had been pulled:

> - **≥1 family passes gates 1–8 with positive holdout Sharpe** → start paper
>   trading it that week; spend the $1,000.
> - **All fail** → do not spend. Run the ETF-basket trial next ($0). The
>   failure itself is the platform working.

Four families, 425 variants, eight years of Binance spot bars, ten gates each.
**Nothing passed. Do not spend the $1,000.**

## What was run

| | |
|---|---|
| Data | Binance public bucket, 734 USDT pairs, 55,476 files, checksums verified |
| Universe | `binance_spot_top30`, point-in-time, volatility-floored |
| In-sample | 2018-01-01 → 2024-12-31 |
| Holdout | 2025-01-01 onward, untouched until gate 9 |
| Costs | VIP0 + BNB, 9.5 bps/side, verified against the account's own fee panel |
| Permutations | 100, with re-optimisation over a 25-variant subgrid |

## The result

| hypothesis | variants | verdict | best IS Sharpe | net/gross | round trips | holdout Sharpe |
|---|---|---|---|---|---|---|
| `tsmom_v1` | 200 | **FAIL** | 0.749 | 0.831 | 2,593 | −0.55 |
| `xsmom_v1` | 144 | **FAIL** | 0.573 | 0.941 | 351 | −0.82 |
| `reversal_v1` | 54 | **FAIL** | 0.421 | 0.877 | 923 | −0.39 |
| `rsi_reversal_v1` (control) | 27 | **FAIL** | 0.695 | 0.948 | 173 | WARN, 17% retained |

## The single cleanest finding

Gate 5 runs Hansen's SPA against buy-and-hold of the same universe:

| family | SPA p |
|---|---|
| `tsmom_v1` | 0.890 |
| `xsmom_v1` | 0.898 |
| `reversal_v1` | 0.910 |
| `rsi_reversal_v1` | 0.830 |

**Not one of 425 configurations beats holding the basket.** Everything below is
commentary on that one line.

Three independent gates agree with it. Gate 3: HAC t-statistics of 1.93, 1.46,
1.08 and 1.89, all below the 2.5 floor and all below the 2.0 that would be
conventional significance before any multiple-testing correction. Gate 4:
deflated Sharpe ratios of 0.78, 0.50, 0.51 and 0.60 against a 0.95 requirement.
Gate 9: the holdout, which none of the three real families survived.

And the number that settles it. The engine's own synthetic self-test searches
200 variants over **pure noise** and reports the best it finds: Sharpe
**1.058**. Searching 200 momentum variants over seven years of real Binance
data produced **0.749** — a worse winner than the same search over a random
number generator. That is not a strategy failing to clear a bar. That is a
search finding less than it would have found in nothing.

## Scoring the pre-registrations

The verdicts were mostly right. **The reasons were wrong almost every time**,
and that is the more useful half of the record.

| registered prediction | outcome | |
|---|---|---|
| `tsmom` Sharpe 0.5–1.0 | 0.749 | ✅ |
| `tsmom` beta to BTC 0.3–0.7 | 0.21 | ❌ |
| `tsmom` "most likely to pass 1–7, fail gate 8 on beta" | failed gate 3 | ❌ |
| `xsmom` best chance at gate 8, worst at gate 2 | exactly backwards: gate 2 kept 94%, gate 8 gave alpha t = 0.21 | ❌ |
| `xsmom` beta 0.1–0.4, lower than time-series | 0.21 — same as `tsmom`, not lower | ➖ |
| `reversal` net/gross may fall below the 60% floor | 87.7% | ❌ |
| `reversal` beta near zero or negative | 0.21 | ❌ |
| control fails | it failed | ✅ |
| control "fails gate 8 on trade count, not return" | 173 round trips, passed the count, failed on significance | ❌ |

Three things are worth extracting.

**My cost predictions were systematically wrong, in one direction.** I expected
transaction costs to be the binding constraint for two of the four families.
Gate 2 passed comfortably for all four: 83% to 95% of gross return survives. At
9.5 bps a side on daily bars, costs are simply not the problem. The problem is
that there is nothing for them to erode. I had the mechanism of failure
backwards — I was picturing a real edge eaten by friction, and what is actually
there is no edge and very little friction.

**The control failed for the wrong reason, and the wrong reason is informative.**
I predicted the three-down-days-on-volume condition would almost never coincide
with RSI below 30, because on 900 bars of random walk they coincided zero times.
On real crypto they coincide 173 times over seven years, comfortably above the
50-round-trip floor. Crypto sells off harder and more persistently than a random
walk does, so the conjunction is not rare there. My prior came from a simulation
whose tails were too thin, which is exactly the error the whole apparatus exists
to catch when it happens to a strategy — and it happened to me, in a document I
had signed.

**One prediction held together unusually well.** All three vol-targeted
families report beta to BTC of 0.21, to two decimal places. That is not a
coincidence and not a bug: a 20% volatility target divided by BTC's ~55%
realised volatility, times the family's correlation to it, produces about that
number arithmetically. The vol targeting is doing precisely what it says on the
tin. It is the one component of the stack the run positively confirms.

## What I do not trust, and why it does not change the answer

Four defects surfaced in the reports. All four are now fixed
(`docs/07_ENGINE_FIXES.md`); none of them touches the verdict.

1. **Gate 1 failed all four families on data they were never served.** It ran
   QA over each symbol's full history including the six corrupt bars that
   `Panel.tradable()` had already withheld from the strategy. The platform was
   blaming a strategy for bars it had itself refused to serve. This is why every
   family reads `stopped_at = 1`.
2. **The capacity figures were nonsense.** `tsmom` reported $10,000 for a book
   trading pairs that turn over nine figures a day, because the square-root
   impact law was being extrapolated a thousandfold below the participations it
   is fitted over and charging basis points of "impact" for orders smaller than
   the spread — which `linear_bps` had already charged.
3. **Gate 6's p = 1.000 is not a clean statement about timing.** Permuting bars
   destroys volatility clustering as well as time ordering, and all three real
   families are vol-targeted, so the observed statistic contains a
   volatility-management premium that the null has been stripped of. Measured
   on six synthetic worlds, the choice of null moves the p-value by about 0.2 —
   enough to cross gate 6's own pass/fail boundary — in **either** direction,
   which is not what I predicted when I flagged it. It does not move a p of
   1.000.
4. **`reversal_v1`'s walk-forward efficiency of 13.62** — a strategy thirteen
   times better out of sample than in — was a near-zero denominator, not a
   finding.

The verdict rests on gates 3, 4, 5 and 9: four tests resting on different
assumptions, agreeing across four strategies, with an untouched holdout
confirming out of sample. Defect 1 changes which gate the run *stops* at.
Defects 2 and 4 are numbers in the report that nothing was decided on. Defect 3
makes one gate's number less certain than it looked, by an amount far too small
to reach the value it actually reported. Nothing here rescues a family whose
best variant loses to buy-and-hold with p = 0.89 and then loses money out of
sample.

That is also the reason to fix them anyway. A platform whose entire claim is
that it reports honestly cannot carry four numbers that mean something other
than what they say, and the time to fix them is when nothing is riding on them.

## Confirmation run — done, 12 September 2026

Re-run against the same lake after the four engine fixes, same window, same
100 permutations. **All four families FAIL again, and all four now stop at gate
3 rather than gate 1.**

| hypothesis | verdict | stopped_at | gate 1 | gate 7 WFE | capacity |
|---|---|---|---|---|---|
| `tsmom_v1` | FAIL | 3 | WARN | 1.18 | $30,000 |
| `xsmom_v1` | FAIL | 3 | WARN | 0.65 | $1,000,000 |
| `reversal_v1` | FAIL | 3 | WARN | −0.64 | $100,000 |
| `rsi_reversal_v1` | FAIL | 3 | WARN | 0.47 | $30,000 |

Every number the verdict rests on is **unchanged**: HAC t of 1.93, 1.46, 1.08,
1.89; DSR of 0.78, 0.50, 0.51, 0.60; SPA p of 0.890, 0.898, 0.910, 0.830. The
fixes moved what they were supposed to move and nothing else, which is the
result a confirmation run is for.

### Scoring the predictions written before it ran

| prediction | outcome | |
|---|---|---|
| all four still FAIL | all FAIL | ✅ |
| the stop moves from gate 1 to gate 3 | 3 for all four | ✅ |
| gate 1 passes or warns | WARN for all four | ✅ |
| `reversal_v1` WFE inside [−2, 2] | −0.64 | ✅ |
| capacity up **an order of magnitude**, every family | 3x for two families, unchanged for two | ❌ |

**The capacity prediction was wrong and it corrects something I wrote.**
`docs/07_ENGINE_FIXES.md` claimed the spread double-count "is what made the
first capacity estimate read $10,000". Removing it moved `tsmom_v1` from
$10,000 to $30,000 and moved `xsmom_v1` and `reversal_v1` not at all. So the
double-count was real, the fix is correct, and it accounted for roughly one
ladder rung rather than the bulk of the figure. What governs the level is
`impact_coef = 1.0` against crypto's daily volatility — the uncalibrated number
the reported band exists to express. I fixed a real defect and then overstated
how much of the symptom it explained, which is its own kind of error: the fix
was measured, the attribution was not.

### Gate 9 could not be re-run, by design

All four report *"the holdout was already opened on 2026-09-12T06:01; it is not
a holdout any more."* That is gate 9 doing its job — a holdout opened twice is
not a holdout — and it means this run's gate 9 is **bookkeeping, not evidence**.

The oversight is mine: I recommended the re-run with `--all-gates` knowing gate
9 consumes the holdout on first contact, and did not say so. The first run's
holdout Sharpes of **−0.55, −0.82 and −0.39** remain the only legitimate
reading of that period, and nothing in the four fixes touches how they were
computed. But a future family gets exactly one shot, and a confirmation re-run
must in general be capped with `--upto 8`.

### One finding the fixes uncovered

`rsi_reversal_v1` gate 1 now warns that its Sharpe **peaks at the reported lag,
5.88x its neighbours**. That was invisible in the first run because gate 1
returned on the QA failure before reaching the lag probe — so fixing gate 1 did
not only unblock four families, it surfaced something the old gate had been
hiding. A spike that size on a strategy pre-registered as having no edge is the
signature of a look-ahead inside `RSIReversal`, and it is open: it needs
answering in the trial log or in the code, not shrugging at. It does not change
the control's verdict, which failed gates 3 through 8 on its own merits.

## The decision

**Do not spend the $1,000.** Per the rule agreed on 11 September, the next step
is the ETF-basket trial, which costs nothing.

The useful thing to say about a week that ended in four failures is what it
bought. It bought a data layer that found two genuine corruptions in Binance's
published archive, and a universe definition that caught itself quietly seating
stablecoins in a crypto top-30. It bought a validation engine that rejects
searched-over noise, that has found a bug in itself at every stage including
this one, and that has now said no to four strategies — including one whose
pre-registered prediction it had to score as wrong in five places, and a
methodological complaint about gate 6 that it had to withdraw twice before
measuring what was actually there.

An engine that had said yes to any of these would have been worth less than
nothing, because the $1,000 would have followed.
