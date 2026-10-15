# The carry holding — what it is, what it pays, what it risks, and the execution leg built for it

*14 October 2026. Built while the Programme 3 recording accumulates, on the owner's "let's do this while
waiting". Nothing here is a strategy and nothing is registered: it is the execution path for a holding
decision the owner has not taken (`docs/31` §15, "C1's funding carry as a holding"). No order is placed
by this code without the owner's typed line at a terminal, and the live key's trading permissions are
off today.*

## What it is

Buy a coin on Binance spot and short the same quantity of its USDⓈ-M perpetual. The two legs cancel the
price; what is left is the perpetual's funding, paid every eight hours by the side that is crowded —
historically the longs, so the short collects. Programme 2's C1 measured this on the perp lake: the
*timing* rule failed the gates because timing added nothing, and the always-in book earned the funding
(`docs/20`, 19 September: net Sharpe 4.8 on the ledger, funding 97% of the return; gate 1's shuffled
placebo said any perp pays about the same). That is the finding this holding rests on: it is a yield,
not an edge.

## What it pays and what it costs

- **Yield**: the funding rate, annualised ×1,095. Today's BTC rate is printed by `preview`; the 2021–2025
  average for the top names was in the high single digits a year, with long stretches near zero and
  short stretches negative.
- **Entry and exit, measured where we could**: the perp leg at stage 1's measured maker cost, 3.2 bps a
  side; the spot leg at 7.5 bps (VIP 0 with BNB, maker = taker, the trial's verified tier). A round trip
  of both legs is ≈ 21 bps — one week of funding at 10%/yr. Held for months, the cost is noise.
- **Capital**: the spot notional in full, plus margin on the perp (the harness runs the perp at 1×
  unless told otherwise, so the perp leg also needs its notional in USDT on the futures wallet, or the
  owner sets leverage by hand). A $1,000 holding is ~$1,000 of coin and ~$1,000 of USDT margin, or less
  margin with leverage the owner chooses.

## What it risks (the tail the ladder's T-bill does not have)

1. **The exchange.** Both legs sit on Binance; the holding is an unsecured claim on the venue for its
   whole value. The stress simulator's named-event tiers (`docs/31` §13 B) are the frame.
2. **Negative funding.** When the shorts are the crowded side the holding pays instead of collecting;
   2022 had months of it. The close is the answer, and costs a round trip each time.
3. **Basis and liquidation.** The perp can trade away from spot for days; with thin margin a spike can
   liquidate the short while the spot leg sits there. Margin at 1× removes the liquidation and halves
   the yield on capital.
4. **Operational.** Two legs; one filled and one not is an outright position. The harness takes the
   unfilled leg after the maker wait so that state lasts minutes, not hours.

## The execution leg (`qr/execution/carry.py`, `scripts/study_carry.py`)

Built on the stage-1 harness: the same journal, intents, policy caps and venue adapters, plus a spot
client (`BinanceSpot`: `LIMIT_MAKER` post-only, IOC takes, balances-as-positions for the configured
coin), an IOC entry and a funding-income read on the perp client, and a two-leg session:

| action | what it does | mandate |
|---|---|---|
| `preview` | books, matched quantity on the coarser step, basis, funding rate, round-trip cost | no |
| `open` | both legs post-only at the touch; after `ttl_s` the unfilled remainder is taken through the touch until both legs equal; then the journal returns to PAUSED with the positions standing | **yes** — `<config hash> CARRY` |
| `status` | quantities, imbalance, basis, funding collected, NAV | no |
| `funding` | books every funding payment from the venue's income rows, once each | no |
| `rebalance` | when the legs differ by more than `max_imbalance_pct`, trades the difference on the perp | yes when it adds to the short |
| `close` | cancels what is working, maker exits, then taker, then market; leaves PAUSED | no |

Caps come from the config (`study/carry.testnet.json`): notional a leg, a hard maximum, a stop in
dollars, leverage, the maker wait, the imbalance tolerance. Every order is an intent with a client id
that cannot be sent twice; every fill is posted once by the venue's execution id; every funding payment
once by its transaction id. Tests on the fake venues cover the maker fills, the take after the wait, a
partial take completed on the next tick, funding booked once, the rebalance, and the close with and
without maker fills (`tests/qr_platform/test_execution_carry.py`).

## What it has not had

A rehearsal on a venue. The futures demo key exists from stage 1; the spot testnet
(testnet.binance.vision) issues its own key pair — the owner creates one (free, a GitHub login) and puts
`BINANCE_SPOT_TESTNET_KEY` / `BINANCE_SPOT_TESTNET_SECRET` in `~/.qr/secrets.env`. Then:

    QR_ROOT=~/qr/lake python scripts/study_carry.py preview --config study/carry.testnet.json
    QR_ROOT=~/qr/lake python scripts/study_carry.py open    --config study/carry.testnet.json --confirm
    QR_ROOT=~/qr/lake python scripts/study_carry.py close   --config study/carry.testnet.json

Live would need the owner's key with spot and futures trading ticked, a funded spot wallet and futures
margin, the typed line at the terminal, and — first — the ladder decision itself.

## Rehearsed, 14 October 2026, on the testnets

The owner created the spot-testnet pair the same afternoon. `preview` read both venues (spot testnet book
81,658.00/81,658.01; futures demo 81,601/81,607; demo funding 0.0001 per 8 h). `open --confirm` at 18:22
UTC: the spot maker (BUY 0.0012 BTC at the bid) **filled as a maker**; the perp maker (SELL 0.0012 at the
ask) did not fill within the 120-second wait, was cancelled and **taken through the touch** — both legs
0.0012, imbalance 0, the journal parked PAUSED with the positions standing. Left open overnight so that
`funding` books a real demo payment at 00:00 UTC; `close` follows. Fake money throughout; the spot testnet
faucet's 1 BTC that the account already held is not the journal's and is ignored, which is how a live
account that holds the coin for other reasons would be treated too.

**Overnight, 15 October.** The demo paid funding at 00:00 UTC and `funding` booked it once: **0.00979773 USDT**,
which is 0.0012 × 81,648 × 0.0001 to the cent. Then an unplanned test of the recovery path: the detached job
that ran `close` at 01:15 UTC staged both maker exits (spot SELL at the ask, perp BUY at the bid), the venues
filled them, and the process hung before it could record the fills (the laptop had slept and the socket never
answered). The next run, an hour later, loaded the staged intents, asked the venue to cancel, was told
`-2011 Unknown order sent` — the venue's way of saying "filled" — reconciled, posted the five executions by
their venue ids, and reported `flat`. The journal and both venues agree: no coin held that is ours, the
testnet's faucet balance untouched. That is the race the stage-1 journal was built for, seen on two venues.
The hung process was stopped by hand afterwards.
