# `p4_etf_flow_pressure_v1` — forced buying after US spot-ETF flow days

*Drafted 27 October 2026 for the data-expansion programme (`docs/31` §15, candidate 1); the rule made exact
the same evening and **registered on the owner's yes** — the first counter of Programme 4 (`docs/35`). The
family (`qr/strategies/etfflow.py`) and the instrument build (`qr/data/etfflow.py`) were written and tested on
synthetic fixtures before registration; no flow has been read against a price. The data: the issuer's own
daily share-count history (`reference/etf_flows_ishares_daily`, IBIT from 5 January 2024, refreshed daily on
the box) and the BTCUSDT USDⓈ-M perpetual's hourly bars with the venue's funding.*

## Mechanism

A US spot-bitcoin ETF creates shares for cash. On an inflow day T the issuer's trading desk buys the bitcoin
during and after US hours, and the shares settle T+1. The buyer is forced by the order, not by a view — the
named forced party `docs/31` §15 asks for. Flows are autocorrelated (inflow days cluster), so a large flow on T
says something about the buying still to come on T+1 and T+2. The hypothesis is that this buying moves the
price in the US session *after* the flow is known — and the honest prior is modest, because the same desks
hedge as they go and most of the flow's impact is contemporaneous with T.

## What can be known, and when (the point-in-time rule)

The issuer's workbook dates a creation by the NAV date on which the shares were issued, one session after the
trade date T on which the authorised participant placed the order and the desk bought the coin: the
aggregators' "flow of 12 October" is the issuer's row of 13 October (`docs/31` §18; the record day of 7
November 2024 sits on the 8th in the series). Call the row's date D = T + 1 session. The row is published
after D's close and the box reads it at 06:00 UTC the next morning, so **the flow of T is known to us on the
morning of the session after D — T + 2 sessions — and that is the tradable signal, the primary arm
(`timing = t2`).** Entry sessions follow the New York exchange calendar, public years ahead: the row of a
Friday enters on Monday, the row before a holiday on the session after it. Aggregators publish the flow of T
on the evening of T; the box records one (bitbo) from 15 October 2026 as a cross-check, so a T + 1 path exists
live but has no history. A **diagnostic arm (`timing = t1`)** acts on the issuer's row during D itself, as
that path would allow: it says whether anything exists at the faster horizon; it is a control sweep
(`p4_etf_flow_pressure_v1_t1`), not a candidate for the holdout or for money.

## Prediction

**Sign:** positive session return after large inflow days, negative after large outflow days.
**Size:** 10–20 bps per trade for the primary arm after a top-decile flow, if the mechanism is real at T + 2;
0–5 bps is the "contemporaneous only" world. The measured maker round trip is about 4.5 bps on weekdays
(2.2 a side, below), so a mean net edge under that is a failure whatever its t.

## Universe and instrument

BTCUSDT on Binance's USDⓈ-M perpetual — the instrument stage 1 measured its maker fill rate and fee on
(`docs/33`), and the one that carries both sides — executed as a maker. Funding is settled gross by the
ledger on the bar it is paid for; the 16:00 UTC settlement falls inside the session hold. IBIT flows only:
ETHA's series begins 18 February 2026 and its mean |flow| is $6M against IBIT's $163M, too thin by rule,
stated now. The instrument is the lake market `etfflow-um` (`qr data etfflow-build`): the perp's hourly
bars, the funding on the bar whose close is the settlement, and each issuer row's standardised flow on the
one bar a rule may act on it.

## Signal and rule

`z_D = flow_D / mean(|flow|)` over the sixty issuer rows before D, the row itself excluded, defined once
twenty rows exist; a flat day is z = 0 and never a trade. On the entry session the decision is taken on the
hourly bar that closes at **09:00 New York** (13:00 UTC in summer, 14:00 in winter): long when `z ≥ k`, short
when `z ≤ −k`, nothing otherwise. The order is a resting maker order at 09:00, before the cash open; the
position is held for the cash session — flat at the bar closing 16:00 New York, seven hourly bars — or for
24 hours. Entry sessions are at least a day apart, so one position is ever open; a new signal on the bar a
24-hour position ends is a hold, not a round trip. Weight 1.0 of the sleeve on the one symbol; the sleeve is
$200 at the stage-1 size.

## Parameter grid

`k ∈ {0.5, 1.0, 1.5}` × `hold ∈ {session, 24h}`: **6 variants** in the primary sweep (`timing = t2`), the
count gate 4 deflates. The diagnostic arm runs the same six at `timing = t1` as its own sweep, so twelve
variants are tried in all and are declared here. No other knob.

## Cost model

`CostModel.maker_measured(day_type="weekday")` — `qr gates --costs maker`: stage 1's weekday figures (96.0%
of resting orders filled inside the deadline, +0.50 bps adverse mark after the fill; the unfilled share taken
at the deadline at the taker fee and the half-spread), blended to about 2.2 bps a side, and the measured fill
rate as the haircut on the book. The weekday figures rather than the weekday/weekend blend because every entry
is a New York session (and the by-weekday haircut would re-scale a Friday 24-hour position at the Saturday
boundary). The forced cross at the end of a hold pays the same model's side. Frozen.

## Sample and period

**In-sample:** 11 January 2024 → 30 June 2026 (`--start 2024-01-11 --end 2026-06-30`); the issuer's series
begins 5 January 2024 and its first twenty rows define no z. **Holdout:** 1 July 2026 → 31 October 2026,
opened once, after gates 1–8 and only if they pass; the lake's perp bars end 31 August 2026 and are pulled to
31 October before it opens (public files, $0, no rule changes). It holds perhaps fifteen trades and is stated
as thin. **Forward:** the box's daily series from 1 November 2026, read monthly. **Minimum sample: 60 primary
entries in-sample at k = 1.0**, counted by the instrument build before the run
(`qr data etfflow-build --count-start 2024-01-11 --count-end 2026-06-30` — a count, not a read); fewer and the
read is deferred until the series is long enough.

## Controls — each its own registered sweep (`control = …`), the same grid

- **Placebo** (`p4_etf_flow_pressure_v1_placebo`): the standardised flows permuted among the entry bars within
  each calendar month, fixed seed — the same days and the same volatility, the flows on the wrong days.
- **Mirror** (`p4_etf_flow_pressure_v1_mirror`): the sides reversed.
- **Base rate** (`p4_etf_flow_pressure_v1_always_long`): long on every eligible entry session whatever the
  flow, session and 24-hour holds — what gate 5 compares against beyond cash.
- **The diagnostic arm** (`p4_etf_flow_pressure_v1_t1`): the six variants at T + 1, as above.

## Gates

The standard eight on the ledger engine (`--engine ledger`), benchmark cash (`--benchmark cash --risk-free
fred`, FRED DTB3). Gate 3 is the engine's HAC t on the hourly net series (its lag rule covers the seven-bar
hold): the engine fails below 2.5 and passes at 3.0 (`GateThresholds`); the memo's own falsifier below is
looser, and anything between is a WARN that does not pass. DSR ≥ 0.90 over the six variants, placebo and
mirror separated, SPA against cash, walk-forward on calendar years. A pass sends the $200 sleeve forward for a
month before any size change; the owner decides.

The run, once, counted:

    qr gates --family etf_flow_pressure --hypothesis p4_etf_flow_pressure_v1 --market etfflow-um --interval 1h \
      --basket btc --costs maker --engine ledger --benchmark cash --risk-free fred \
      --start 2024-01-11 --end 2026-06-30 --grid "k=[0.5,1.0,1.5]" --grid 'hold=["session","24h"]' \
      --param timing=t2 --upto 8

then the four control sweeps under their own hypothesis ids (`--param timing=t1`; `--param control=mirror`;
`--param control=placebo`; `--param control=always_long --param k=0 --param timing=t2`).

## What would falsify this

Mean net edge below the round trip; |t| < 2 with ≥ 60 entries; the placebo within one standard error of the
family; the mirror positive; the diagnostic arm positive while the primary is not (the effect is real but
faster than our data path — a data question, not a trade); the edge concentrated in fewer than five days.

## Build (done before registration, on fixtures)

`qr/data/etfflow.py` (the instrument: the perp's bars, `bar_funding`, `flow_z`, the New York entry calendar,
`flow_features`, `build_etfflow_lake` with its counts), `qr/strategies/etfflow.py` (`EtfFlowPressure` with the
hold, the two timings and the three controls), `qr gates --costs maker` and `--basket btc`, tests in
`tests/qr_platform/test_etfflow.py` on synthetic flows and bars. The real instrument is built after
registration; the run waits for the owner's yes.
