# The maker-fill study — a proposal, nothing sent

*17 September 2026. Written for the owner's decision. No order has been
placed; no key is used by anything in this document. Fees quoted are the
venues' published schedules as read on this date and are marked unverified
until seen on a statement.*

## Why

Two Programme 2 mechanisms are real and untradeable at taker costs:

| | what it pays | taker round trip (two perp legs) | days to break even |
|---|---|---|---|
| C1 funding carry (always-in, hourly unit) | Sharpe 2.4 net, funding 97% of gross | ~15 bps (spot + perp) | — it passes costs; it fails gate 6 as a *timing* rule, not as a holding |
| C2 cross-venue spread (best variant) | 2.7 bps a day when open | ~25 bps | ~9 |

A maker order pays the lower fee and does not cross the spread. Published
schedules: Binance USDⓈ-M regular tier maker 2.0 bps / taker 5.0 bps
(1.8 / 4.5 with BNB); Bybit non-VIP linear maker 2.0 / taker 5.5. With
both legs made, C2's round trip falls from ~25 bps to **~8 bps plus
whatever the wait costs** — both figures per one leg's notional (the
taker: 2 × 5 + 2 × 5.5 = 21 bps of fees plus two spreads; the maker:
2 bps × two legs × two sides; per two-leg gross notional halve both).
Until 18 September 2026 this line read "~4–5 bps", which was the maker
figure on the gross denominator against the taker figure on the one-leg
denominator — caught by the independent scope review (`docs/27`). The
engine charges it the 8-bps way (`CostModel.carry_pair` sums both legs'
fees on unit turnover), so no reported number moves; C2's break-even
falls from ~9 days to ~3. The wait cost is the unknown this study
measures. Nothing else in the programme changes: same units, same gates,
same 3× bar — only the cost model, and only after it is measured.

## What is unknown, precisely

A resting order fills only when the market comes to it. Three things
decide the cost of that:

1. **Fill probability within a deadline** — P(fill | post at best, wait T).
2. **Adverse selection** — the fills you *do* get skew toward moments the
   price is moving through you; the average fill is worse than the quote.
3. **Time cost** — while unfilled, the leg you already have on is
   unhedged (for a two-leg unit), and the funding you were chasing may
   have settled without you.

A backtest that sets (1) to 100% and (2), (3) to zero is the assumption
the engine refuses. The study replaces the assumption with a number.

## Stage 0 — no orders, $0: replay the tape

Before any order, the same question can be asked of recorded data. Binance
and Bybit both stream the best bid/ask and every trade over public
websockets (no key). A recorder on the Hetzner box (standard library, like
the flow collector) writes, for ~20 symbols on each venue:

- `bookTicker`: best bid, best ask, sizes, every update;
- `aggTrade`: every print with side and size.

From this a **virtual post-only order** is simulated honestly: placed at
the best bid at time t, it is filled when cumulative *sell* prints at or
below that price since t exceed the size that was queued ahead of it (the
displayed size at placement — a conservative queue model), or cancelled
at t + T. Repeat every minute over the window, for T ∈ {1, 5, 15, 60}
minutes, both sides, both venues. Output: fill probability by T, symbol,
hour and volatility regime; the mark-to-mid of filled orders one minute
later (adverse selection); the distribution of wait times.

- Duration: **14 days** of recording (≈ 20,000 virtual orders a symbol).
- Cost: $0. Disk: a few GB. Risk: none.
- Decision rule, fixed now: proceed to stage 1 only if the 15-minute fill
  probability is **≥ 70%** for the units C2 would hold and the
  adverse-selection mark is **< 2 bps** in median. Otherwise the maker
  route is closed by the tape and stage 1 is not run.

Stage 0 is also the only way to get the *shape* of the fill model (which
hours, which coins) before risking anything; a live study of a few
hundred orders cannot resolve that.

## Stage 1 — tiny live orders (needs the owner's explicit yes, later)

Run only if stage 0 passes. Purpose: check that real fills match the
tape's prediction (exchanges do not always show the whole queue; self-
match prevention and latency are real).

- Venues: Binance USDⓈ-M and Bybit linear, the owner's own accounts, API
  keys with **trade permission and no withdrawal permission**, IP-restricted.
- Instruments: 5 coins from the C2 top-80 with the smallest minimum order
  (min notional $5 on Binance; Bybit min-quantity varies — chosen so every
  order is **under $10**).
- Protocol: every 15 minutes during the study's hours, one post-only limit
  at the best bid (or ask; alternating), cancel after 15 minutes if
  unfilled; any fill is closed by a post-only order on the other side with
  the same rule, and by a taker order at 60 minutes if still open. Max
  open exposure at any time **$50 total**, no leverage above 1×, flat at
  the end of every day.
- Duration: **10 trading days**, ≈ 500 orders a venue.
- Expected cost: fees under $2; the taker closes are the real cost, bounded
  by 500 × $10 × 10 bps = $5; adverse moves bounded by the $50 cap and the
  60-minute exit — worst plausible day ≈ $2. Total budget **$25**.
- Logged, every order: placement time, side, price, displayed queue ahead,
  fill time and price or cancel time, mid at placement and at +1 min.
- Decision rule, fixed now: the live fill probability must be within
  **10 points** of stage 0's for the same T, or the tape model is wrong
  and the study stops there.

This is the first thing in the programme that would touch money. It is
small by construction; it is still live orders on your accounts, placed by
a script, and you would be saying yes to that specifically.

## What comes out

A cost model, `CostModel.maker_measured(...)`, with:
- fee per leg = the venue's maker fee, *verified on a statement*;
- an expected wait cost = (1 − P(fill|T)) × taker cost (the unfilled
  share is assumed to be taken at the deadline — conservative);
- an adverse-selection charge = the measured median mark;
- and a **fill-rate haircut on the signal**: a unit that was open 30% of
  the time at 100% fills is open less at 70%.

Then, and only then, C1 and C2 are **re-registered** as new hypotheses
(`_maker` suffixes) against that model, with the same gates and the same
falsifiers plus one: *the measured fill rate applied to the backtest must
leave the net Sharpe above 1, or the mechanism is still not tradeable.*
They count toward a new counter; the current one stays at eight.

## What this does not do

- It does not trade a strategy. Stage 1's orders are round trips for
  measurement, closed the same hour.
- It does not use leverage, does not short-sell spot, does not move funds.
- It does not touch the E-families: their cost is the equity spread on
  Alpaca, which is a different study (and Alpaca's paper account gives
  fills for free, which is where that one would start).
- It does not change any gate, bar, or count.

## The decision asked of you

Only stage 0 now: **yes / no to running a two-week public-data recorder
on the Hetzner box.** No key, no order, $0. Stage 1 gets its own question
after stage 0's numbers are on the table.
