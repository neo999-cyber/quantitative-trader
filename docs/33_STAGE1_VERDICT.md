# Stage 1 verdict — the maker cost, measured live (2–11 October 2026)

*One page. The study is `docs/24` (decision rule fixed 15 September), the scope `docs/27`, the day-by-day
log the dated entries of `docs/20`, the day reports `reports/stage1/`, the model
`CostModel.maker_measured` (`qr/execution/costs.py`).*

## The rule, and the result

**Rule (docs/24):** the live 15-minute fill probability must be within **10 points** of stage 0's tape
replay (96.3%), or the tape model is wrong and the study stops. **Result: 94.2% — PASS.** 1,169
post-only orders under $10 on SUI, DOGE, ONDO, XRP and ADA, ten daily sessions of 32 slots on Binance
USDⓈ-M, the owner's account, 11:00–19:00 Dubai; day 1 from the laptop, days 2–10 unattended on the
Hetzner box under a standing mandate.

| | tape (stage 0, 14 days) | live (stage 1, 10 days) |
|---|---|---|
| orders | 52,780 virtual | 1,169 real |
| filled within 60 s / 300 s / **900 s** | 83.8% / 93.2% / **96.3%** | 80.1% / 91.1% / **94.2%** |
| wait to fill, quantiles 25/50/75/90 (s) | 1 / 3 / 18 / 84 | 2 / 9 / 31 / 104 |
| adverse mark at +5 s, median (bps) | +0.98 | +1.01 |
| **adverse mark at +60 s, median / mean (bps)** | **+0.92 / +0.72** | **+1.06 / +0.86** |
| adverse mark at +300 s, median (bps) | +0.84 | +1.75 |
| maker fee, per side | 2.0 bps (schedule) | **2.00 bps** (1,101 round trips, statement) |

By side: buys 94.5%, sells 93.9%. By name: 92.7% (ADA) to 95.9% (SUI). By day: 100, 88, 96, 90, 98, 94,
99, 97, 93, 88 — **weekdays 96.0%, weekends 91.6%**. By hour: 90–97%, weakest 12:00 UTC. 122 post-only
orders were rejected because they would have crossed (a moving market); 235 entries were refused by the
harness's own guards (the $50 gross cap with five $10 names, a stale mark, the cash reservation) — never
placed, so not in the fill rate. Exits: 1,050 maker exits filled, 239 re-posted, **one** taker close in
ten days (the netting of the next slot's opposite order did most of the closing).

**Money:** wallet $98.14 → $91.77, **−$6.37** of the $25 budget on $21,358 traded: $4.27 of fees and
$2.10 of price movement against the fills — **5.8 bps a round trip realised**, 4.0 of them fees.

## What the tape got right and what it hid

The averages held: fills a few points lower than the replay, waits a few seconds longer, the 60-second
mark within 0.15 bps. The replay's queue model — behind the whole displayed size, consumed by prints only
— was called a floor in `docs/24`; live it was slightly kind, as a floor can be when hidden queue and
latency are real. What the tape could not show was the **spread between days**: 88% on a Saturday with a
market running away from the bids, 99% on a quiet Thursday. A strategy's fills depend on the day it needs
them, and the days it most needs a fill are the days it gets fewer.

## The cost model

`CostModel.maker_measured()`: per side, the filled share (94.2%) pays the maker fee and the measured
adverse mark; the unfilled share (5.8%) is assumed taken at the deadline and pays the taker fee and the
half-spread — the conservative reading `docs/24` fixed in advance. **3.2 bps a side, ~6.5 bps a round
trip**, against the 8 bps the Programme 2 families were judged on and the 13 bps a taker round trip
costs. The model carries `fill_rate = 0.942`, by which a maker family's signal is to be haircut (a unit
open 30% of the time at 100% fills is open less at 94%); wiring that haircut into the runner is part of
any re-registration, not done yet.

## What it changes, and what it does not

- **C2** (the cross-venue spread) failed Programme 2 **on costs**. Against 6.5 bps instead of 8 it is the
  one family worth one more registered look — `_maker` suffix, the same gates and falsifiers plus the
  fill-rate haircut, and the added falsifier of `docs/24`: the haircut must leave the net Sharpe above 1.
  That is a decision for the owner, with a new counter.
- **C1's always-in funding carry** was never cost-bound; its entry and exit now have a measured price.
  Whether to hold it is a question for the yield ladder (`docs/31` §13), not a hypothesis.
- **The main finding stands.** Cheaper execution makes a real edge tradeable; it does not make one. No
  family failed by 2 bps.

## Operations, for the record

Ten sessions, $21k of notional in $10 pieces, every day closed flat, journal and venue agreeing to the
cent, nine of the ten days from a server with no one watching. Day 1 exposed three shutdown defects (an
interrupted close, a partial taker close, `status` pausing a session), each fixed and rehearsed on the demo
exchange the same evening. The last morning the timer fired after the mandate had ended, was refused,
ran the close-on-failure unit (flat) and sent the alert it was built to send. **The timers are still
enabled and should be disabled by the owner** (`systemctl disable --now qr-stage1.timer
qr-stage1-summary.timer`); the live key stays trade-only, withdrawal-off and IP-locked to the box.

## Addendum, 12 October — two refinements of the model

- **Day type.** Weekdays filled 96.0% with a 60-second mark of +0.50 bps; weekends 91.6% and +1.76 bps.
  `CostModel.maker_measured(day_type="weekday" | "weekend")` carries each, and `by_dow=True` gives the
  runner a haircut that follows the calendar (`fill_rate_by_dow`).
- **The tape, calibrated.** On the five names traded, live fills ran 3.5 points below the tape with a
  spread of under one point between names, and the mark 0.3 bps above it — a correction steady enough to
  apply to the fifteen tape names never traded live (`CostModel.maker_measured_for(symbol)`, table in
  `reports/stage1/tape_calibration.md`: BTC 93.9%, ETH 94.4%, SOL 94.2%, down to BEAT 82% and XAUT 76%).
  This is what a C2 re-test would price each name with.
- **The runner applies the haircut** (`_FillHaircut`): a maker family's exposure is scaled by the measured
  fill rate, per weekday when the model carries one, while the model's blended fee already pays the
  deadline take for the unfilled share — both, as `docs/24` fixed in advance.
