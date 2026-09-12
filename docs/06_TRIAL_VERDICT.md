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

## Confirmation run

**Status: pending.** The fixes are in and the engine's synthetic self-test still
holds — searched-over noise is still rejected at gates 4 and 5, the planted edge
still survives all nine — but the confirmation against real data has to run on
the laptop, since the sandbox cannot reach Binance.

First record the engine change in the trial log, so the log shows the fixes
landing *between* the two runs rather than alongside the second one:

```
for h in tsmom_v1 xsmom_v1 reversal_v1 rsi_reversal_v1; do
  qr trial note $h "engine fixes 1-4 (docs/07_ENGINE_FIXES.md) applied after the first run; re-running"
done
```

Then the run itself:

```
qr families --start 2018-01-01 --end 2024-12-31 \
            --holdout-start 2025-01-01 --permutations 100 --all-gates
```

Gate 6 now runs a second null, so expect it to take roughly twice as long as
the first run. `--vol-permutations 0` skips it.

The prediction, recorded here before it runs, so that it can be wrong:

- All four families still **FAIL**.
- The gate they stop at moves from 1 to **3** for all four.
- Gate 1 passes for all four, possibly with a QA warning on held symbols.
- Capacity rises by at least an order of magnitude for every family, and every
  one of them reports `capacity_extrapolated = true`.
- `reversal_v1`'s WFE lands somewhere in [−2, 2].
- Gate 6's two nulls differ by less than 0.2 in p for each of the four
  families, in a direction I am explicitly **not** predicting — six synthetic
  seeds split three-three. Neither null moves `tsmom_v1` off the 0th
  percentile, and neither takes any family below 0.05.

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
