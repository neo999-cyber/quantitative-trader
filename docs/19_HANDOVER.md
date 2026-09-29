# Handover: objective, execution, failure analysis, and what would actually be required

*15 September 2026. Written for a quantitative professional or a successor
model taking this over cold. It assumes no familiarity with the repository and
no goodwill towards its conclusions. Every figure is reproducible from the
hash-chained trial log (`qr trial verify`).*

---

## 1. Objective

Build a systematic trading capability for a retail account of approximately
**$1,000**, starting from zero infrastructure, and determine whether any
tradeable edge was accessible to it.

Two constraints were fixed at the outset and never relaxed:

- **Judged by validation gates, not by P&L.** The decision rule was written
  before any code existed: if a strategy family passed the gates, paper-trade
  it; if none did, do not deploy capital.
- **$0 spent on data or execution during research.** Free or already-owned
  sources only.

The implicit objective — the one the owner actually cared about — was income
from trading. **That was not achieved and, on the evidence assembled, is not
achievable in the configuration that was built.**

---

## 2. What was built

A twelve-gate validation engine and the data platform beneath it. Python 3.11,
~707 tests, no network in the test suite.

**Data layer.** Binance public bucket loader (734 USDT spot pairs, 55,476 files,
checksums verified, point-in-time listing/delisting dates); Tiingo EOD for a
twelve-ETF basket (SPY QQQ IWM EFA EEM TLT IEF LQD HYG GLD DBC VNQ, 5,183–8,462
bars each, dividend- and split-adjusted); Parquet lake with a DuckDB manifest;
QA checks that gate downstream use; Binance perpetual funding and open interest
as point-in-time features on the spot panel.

**Cost models**, calibrated to the actual account's fee schedules rather than
to conventions: Binance spot VIP0 + BNB at 9.5 bps per side including spread;
IBKR tiered at $0.0035/share with a **$0.35 per-order minimum** and a 1% cap,
plus 50 bps/yr borrow on shorts. Market impact is charged **nowhere** — a known
and documented gap, which means the models imply unbounded capacity.

**Validation engine**, gates 0–11: pre-registration (hash-chained, append-only),
data integrity, cost survival, HAC-corrected significance, Sharpe deflation
(DSR / haircut / MinBTL), selection bias (CSCV/PBO plus Hansen's SPA against
buy-and-hold), permutation with re-optimisation, purged/embargoed cross-
validation, robustness, untouched holdout, forward incubation, and position
sizing.

**Research apparatus.** A discovery/validation sandbox with SHA-256 symbol
splitting and three enforcement layers; a pre-committed research policy (2
promotions/week, 5/quarter, 250 variants/family, a 3× cost bar, and a hard stop
at 8 gated candidates); an LLM mechanism-memo generator with deterministic
triage that re-decides independently of the model's own verdict; cheap kill
tests in the sandbox; and `qr autopilot`, which runs the whole funnel unattended.

---

## 3. What was run

**Nine pre-registered strategy families**, 1,541 counted backtest runs.

*Crypto (Binance spot, top-30 by quote volume, IS 2018–2024, holdout 2025+):*

| family | variants | stopped at | IS Sharpe | holdout Sharpe | SPA *p* |
|---|---|---|---|---|---|
| `tsmom_v1` | 200 | gate 5 | 0.749 | −0.55 | 0.890 |
| `xsmom_v1` | 144 | gate 5 | 0.573 | −0.82 | 0.898 |
| `reversal_v1` | 54 | gate 5 | 0.421 | −0.39 | 0.910 |
| `rsi_reversal_v1` (control) | 27 | gate 5 | 0.695 | WARN | 0.830 |

*ETFs (IBKR tiered, $1,000; IS 2007–2022, holdout 2023+):*

| family | variants | stopped at | IS Sharpe | net/gross |
|---|---|---|---|---|
| `etf_tsmom_v1` | 30 | gate 5 | 0.678 | 0.733 |
| `etf_xsmom_v1` | 12 | gate 3 | 0.398 | 0.570 |
| `etf_reversal_v1` | 12 | gate 2 | 0.073 | 0.127 |
| `etf_buyhold_v1` (control) | 1 | gate 6 | 0.664 | 0.957 |
| `ls_xsmom_v1` (long-short, $10k) | 12 | gate 3 | 0.326 | 0.634 |

**Forty-six mechanism candidates** generated from "who is forced to trade, and
why?", across six nights. Forty-three killed at triage. Three reached a sandbox
cost test. Zero promoted.

**An account-size sweep** re-scoring all nine families at $1,000 / $10,000 /
$100,000, changing only the account the cost model prices orders against.

---

## 4. Findings

**4.1 Nothing beat buy-and-hold.** Not one of 425 crypto configurations or 67
ETF configurations. Hansen's SPA *p*-values against an equal-weight hold of the
same universe: 0.83–0.91 (crypto), 0.53–0.96 (ETF at $100k). Gate 5 is where
eight of nine died, and the three independent gates that should agree with it
do: HAC *t* of 1.08–1.93 against a 2.5 floor, deflated Sharpes of 0.50–0.78
against 0.95, and negative holdout Sharpes.

**4.2 The single most damning number.** The engine's synthetic self-test
searches **200 variants over pure noise** and reports the best Sharpe it finds:
**1.058**. Searching 200 momentum variants over seven years of real Binance data
produced **0.749**. The search over a random number generator won. This is not a
strategy narrowly missing a threshold; it is evidence that what the search found
in real data was weaker than what the same search finds in nothing.

**4.3 Account size does not rescue the nine.** Crypto is size-independent to
four significant figures, because a Binance taker pays the same basis points on
$10 and $10,000. ETF costs fall sharply — the long-short book retains 1.9% of
gross return at $1,000 and 80% at $100,000 — and two families cross gate 2 from
FAIL to PASS. **SPA *p* never materially improves**, because the benchmark gets
cheaper too.

**4.4 One real effect was found, and it is too small.** Turn-of-month buying
driven by retirement-contribution flow: **4.8 bps per round trip**, sign
committed in advance, measured in the discovery sandbox. Against round-trip
costs of 7.5 bps at $1,000, 1.2 bps at $10,000 and 0.5 bps at $100,000 — that is
**0.6× / 3.9× / 9.5×** against a pre-committed 3× bar. Cleared at a larger
account. But its Sharpe against simply holding the same basket is **−0.84 /
−0.14 / −0.10**: negative at every size. *The account bound the cost bar and not
the outcome.* A larger account buys the ability to afford a trade that is worse
than doing nothing.

**4.5 Crypto spot has no reachable forced-flow mechanism.** Forty memos, forty
kills, none reaching a backtest. The forced traders in crypto — liquidated
leverage, funding payers — are forced **on the perpetual**, and the obligation
is discharged there. Perpetual funding data was ingested specifically to test
this. The strongest counter-argument (cash-and-carry arbitrageurs must sell spot
when the carry stops paying) was handed to the generator pre-formed and
correctly killed: **an arbitrageur is not forced.** Delta-neutral and
discretionary, they unwind when it suits them, at a price they choose.

**4.6 Four measurement errors were found in the final two days, all
self-flattering.**

| | claimed | actual |
|---|---|---|
| Gate 11 drawdown probability | "42% chance of a 25% drawdown" | P(ever 25% below *launch*); the named quantity is 1.0 at every leverage over an infinite horizon |
| Kill-test cost multiple | 1.6× costs | 0.6× — the $0.35 order minimum was not being charged |
| Same ratio | — | compounded 16-year return divided by a per-trade cost |
| Data precision check | "13–17 significant figures, fine" | reading net assets, which the source computes as shares × NAV — measuring its own multiplication |

The asymmetry is the finding, not the count. An error that makes a result look
worse gets investigated on sight; one that makes it look better gets believed.
Three of these four were in code that had passing tests.

---

## 5. Why it failed — root causes, ranked

**These are ranked by how much each one alone would have prevented success.
The first three are structural and were determined at design time.**

**5.1 The benchmark was unbeatable by construction.** Gate 5 tests against
buy-and-hold of the same universe. The universes were twelve beta-heavy ETFs
and thirty crypto majors, over samples dominated by large positive drift. Every
strategy tested was **long-only with a timing overlay** — i.e. a strict subset
of the benchmark's exposure, paying costs the benchmark does not, with less
time in a rising market. A long-only timing rule beating buy-and-hold on
risk-adjusted return over such a sample is close to a null hypothesis. *This was
the single biggest design error and it was invisible from inside the project,
because each individual gate is correct.*

**5.2 A $1,000 account with a $0.35 per-order minimum is 35 bps per order.**
That structurally excludes anything trading more often than a handful of times
per year, before any question of edge arises. It was known on day one and not
treated as disqualifying. It should have been.

**5.3 Daily bars cannot see where forced flow resolves.** Month-end rebalancing,
index reconstitution and creation/redemption all execute in **closing
auctions** and in the final minutes of the session. Daily OHLCV sees the
outcome, never the imbalance. Every mechanism the research plan was organised
around lives at a resolution the data does not have.

**5.4 The instruments with the forced traders were not tradeable here.** Crypto
forcing is on perpetuals; index reconstitution forces single stocks; ETF
creation forces authorised participants in the primary market. The project
traded crypto spot and twelve ETFs. Ten of the first twelve mechanism kills were
*access* failures, not reasoning failures.

**5.5 No point-in-time alternative data.** Fund flows, index membership, short
interest and unlock schedules are either paid or must be recorded forward. Every
mechanism that survived reasoning needed one of them. Free history does not
exist for any of them, and using today's version against past dates is
look-ahead that would manufacture a false edge.

**5.6 Cross-sectional breadth was far too low.** Twelve ETFs and thirty crypto
pairs, the latter highly correlated to BTC. Cross-sectional strategies extract
signal from dispersion across many names; a twelve-name cross-section has
almost none.

**5.7 The idea generator exhausted its space.** The LLM memo generator converged
to re-proposing the same two calendar strategies under new titles by the sixth
night. It is a filter of ideas, not a scalable source of them.

**5.8 Market impact is charged nowhere.** Not a cause of the failures observed —
it would only make results worse — but it means the cost models imply unbounded
capacity and no capacity question has been answered.

---

## 6. What was achieved

Stated without inflation:

- **A validation engine that demonstrably works.** Its control (buy-and-hold)
  fails gate 6 as it should; its noise self-test correctly fails at gates 4–5;
  its planted-edge self-test correctly passes. It caught four self-flattering
  measurement errors in its own code in two days.
- **A definitive negative result** for nine strategy families across two asset
  classes and three account sizes, with pre-registration, an untouched holdout,
  and multiple-testing correction. This is a real research output, of the kind
  that is normally skipped.
- **Reusable infrastructure**: point-in-time data plumbing, broker-accurate cost
  models, a tamper-evident trial log, a discovery sandbox that cannot be
  quietly violated.
- **$0 of capital deployed.** The realistic counterfactual was not "find an
  edge"; it was "deploy against a false positive". At $100,000 the turn-of-month
  candidate reads "9.5× its trading costs" and would have looked like a green
  light.

Cost: roughly two weeks of elapsed time, LLM API spend, no data spend, no
trading losses.

---

## 7. What would actually be required

Each path below is stated with its real precondition, not an optimistic one.
None is recommended at $1,000.

**Path A — change the benchmark question (highest leverage, lowest cost).**
Stop trying to beat buy-and-hold with long-only timing. Construct
**market-neutral** (dollar- and beta-neutral long/short) or **cash-benchmarked**
strategies, where the comparator is the risk-free rate rather than a rising
equity market. This changes what gate 5 is asking. Precondition: the ability to
short, which at IBKR means ≥$2,000 and realistically ≥$25,000 for the pattern-day-
trader rule to be irrelevant. **This is the single change most likely to alter
the result, and it costs nothing but a redesign.**

**Path B — change the universe to single equities.** 1,500–3,000 US names gives
the cross-sectional breadth twelve ETFs cannot, and makes index reconstitution,
short interest, earnings drift and float changes testable. Precondition:
survivorship-bias-free point-in-time data — Sharadar (~$180/yr), Norgate
(~$500/yr) or CRSP (institutional). Non-negotiable: without point-in-time
membership, results are fiction.

**Path C — change the resolution.** Minute bars or better, plus closing-auction
imbalance feeds (Nasdaq Net Order Imbalance Indicator, NYSE Order Imbalance
Information) where the forced flow actually clears. Precondition: paid feeds and
materially more engineering. This is where the mechanisms this project reasoned
about are actually visible.

**Path D — change the instrument to crypto perpetuals.** The forced traders are
there, demonstrably. Funding carry and basis trades are documented, capacity-
constrained, and real. Preconditions: a perpetual cost model including funding
paid *and* received, a liquidation and margin model, exchange counterparty risk,
and acceptance of total-loss scenarios. Capital ≥$10,000 to be meaningful.
**This is the highest-variance path and the only one where the evidence
positively points somewhere rather than merely failing to exclude it.**

**Path E — capital.** At $100,000 the per-order floor becomes irrelevant (0.35
bps) and the cost-bound failures disappear. It does not create edge — the
turn-of-month result proves that directly — but it removes one of three binding
constraints.

**Minimum viable configuration, in the author's assessment:** ~$25,000–50,000,
point-in-time single-equity data, intraday resolution, and market-neutral
construction. Below that, transaction costs and benchmark structure dominate any
plausible signal.

**Honest base rate:** most retail systematic strategies that clear this kind of
validation still fail in live trading, because gates control for multiple
testing and look-ahead but not for regime change, capacity, or execution
slippage that models do not contain. The prior on any of the above producing
durable net income after costs is low. It is not zero, and it is materially
higher for Path A and Path D than for anything attempted here.

---

## 8. What a successor should not redo

- **Do not re-test momentum, cross-sectional momentum or short-term reversal** on
  these universes. Nine families, 1,541 runs, pre-registered and deflated. Gate
  4 deflates against the cumulative count, so re-running them makes every
  subsequent test *harder* to pass.
- **Do not run another autopilot night without a new input.** The brief space is
  exhausted; the generator now returns the same two ideas renamed.
- **Do not attempt liquidation-cascade or index-reconstitution strategies in
  these instruments.** Both were killed on transmission, not on data: the forced
  trade occurs in an instrument this project cannot trade. Acquiring the data
  does not repair the reasoning.
- **Do not loosen the 3× cost bar or the 8-candidate stopping rule** to admit a
  near miss. Both were pre-committed precisely against the moment when a 1.6×
  result makes a 2× bar look reasonable.
- **Do trust the gates and distrust the reported numbers.** Four self-flattering
  measurement bugs were found in two days, three of them in tested code. Assume
  more exist. Re-derive any figure before building on it.

---

## 9. Artifacts and verification

| | |
|---|---|
| Repository | `neo999-cyber/quantitative-trader`, branch `claude/funny-faraday-nizzck` |
| Verdicts | `docs/06` (crypto), `docs/08` (ETF), `docs/11` (account size), `docs/15` (mechanisms), `docs/16` (independent sizing review), `docs/18` (summary) |
| Engine | `qr/validate/gates.py` — gates 0–11 |
| Trial log | append-only, hash-chained; `qr trial verify` walks the chain and prints the run count |
| Tests | `pytest -q` — synthetic data, no network |
| Still running | `scripts/collect_flows_standalone.py` on an always-on host, recording ETF share counts every 30 minutes on weekdays; daily change × NAV is creation/redemption flow. Point-in-time by construction because it is recorded, not downloaded. Usable sample: 12+ months. |

The independent review in `docs/16` was run by a different model in an isolated
session and found a genuine defect the author's own tests could not detect,
because the test and the formula were drawn from the same source. **Any
successor should repeat that pattern rather than trust this document.**

---

## 10. Bottom line

The infrastructure is sound and the research was executed honestly. The
strategies failed, and the three reasons that matter were fixed at design time:
the benchmark was a rising market that long-only timing rules cannot beat, the
account was too small for the per-order cost floor, and the data resolution
could not see the flow the mechanisms depended on.

For $1,000, the defensible action is a broad index fund. Any serious attempt at
the original objective requires changing at least two of {benchmark
construction, universe breadth, data resolution, instrument, capital} — and the
honest expected value even then is low.
