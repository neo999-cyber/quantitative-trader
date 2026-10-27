# `p4_cot_crowding_v1` — CME positioning extremes as a timing input for the carry holding

*Drafted 27 October 2026 for the data-expansion programme (`docs/31` §15, candidate 2). **Not registered.**
Data in the lake: the CFTC Traders in Financial Futures files 2018–2026 (`mirror/cftc`, CME Bitcoin from 10
April 2018, ~440 weekly reports) and the carry units' daily funding (`raw/binance/carry-um`). Nothing read.*

## Mechanism

The leveraged-fund net short in CME bitcoin futures is, in the main, the basis trade: long the ETF or spot,
short the future, collecting the basis — the same yield the carry holding collects as funding on the perp. When
that short is at an extreme relative to its own history, the carry is crowded: the basis is bid down by the
crowd (less yield ahead), and in a sell-off the shorts cover in a rush (the funding and basis compress or flip).
So the positioning should say something about the *next month's funding*, which is what the holding earns.

This memo is a timing test for the holding, not a directional bet: `docs/20` found that timing funding on
funding itself added nothing over always-in (C1). CME positioning is a different input with a forced party —
the funds that must unwind when the basis closes.

## What can be known, and when

The CFTC publishes Tuesday's positions on Friday at 15:30 ET. The signal for a week is taken from the Friday
release, usable from 00:00 UTC on Saturday. No revision is applied afterwards (the files are read as released).

## Prediction

**Sign:** the next four weeks' BTC funding yield is *lower* when the leveraged-fund net short (as a share of
open interest) sits in the top decile of its trailing year, and the carry's net yield improves if the holding
steps out in those weeks — after paying the round trip (21.5 bps) each time it does.
**Size:** a sort of the ~440 weeks into crowded (top decile) and not: funding in the crowded decile 3–6
percentage points a year lower than the rest. Timing that pays after costs needs the step-outs to be rare: at
most eight a year.

## Universe

BTCUSDT carry unit (the holding under decision). ETH as a second arm (CME Ether from 2021, ~280 weeks),
reported but not pooled.

## Signal and horizon

`crowd_w = (Lev_Money_Short − Lev_Money_Long) / Open_Interest`, percentile over a trailing window. State
"crowded" when the percentile ≥ `p`. Horizon: the following four weeks of funding, and for the holding test a
rule "out of the carry while crowded, back in at the first week below `p`".

## Parameter grid

`p` ∈ {80, 90, 95} × window ∈ {26, 52} weeks: six runs. The sort test has no parameter beyond the decile.

## Cost model

The holding's round trip at the measured rates, 21.5 bps (spot 7.5 a side at VIP 0 with BNB, perp 3.23 a
side from stage 1), charged each time the rule steps out and back in. Frozen.

## Sample and period

**In-sample:** 10 April 2018 → 31 December 2024 (~350 weeks, two full funding cycles). **Holdout:** 1 January
2025 → 31 August 2026 (the lake's funding runs to 31 August), opened once. **Minimum sample:** 35 crowded
weeks in-sample at `p` = 90, else deferred.

## Controls

Always-in (the holding with no rule — `p2_funding_carry_v1_always_in` is the reference). Placebo: the
percentile series shuffled in blocks of 13 weeks. Mirror: step out when *un*-crowded.

## Gates

The sort: a difference in next-4-week funding with t ≥ 2 on non-overlapping four-week blocks. The rule: the
standard eight on the ledger engine against the always-in control (gate 5's comparator here is the holding
itself, not cash), DSR over six runs, placebo and mirror separated.

## What would falsify this

Crowded weeks no different from the rest (|t| < 2); the rule's net yield below always-in after its round trips;
the placebo matching; the effect living only in 2021–2022 (walk-forward fails on the other years). A failure
leaves the holding decision where it was — a yield with a tail, untimed.

## Build needed (none touches the data)

A CFTC TFF parser (the 2017–2026 zips are in the lake, `BITCOIN - CHICAGO MERCANTILE EXCHANGE` and the Ether
rows), a weekly feature joined to the carry unit at the Saturday availability time, a `Strategy` family
`CarryCrowdingTimer`, tests on synthetic weeks. About a day.
