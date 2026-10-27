# `p4_exchange_inflow_v1` — coins moving onto exchanges precede selling

*Drafted 27 October 2026 for the data-expansion programme (`docs/31` §15, candidate 3). **Not registered.**
Data in the lake: Coin Metrics community metrics (`mirror/coinmetrics/btc.csv`, exchange in/outflows from 24
April 2011 to 23 May 2026 — the mirror needs a free refresh to October before any run) and Binance spot bars.
Nothing read against prices.*

## Mechanism

A holder who moves coins from a private wallet to an exchange address has, more often than not, decided to
sell; the move is visible on-chain a day before the sale clears the book. Net exchange inflow (in minus out)
far above its recent norm should therefore precede selling pressure. The party is not forced; the claim is a
revealed intention, which is weaker than the other two memos and is said so here.

## The known defect of the data (stated before the run)

Coin Metrics labels exchange addresses with lists that are revised over time; the historical series is computed
with today's labels. That is a look-ahead in the *labelling*, not in the prices — a flow that was unknown as an
exchange flow at the time may count now. A pass in-sample is therefore necessary, not sufficient: the forward
read on the box's daily refresh is the real test, and the memo says so now rather than after a result.

## What can be known, and when

Coin Metrics publishes day d's metrics the next day; the signal for day d is usable from 12:00 UTC on d+1.

## Prediction

**Sign:** negative BTC return after days of extreme net inflow; positive after extreme net outflow (the mirror
is the long side and is run as its own arm, not pooled).
**Size:** −15 to −40 bps over the following three days after a 2σ inflow day, if real; the round trip is 6.5 bps.

## Universe

BTCUSDT on Binance's USDⓈ-M perpetual as a maker, both sides — the instrument the fill rule and the fee were
measured on (`docs/33`), and the one that carries a short without a borrow; funding over the hold is settled
gross by the ledger (a short receives a positive rate). ETH as a second arm from Coin Metrics' `eth.csv`,
reported separately.

## Signal and horizon

`net_d = FlowInExNtv_d − FlowOutExNtv_d`, standardised over a trailing 90-day window. Short when `z ≥ k`,
hold `h` days, then exit at the touch (cross at the end of a TTL as in stage 1). One position at a time.

## Parameter grid

`k` ∈ {1.0, 1.5, 2.0} × `h` ∈ {1, 3, 7} days: nine runs per side.

## Cost model

`CostModel.maker_measured(by_dow=True)` (`qr gates --costs maker` once a daily-bar variant of it exists;
entries fall on any weekday, so the weekday/weekend blend), 3.2 bps a side; the short's carrying cost is the
perp's funding over the hold, settled gross. Frozen.

## Sample and period

**In-sample:** 17 August 2017 (Binance bars begin) → 31 December 2023. **Holdout:** 1 January 2024 → 23 May
2026 (the mirror's end; extended to the refresh date before the run, stated here). **Minimum sample:** 80
signal days in-sample at `k` = 1.5, else deferred.

## Controls

Placebo: the flow series shifted by 180 days. Mirror: the long side after outflows, as above. Base rate: short
BTC on random days with the same count and holding period (the trend of the sample is what this controls for —
BTC rose over the in-sample years, so a short strategy carries a negative drift to overcome).

## Gates

The standard eight on the ledger engine against cash, DSR over nine runs, placebo and mirror separated,
walk-forward by year, the random-day control. A pass goes forward on the box's refreshed series for two months
before any money; the labelling defect above is why.

## What would falsify this

|t| < 2 with ≥ 80 signal days; the placebo or the random-day control within one standard error; the effect only
in 2017–2018 (the walk-forward fails on later years, which is the most likely outcome: the signal is widely
published and the data vendors sell it); the forward read disagreeing with the in-sample after a pass.

## Build needed (none touches the data)

A Coin Metrics community loader with the publication-time rule, a refresh of the mirror to today (free), a
`Strategy` family `ExchangeInflowFade`, tests on synthetic flows. Half a day.
