# Session brief — the position/cash ledger (Opus 5 build session, from 18 September 2026)

*Handover from the 15–17 September session. Read `docs/23` (report), `docs/25`
(review response) and this file; skim `docs/20`'s last three entries. Do not
re-read the whole of `docs/20`. `export QR_ROOT=~/qr/lake` in every shell.
Commit as `git -c user.email=276883747+neo999-cyber@users.noreply.github.com
-c user.name=neo999-cyber`, push to `claude/funny-faraday-nizzck`. Keep
replies short.*

## State on handover

- Programme 2 closed at eight gated candidates, none passed (`docs/23`).
  Counter full; **nothing is registered without a new input and the owner's
  yes.** Trial log 651 records / 2,055 trials, chain verified.
- Independent review (Codex, `docs/25`) confirmed all fixes and found four
  more, closed with tests on 17 Sep (held-position masking, overnight round
  trips, intraday minute stamps, StepM stop) plus the external exposure
  benchmark. 801 tests pass. One item open and specified: **this brief**.
- Running unattended on the Hetzner box (`root@91.98.172.9`): `qr-tape-binance`,
  `qr-tape-bybit` (maker-fill study stage 0, `docs/24`; read on/after
  **1 October**, rule fixed: ≥ 70% fills in 15 min, < 2 bps adverse mark);
  `qr-liq-okx`, `qr-liq-bybit` (C3, kill test ~late October); the ETF flow
  collector. Nothing runs on the laptop.
- Owner's standing inputs: "$2,000 is fine if a proper system emerges"
  (unused); yes to stage 0 only; stage 1 (tiny live orders) needs its own
  yes. No live order has ever been sent.
- QuantConnect: free tier, project 36614350; the web API works from a
  logged-in Chrome tab via cookies (`files/update`, `compile/create`,
  `backtests/create|read|chart/read`) — no clicking needed. Bootstrap
  `qc/bootstrap_main.py` loads `qc/<impl>.py` from the public repo.
- Keys: `~/.qr/secrets.env` (Databento, Alpaca paper). Databento $47.70 left.

## The task: an authoritative position/cash ledger

The runner (`qr/research/runner.py::run_backtest`) computes returns from
*weights*: targets → shift → drift (`hold_between`) → masks → `held × returns`,
turnover = |held − drifted|. The review (`docs/25` §1.2, 1.3, 1.5) shows what
that cannot represent: cash and short liabilities in the denominator, the
two legs of a carry unit, integer shares at real prices with a persistent
count. Build the ledger **beside** the runner, reconcile the two on every
existing test panel, then switch.

### Specification (from `docs/25`; acceptance tests first)

1. **State** per bar: `qty[symbol]` (float, or int when `whole_shares`),
   `cash`, `borrow` (short liabilities at mark), `nav = cash + Σ qty·price`.
   Weights are *derived*: `w = qty·price / nav`.
2. **Events, in order, per bar t**: (a) mark to bar t's close → price P&L;
   (b) funding on held notional (`funding_rate × qty × price`, sign as the
   panel states: what a long pays); (c) borrow fee on short notional; (d)
   orders decided at t (from targets at t, filled at the fill price — bar
   t's close or `close_unadjusted`, next open where the instrument says so)
   → `qty` changes, `cash` changes by notional ± fees (per-side bps, per-
   share, min commission, half-spread, slippage, impact); (e) cash interest
   at the risk-free rate when `--risk-free` is given, else zero.
3. **Scheduled books**: between `trades_on` marks no order is generated;
   `qty` is constant; weights drift by themselves. Turnover is Σ|Δqty·fill|
   / nav, so it is zero between marks by construction (review's acceptance).
4. **Entry vs hold**: an order needs `tradable()` at the decision bar; a
   position needs `price_valid()` to be carried; a bar with no valid price
   liquidates at the last close (convention, keep).
5. **Whole shares**: `qty = floor(target_notional / fill_price)`, persistent
   until an order or a split; synthetic instruments must expose the real
   fill price (`auction-xnas`, `intraday-xnas` need `session_open` /
   `session_close` used for sizing, not the synthetic level).
6. **Two-leg units** (`carry-um`, `xvenue-um`): a `legs` adapter that maps a
   unit order into two physical orders (spot buy + perp sell, or perp/perp),
   each with its own fill price, fee model and funding; the unit's return is
   Σ leg P&L / nav. The ratio price stays as the panel's `close` for signals.
   Capital convention: spot notional + perp margin (state the margin, default
   100% for the reserve line) — record it in the report.
7. **Round-trip-each-bar** instruments: entry and exit are two fills on one
   bar (already in the runner as `round_trip_each_bar`; carry it over).

### Acceptance tests (write these before the code; expected values from a
hand ledger, not from the production formula)

- $50 stock + $50 cash, stock +20% → weight 54.545%, no trade, zero turnover.
- −$50 stock + $150 cash, stock +20% → NAV $90, weight −66.667%.
- Long-only monthly book: `qty` unchanged between marks; turnover zero there.
- Carry unit, spot 100→120, perp 100→110, one unit each: P&L +$10; with the
  stated capital convention the return is +10% on $100 spot notional (+5% on
  $200 if margin is counted); funding both signs; entry/exit fees per leg.
- Overnight unit: three consecutive nights → six fills.
- Whole shares: $250 slice at a real price of $400 → 0 shares, cash kept;
  at $100 → 2 shares; count persists through a rise.
- Corrupt volume on a crash bar: the held loss is booked; a new order on
  that bar is refused.
- A `BuyAndHold` on a clean panel: ledger NAV path equals the weight
  runner's `(1+net).cumprod()` to 1e-9 (the identity case), and equal on
  every existing `edge_world` fixture for daily-rebalanced strategies.

### Then

- `run_backtest(..., engine="ledger")` switch; gates unchanged (they read
  `BacktestResult`); `qr gates --engine ledger`.
- Re-score the closed Programme 2 families' saved reports? No — a re-run is
  a counted trial. Prepare the night chain for the review's step 8 (frozen
  grids, before/after table) and ask the owner before running it.
- `docs/20` entry, `docs/25` "Not done" updated, commit, push.

## Rules still in force

3× cost bar, 250 variants a family, gate 4 per hypothesis, no loosening;
every backtest counted; never register after a run; no live orders, no money
movement, no data spend, no funded evaluation without the owner's yes; no
`qr autopilot`; `centaur/` untouched; re-derive every reported figure from
the trial log / gate JSON; do not write the test count into docs.

## Owner's working pattern

Decisions and QuantConnect sessions by day (Dubai, UTC+4); unattended chains
at night (`scripts/night*_*.sh` pattern, status in
`~/qr/lake/logs/overnight_status.txt`, babysit hourly with a wakeup); don't
stop on your own — after each item, move to the next; only decisions that
need a yes pause a thread.
