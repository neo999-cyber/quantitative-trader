# quantitative-trader — the whole project, for an outside reviewer

*Written 18 September 2026 for a review by a tool that has not seen this
repository. It is self-contained: what was started, what was built, what
was found, every rule in force, what is planned, and what is being waited
on. Every number is re-derivable from the files named; the trial log
(`qr trial verify`: 799 records, 2,268 trials, hash chain verified) is
the record of every backtest ever run. Nothing here is a claim of a
working strategy. The reviewer is asked for a verdict on the whole: the
method, the findings, the decisions, and what should happen next.*

---

## 1. What was started, and by whom

One person in Dubai with ~$1,000 (a stated willingness to add up to
$2,000 "if a proper system emerges" — never used), a MacBook Air, a €6/mo
Hetzner server, Binance and Interactive Brokers accounts, and a $0 data
budget. The question, set in early September 2026: **can a small retail
account find a trading rule that is profitable after costs — and prove it,
rather than fool itself?**

The first thing built was therefore not a strategy but a **testing
machine** whose purpose is to say "no" reliably: a data lake with
checksummed sources, a cost model with the account's real fee tier, a
backtester, and an eleven-gate validation engine every idea must pass. All
research runs through Claude Code sessions with the owner deciding; the
build is 183 commits on one branch. Python 3.11+, `pip install -e
".[dev,qr,gates,ai]"`, `pytest -q` (synthetic data, no network).

## 2. The rules in force (all of them)

These are not advice; they are constraints the code and the process
enforce, and a reviewer should judge whether they are the right ones.

**Research discipline**
1. **Pre-register, then run.** A hypothesis document (`docs/prereg/*.md`,
   32 of them) states mechanism, predicted sign and size, data, universe,
   rule, parameter grid, cost model, benchmark, controls and falsifiers,
   and is stamped into the trial log (`qr trial prereg`) *before* the
   first backtest. Registering after a run is recorded as such and the
   run is exploratory, not a test.
2. **Every backtest is counted.** Each run appends a hash-chained record
   with its variant count; gate 4 deflates significance by the count per
   hypothesis. Sensitivity analyses read the log and write nothing.
3. **Nothing is registered without a new input and the owner's yes.** The
   Programme 2 counter closed at eight; a ninth was registered on 17
   September on a new mechanism (unlocks) and failed.
4. **The 3× cost bar**: a family must clear three times its own round-trip
   costs; gate 2 also stresses costs 2×. Costs are the account's verified
   fee tier (Binance VIP0 with BNB discount: 7.5 bps taker; USDⓈ-M perp
   2/5 bps; Alpaca $0 commission with 6 bps spread/slippage), plus
   half-spread, plus square-root impact where charged.
5. **250 variants a family**, gate 4 per hypothesis, no loosening of any
   threshold after seeing a result.
6. **Holdouts open once**, after gates 1–8, on a date fixed in the
   pre-registration. None has been opened in Programme 2.
7. **LLM output enters only as a point-in-time feature, never as a
   trade.** The idea generator was run to exhaustion and retired.
8. **yfinance is prototyping-only**; never a system of record.
9. Every reported figure is re-derived from the trial log / gate JSON;
   the test count is never written into docs (it goes stale).

**Money and operations**
10. **No live orders, no money movement, no data spend, no funded
    evaluation without the owner's explicit yes** to that specific thing.
    Total data spend to date: $55 of a $125 Databento credit. No real
    order has ever been sent; the only orders ever sent were on Binance's
    demo environment on 18 September (§6).
11. Stage 1 of the maker-fill study, if run: < $10 an order, ≤ $50 gross
    open including pending, 1× leverage, $25 session loss stop, attended
    only, flat at the end of every session verified at the venue.
12. The Hetzner box runs only standard-library recorders, without the
    `qr` package, so nothing there can break anything else.
13. Keys live in `~/.qr/secrets.env`, mode 600, never in the repo, never
    printed. A key pasted into a chat is treated as burned.

**Engineering**
14. Model split: Opus 5 builds; Fable 5.1 reviews gate mathematics and
    final reports; Sonnet for small fixes. Independent review by a
    different tool for engine changes (Codex, twice so far).
15. Commit after every stage, tests before every commit, author on the
    GitHub noreply address.

## 3. The eleven gates (what "pass" means)

0 pre-registration exists and matches its stamp · 1 data integrity and a
leakage probe (Sharpe at lag 0/1/2; a gross Sharpe above 8 is ruled
implausible) · 2 cost survival (net over gross, 2× stress, capacity) · 3
single-strategy significance (HAC t, PSR) · 4 multiple-testing deflation
(DSR over the counted trials) · 5 selection overfitting (CSCV/PBO, SPA
with StepM against the pre-registered benchmark: costed buy-and-hold,
cash at the FRED T-bill rate, or exposure-matched) · 6 permutation nulls
(bar permutation with re-optimisation, random entry, volatility-
preserving) · 7 combinatorial purged CV and walk-forward · 8 robustness
(parameter plateau, regimes, round-trip count) · 9 holdout · 10/11
sizing and incubation (63 sessions live, decisions logged before
outcomes). A synthetic self-test must reject planted noise and pass a
planted edge (`qr selftest`).

## 4. What was found — Programme 1 (crypto spot, ETFs; closed 15 Sep)

`docs/18_THE_VERDICT.md`, `docs/19_HANDOVER.md`. Nine pre-registered
families (trend, cross-sectional momentum, reversal, RSI, calendar, on
Binance spot and twelve US ETFs) **all failed, none surviving gate 5**
(the buy-and-hold comparison). Forty-six "who is forced to trade?"
mechanism memos: forty-three died on reasoning, three reached a sandbox
cost test, the best — turn-of-month retirement inflows, +4.8 bps a round
trip, correctly signed in advance — is 0.6× its costs at $1,000, clears
the bar at $10,000, and is a *worse* risk-adjusted way to own the basket
than holding it at every size to $100,000. Account-size sweep (`docs/11`):
crypto costs are size-independent; the ETF families get cheaper with size
and still lose to the basket. **Verdict written: for this account, an
index fund; the constraint was ideas, not capital.**

## 5. What was found — Programme 2 (perps, single stocks; closed 17 Sep, reopened once)

`docs/20` (plan and dated log), `docs/23` (report). Changed the
instruments (USDT perpetuals with funding and open interest; US single
stocks at $0 commission; minute bars; auction imbalance data bought from
Databento), the point-in-time discipline, and the comparator (cash for
market-neutral and carry books; exposure-matched for stock selection).
Eight candidates registered and gated in three days:

| | Family | Stopped at | Best net Sharpe | What the controls said |
|---|---|---|---|---|
| C1 | funding carry (long spot / short perp on a funding rule) | v1 gate 1 (gross Sharpe 9.7 > ceiling); v2 gate 6, permutation p 0.99 | 3.09 | the always-in carry (Sharpe 2.4, funding 97% of gross) is real; the timing rule adds nothing |
| E1 | closing-auction imbalance fade, 31 Nasdaq names | gate 2 (costs 50% of gross) | 0.66 | mirror loses |
| E5 | insider clusters (QuantConnect) | gates 5/8, alpha t 1.31 | 0.69 = benchmark | random-name control 0.33 |
| E2 | late-day momentum, QQQ | gate 2 (gross negative) | −1.04 | reverse also loses |
| E4 | post-earnings drift (QuantConnect) | gates 3/4/5 | 0.36 | a drift, not an edge |
| C5 | OI-conditioned reversal, mid-cap perps | gate 3, t 1.68 | 0.84 | unconditioned reversal loses: OI points the right way |
| C2 | cross-venue funding spread, Binance/Bybit | gate 3, t 1.76; costs 45% of gross | 0.62 | always-in loses |
| E7 | short squeeze (short interest + fails) (QuantConnect) | gates 3/4/5 | 0.70 | random control alpha t 2.49 — higher than the family |
| C6 | **unlock fade** (short perps into scheduled insider cliffs; registered 17 Sep on a new input) | gates 2–6, t 0.64, p 0.52 | 0.32 | long mirror flat; ecosystem-cliff control earned as much as the family |

Nine registered, nine failed. Two effects are *real but not tradeable at
this size*: hold-the-carry, and the OI direction. One exploratory study
outside the counter (S1, S&P 500 discretionary deletions, run on
QuantConnect on 18 September **before registration** — recorded as
exploratory, seq 796): net Sharpe 0.69, t 2.13, but SPA p 0.20 and PBO
0.67 against an SPY-matched benchmark; +4.9%/yr over it, not the
literature's +20%; parked.

## 6. The engine reviews (what was wrong with the machine itself)

Two independent reviews by a different tool (Codex), 15 and 17
September (`docs/22`, `docs/25`). The second found **eleven defects**,
all confirmed: a held position zeroed by a corrupt volume field (a −50%
loss erased); overnight round trips under-charged; a one-minute
look-ahead in the intraday decision; StepM misapplied inside `arch`; the
external "exposure-matched" benchmark never scaled (proxy 1.0 for every
backtest); two E5 re-scorings double-counted as trials; the carry unit's
ratio return claimed "exact" (second-order, ~7% Sharpe overstatement).
Ten fixed with tests the same day; corrections moved numbers (E5's SPA p
0.19 → 0.066; E7's 0.88 → 0.52) and **no verdict**. The eleventh — replace
weight-space arithmetic with a real position/cash ledger — was built on
17–18 September (`qr/research/ledger.py`, `docs/26`): quantities, cash,
short liabilities, per-leg fills for two-leg units, whole shares at real
prices, funding on marked notional, cash interest reported beside the
return. Reconciled with the old engine to 1e-9 at zero cost; three
defects of its own found by the real panels and fixed (NaN turnover on
untradable bars; cash interest booked into gross — which made a cash-heavy
book read Sharpe 20 and looked like a pricing anomaly; the "second-order"
fee arithmetic in the maker study's own note). The eleven Programme 2
runs were re-run on it overnight: **every verdict stands**, but the
after-numbers carry the interest defect and are not quotable as the
engine comparison; a clean re-run is on the owner's list. The ledger is
not yet the default engine.

A third Codex document (17 Sep) proposed a full "trading platform" build
(assistant, dashboard, order management, 264–448 engineering hours). It
was assessed (`docs/27`) and cut to the seven tickets the maker-fill
study's stage 1 needs; its three research templates were the families
already failed here; its execution-layer criticisms of the ledger were
accepted. Codex's own revised scope agreed.

## 7. What is built and works (verified, not claimed)

- **Lake:** Binance spot and every USDT perp's daily bars with funding
  and open interest (471 both-leg symbols); Bybit perps and funding;
  carry and cross-venue synthetic units; Databento Nasdaq auction
  snapshots (202,713) and minute bars for 31 names; FINRA short interest
  and SEC fails-to-deliver mirrors; Form 4; FRED DTB3; DefiLlama vesting
  schedules for 105 perps; ETF share counts (collector); public tape
  (Binance and Bybit top-of-book and trades, since 17 Sep); OKX/Bybit
  liquidation streams (since 15 Sep). Manifest with hashes.
- **Engines:** the weight runner and the ledger; the full suite passes (868 on 18 September; the number is not maintained in docs).
- **Gates:** all eleven, plus an external path that scores QuantConnect
  backtests (used for E4, E5, E7, S1) with holdings-based exposure.
- **Maker-fill study, stage 0** (`docs/24`): a virtual post-only replay
  against the recorded tape (queue behind displayed size, consumed by
  prints only — a floor). First day: Binance 96.8% of orders filled within
  15 min, median adverse mark 0.84 bps; Bybit 94.9% / 1.38 bps. The
  registered rule (≥ 70%, < 2 bps) is read on the full 14-day tape on 1
  October; the first day is a preview.
- **Maker-fill study, stage 1 harness** (`docs/27`, `qr/execution/`):
  SQLite journal (idempotent intents, order-state table with UNKNOWN
  leaving only by reconciliation, executions posted once, reservations,
  NAV uncertain without a mark, opens PAUSED, replay); study limits;
  Binance USDⓈ-M and Bybit adapters (post-only, reduce-only, cancel,
  reads; no fund-moving method); mandate preview/start (config hash
  typed back); attended runner (15-minute slots, TTL cancel, maker exit
  re-posted, taker exit 60 minutes *from the fill*, mark 60 s after,
  every attempt logged, loss stop, close-all verified at the venue,
  resume by reconciliation). **Rehearsed on Binance's demo environment
  on 18 September**: 27 attempts, 16 placed, 11 refused by the limits
  with reasons, 9 maker fills all closed, 28 executions (24 maker),
  ended flat by itself. Five defects found by the real wire in three
  takes, fixed with tests (balance import, client-id collision, working
  set across restarts, refused-cancel reconciliation, exits while paused).

## 8. What is not possible for this owner (venue access)

Bybit refuses a Dubai address on its global site and testnet; it serves
UAE customers only through a licensed onboarding, without a demo. The
owner rejected OKX; chose Hyperliquid, then parked it (its testnet
requires deposit history, i.e. a real deposit first). **Stage 1 is
therefore Binance-only, and no cross-venue unit is tradeable for this
owner** — C2, the family nearest to passing on costs, is closed for that
reason, not a statistical one.

## 9. What is planned, and what is being waited for (dated)

| When | What | Decides |
|---|---|---|
| **1 October** | read stage 0 on the full 14-day tape against the frozen rule | whether maker execution is plausible; if yes, the owner's separate yes to stage 1 |
| early October, if yes | **stage 1**: ~500 post-only orders on Binance over 10 attended days under the caps in §2 | live fill rate within 10 points of the tape → `CostModel.maker_measured`; else the maker route is closed |
| mid October, if stage 1 passes | re-register **C1** as `_maker` against measured costs, same gates plus a fill-rate haircut | the one effect that was real (carry) at the lower cost bar |
| late October | **C3** liquidation-cascade kill test (recorders running since 15 Sep) | the last untested mechanism |
| March 2027 | C6 holdout (cliffs dated after the frozen calendar) | the only revision-proof test of C6 |
| owner's call | clean eleven-run re-run on the fixed ledger | whether the ledger becomes the default engine |
| owner's call | S1 registration on its untouched holdout (entries from 1 Sep 2024) | a slow backup, if ever |
| only after a pass at gates 0–9 | 63-session incubation → owner-approved small live pilot → limited automation | each stage earns the next |

**Parked, deliberately:** the assistant/dashboard/platform build, every
subscription (TrendSpider, Trade Ideas — 60–240%/yr of the account under
the fixed-cost table), hosting, LLM idea generation, US-stock execution,
any further literature-sourced fast-cycle idea (hit rate 0 of 18).

## 10. The honest position (what the authors think, for the reviewer to test)

- Eighteen ideas across crypto spot, ETFs, perps, single stocks and a
  scheduled-flow mechanism: eighteen fails. The machine has caught its
  own defects three times; the answer has not moved.
- Published anomalies reachable by a retail reader are, on this evidence,
  arbitraged, smaller than the cost bar, or not reproducible.
- What remains is dated and cheap: an execution-cost measurement (1
  October), one mechanism (late October), one holdout (March). If all go
  the wrong way, `docs/18`'s index-fund verdict stands and the project's
  product is the machine and the negative results.
- Capital does not rescue any tested idea; it only converts a future pass
  into money. The realistic ceiling at $1–2k, even with a pass, is a
  proof, not income.
- The single most consequential non-research fact is venue access from
  Dubai (§8).

## 11. What we ask the reviewer to judge

1. Is the method sound — pre-registration, counted trials, the eleven
   gates, the 3× bar, the benchmarks? Anything that would let a false
   positive through, or that kills a true positive?
2. Are the eighteen verdicts safe, given the engine defects found and
   fixed along the way? Which, if any, deserve a re-run on the ledger?
3. Is the maker-fill study the right next experiment, and is stage 1's
   design (caps, attended, Binance-only, 10 days, the 10-point agreement
   rule) sufficient to validate a cost input?
4. Is anything being waited on that could be run now, or run in parallel?
5. Is there a mechanism class this project has not tried that a $1–2k
   account in Dubai, with Binance and IBKR, could actually trade?
6. Should the project continue past October if the dated items fail?

## 12. Where to look

`docs/18` verdict · `docs/19` handover · `docs/20` Programme 2 plan and
dated log · `docs/23` Programme 2 report · `docs/22`, `docs/25` the
engine reviews and response · `docs/24` maker-fill study protocol ·
`docs/26` ledger brief · `docs/27` stage-1 scope and rehearsal record ·
`docs/prereg/` every pre-registration · `docs/research/` sourced
research incl. `10` (forced flows in FX and stocks) · `qr/` the code ·
`tests/` · `$QR_ROOT/trial_log.jsonl` and `reports/` for every run.
