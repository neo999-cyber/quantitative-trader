# `p4_etf_flow_pressure_v1` — forced buying after US spot-ETF inflow days

*Drafted 27 October 2026 for the data-expansion programme (`docs/31` §15, candidate 1). **Not registered.**
Registration needs the owner's yes and opens a new counter (Programme 4). The data it reads already sits in the
lake: the issuer's own share-count history (`reference/etf_flows_ishares_daily`, IBIT from 5 January 2024, refreshed
daily on the box) and Binance spot hourly bars. No line of either has been read against the other.*

## Mechanism

A US spot-bitcoin ETF creates shares for cash. On an inflow day T the issuer's trading desk buys the bitcoin
during and after US hours, and the shares settle T+1. The buyer is forced by the order, not by a view — the
named forced party `docs/31` §15 asks for. Flows are autocorrelated (inflow days cluster), so a large flow on T
says something about the buying still to come on T+1 and T+2. The hypothesis is that this buying moves the
price in the US session *after* the flow is known — and the honest prior is modest, because the same desks
hedge as they go and most of the flow's impact is contemporaneous with T.

## What can be known, and when (point-in-time rule)

The issuer's workbook dates a creation by the day the shares were issued (T+1) and publishes the row after
that day's close. Our box reads it at 06:00 UTC, so **the flow of day T is known to us at 06:00 UTC on T+2**.
That is the tradable signal and the primary arm. Aggregators (Farside, bitbo) publish the flow of T on the
evening of T; the box records bitbo's table from 15 October 2026 as a cross-check, so from then a T+1 path
exists live, but there is no backfill of it. A **diagnostic arm** uses T+1 timing on the issuer series to show
whether anything exists at the faster horizon; it is not eligible for the holdout verdict or for money.

## Prediction

**Sign:** positive US-session return after large inflow days, negative after large outflow days.
**Size:** 10–20 bps per trade for the primary arm after a top-decile flow, if the mechanism is real at T+2;
0–5 bps is the "contemporaneous only" world. The measured maker round trip is 6.5 bps, so a mean below that
is a failure whatever its t.

## Universe

BTCUSDT on Binance spot, executed as a maker (stage 1's measured fill rule). IBIT flows only: ETHA's series
begins 18 February 2026 and its mean |flow| is $6M against IBIT's $163M, too thin by rule, stated now.

## Signal and horizon

`z_T = flow_T / mean(|flow|, trailing 60 business days)`. Long when `z ≥ k`, short when `z ≤ −k`, entered at
13:00 UTC and held for the US session (13:30–20:00 UTC) or 24 hours. One position at a time; the sleeve is
$200 at the stage-1 size.

## Parameter grid (the trial count gate 4 deflates against)

Timing ∈ {T+2 primary, T+1 diagnostic} × k ∈ {0.5, 1.0, 1.5} × hold ∈ {US session, 24 h}: twelve runs, six
of them primary. No other knob.

## Cost model

`CostModel.maker_measured(by_dow=True)`, 3.23 bps a side (stage 1); the forced cross at the end of a TTL pays
the taker fee. Frozen.

## Sample and period

Issuer series 11 January 2024 → today: about 690 trading days; at k = 1 roughly one day in six fires, so ~110
trades in-sample. **In-sample:** 11 January 2024 → 30 June 2026. **Holdout:** 1 July 2026 → 31 October 2026,
opened once after gates 1–8 and only if they pass; it holds perhaps fifteen trades and is stated as thin.
**Forward:** the box's daily series from 1 November 2026, read monthly. **Minimum sample:** 60 primary trades
in-sample at the chosen k, else the read is deferred.

## Controls

Placebo: flows shuffled within calendar month (the day-of-week and vol structure kept). Mirror: the signs
reversed. Base rate: always long BTC in the US session over the same days (what gate 5 compares against
beyond cash). The T+1 diagnostic is a control on the mechanism's speed, not a candidate.

## Gates

The standard eight on the ledger engine, benchmark cash (DTB3): t ≥ 2 on clustered-by-week standard errors,
DSR ≥ 0.90 over the twelve runs, placebo and mirror separated, SPA against cash, walk-forward on the two
calendar years. A pass sends the $200 sleeve forward for a month before any size change; the owner decides.

## What would falsify this

Mean net edge below the 6.5 bps round trip; t < 2 with ≥ 60 trades; the placebo within one standard error of
the family; the mirror positive; the diagnostic arm positive while the primary is not (the effect is real but
faster than our data path — a data question, not a trade); the edge concentrated in fewer than five days.

## Build needed before the run (none touches the data)

A `Strategy` family `EtfFlowPressure` over an hourly BTCUSDT panel with the flow series joined at its
availability time (`qr/data/pit.py::asof_view`), a US-session bar aggregator, and tests on synthetic flows.
About a day. The run itself: one `qr gates` invocation, counted.
