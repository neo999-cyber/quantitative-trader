# The verdict

*15 September 2026. What this project set out to answer, what it found, and
what a reader should do about it. Everything below is drawn from `docs/06`,
`08`, `11`, `15`, `16` and `17`; this page exists so that nobody has to read
all six to learn the answer.*

## In one paragraph

**No strategy built here beat buying a broad basket and holding it.** Nine
pre-registered families across crypto spot and US ETFs failed the twelve gates,
none surviving gate 5. Forty-six mechanism candidates were then generated from
"who is forced to trade?" — forty-three died on reasoning, three reached a
sandbox cost test, and the best of those was **0.6x its own trading costs at a
$1,000 account** against a pre-committed bar of 3x. Made ten times richer it
clears that bar comfortably and is *still* a worse risk-adjusted way to own the
same twelve funds than holding them. For an account of this size the answer is
a broad index fund, and the evidence for it is unusually specific.

## The three questions, answered

**1. Is there an edge these nine families can reach?** No. `docs/06` (crypto)
and `docs/08` (ETFs). All nine stop at or before gate 5, which is the test
against buy-and-hold. The control — buy-and-hold itself — fails at gate 6,
which is the engine working: a benchmark should not pass a test designed to
find something better than it.

**2. Is the constraint the account or the ideas?** For those nine, the ideas
(`docs/11`, Step 0). Crypto costs are size-independent to four significant
figures, because a Binance taker pays the same basis points on $10 and
$10,000. The ETF families get dramatically cheaper with size — the long-short
book keeps 1.9% of its gross return at $1,000 and 80% at $100,000 — and still
cannot beat the basket at a hundred times the account. **No deposit rescues any
of them.**

**3. Is there a forced-flow mechanism worth trading?** One was found and it is
too small (`docs/15`). Turn-of-month buying by retirement contributions is
real, measurable, and correctly signed in advance: **4.8 bps per round trip**.
Against costs of 7.5 bps at $1,000, 1.2 bps at $10,000, and 0.5 bps at
$100,000 — so 0.6x, 3.9x, 9.5x. The cost bar is cleared at a larger account.
The buy-and-hold comparison is negative at **every** rung.

That last line is the whole finding compressed: *the account was the binding
constraint on the cost bar and not on the outcome.* A bigger account buys the
ability to afford a trade that is worse than doing nothing.

## What was ruled out, and how

* **Crypto spot: forty memos, forty kills.** Not one reached a backtest. The
  forced traders in crypto are forced on the **perpetual**, and the obligation
  is discharged there. Spot is where the consequences are observed, not where
  anyone must act. Perpetual funding data was bought into the lake specifically
  to test this and the answer held (`docs/15`).
* **The basis-arbitrage escape.** The best counter-argument — that
  cash-and-carry arbitrageurs must sell spot when the carry stops paying — was
  handed to the memo generator pre-formed, and killed: **an arbitrageur is not
  forced.** Delta-neutral and discretionary, they unwind when it suits them, at
  a price they choose. A transmission whose transmitter is voluntary transmits
  nothing.
* **The remaining shopping list, priced** (`docs/17`). Of four datasets the
  nights asked for, two fail on *reasoning* rather than availability:
  liquidations and index reconstitution both name a forced trade in an
  instrument this project does not trade. One survives and is now being
  recorded forward.

## What is running

`scripts/collect_flows_standalone.py` on the Hetzner box, every thirty minutes
on weekdays, recording ETF share counts. Daily change times NAV is the
creation/redemption flow — the only named mechanism whose forced trader (the
authorised participant) trades **the same instrument this project trades**.

It is recorded rather than downloaded because no free history exists, and that
turns out to be a feature: **data you record yourself is point-in-time by
construction.** Its odds are low and its cost is zero. A year of it is ~250
daily observations and twelve month-ends, and whatever it shows still has to
beat holding the basket.

## What this project is actually for

The strategies failed. The instrument that judged them did not, and it is the
part worth keeping.

In the final two days it caught **four** of its own numbers measuring something
other than what they claimed:

1. The sizing maths reported "42% chance of a 25% drawdown". It was computing
   the probability of ever falling 25% below *launch equity*; the quantity it
   named is 1 at every leverage over an infinite horizon (`docs/16`, found by
   an independent review).
2. The kill test scored a candidate at 1.6x its costs. It was charging 2.0 bps
   and ignoring the $0.35 per-order minimum that dominates a small account. The
   real figure was 0.6x.
3. The same test divided a **compounded** sixteen-year return by a per-trade
   cost — a numerator carrying sixteen years of compounding against a
   denominator carrying none.
4. The data-precision check reported 13–17 significant digits and waved a
   dataset through. It was reading net assets, which the source *computes* as
   shares times NAV; it was measuring its own multiplication.

Every one of those errors flattered the result. That is not coincidence: an
error that makes an idea look worse gets investigated immediately, and one that
makes it look better gets believed. **The realistic alternative to this project
was not finding an edge — it was funding a fake one.** At $100,000, "9.5x its
trading costs" would have read as a green light.

## The recommendation

For ~$1,000: a broad index fund, left alone. That is the conclusion of the
work, not a concession.

The one door the evidence points at is crypto perpetuals, where the forced
traders actually are. It is a serious build — new cost model, leverage,
liquidation risk, custody — and a decision about risk appetite rather than a
research question. The gate 11 sizing mathematics has now been independently
reviewed (`docs/16`) and its fixes applied, which was the precondition for
sizing real money either way.

## If you come back to this

Read this page, then `docs/17` for what is collecting and why. `docs/11`,
`15` and `16` have the workings. `qr trial verify` walks the hash chain and
prints the run count; every verdict above is in it, including the killed ones.
