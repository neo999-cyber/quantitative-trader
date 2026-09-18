# Programme 2: the plan, the decisions, and the week-1 log

*15 September 2026. The plan below was written from `docs/18`'s handover and
from facts verified that day against official pages and the papers
themselves; the sources are in §14. The owner's decisions and what was built
on day one follow the plan.*

## Owner's decisions (15 September 2026)

| Decision | Choice | Consequence |
|---|---|---|
| Residence | **Dubai** | Alpaca for US equities — its About page (alpaca.markets/about-us, read 15 Sep 2026) lists the United Arab Emirates among the 40+ countries it operates in, so open the account directly; whether margin/shorting is offered to a non-US account shows in the application. IBKR stays Pro; Bybit, Binance FZE and Hyperliquid for perps; Polymarket international open; Kalshi not |
| Data budget | **$0** | QuantConnect free tier, Databento's $125 credit, Binance Vision, FRED, FINRA, SEC, EDGAR. Reassess at week 9; the only foreseeable paid item is Alpaca's $99/mo full feed, and only at live time |
| Funded evaluation | **None yet** | Buy the smallest HyroTrader tier only after a crypto family passes gates 0–9; one Topstep $50k Combine only after an intraday futures family does |
| Own capital | **Nothing moves until a family has passed every gate, incubation included** (owner, 15 Sep 2026) | Research, registration, backtests and the 63-day incubation all run at $0 at risk. The $1,000 goes to a venue only for a family past gate 10, and then at ≤25% of equity per family. The IBKR balance ($78) stays where it is. |

## The stopping rule, re-scoped and not loosened

`docs/10` fixed a rule in advance: eight candidates with named mechanisms
through the full gates and none surviving means *no edge is accessible at
this account size with this data*. Programme 1 ran nine families and 46
memos against **that** account size, **that** data (daily spot and ETF bars)
and **that** benchmark (buy-and-hold of a rising universe), and the handover
records the finding. The rule's premise is what Programme 2 changes — the
instruments, the resolution, the point-in-time data, and the comparator for
market-neutral books — so it starts its own counter at zero under the same
numbers: **eight gated mechanism candidates, 3× cost bar, 250 variants a
family, 2 promotions a week, 5 a quarter.** Gate 4 deflates against each
hypothesis's own variant count (`GateContext.trial_count`: the sweep, else
the log's count for that hypothesis id), not against a global total. The
handover's 1,541 is 492 distinct variants re-run about three times (the
account-size sweep and the holdout openings); reconciled from the log on
15 September 2026 after an independent plan asked the question. That
figure governs the research policy's budget, not any deflation. This
paragraph is the record that the counter was restarted deliberately and
why, so it cannot be read later as a quiet relaxation.

Two corrections to the handover's own text, for the record: five of nine
families stopped at gate 5 (four crypto, `etf_tsmom_v1`), two at gate 3,
one at gate 2 and the control at gate 6 — not eight at gate 5; and the
"$0.35 per order = 35 bps at $1,000" sentence means the $83–$100 orders a
twelve-name basket implies at that equity, where the floor is 35–42 bps per
leg. The engine charged the floor per order correctly; the sentence was
loose, and it is stated precisely here.

## Week 1 log

**Built on 15 September 2026, tests green, no run counted:**

- `GateContext.benchmark` (`buyhold` | `cash`) and `risk_free`; gate 5 tests
  against `qr.validate.spa.cash_benchmark` when told to, and says which
  comparator it used in its detail and in `stats["benchmark"]`. Part of the
  pre-registration, exposed as `qr gates --benchmark cash --risk-free fred`.
- `qr data riskfree-pull`: FRED DTB3 → `reference/risk_free_dtb3.parquet`
  (18,165 observations, 1954-01-04 to 2026-09-11, 3.92% on the last day).
- `CostModel.binance_perp()` (regular user 2.0/5.0 bps, 10% off in BNB;
  **unverified** until read off the account's own fee panel) and
  `CostModel.hyperliquid_perp()` (1.5/4.5 bps, verified against the venue's
  docs on 2026-09-15). Both `funding=True`.
- Funding enters **gross**, not costs: `qr.research.runner.funding_pnl`,
  sign convention longs pay a positive rate, applied only when the cost model
  settles funding. `BacktestResult.carry` keeps it visible.
- **A gate-5 defect found by the new control and closed the same day.** A
  family whose variants never took a position reached gate 5 with a PBO of
  zero, the SPA half refused to run on constant series, and the gate read
  PASS with the error in its stats. It now fails outright when no variant
  ever traded and cannot pass when SPA could not run for any other reason.
  Every Programme 1 report was computed before this change; none of the nine
  families reached gate 5 with untraded variants, so no verdict moves.
- Perp data: daily bars for every USDT perpetual and funding for every
  perpetual are being mirrored into `$QR_ROOT` (`~/qr/lake`); metrics were
  already there for 40 symbols.

- **Liquidation recorder** (`scripts/record_liquidations.py`), three venues.
  Probed live on 2026-09-15 from Dubai: Binance's futures websocket
  connects and sends nothing (its REST answers; the block is on the stream),
  so the default venue is **OKX** (`liquidation-orders`, every SWAP in one
  subscription; 5 events in a 90-second smoke) with **Bybit** second
  (`allLiquidation.<symbol>` across 770 USDT perps; 6 events in 90 seconds).
  One JSON line per event under `$QR_ROOT/liquidations/<venue>/<day>.jsonl`.
  **Running since 11:02 UTC on 15 September 2026 on the always-on box**
  (root@91.98.172.9, the host that runs the ETF share-count collector):
  `qr-liq-okx.service` and `qr-liq-bybit.service`, each in its own
  virtualenv at `/root/liq/.venv`, writing `/root/liq/data/<venue>/`.
  Binance's stream is silent from Germany as well, so it is not deployed.
  Check with `ssh 91.98.172.9 'systemctl status qr-liq-okx qr-liq-bybit;
  wc -l /root/liq/data/*/*.jsonl'`.
- **The carry unit and family C1, built ahead of week 2.** `qr/data/carry.py`
  turns a spot series, a perp series and the funding feature into one
  synthetic instrument (price = spot / perp, so its return is exactly the
  pair's; funding stored with the short leg's sign; liquidity = the thinner
  leg) and `qr data carry-build` writes it under market `carry-um`.
  `FundingCarry` (`qr/strategies/carry.py`) opens units above an annualised
  funding floor, keeps them above a lower exit, refuses to open in the top
  tail of the coin's own trailing year (the BIS crash filter), and is
  benchmarked against cash. `CostModel.carry_pair` adds the two legs' costs:
  15 bps a side, 30 a round trip, 60 stressed.
- **A second defect, found by the carry round-trip test.** The lake's panel
  loader joined the raw perp funding feature onto *every* Binance panel,
  including one that had defined `funding_rate` itself, and so flipped the
  carry unit's receipt back into a payment after loading — the file on disk
  was right and the panel in memory was wrong. It now leaves a panel's own
  `funding_rate` alone. No Programme 1 result touched this path.

- **Perp bars into the lake, with two ingest defects on the way.** The
  futures bucket writes a header row with `count`, `taker_buy_volume`,
  `taker_buy_quote_volume` where spot has `trades`, `taker_buy_base`,
  `taker_buy_quote`; the parser now maps them (test added). Worse: `qr data
  ingest` never passed `--market` through to the lake, so the first perp
  ingest wrote 864 perpetual series **over the spot market** and replaced
  the instruments table. The mirror was untouched; the repair was to purge
  the 393 perp-only symbols from the spot market, re-ingest all 734 spot
  series from the mirror, then ingest the perps under `futures/um` with
  their own `instruments_futures_um` reference. The trial log is a separate
  file and was never touched; `qr trial verify` is the check. Any Programme
  1 report cites the manifest hash it was computed on, which the log keeps.
- `qr gates --market carry-um --costs carry` runs a family on the carry
  panel with the two-leg cost model; the universe's volatility floor reads
  the spot leg there (`UniverseSpec.vol_field`), because the unit's own
  price is spot / perp and never moves.

**Not yet done from the week-1 list:** the Polymarket book recorder; the C1
pre-registration (drafted at `docs/prereg/p2_funding_carry_v1.md`, to be
registered only after `qr data carry-build` has run and the universe file
is checked, and before any run); the recorders running on a permanent host;
and the QuantConnect / Alpaca / Databento accounts, which only the owner can
open.

**15 September 2026, evening (the Opus 5 build session, `docs/21`).** Trial
log at the end of the session: 1,801 trials, chain verified (`qr trial
verify`), up from 1,541. Everything below is re-derived from the log and the
gate JSON.

- **Data finished.** Funding ingested for all 471 both-leg symbols; 471
  carry units built (`carry-um`, manifest `f2d67332…`). The bucket's monthly
  funding archive ends with August 2026, so the last carry bar is
  **2026-08-31**, not 14 September; the C1 amendment records it. No
  redenomination artefact was found among the 471 units.
- **Universe read before registration** (C1 amendment §3): `carry_top40`
  holds 40 members every month from 2021; 194 symbols ever members; no peg,
  fiat, gold or leveraged token; no member-bar under the 15% spot-vol floor.
  Mean perp funding of members, annualised: 2020 +23%, 2021 +38%, 2022 −6%,
  2023 +2%, 2024 +12%, 2025 −1%, 2026 −10%.
- **Four engine defects found by C1's first runs, fixed the same day, each
  with a test:** (1) the carry unit's high/low equalled its close while its
  open did not, so `Panel.tradable()` rejected nearly every bar and the
  universe read empty — found *before* registration; (2) the unit's `volume`
  was the thinner leg's coin count, so the QA identity quote = volume × price
  failed every unit at gate 1; (3) `permute_panel` dropped every field
  outside OHLC and volume (a permuted carry panel had no funding; gate 6
  raised) and, worse, aligned the global permutation by rank within each
  symbol's live window, so symbols with different listing dates lost their
  cross-section — mean pairwise funding correlation of eight majors fell from
  0.63 to 0.03 and the always-in control sat at the 0th percentile of its own
  null (p = 1.000); now by bar, and the control reads p = 0.12; (4) **a
  one-bar look-ahead in every non-daily-rebalanced book**: `hold_between`
  grew the book held over bar *t* by bar *t*'s own return (and the runner's
  turnover drift did the same), tilting toward that bar's winners before it
  happened — about half the variance per bar. Every Programme 1 monthly and
  weekly family ran with it; all failed regardless, so no verdict moves, but
  their gross figures were flattered. The reference loop in the test suite
  carried the same defect and is corrected. Defects 3 and 4 change gate 6
  and every scheduled book for every future run; Programme 1 reports predate
  them.
- **C1 `p2_funding_carry_v1`: registered (seq 385), run in-sample to
  2025-09-14, verdict FAIL at gate 1; every other gate shown with
  `--all-gates`.** Best variant lookback 30, entry 5%, ceiling 1.0, n_max 5.
  Gate 1: gross Sharpe 9.9 / 9.7 / 9.2 at lags 0 / 1 / 2 — no spike, but
  above the engine's 8.0 plausibility ceiling. Gates 2–8: 94% of gross
  survives, Sharpe 7.8 at 2× costs, capacity ~$300M; t = 9.7; DSR 1.00 over
  64 trials; PBO 0.00, SPA p = 0.008 vs cash with 61 of 64 variants
  surviving StepM; bar-permutation p = 0.005 (re-optimised), random-entry
  p = 0.005; gate 7 WARN (WFE 0.47, all 9 paths positive); gate 8 PASS (71
  round trips, profitable every year, Sharpe 8.1 without the best year).
  Tear sheet: CAGR 15.8%, vol 1.7%, max drawdown −1.6%, net Sharpe 8.85,
  turnover 6.7×/yr, 91% time in market. **The leak hunt found no leak:**
  funding settlements floor to their UTC day and are credited to the book
  held over that day; the three lags agree; the 9 member-bars in 71,383 with
  |basis| > 5% are real events (OMG Nov 2021, LUNA 12 May 2022, SOL at
  FTX). The number is arithmetic: a member unit's daily-close return vol is
  ~1.5%/yr (p90 3.6%) against ~10%/yr median (p90 32%) of persistent
  funding, and the always-in book with no rule at all reads 3.9 gross. What
  the daily-close backtest cannot see is intraday basis, liquidation, ADL and
  venue failure. The pre-registration predicted net 3–8%, vol 3–6%, Sharpe
  0.8–1.5 and said a Sharpe above 3 means look for a leak; that was done.
  The gate-1 ceiling was **not** changed after seeing the result. The
  funding share of gross (falsifier: ≥ 80%) is not in this report; the tear
  sheet now carries `carry_share_of_gross` for every future run.
- **Controls.** Always-in carry (`p2_funding_carry_v1_always_in`, seq 392,
  one variant, hold every eligible unit): gate 1 WARN, gross 5.1 / net 4.8,
  93% survives, t = 5.8, gate 6 p = 0.12 (fails, as a timing-free control
  should), gate 8 fails on parameter count by construction. So the entry
  rule roughly doubles the Sharpe of holding everything, and is what gate 6
  credits. Hold-T-bill is the benchmark itself (SPA above). The control is
  being re-run overnight on the committed engine (defect 4 changed
  turnover slightly).
- **Holdout not opened.** The pre-registration opens it once, after gates
  1–8 are complete; a family that failed gate 1 does not spend it.
- **Engine additions for the stock families (all with tests):**
  `--benchmark exposure` (buy-and-hold of the eligible universe at the best
  variant's mean gross exposure, remainder at DTB3; a half-invested tracker
  passes against cash in a rising world and is nothing against it);
  `CostModel.alpaca_zero()` ($0, 2 bps half-spread placeholder, 1 bp PFOF
  slippage, whole shares floored in the runner); the four owed audit cases
  as hand-computed tests (one leg unfilled; a redenomination hitting the
  legs on different days, masked, while a persistent LUNA-style basis is
  not; a Form 4 amendment published after the signal, via
  `qr/data/pit.py::asof_view`; a funding-interval change, with the interval
  now kept by the parser).
- **E5.** Form 4 loader (`qr/data/form4.py`) from the SEC insider-transactions
  data sets with EDGAR acceptance times from the submissions API as
  `published_at`. **Labelling audit** (`docs/audit/`): 100 filings from
  2025 Q1 labelled with no price data; first parser 76% precision, every
  miss visible in the filing's fields; six mechanical rules added; revised
  parser **98.6% precision (72/73), 94.7% recall**. `p2_insider_cluster_v1`
  amended and **registered (seq 427)**. No run: prices need the owner's
  QuantConnect account and nothing was substituted.
- **Overnight chain** (`scripts/overnight_2026-09-15.sh`, status in
  `~/qr/lake/logs/overnight_status.txt`): control re-run; hourly bars for
  all 864 perps and the 471 both-leg spot pairs; Form 4 history 2006–2026 Q2
  with acceptance times → `reference/form4_purchases.parquet` and
  `form4_clusters.parquet`; open-interest metrics for the 471 symbols;
  `pytest`, `qr trial verify`. Nothing registers, trades, spends or opens a
  holdout.
- **For the owner, in the morning:** (a) C1's gate-1 ceiling — a `v2` with
  the argument written before its run, and better, an hourly carry unit
  (8-hour funding aligned to the bars, intraday basis visible) once the
  hourly bars are in, which is the plan's own resolution fix applied to its
  own family; (b) QuantConnect, Alpaca and Databento accounts (E5 is
  registered and waiting; E1/E2 queued); (c) C3 waits on weeks of the
  liquidation recorders (12k events on day one); C5 on the hourly bars and
  OI now downloading; C2 needs a second venue's funding; C4 needs unlock
  schedules — none of these was drafted, because their data is not in the
  lake yet.

**16 September 2026, morning — what the overnight chain did.** Hourly perp
bars: 42,766 files, none failed, **864 series** ingested (BTCUSDT 58,440
bars, 2020-01-01 → 2026-08-31). Hourly spot bars for the 471 both-leg
symbols: 42,224 files, none failed, **471 series** ingested. Form 4 history
2006 Q1 → 2026 Q2: **148,431 qualifying purchases, all 148,431 stamped with
EDGAR acceptance times** (9.28M accessions indexed from the submissions
API, cached under `mirror/sec/submissions`), **14,256 cluster signals** at
the registered rule → `reference/form4_purchases.parquet`,
`form4_clusters.parquet`, `form4_mirror_summary.json`. Two filing-data
defects stopped the mirror and were fixed with tests: quarters before 2023
have no `AFF10B5ONE` column (the 10b5-1 checkbox), and 2012 Q3 carries a
transaction dated in the year 12. The control re-run on the committed engine
reproduced the previous numbers exactly. The open-interest metrics pull
(one request per symbol-day) was still running at 06:45 with 77 of 471
symbols mirrored; it is resumable and its ingest, `pytest` and `qr trial
verify` follow it in the chain. Owner opened the QuantConnect, Alpaca and
Databento accounts this morning.

**16 September 2026, midday — C1 on hourly bars (`p2_funding_carry_v2`).**
Trial log 1,866 trials, chain verified. Built and tested: hourly carry
units (settlement on the bar it was held for, `bar_funding`), bar-generic
`FundingCarry` (annualised by the panel's bar count; the ceiling's
percentile over decision bars), `--vol-lookback`. **A fifth defect** found
while vectorising the book loop: when fewer than `n_max` units cleared the
entry floor, the pandas version filled the spare room with the
alphabetically first *non-qualifying* units (`score.where(candidates)
.sort_values().index[:room]` keeps the NaN tail). The v1 run carried it;
v1's report stands as recorded. v2 and its always-in control were
registered (seq 448, 449) before any run, with predictions: net Sharpe 1–3,
gross below 8, funding ≥ 80% of gross.

- **v2 control** (hold every eligible hourly unit, decisions daily): gate 1
  WARN (the 8.0 ceiling no longer binds: gross 2.7), net Sharpe 2.42, 92% of
  gross survives, t = 11.6, gate 6 p = 0.63 (a timing-free book at its
  null, as it should be), capacity ~$30M. Against the daily-close control's
  4.76: hourly resolution halves the Sharpe of the same book.
- **v2 family, as run — verdict FAIL at gates 6 and 8.** Gate 1 WARN (gross
  3.54 / 3.56 / 3.55 at lags 0 / 1 / 2 — no spike, below the ceiling);
  gate 2 PASS (88% survives, Sharpe 2.63 at 2× costs, capacity ~$10M);
  gate 3 t = 12.9; gate 4 DSR 0.998 over 64 trials, haircut Sharpe 3.10;
  gate 5 WARN (PBO 0.39 — the variants are interchangeable; SPA p = 0.000
  vs cash, 63 of 64 survive StepM); **gate 6 FAIL: bar-permutation p =
  0.49** (null median 4.03 vs observed 3.56; random-entry p = 0.005);
  gate 7 WARN (median path 81% of in-sample, WFE 0.35); **gate 8 FAIL:
  neighbours keep 69% of the peak Sharpe (a spike)**. Tear sheet: CAGR
  14.2%, vol 4.3%, max drawdown −4.5%, net Sharpe 3.10, turnover 12.7×/yr,
  **funding = 100% of gross** (`carry_share_of_gross` 1.005: the basis
  contributed slightly less than nothing), so the mechanism named is the
  one that paid; the predictions on sign, size and funding share held. What
  gate 6 says is that a world with the same funding and basis values in a
  shuffled order pays the *timed* book as well as the real one does — the
  entry rule's timing adds nothing over holding the carry, which is the
  control's answer too (2.42 without a rule against 3.10 with one, and the
  difference does not survive the permutation).
- **But the run did not match the registration, and it is being re-run.**
  The invocation passed `--param rebalance=24 --param percentile_window=365`
  beside `--grid`, and the CLI silently dropped `--param` whenever `--grid`
  was present (a sixth defect, `_build_grid`, fixed with a test): the 64
  variants decided **hourly** (`rebalance=1`), not daily as registered. The
  control, run with `--param` alone, was correct. The registered
  configuration (daily decisions on hourly bars) started at 11:55 and is
  counted as a further 64 trials; the document is unchanged and needs no
  re-registration. The run above stands in the log as what it was.
- **Databento.** Key verified; E1's imbalance history bought for SPY, QQQ,
  IWM, DIA, 2018-05-01 → 2026-09-01: **$6.27** of the $125 credit, 3.76M
  messages, hash and time in a sidecar. Only **QQQ** carries a real Nasdaq
  closing cross (median $122M paired at 15:58); SPY, DIA and IWM are
  Arca-listed and Nasdaq's secondary cross in them is empty — the plan's own
  table said Arca imbalance exists from 2025 only, and the scope did not
  apply it. E1's universe must be Nasdaq-listed names; a ~30-name pull is
  ~$45 and waits for the owner's yes. Loader `qr/data/imbalance.py` (last
  message at or before 15:50 / 15:55 / 15:58 ET, `published_at` = receive
  time, `age_seconds`), 24,132 snapshots in `features/imbalance/`.
- **QuantConnect.** Free tier confirmed browser-only (no API, no data
  download). Driven from here through the owner's logged-in Chrome: a probe
  project built and ran on the free node. Facts: the algorithm's working
  directory is `/QuantConnect/backtesting` and project data files are not
  readable with `open()`; Python files are importable, so E5's signals go in
  as a `.py` module; the IDE's Return copies the previous line's indent
  (`qc/monaco_type.py` types code accordingly).

**16 September 2026, afternoon — E1 data complete.** Owner approved the
stock pull; a streamed request dropped after 20 MB (`IncompleteRead`), so
it was resubmitted as a Databento **batch job** (`XNAS-20260916-Q6HSRHN5G6`,
100 monthly files, 570 MB, **$48.99**, billed once; `scripts/databento_fetch_job.py`).
30 Nasdaq-listed large caps that were Nasdaq-100 members throughout
2018–2026 (AAPL MSFT NVDA AMZN META GOOGL GOOG TSLA AVGO COST NFLX AMD PEP
CSCO ADBE INTU QCOM TXN ISRG AMGN CMCSA INTC BKNG AMAT MU LRCX ADI GILD SBUX
MDLZ): 29.4M messages → 178,581 closing-auction snapshots; with the ETF
file, **202,713 snapshots, 34 symbols** in `features/imbalance/`. Every
one of the 30 has a real Nasdaq closing cross (median paired $59M–$903M at
15:58; imbalance non-zero on 63–87% of sessions). Gaps to carry into E1's
pre-registration: META's raw symbol starts June 2022 (FB before); the list
is names that survived in the index, which is a mild survivorship on
liquidity, not on returns, and is stated. Databento credit used so far:
$55.26 of $125.

**16 September 2026, 15:00 — `p2_funding_carry_v2` as registered (daily
decisions on hourly bars): verdict FAIL at gate 6.** 1,930 trials, chain
verified. Best variant lookback 720, entry 5%, ceiling 0.95, n_max 10,
rebalance 24. Gate 1 WARN (gross 3.39 / 3.36 / 3.36 at lags 0 / 1 / 2;
below the ceiling); gate 2 PASS (92% survives, Sharpe 2.81 at 2× costs,
capacity ~$10M); gate 3 t = 15.0; gate 4 DSR 0.99, haircut 3.09; gate 5
WARN — PBO 0.35 and **SPA did not run** ("zero-size array to reduction
operation maximum", inside `arch`; a seventh defect, open: it does not
reproduce on synthetic inputs of the same shape, and runs now save their
variant-return matrix beside the report so the next occurrence can be
diagnosed); **gate 6 FAIL: bar-permutation p = 0.99 — the permuted worlds
pay the re-optimised book *more* (null median 4.40 against 3.36)**;
random-entry p = 0.005; gate 7 WARN (83% of in-sample, WFE 0.12); gate 8
PASS (181 round trips, every year profitable, plateau). Tear sheet: CAGR
15.5%, vol 4.7%, max drawdown −6.3%, net Sharpe 3.09, turnover 8.5×/yr,
funding 97% of gross. Every prediction on sign, size and mechanism held;
the timing did not. What p = 0.99 means is specific and is the BIS paper's
own finding: in the real sequence the basis losses arrive *when* funding is
high — the crash risk the ceiling was meant to filter — and shuffling the
bars detaches them, so a world with the same funding in random order pays
more. The rule collects the carry and eats its crashes; it does not time
them. Beside it, the same book with hourly decisions read p = 0.49 and
failed gate 8 as a spike; the always-in control read p = 0.63 at Sharpe
2.42. **Holdout not opened** (gates 1–8 did not pass). C1 is closed at
two runs and one control on each resolution: hold-the-carry is a real,
funding-paid return of Sharpe ~2.4 net at hourly resolution on daily
closes' arithmetic of 4.8; the entry rule is not an edge over it. That is
the first Programme 2 mechanism candidate gated: **1 of 8**.

**16 September 2026, evening — E1 `p2_auction_imbalance_v1`: verdict FAIL
at gate 2.** 1,964 trials, chain verified. Built with tests: the
`auction-xnas` instrument (bar return = open(t) / close(t−1) − 1, split
nights empty, `META` from 9 June 2022 because the raw ticker was an ETF
before), `AuctionFade` (`side=sell` family, `side=buy` mirror), `--basket
nasdaq31`, `--costs alpaca`, `--equity`, the XNYS calendar for gate 1;
minute and daily bars for the 31 names bought as batch jobs ($21.94 +
$0.10; Databento used $77.30 of $125). Registered at seq 480 (mirror 481)
after the QA read, whose amendment is in the document. **An eighth defect**:
Databento's `side` is `A` (ask) for a sell imbalance and the loader mapped
`S`, so every sell imbalance read as zero and the first family run
(counted, 16 trials, stands) never took a position; fixed with a test on
the real codes, snapshots and panel rebuilt, both hypotheses re-run.
Results, best variant k = 0.20, 15:55, n_max 8, $1,000 book: gross 1.9%
a year on 42% time in market over 1,188 round trips — **about 9 bps gross
per event, inside the pre-registered 5–15** — of which the 6-bps round
trip takes half (net 0.95%/yr, vol 1.4%, Sharpe 0.66, max drawdown −1.9%);
gate 2 FAIL (costs eat 50%, all of it spread), gate 3 t = 1.84, gate 4
DSR 0.61 over 16, **gate 5 SPA p = 0.51 vs the exposure-matched benchmark
(7% invested)**, gate 6 p = 0.10 / random-entry 0.07, gate 7 44% of paths
positive, gate 8 alpha t = 0.24. Two falsifiers fired independently of
costs: the benchmark was not beaten, and the return is **not monotone in
the threshold** (k = 0.10 earns more than k = 0.50), so the imbalance is
not shown to be the driver. Mirror control (`side=buy`): t = −0.19, costs
108% of gross — as the mechanism predicts, and it says the family's gross
is not overnight drift either. Holdout not opened. Mechanism candidate
**2 of 8**. The $100,000 twenty-position companion book is registered as
`p2_auction_imbalance_v1_100k` and runs overnight.

**16 September 2026, evening — E5 `p2_insider_cluster_v1` run on
QuantConnect's free tier, through the owner's Chrome.** Alpaca paper keys
verified (account ACTIVE, $100k paper cash, IEX quotes answer; nothing
traded). QC facts: no API on the free tier; one coding session at a time;
`self.download()` works, so the 10,877 cluster signals (2010 →, zlib +
base64, SHA-256 checked in the algorithm) are fetched from this repo's
public branch (`qc/e5_signals.b64`; the owner made the repo public for
it); results leave as JSON saved from the logged-in session
(`/api/v2/backtests/read` and `chart/read`), read by
`qr/data/quantconnect.py`. Algorithm `qc/e5_main.py`: entry MOO at the
second session after acceptance, exit MOO after `hold` sessions, price >
$5 and 20-session median dollar volume > $5M at entry, $1,000 book, 4
whole-share slices, $0 fees (spread charged locally). Two LEAN defects
fixed on the way (a security cannot be ordered on its first bar; a
history frame without `volume`). All **8 pre-registered variants** ran
(≈7 min each) and are in `mirror/quantconnect/e5/`:

| hold | min $ | insiders | $1,000 → | gross Sharpe | max DD | round trips |
|---|---|---|---|---|---|---|
| 60 | 100k | 2 | 2,017 | 0.30 | 64% | 351 |
| **20** | **100k** | **2** | **11,629** | **0.72** | 47% | 895 |
| 60 | 250k | 2 | 1,726 | 0.26 | 52% | 328 |
| 20 | 250k | 2 | 4,029 | 0.48 | 56% | 789 |
| 60 | 100k | 3 | 2,182 | 0.35 | 48% | 134 |
| 20 | 100k | 3 | 1,489 | 0.26 | 53% | 147 |
| 60 | 250k | 3 | 1,174 | 0.14 | 46% | 60 |
| 20 | 250k | 3 | 909 | 0.01 | 47% | 63 |

`scripts/e5_external_gates.py` records the sweep in the trial log (seq
535; seq 533 recorded 4,084 "variants" by a script slip — the session
count — and seq 534 is the correction) and computes what the engine's own
functions can from series: best variant **net Sharpe 0.69** after the
alpaca_zero round trip (95% of gross survives, 0.66 at 2×), **HAC t =
2.90**, PSR 0.997, **DSR 0.94 over 8**, PBO 0.23 (OOS loss 15%). So E5
clears gates 2–4 on the statistics; the pre-registered comparison
(exposure-matched equal weight of the eligible universe) and the
random-entry control are QC runs in a second project
(`qc/e5_benchmark_main.py`), the benchmark running as this was written.
Gates 1, 6 and 8 cannot run on an external engine and the report says so;
the single-draw random control stands beside gate 6 as evidence, not as
a p-value. Not to be read as a pass: 4 positions of small caps, 47%
drawdown, and the 20-session hold is the shorter of the two declared, not
the paper's.

**16 September 2026, night — E5 verdict: FAIL, on the pre-registered
falsifiers for gates 5 and 8.** The comparison runs (`qc/e5_benchmark_main.py`,
project 36614350): the first equal-weight benchmark hit LEAN's 10,000-order
cap in May 2017 and sat in cash after (moved to `e5_benchmark/invalid_order_cap/`,
not used); the second, rebalanced annually (2,648 orders, trading to
2025-08-28), is the **exposure-matched benchmark: equal weight of the 500
most-traded eligible names, 10.6%/yr, Sharpe 0.69, drawdown 35%**. The
**random-entry control** (same signal dates and sizing, a random eligible
name each time, one draw, seed 1): 5.1%/yr, Sharpe 0.33, drawdown 41%.
Against the benchmark the family's best variant has **SPA p = 0.19** (no
StepM survivor), **alpha 6.0%/yr with t = 1.31, beta 1.05** (HAC, 9 lags);
family minus control 10.0%/yr, **t = 1.77**. The pre-registration set
"alpha t below 2 against the market factor → the return is beta" and "not
distinguishable from zero with clustered errors → the mechanism is not
there in this period"; both fire. Same Sharpe as holding the universe,
more return only through 4-stock concentration and a 47% drawdown.
By year the family beat the benchmark in 8 of 16, and lost to it in 2013,
2023 and 2024. Gates 1, 6 and 8 could not run in full on an external
engine (no panel); gate 4 (DSR 0.94) and gate 2 pass; recorded as such,
trial log seq 535–537. Holdout not opened. Mechanism candidate **3 of 8**.
What it would take to reopen: the long/short version with shorting (the
paper's specification), or a 20-position book — both need ≥ $2,000 and a
finding, not a re-run of this one.

**16 September 2026, late — E2 `p2_late_day_momentum_v1`: verdict FAIL at
gate 2.** Built with tests: the `intraday-xnas` instrument (two bars a
session from Nasdaq minute bars: 09:30 → 15:30 carrying `ret_to_decision`,
15:30 → 16:00 carrying the trade; overnight gap dropped), `LateDayMomentum`
(long-only, `side=reverse` control), basket `qqq`, and a `sessions2` QA
calendar because the cadence checks assume one bar a period (gate 1 had
failed on `bar_spacing` — an artefact, fixed with a test, re-run). Registered
(seq 538, control 539) after the unconditional read only (2,094 sessions,
+0.43 bps a late bar). Result, 4 variants k ∈ {0, 0.25%, 0.5%, 1%}: the
last half hour of QQQ, 2018–2026, is **uncorrelated with the day's move
(r = 0.006)**: up-days +0.04 bps, days up ≥ 1% **−2.7 bps**, down-days +0.9
bps; every variant's gross is negative, best HAC t = −2.63, SPA vs cash p =
0.50, no monotone relation in k (it runs the wrong way). The reverse
control also loses (t = −2.48). Two pre-registered falsifiers fire (gross
per fire below 2 bps; no monotone relation), before costs are even
charged. Baltussen et al.'s sample ends in 2020 and is in futures; in
QQQ's own last half hour since 2018 the hedging demand is not visible at
this resolution. Mechanism candidate **4 of 8**. SPY/IWM (~$1.50 of
minute bars) would be the same test on a different index, not a new
mechanism, and are not queued. Trial count 2,006 after a `void` note (seq
580) took the miscounted seq 533 out of the count without touching the log;
`TrialLog.trial_count` honours `void_seq`, with a test.

**17 September 2026, 03:40 Dubai — E4 `p2_pead_v1`: verdict FAIL at
gates 3, 4 and 5.** Run on QuantConnect's free tier (four pre-registered
variants, two controls, six backtests; equity curves mirrored under
`mirror/quantconnect/e4/`, gates 2–5 by `scripts/external_gates.py
--family e4`, trial log seq 584, count 2,010). Events: 8-K item 2.02
filings from the submissions mirror (`qr/data/earnings.py`), ranked by the
two-session announcement return, long the top decile, $1,000 book,
`alpaca_zero`, 2010-01 → 2025-08.

| impl | hold | top | final $ | Sharpe | max DD | orders |
|---|---|---|---|---|---|---|
| e4_h60_t20 | 60 | 0.20 | 2,926 | 0.37 | 68% | 718 |
| e4_h20_t20 | 20 | 0.20 | 1,512 | 0.24 | 77% | 1,986 |
| e4_h60_t10 | 60 | 0.10 | 1,373 | 0.21 | 74% | 688 |
| e4_h20_t10 | 20 | 0.10 | 476 | −0.02 | 77% | 1,767 |
| control: bottom decile | 60 | 0.20 | (−3.6%/yr) | 0.03 | 84% | — |
| control: random events | 60 | 0.20 | (+3.6%/yr) | 0.15 | 57% | — |

Best variant e4_h60_t20: net Sharpe 0.36, net/gross 0.97, Sharpe at 2×
costs 0.35 (gate 2 passes — a 60-session hold is cheap); HAC t = 1.37,
p = 0.17 (**gate 3 fails**); PSR 0.93, DSR 0.76 over 4 (**gate 4 fails**,
bar 0.90); PBO 0.41 with a 22% out-of-sample loss; SPA p = 0.76 against
the exposure-matched benchmark (**gate 5 fails**), best excess −0.1%/yr.
Alpha regression against the E5 equal-weight eligible universe (v2,
annual rebalance; 4,084 common sessions): **alpha −2.9%/yr, t = −0.50,
beta 1.28**, benchmark Sharpe 0.69 vs family 0.37. The ordering top >
random > bottom is the right way round (the bottom-decile mirror earns
nothing), so a small drift may exist, but a four-position book at $1,000
turns it into noise, and after beta there is nothing left — exactly the
pre-registered prior. Two falsifiers fire (alpha t < 2; SPA > 0.5) plus
gate 4. Mechanism candidate **5 of 8**. Holdout not opened.

Night chains: night-2 (Databento bars) and night-3 (FTD 212 zips, Reg SHO
2,042, FINRA SI 179 files, Bybit funding 765 symbols, pytest 791 passed)
finished; night-4 is still waiting on the Binance `metrics` pull (open
interest; 415 of the 471 both-leg symbols started, ~800 files a
minute, workers alive) before the C5 mechanical check decides whether C5
is registered and run.

**17 September 2026, 09:15 Dubai — C5 `p2_oi_reversal_v1`: verdict FAIL at
gate 3 (and 4, 5, 6).** Registered by the night chain at seq 585 (control
586) after the mechanical universe check passed, and only then. Two
defects surfaced on the way, both closed with tests before the counted
re-run:

- *The check itself.* Its stablecoin/fiat-base filter tested `"TUSD"`,
  `"BUSD"` as substrings and so flagged DOTUSDT, ARBUSDT and 44 other real
  assets → FAIL. Fixed to an exact base-asset match
  (`scripts/c5_universe_check.py`); no return was read. Open interest was
  also ingested for the 187 perp-only USDT symbols already mirrored (the
  first ingest covered only the 471 both-leg names). Final check: members
  per bar median 119 (min 0 before `min_history`, max 120), OI coverage
  median 1.00 with 20 names below 0.5 (perp-only names whose metrics the
  workers had not reached — KAS, LUNA2 and the like; 20 of 359 ever-members),
  OI observed from 2021-12-01, sample 1,370 bars, **PASS**.
- *Gate 1 on the perp lake.* Both runs stopped at gate 1: Binance's `um`
  daily archive carries **24 bars (19 pairs, five dates in September and
  November 2023) whose quote volume is ~1.5× what the bar's range allows**
  (AAVE 2023-09-21: implied VWAP $96 against a high of $66). `qa.check_klines`
  had always flagged them; `Panel.tradable` did not withhold them, so the
  gate failed a book for bars the platform had served. `tradable()` now
  withholds a bar whose implied VWAP lies outside [low·0.95, high·1.05]
  (same tolerance as QA; the third "cannot be true" rule after negative
  volume and high-below-close), and `permute_panel` carries quote volume
  as a ratio to close so the permuted bars stay consistent. Three synthetic
  fixtures that scaled price or quote volume alone were made consistent.
  792 tests pass. The first, gate-1-blocked family attempt was still
  written to the trial log (seq 587–604) and counts.

Re-run (night-4d), 2021-12 → 2025-08, `futures/um` ranks 31–150, `--costs
perp`, benchmark cash:

| run | gate 1 | gate 2 | gate 3 | gate 4 | gate 5 | gate 6 | gate 7 | gate 8 |
|---|---|---|---|---|---|---|---|---|
| control (unconditioned, 1 variant) | WARN | **FAIL** gross ≤ 0 | HAC t −0.80 | DSR 0.27 | skip | p 0.92 | 0/9 paths | 40% years |
| family (18 variants) | WARN | PASS 78% net/gross, Sharpe 0.60 at 2× | **FAIL** HAC t 1.68 (p 0.09) | FAIL DSR 0.63 (eff. rank 5) | FAIL PBO 0.43, SPA p 0.46 | FAIL p 0.35 re-optimised; random-entry 0.005 | WARN 0.62 = 74% IS, 8/9 paths | FAIL alpha t 1.69 |

Best variant `lookback3_n_side10_oi_min0.1_rebalance_W`: net Sharpe 0.84
(gross 1.07), 16.9%/yr, vol 20%, max DD 23%, turnover 71×/yr, 2,291 round
trips, capacity ~$30k. What that means: the pre-registered falsifier
"DSR below 0.90 over 18" fires, and the unconditioned control earning
*nothing* (t −0.80) while the OI-conditioned book earns t 1.68 is the
right direction but not evidence — PSR 0.95 over 3.75 years with a
minimum track record of 8.3 years, and a re-optimised permutation null
that reaches the observed Sharpe 35% of the time. The 9-path CV is the
one thing that looks alive (8 of 9 positive, WFE 0.47). Not enough to
pass; not nothing. Mechanism candidate **6 of 8**. Holdout not opened.
Trial count **2,048** (624 records, chain verified).

What it would take to reopen: the same rule on a longer sample (OI
metrics start 2021-12, so the sample cannot grow backwards) or on a
second venue's OI (Bybit's is mirrored for funding only) — a new
pre-registration, not a re-run.

**17 September 2026, 14:30 Dubai — C2 `p2_venue_spread_v1`: verdict FAIL
at gate 3 (and 4, 5, 6).** Registered seq 624 (control 625) after the
owner's yes on the unit read (`docs/prereg/p2_venue_spread_v1.md`: 942
units, spread persistence 0.20, 25 bps a round trip). Built the same
morning: Bybit daily klines (`qr/data/bybit.py::kline_history`, 765
symbols), the cross-venue unit (`qr/data/xvenue.py`, `xvenue-um`, two
mirrored units a symbol so `FundingCarry` runs unchanged), `CostModel.bybit_perp`
(5.5 bps taker, unverified), `--costs xvenue`; tests. Run 2021-01 →
2025-08, top 80 units:

| run | gate 2 | gate 3 | gate 4 | gate 5 | gate 6 | gate 7 | gate 8 |
|---|---|---|---|---|---|---|---|
| always-in control | **FAIL** gross ≤ 0 | t −2.45 | — | skip | p 0.57 | 0/9 | 0% of years |
| family (18) | WARN 55% net/gross | **FAIL** t 1.76 | FAIL DSR 0.71 (eff. 3) | FAIL PBO 0.73, SPA p 0.97 vs cash | FAIL p 0.17 | FAIL 0.18 = 29% IS | 32 round trips |

Best variant `lookback7_entry0.05_n_max5`: net Sharpe 0.62 (gross 1.16),
2.0%/yr at 3.1% vol, drawdown 3.1%, in the market 30% of the time, 32
round trips in 4.7 years, funding 96% of gross. So the spread is real and
is what the book collects — and there is not enough of it: the always-in
control *loses* (t −2.45; the mean spread does not pay two taker legs),
and the selected tail earns 2% a year on the 30% of the time it is open.
Falsifiers "net Sharpe below 0.5 at 2×" (costs take 45% of gross) and
"DSR < 0.90" fire; the "always-in within 0.3 Sharpe" one does not — the
selection matters, it just selects too little. Mechanism candidate **7 of
8**. Holdout not opened. Reopen only with maker fills on both legs (a
different cost model that needs verified rebates and a fill assumption
this engine refuses to make) or a third venue with a wider spread.

**17 September 2026, 14:30 Dubai — E7 `p2_short_squeeze_v1`: verdict FAIL
at gates 3, 4 and 5.** Registered seq 626, amendment 644 (what "credible"
means for a publication stamp: FINRA's 2019 → mid-2023 archive all carries
a 2023-07-27 regeneration stamp, so a stamp counts only 0–60 days after
settlement; otherwise the 20-day rule). Event file built offline from the
FINRA and SEC mirrors with no price read (`scripts/e7_events.py`: 1,700
top, 1,700 low-cover, 1,700 random names over 170 publication dates, entry
20–57 days after settlement); QuantConnect executes only
(`qc/e7_impl.py`, six backtests through the cookie-authenticated web API,
which the free tier does allow from a logged-in page — no more clicking).
The FTD parser needed one fix (a literal `|` inside a description).

| impl | n | hold | final $ | CAGR | Sharpe (QC) | max DD | orders | alpha vs benchmark | t |
|---|---|---|---|---|---|---|---|---|---|
| e7_n10_h10 | 10 | 10 | 1,799 | 9.2% | 0.37 | 21% | 1,734 | +5.7%/yr | 1.34 |
| e7_n5_h10 | 5 | 10 | 1,602 | 7.3% | 0.23 | 36% | 816 | +4.5% | 0.87 |
| e7_n10_h20 | 10 | 20 | 952 | −0.7% | −0.16 | 55% | 1,569 | −6.4% | −1.18 |
| e7_n5_h20 | 5 | 20 | 682 | −5.6% | −0.33 | 68% | 747 | −10.8% | −1.69 |
| control: low-cover mirror | 10 | 10 | 1,297 | 4.0% | −0.03 | 6% | 936 | +2.8% | 1.51 |
| control: random names | 10 | 10 | 1,487 | 6.1% | 0.30 | 5% | 666 | +4.7% | **2.49** |

Gates 2–5 on the best variant (`scripts/external_gates.py --family e7`,
trial log seq 648): net Sharpe 0.70, net/gross 0.92 (gate 2 passes);
HAC t 1.88, p 0.06 (**gate 3 fails**); DSR 0.75 over 4 (**gate 4
fails**); PBO 0.01 but SPA p 0.88 against the exposure-matched benchmark,
best excess **−5.7%/yr** (**gate 5 fails**). The random-name control has
a higher alpha t than any variant, which is the pre-registered falsifier
"the mirror earning as much"; and the 20-session holds lose outright,
which is the opposite of a squeeze that builds. Beta 0.25 on a
nominally full book: about half the names each date were not tradable in
LEAN's universe (delisted tickers, symbol changes), stated, not repaired.
Mechanism candidate **8 of 8**. Holdout not opened. Trial count **2,071**
(649 records, chain verified).

**The counter is at eight.** Under the rule restated at the top of this
document — eight gated mechanism candidates, none surviving — Programme 2's
answer on its own terms is the same as Programme 1's: no edge accessible
at this account size with this data was found. C1 (t 0.99 at gate 6), C5
(t 1.68), C2 (t 1.76) and E7 (t 1.88) are the four that showed a sign
in the predicted direction and none reached significance, deflation, or
the benchmark. What is *not* concluded: the recorders (C3 liquidations,
ETF flows) keep running and were never counted; the independent review
(`docs/22`, ten defects) has not been done and precedes any live order;
the week-12 report (per family, capacity, what a serious attempt needs)
is the remaining deliverable. Nothing is registered from here without a
new input.

**17 September 2026, 15:40 Dubai — after the counter.** `docs/23` (the
report) and `docs/24` (the maker-fill study) written. Owner: "$2,000 is
fine if eventually a proper system emerges" — recorded as a standing input
for E5/E4's long/short versions, unused. Owner said yes to **stage 0** of
the maker study: two recorder services on the Hetzner box
(`qr-tape-binance`, `qr-tape-bybit`; `scripts/record_tape.py`) now write
the public top-of-book and every trade for the 20 most liquid cross-venue
symbols (BTC, ETH, SOL, XRP, HYPE, ZEC, DOGE, ADA, ENA, BEAT, NEAR, LINK,
1000PEPE, CL, XAUT, WLD, SUI, UNI, ONDO, BNB) to `/root/tape/data/`, ~320
rows a second on Binance, gzip per day. No key, no order. Binance's
`@aggTrade` sends nothing to that host; `@trade` does. Stage 0's decision
rule (≥ 70% fills in 15 minutes, < 2 bps adverse mark) is fixed in
`docs/24` before any tape is read; the read is on or after **1 October
2026**. The independent review is running on Codex.

**17 September 2026, evening (Fable 5.1) — the independent review came
back (`docs/25`).** Codex confirmed the nine tests and found four more
defects plus the StepM cause, all reproduced here by inspection and closed
with tests the same evening: a held position was zeroed by a corrupt
*volume* field on the bar (a −50% loss erased; now entry needs the decision
bar tradable, holding needs a valid price); the overnight unit charged one
round trip for consecutive nights (now one per night); the 15:30 intraday
decision read the minute stamped 15:30, which closes at 15:31; arch's StepM
loop re-ran SPA on an empty set. The external gates' "exposure-matched"
benchmark had never been scaled (its proxy read 1.0 for every backtest);
with LEAN's holdings-based exposure **E5's SPA p moves 0.19 → 0.066** and
its best excess −1.9% → +8.7%/yr, **E7's 0.88 → 0.52**; both verdicts
stand on their pre-registered alpha-t falsifiers (E5 t 1.31; E7 t 1.34 with
the random control at 2.49). Gate 7 now runs externally. Seq 536–537 (E5
re-scorings) voided with a reason; trial count **2,055**, E5 = 8 unique
configurations. Not done: the per-leg position/cash ledger the review puts
first — a rewrite of the runner core, specified in `docs/25`, and the
prerequisite for the maker study's stage 1. No family was re-run; every
change's direction on the closed verdicts is stated in `docs/25`.

**18 September 2026, 04:00 Dubai — night5: the eleven frozen grids re-run
on the ledger (`docs/25` step 8).** Eleven counted runs, 17:08 → 23:59 UTC
(C1 v2 hourly alone 6 h 11 m: gate 6 re-optimises 25 of 64 variants over
200 permutations, and the ledger is 3–5× the runner per backtest on
hourly bars). **Every verdict stays FAIL.** Trial log 772 records / 2,247
trials, chain verified. The table (`scripts/ledger_before_after.py`,
before → after; reports in `reports/weights_engine/` and
`reports/ledger_engine/`, the recorded verdicts untouched):

| hypothesis | verdict | failed gates | net Sharpe | gross Sharpe | cost drag/yr | turnover/yr | gate 3 t | gate 6 p | engine |
|---|---|---|---|---|---|---|---|---|---|
| p2_auction_imbalance_v1 | FAIL → FAIL | 2,3,4,5,6,7,8 → 2,3,4,5,7,8 | 0.66 → 0.65 | 1.33 → 1.47 | 0.0096 → 0.0111 | 31.9 → 22.3 | 1.84 → 1.79 | 0.10 → 0.08 | weights → ledger |
| p2_auction_imbalance_v1_mirror | FAIL → FAIL | 2,3,4,6,7,8 → 2,3,4,6,7,8 | -0.07 → -0.20 | 0.91 → 0.67 | 0.0255 → 0.0280 | 85.0 → 57.7 | -0.19 → -0.52 | 0.30 → 0.64 | weights → ledger |
| p2_funding_carry_v1 | FAIL → FAIL | 1 → 1 | 8.85 → 7.49 | 9.69 → 9.20 | 0.0100 → 0.0315 | 6.7 → 0.0 | 9.66 → 9.41 | 0.00 → 0.00 | weights → ledger |
| p2_funding_carry_v1_always_in | FAIL → FAIL | 6,8 → 8 | 4.76 → 6.37 | 5.13 → 7.87 | 0.0077 → 0.0268 | 5.1 → 0.0 | 5.75 → 6.80 | 0.12 → 0.00 | weights → ledger |
| p2_funding_carry_v2 | FAIL → FAIL | 6 → 6 | 3.09 → 3.81 | 3.36 → 4.52 | 0.0127 → 0.0278 | 8.5 → 0.0 | 15.02 → 20.65 | 0.99 → 0.11 | weights → ledger |
| p2_late_day_momentum_v1 | FAIL → FAIL | 2,3,4,5,6,7,8 → 2,3,4,5,6,7,8 | -1.04 → -0.25 | -0.31 → 0.48 | 0.0203 → 0.0207 | 67.6 → 68.9 | -2.63 → -0.62 | 0.80 → 0.44 | weights → ledger |
| p2_late_day_momentum_v1_reverse | FAIL → FAIL | 2,3,4,6,7,8 → 2,3,4,6,7,8 | -0.90 → -0.26 | 0.11 → 0.76 | 0.0338 → 0.0349 | 112.5 → 116.3 | -2.48 → -0.72 | 0.56 → 0.28 | weights → ledger |
| p2_oi_reversal_v1 | FAIL → FAIL | 3,4,5,6,8 → 3,4,5,6 | 0.84 → 1.00 | 1.07 → 1.21 | 0.0463 → 0.0417 | 71.3 → 0.0 | 1.68 → 2.03 | 0.35 → 0.36 | weights → ledger |
| p2_oi_reversal_v1_unconditioned | FAIL → FAIL | 2,3,4,6,7,8 → 2,3,4,6,7,8 | -0.34 → -0.34 | -0.23 → -0.24 | 0.0645 → 0.0569 | 99.2 → 0.0 | -0.80 → -0.80 | 0.92 → 0.96 | weights → ledger |
| p2_venue_spread_v1 | FAIL → FAIL | 3,4,5,6,7,8 → 6,8 | 0.62 → 1.54 | 1.16 → 2.02 | 0.0161 → 0.0145 | 12.9 → 4.8 | 1.76 → 4.24 | 0.17 → 0.02 | weights → ledger |
| p2_venue_spread_v1_always_in | FAIL → FAIL | 2,3,4,6,7,8 → 1,8 | -1.20 → 8.28 | 0.33 → 20.70 | 0.0028 → 0.0119 | 2.2 → 3.2 | -2.45 → 11.61 | 0.57 → 0.00 | weights → ledger |

Read with three qualifications. (1) **Turnover 0.0 and C1's "$1bn
capacity" are a ledger defect, fixed the same morning with a test:** on a
bar where any symbol is not tradable the unit-notional sum was 0 × NaN,
so the whole bar's turnover read NaN and the impact/capacity arithmetic
saw no trading. Costs, returns and verdicts use a separately masked term
and are right; only the turnover column and gate 2's capacity line on
the C1/C5 rows are wrong, and they are not re-run (each is a counted
trial; the fix is in the engine for the next). (2) **Carry books move
most**, in the direction the review predicted: C1 v1 always-in gross
Sharpe 5.1 → 7.9, v2 3.4 → 4.5, gate-6 p 0.99 → 0.11 — per-leg dollar
P&L at the coin's own prices instead of the ratio's second-order return,
funding on the marked notional, and the coin's drift re-hedged daily
(cost drag 1.3% → 2.8%/yr on v2). v2 still fails gate 6 (p 0.11 > 0.05);
its verdict does not move. (3) **The cross-venue always-in control is an
open item**: net Sharpe −1.2 → 8.3, gross 0.3 → 20.7, failing only at
gate 1's ceiling. On the three majors alone the two engines agree on
gross (1.70 vs 1.65) and the ledger loses on costs (net 1.56 → −0.94;
counted smoke `ledger_engine_smoke`), so the anomaly lives in the broad
top-80 universe — a leg price derived from the ratio on a name with a
bad print is the suspect. Gate 1 caught it as "not a plausible edge",
which is what the ceiling is for; it is diagnosed before the ledger
becomes the default engine, not after. E1/E2 move little (E2's net
−1.04 → −0.25 as the round-trip exits fill at the session open; still a
gross-negative family). C2's family row improves (t 1.8 → 4.2, gate 6 p
0.02) and still fails gates 6 and 8 — the same open item applies to it
and it is not read as a result. **Decision:** the ledger is not made the
default until (3) is closed; C6 runs on it tonight as registered, on
single-leg perps, which the item does not touch.

**18 September 2026 (Opus 5) — the position/cash ledger is built
(`qr/research/ledger.py`, `docs/26`).** Review 22's first ticket: an
engine that holds `qty`, `cash` and `nav` and derives weights, beside the
weight runner, behind `run_backtest(engine="ledger")` and `qr gates
--engine ledger`; the gates read the same `BacktestResult` and the trial
log records the engine. Written from the acceptance tests first
(`tests/qr_platform/test_ledger.py`, expected values from a hand ledger):
$50 stock + $50 cash drifts to 54.545% with no trade; a −$50 short against
$150 cash marks to NAV $90 and −66.667%; a monthly book's quantities are
constant between marks and its turnover zero there; the carry unit books
spot 100→120 against perp 100→110 as +$10 on $100 (the ratio runner reads
9.09%), settles funding on the perp leg with the venue's sign, pays each
leg's fee on its own notional; three consecutive overnight signals are six
fills; a $250 slice at $400 is no shares and the cash stays, at $100 two
shares that persist through a rise; a corrupt volume field on a crash bar
books the loss and refuses a new order; cash earns the risk-free rate only
when asked. With no costs the ledger's NAV path equals the runner's equity
to 1e-9 on `edge_world` for seven daily and scheduled strategies; with
fees they differ by the fee the runner's drift leaves out of its
denominator (equity within 1e-4 over two years at 9.5 bps a side — the
ledger is the one that is right). Two conventions are stated in the
report: fees of an order at the close of *t−1* are booked on bar *t*, the
bar the position is held over (the runner's split, which gate 2 reads);
a two-leg unit is delivered in dollars on every decision bar like any
other family's weight (`unit_sizing="dollars"`), because the ratio runner
never charged the coin's own drift. That last one is the first thing the
ledger found: on the real carry unit (three names, always-in, one counted
smoke, `ledger_engine_smoke`, not a candidate) the same book turns over
12.4 a year on the ledger against 1.6 on the ratio, costs 2.7%/yr against
0.3%. Holding the coins instead (`unit_sizing="coins"`) removes the
re-hedge and doubles the vol — the notional floats against a NAV that
does not — so it is an option, not the default. The ledger is ~6× slower
than the runner (0.12 s against 0.02 s on 40 names × 6 years); a night
chain is fine, a permutation gate is longer. **The review's step 8** — the
frozen grids re-run on the ledger with a before/after table — is written
and not run: `scripts/night5_ledger_rerun.sh` (eleven counted runs: C1
v1/v2 and controls, C5, C2, E1, E2 and their controls; the three
QuantConnect families are not local) and `scripts/ledger_before_after.py`.
Every one is a counted trial, so it waits for the owner's yes. Trial log
**652 records / 2,057 trials**, chain verified.

---

## Reviewed against an independent plan (Codex, 15 September 2026)

A second plan, written by a different tool from the handover alone, was
compared with this one. Taken from it: the exposure-matched benchmark for
long-only stock families (this plan had them against cash, which would have
passed beta as skill); the trial-inventory reconciliation, which showed gate 4
is per hypothesis; the precise wording of the per-order floor; incubation of
at least 63 observations (the repo's own gate 10, which this plan had
shortened to four weeks); the concrete insider-cluster rule and its
hand-labelling audit; the always-in carry control, capital-committed sizing
and stress list for C1; its eight audit cases; odd-lot tenders as a backlog
family; Quantiacs as a zero-capital route; Norgate's Windows-only interface.
Not taken: keeping IBKR tiered pricing as the equity venue and building a
cost ledger around the $0.35 floor (this plan removes the floor); reverting
the cash benchmark for carry; narrowing C1 to BTC and ETH by hand (the
engine already runs the breadth); a blocking measurement-audit week (the
controls found four defects in a day; the docs/16 reviewer pattern stays);
Darwinex Zero (paid); the income-to-capital table before there is a result
to size.

## The plan in plain steps

1. Finish the perp funding download; ingest it; build the carry units.
2. Read the carry universe; register C1; run it through gates 0–8 on data up to 14 September 2025.
3. Open the holdout once (15 September 2025 onwards); run gates 9–11.
4. In parallel, hand-label 100 Form 4 filings; register E5; build the exposure-matched benchmark and the Alpaca zero-commission cost model; run E5 on QuantConnect's free data.
5. Pull the closing-auction imbalance history with Databento's credit; register and run E1 and E2.
6. Any family that passes gates 0–9 goes into incubation for at least 63 trading days with every decision logged before its outcome.
7. Owner opens QuantConnect, Alpaca and Databento accounts; buys the first funded evaluation only after a family passes gates 0–9.
8. Independent review of the week-1 engine changes by a different model before any live order.
9. Week 12: report per family, capacity, incubation slippage, capital ladder.

## Sessions and models

- **Build and run** (steps 1–5, 9): a new session on **Claude Opus 5**, the repo's default for code; start it by reading this file, export `QR_ROOT=~/qr/lake`, keep responses short.
- **Independent review** (step 8): a fresh, isolated session on a model that did not write the code — Codex, or Claude Opus 5 if Codex is unavailable — given the raw observations and the questions, not the engine's formulas, per docs/16.
- **Gate mathematics and the week-12 report**: **Claude Fable 5.1**, as before, and only then.

## 1. Context

The handover records nine pre-registered families, 1,541 runs, 46 mechanism memos, zero promotions, and ranks the causes. Three were fixed at design time:

| # | Cause (handover §5) | What actually caused it |
|---|---|---|
| 5.1 | Benchmark unbeatable | Gate 5 compared long-only timing to buy-and-hold of a rising universe |
| 5.2 | $0.35/order minimum = 35–42 bps per leg on the $83–$100 orders a twelve-name basket implies at $1,000 | IBKR Pro tiered pricing on a $1,000 account |
| 5.3 | Daily bars cannot see forced flow | Closing auctions, funding, liquidations all resolve intraday |

Five more followed: forced traders sit in instruments not traded (perps, single stocks, primary market); no point-in-time alternative data; twelve-name breadth; idea generator exhausted; no market-impact model.

Current state: the connected IBKR account holds **$78.34 USD cash, no positions, cash account** (read via the IBKR connector today). Nominal budget stays ~$1,000. The engine (gates 0–11, hash-chained trial log, SHA-256 sandbox, cost models, autopilot, `scripts/collect_flows_standalone.py` still recording ETF share counts) is reused as-is.

**The plan's single principle: every one of the eight causes gets a named fix with a named resource, and no fix requires more capital than exists today except where stated (Track 3, Track 4).**

---

## 2. Root cause → fix map

| Cause | Fix | Resource (verified today) | Cost |
|---|---|---|---|
| 5.1 benchmark | Gate 5 comparator becomes **cash (3-month T-bill)** for market-neutral and carry books; **exposure-matched buy-and-hold** (the eligible universe scaled to the strategy's average exposure) for long-only stock selection, so beta in a rising market cannot pass as skill; plain buy-and-hold kept for long-only timing | FRED `DTB3` series; two parameters in `qr/validate/gates.py` | $0 |
| 5.2 per-order floor | US equities move to a **$0-commission API broker**; crypto moves to **perpetuals** (bps-only fees); futures use micro contracts (~$0.25–0.85/contract) | Alpaca ($0, fractional from $1, MOC/LOC, international); IBKR Lite if US/Singapore resident; Binance/Bybit/Hyperliquid perps 1.5–5.5 bps | $0 |
| 5.3 resolution | **Minute bars + closing-auction imbalance + 8-hour funding + 5-min OI** | QuantConnect free tier (minute, 1998→); Databento imbalance (Nasdaq 2018→, NYSE 2025→, $125 free credit); Binance Vision `futures/um` klines/metrics/fundingRate; Hyperliquid S3 archive | $0–$50 one-off |
| 5.4 instrument access | Trade **where the forced trader trades**: perps (liquidations, funding, unlocks), single stocks via fractional shares, closing auction via MOC/LOC | Same venues as above | $0 |
| 5.5 PIT alt data | Use sources that are **point-in-time by publication**: FINRA short interest (publication date in file), Reg SHO daily short volume, SEC fails-to-deliver, EDGAR Form 4 / 8-K / N-PORT (acceptance timestamps), QuantConnect ETF constituents (recorded daily since 2015), Binance funding/OI archives, on-chain vesting schedules; plus **forward recorders** for everything else | All free | $0 |
| 5.6 breadth | **3,000+ US stocks** (QuantConnect, survivorship-free) and **200–700 perps** (Binance 718 pairs since Aug 2020 on QC; Hyperliquid/Bybit) | Free | $0 |
| 5.7 generator exhausted | Replace the LLM as *source* of ideas with a **literature registry** (papers in §14, Open Source Asset Pricing's 200+ signals, Quantpedia); the LLM only parameterises and triages | Free | $0 |
| 5.8 market impact | Add a **participation-capped square-root impact model** and a hard cap of 1% of the bar's volume per order; report capacity per family | Engine change | $0 |
| Capital | **Three multipliers that need no personal capital**: funded-trader evaluations (futures: Topstep API-permitted; crypto: HyroTrader bots-permitted), WorldQuant BRAIN consultant payments, and compounding rules | §8 | $59–$150 per evaluation |

---

## 3. Week-0 decisions (owner makes these; each branches the plan, none blocks the research tracks)

**D1. Country of residence** — decides venues. Verify inside each logged-in account; third-party lists lag.

| Resident of | US equities at $0 | Crypto perps | Prediction markets | Funded accounts |
|---|---|---|---|---|
| USA | IBKR Lite (US/SG only) or Alpaca | Binance/Bybit/Hyperliquid **blocked**; Coinbase US perps (verify) | Kalshi; Polymarket US (live since 2 Dec 2025, waitlist removed May 2026) | Topstep, Apex; HyroTrader (verify US) |
| UAE / India / other non-EU | Alpaca (195+ countries; the UAE is named on alpaca.markets/about-us); IBKR Pro | Binance (verify futures enabled in-account), Bybit, Hyperliquid (no KYC, US+Ontario excluded) | Polymarket international | All |
| UK / EEA | Alpaca (EEA passported July 2026); IBKR Pro | Binance/Bybit futures restricted for retail; Hyperliquid open | Polymarket international (check country) | All |

**D2. Capital path** — pick one to start; they stack later.
- (a) Own capital only: fund to $1,000 → Track 1 live-paper at once; equities at Alpaca with fractional shares.
- (b) Own capital + one funded-trader evaluation ($59–$150): adds Track 3/4 with a $50k–$100k simulated account once an intraday family passes gates.
- (c) Own capital + WorldQuant BRAIN: adds income from equity alphas with zero capital; runs in parallel from week 1.

**D3. Data budget** — $0 (QuantConnect free + Databento credit + all free feeds) is sufficient for every family below. Optional upgrades: Alpaca Algo Trader Plus $99/mo (full SIP feed, only needed at live-trading time for Track 2), QuantConnect Researcher $60/mo (only for live nodes/tick data), Norgate Platinum ~$630/yr (only if a Track 2 family passes gate 9 and needs a second independent price source; its Python interface is Windows-only, so on this Mac it needs a Windows VM).

---

## 4. Track 0 — Setup (week 1)

### 4.1 Accounts (all free to open)
1. **QuantConnect** free plan — `quantconnect.com`. Confirms: unlimited minute/hour/daily backtests, 1 research (Jupyter) node, no live nodes, no data download. This is the research venue for Tracks 2 and 3 and for perps cross-checks.
2. **Alpaca** paper account + live application — `alpaca.markets`. The UAE is on Alpaca's own list of countries served; what the application will show is margin/short availability for a non-US account and MOC/LOC live. Facts: $0 commission, fractional from $1, no minimum, all accounts open as margin accounts; `cls` time-in-force orders must be whole shares and submitted before 15:50 ET.
3. **Databento** — `databento.com`; $125 credit (6-month expiry). Reserve it for `imbalance` schema pulls (Track 2, E1).
4. **Binance Futures / Bybit / Hyperliquid** (per D1). Hyperliquid needs only a wallet; fees 0.015% maker / 0.045% taker at base tier.
5. **WorldQuant BRAIN** — `worldquantbrain.com` (free; consultant invitation at 10,000 points + Gold rank; quarterly payments, Master ≥$2,000/quarter, Grandmaster ≥$8,000/quarter as published).
6. **Polymarket** (if D1 allows) — wallet + API keys; makers pay 0%.
7. **IBKR**: leave the existing account as is; switch to **IBKR Lite** only if US/SG resident. Otherwise its only use is micro futures (Track 3) once ≥$2,000 is on deposit.

### 4.2 Data pulls (free; scripted into the existing Parquet/DuckDB lake)
| Dataset | Source | Command / URL pattern | Gives |
|---|---|---|---|
| Binance USDT-M perps | `data.binance.vision` `data/futures/um/{daily,monthly}/` | daily: `aggTrades bookDepth bookTicker indexPriceKlines klines markPriceKlines metrics premiumIndexKlines trades`; monthly: adds `fundingRate` | 1-min bars, mark/index, 8h funding, 5-min OI + long/short + taker ratios, book depth |
| Bybit perps | `public.bybit.com` `trading/ premium_index/ spot_index/ spot/` | folder per symbol | second venue for funding spread (C5) |
| Hyperliquid | `s3://hyperliquid-archive/{market_data/[date]/[hour]/l2Book/[coin].lz4, asset_ctxs/[date].csv.lz4}` with `--request-payer requester` | ~monthly uploads | L2 books, funding, OI, premium per asset |
| FINRA short interest | finra.org Equity Short Interest catalog | pipe-delimited; settlement + publication dates (e.g., settle 15 Jan 2026 → due 20 Jan → published 27 Jan) | PIT short interest, twice monthly |
| FINRA daily short volume | finra.org Short Sale Volume Data + `developer.finra.org` Query API | daily files, monthly files | daily short-volume ratio |
| SEC fails-to-deliver | sec.gov Fails-to-Deliver Data | pipe-delimited zips, Feb 2004 → Aug 2026, twice monthly | FTD spikes |
| EDGAR | Form 4 (2-business-day deadline), 8-K (earnings), N-PORT | EDGAR full-text + XBRL APIs, acceptance timestamps | insider trades, earnings times, fund holdings |
| ETF constituents (PIT) | QuantConnect US ETF Constituents (2,650 ETFs, June 2009→, daily since Jan 2015, ≤1-week lag; free in cloud) | universe selection in QC | membership for Russell/S&P universes without look-ahead |
| Anomaly signals | Open Source Asset Pricing (`openassetpricing.com`, Oct 2025 release, Python package `openassetpricing`) | 200+ firm-level signals + portfolio returns | Track 2 E6 candidate list with published costs |
| T-bill | FRED `DTB3` | daily | new gate 5 comparator |

### 4.3 Forward recorders (PIT by construction; start day 1, usable after 3–12 months)
- Binance `forceOrder` liquidation stream + Hyperliquid liquidation feed → per-minute liquidation volume by symbol (not in the public archives; must be recorded).
- iShares daily holdings CSVs for IWM/IWB/IVV/IWV → shares outstanding and constituent snapshots.
- Polymarket order books for the top 200 markets (CLOB API).
- Keep `collect_flows_standalone.py` running (ETF share counts).
- Russell **December 2026** reconstitution (first semi-annual one: rank day 30 Oct, preliminary lists 13/20/27 Nov and 4 Dec, effective after close 11 Dec) → record prelim lists and minute bars of adds/deletes. This event has no history; the recorder creates it.

### 4.4 Engine changes (see §10 for specifics) — 3–4 days of work.

---

## 5. Track 1 — Crypto perpetuals (weeks 1–6; executable at today's capital)

**Why this track first:** fees are basis points with no per-order floor, shorting is native, the forced traders (funding payers, liquidated leverage, unlock recipients) trade *here*, and the benchmark is cash.

Universe: Binance USDT-M perps with listing dates from Binance Vision (PIT), top-100 by 30-day quote volume re-ranked monthly; Hyperliquid as second venue. Cost model: maker 0.018% / taker 0.045% (Binance with BNB) or 0.015% / 0.045% (Hyperliquid); funding paid and received every 8h at the archived rate; mark-price liquidation with initial/maintenance margin per tier; impact = participation cap.

| ID | Family | Mechanism (who is forced) | Data | Benchmark | Pre-registered rule sketch |
|---|---|---|---|---|---|
| C1 | Funding carry, delta-neutral | Leveraged longs pay funding; BIS WP 1087 finds carry averaging >10% p.a. (up to 60%), mostly from funding, with crash risk when carry is high | spot 1m + perp 1m + `fundingRate` | cash | Long spot / short perp when trailing-7d annualised funding > 3× round-trip cost; exit when < 1× or when carry percentile > 95 (crash-risk filter from the paper); cap gross at 2× equity |
| C2 | Cross-venue funding spread | Same payers, different venues clear at different rates | Binance + Hyperliquid funding | cash | Long perp on lower-funding venue / short on higher when spread > costs; 8h holding grid |
| C3 | Liquidation-cascade fade | Forced sellers are liquidation engines; price overshoots then reverts within minutes | `forceOrder` recorder (forward) + `metrics` OI drop + 1m bars | cash | Enter opposite to a liquidation burst > k σ of 1h liquidation volume when OI fell > x%; hold 15–60 min; maker exit |
| C4 | Pre-unlock short | Token unlock recipients (VC/team) sell after cliff dates fixed on-chain at launch | Vesting schedules (DefiLlama unlocks UI / Tokenomist; verify against vesting contracts) + perp availability | cash | Short perp T-3 to T+1 around unlocks > 2% of float; size by ADV; funding-adjusted |
| C5 | OI-conditioned reversal, mid-caps | Crowded positioning (OI up, funding up) unwinds; the March 2026 SSRN post-mortem shows plain OHLCV/funding sorts on **large caps** carry nothing → this family is restricted to ranks 30–150 and conditions on OI change and taker imbalance | `metrics` (OI, long/short ratio, taker buy/sell) + 1h bars | cash, dollar- and beta-neutral | Weekly long/short deciles on 1h-reversal × OI-change; maker execution; ≤250 variants |

Controls for C1: **an always-in carry baseline** (every eligible unit held at equal weight, no entry rule) — the test of whether the entry rule adds anything after its turnover — and hold-T-bill. Capital committed for a unit is spot notional plus perp margin plus an operating reserve, and gate 11 sizes on that, not on notional. Gate 8's stress list for carry: funding reversal, basis widening, one leg filled and the other not, exchange downtime, auto-deleveraging, collateral haircut.

Gate path: sandbox kill-test (3× cost bar) → gates 0–9 with cash benchmark → incubation (gate 10: at least 63 daily observations, about three months, decisions logged before outcomes) → live at ≤25% of equity per family.

---

## 6. Track 2 — US single equities at $0 commission (weeks 2–10; research free on QuantConnect)

Broker: Alpaca (or IBKR Lite if eligible). Cost model: commission $0, half-spread from minute quotes (IEX free feed for research; SIP at live), 1 bp PFOF slippage, MOC fills at official close with impact cap. **Shorting requires ≥$2,000 equity (Reg T)**; until then every family runs long-only, benchmarked to **exposure-matched buy-and-hold** of its eligible universe (not to cash: a long-only stock book benchmarked to cash would pass on beta alone), and the long/short version is pre-registered for later.

The pattern-day-trader $25,000 minimum **no longer exists** (FINRA Regulatory Notice 26-10; effective 4 June 2026; replaced by intraday margin monitoring, transition until 20 Oct 2027). Intraday families are therefore open to this account size.

| ID | Family | Mechanism | Evidence | Data | Rule sketch |
|---|---|---|---|---|---|
| E1 | Closing-auction imbalance | Index/ETF rebalancers must trade at the close; imbalance is published from 15:50 ET; closing-price deviations revert half after the close and fully overnight | Bogousslavsky & Muravyev, JFM 2023 (close = 7.5% of volume in 2018 vs 3.1% in 2010) | Databento `imbalance` (XNAS.ITCH 2018→; XNYS/ARCX/XASE 2025→) + 1m bars | Fade the imbalance direction with a LOC at 15:50–15:55 when imbalance/paired > k; exit next open (MOO) |
| E2 | Late-day hedging momentum | Leveraged-ETF and option-market-maker gamma hedging trade with the day's move in the last 30 min | Baltussen, Da, Lammers & Martens, JFE 2021 (60+ futures, 1974–2020; reverts over next days) | SPY/QQQ/IWM minute bars (QC free); LETF AUM from issuer daily files | Position at 15:30 in the sign of the 09:30–15:30 return scaled by LETF AUM × |return|; flat at close via MOC |
| E3 | Month-end cash settlement reversal | Institutions raise cash before month-end settlement; index returns reverse around the last day that guarantees settlement | Etula, Rinne, Suominen & Vaittinen, RFS 2020 (large liquid stocks strongest) | SPY/large-cap minute bars | Pre-registered T-3…T+1 pattern; long-only-vs-cash version first |
| E4 | Post-earnings drift, small/mid caps | Under-reaction persists where arbitrage is constrained | 2025 reviews find PEAD alive in small/mid caps, diminished in large caps | EDGAR 8-K acceptance timestamps + QC Morningstar; fractional shares | Buy top-decile surprise (announcement-return proxy) at next open, hold 20–60 days; ≤$100 per name via fractionals |
| E5 | Insider cluster purchases | Insiders who do not trade on a calendar routine carry information | Cohen, Malloy & Pomorski, JF 2012 (82 bps/month VW abnormal for opportunistic trades) | SEC insider-transactions data sets + EDGAR Form 4 acceptance times; prices from QC | ≥2 distinct officers/directors, open-market code P, ≥$25k each and ≥$100k combined within 10 trading days; routine insiders (same-month purchases in each of the prior 3 years) excluded; enter at the next regular open after one full session past the filing's acceptance time; hold 60 sessions (20 as the one variant); $1,000 book = 4 positions × 25%; 100 filings hand-labelled before any run, ≥95% precision required. Draft: `docs/prereg/p2_insider_cluster_v1.md` |
| E6 | Low-turnover anomaly composite | Published signals net ~4 bps/month on average, ~10 bps for the best, ~20 bps for combinations (Chen & Velikov, JFQA) — so only monthly-rebalanced combinations are pre-registered, sized as an overlay | Open Source Asset Pricing signals | QC fundamentals + OSAP | Equal-weight top-quintile composite of 5 lowest-cost signals, monthly, long-only-vs-cash; long/short version once shorting is enabled |
| E7 | Short-interest / FTD squeeze | Constrained shorts must cover; FTD spikes flag settlement stress | FINRA SI (PIT publication dates), Reg SHO daily short volume, SEC FTD | Long high-days-to-cover names with rising FTDs after publication date; hold 10 days |
| E8 (backlog) | Odd-lot tender offers | Issuers' tender offers often take odd lots (under 100 shares) in full without proration; only a small account can be all odd lots | Offer documents on EDGAR (SC TO-I, "odd lot" full-text search) | Manual watchlist; reconstruct 20 completed events from their original terms; needs a broker that processes tenders (IBKR does; confirm Alpaca) before any live event |

Not pre-registered (evidence says the flow is already arbitraged): S&P 500 addition/deletion (Greenwood & Sammon, JF 2025: 7.4% in the 1990s → 0.3% last decade; deletions 0.1% 2010–2020). The Russell semi-annual event is recorded forward instead (§4.3).

Research venue: port `gates.py` into a QuantConnect project as project files (multi-file projects import in the research node); run gates 0–9 in the cloud on QC data; export only results (JSON) to the local trial log. Live: Alpaca API from the local machine.

---

## 7. Track 3 — Micro futures, long/short, cash-benchmarked (weeks 6–12; research free, live needs ≥$2,000–$5,000 or a funded account)

Mechanism: multi-asset time-series momentum and carry; 67 markets 1880–2016, positive in every decade (Hurst, Ooi & Pedersen, JPM 2017). Benchmark is cash by construction; shorting is native; per-contract cost ~$0.25–$0.85 + exchange/NFA fees on notional of $10k–$30k = ~0.2–0.5 bps.

Instruments: MES, MNQ, MYM, M2K, MGC, MCL, MBT, MET (CME micro). Margin: MES initial $1,320 / maintenance $1,200 per CME table (September 2026, indicative); intraday margins at Tradovate/AMP/NinjaTrader-class brokers $50–$300 for MES/MNQ.

| ID | Family | Rule sketch | Data |
|---|---|---|---|
| F1 | Trend + carry, 8 micros | Carver-style forecast scaling; 12-1 and 3 breakout speeds; carry from roll yield; volatility-targeted 10% p.a.; whole-contract rounding with the "optimal whole-contract portfolio" method | QC CME futures (free minute/daily) for research; IBKR for live |
| F2 | Intraday index momentum (funded-account version) | E2 executed in MES/MNQ; flat by close (fits daily-loss and trailing-drawdown rules) | QC minute futures |

Capital preconditions stated once: F1 live needs ≥$5,000 for 3–4 contracts; ≥$25,000 for the full set. F2 is what a funded-trader account is for.

---

## 8. Track 4 — Capital multipliers (parallel from week 1)

| Route | Facts (verified) | Step |
|---|---|---|
| **Topstep (futures)** | Bots allowed in Combine and funded accounts via TopstepX/ProjectX API; API $29/mo ($14.50 with code `topstep`); HFT prohibited; **all trading must originate from your personal device — VPS/VPN/remote servers prohibited (a server may research and record, not trade)**; must be actively monitored | Buy one $50k Combine only after F2/E2 passes gates 0–9; run it from the desktop with the monitored-automation rule |
| **Apex (futures)** | One-time evaluation fee since March 2026 ("4.0"), activation $79–$99; bots allowed in evaluation, **banned on funded accounts**; 50% consistency rule; intraday or end-of-day trailing drawdown | Use only as a second evaluation if Topstep rules bind |
| **HyroTrader (crypto)** | From $59; $100k challenge $579; 1-step 10% target, min 5 trading days; 4% daily / 6% max loss; 80–90% split; **bots via Bybit API fully supported**; fee refunded with first payout; payouts in USDT/USDC | Buy the smallest evaluation after C1/C3/C5 pass gates 0–9; the strategy's realised daily loss must be < 2% at 99th percentile before purchase (gate 11 output) |
| **FTMO (FX/CFD)** | EAs allowed; from $89, refunded on first payout | Only if a family maps to CFDs; not planned |
| **WorldQuant BRAIN** | Free; alphas simulated on their PIT data; consultant invitation at 10,000 points + Gold; quarterly payments (Master ≥$2,000, Grandmaster ≥$8,000 as published) | Translate E5/E6/E7 into BRAIN expressions from week 2; 30 minutes/day; this is income without capital |
| **Numerai** | Stake NMR; payout capped at ±5% of stake per round; $532k paid April 2025 | Optional; only after BRAIN is running |
| **Quantiacs** | Free data and platform; qualifying strategies receive allocations with a 10% profit share; the Q25 crypto long-only contest closes 30 Sep 2026 | A later round: port a long-only family once one passes gates; the carry unit cannot be ported (two legs) |
| Regulatory watch | Aug 2026: SEC actions against two prop firms for marketing simulated accounts as live; NFA Notice I-26-12 on affiliate marketing effective 1 Dec 2026 | Treat every evaluation as simulated until the firm states otherwise in writing; withdraw payouts monthly |

---

## 9. Track 5 — Prediction markets (optional; weeks 8+; only if D1 allows)

Facts: Polymarket makers pay 0%; taker fee = shares × rate × p(1−p) with rates crypto 0.07, sports 0.05, finance/politics 0.04, geopolitics 0. Measured arbitrage: $40M extracted April 2024–April 2025 across single-market rebalancing and combinatorial arbitrage (arXiv 2508.03474); NBA markets show median 101 bps per combinatorial opportunity but 76.9% of them cap at ~14.8 shares — i.e., retail-sized by nature (arXiv 2605.00864); $1.12M in negative-risk markets (arXiv 2608.00666).

| ID | Family | Rule sketch |
|---|---|---|
| P1 | Single-market rebalancing | Buy all outcomes when Σ ask < $1 − fee; hold to resolution; size = min depth |
| P2 | Combinatorial | Pairs of logically dependent markets (LLM-triaged as in the paper); same execution |
| P3 | Maker quoting | Two-sided quotes on mid-liquidity markets at 0% maker fee; inventory limits |

Data: Gamma + CLOB + Data APIs (free); record books from week 1 (§4.3).

---

## 10. Engine changes (specific)

1. **Gate 5 comparator** in `qr/validate/gates.py`: add `benchmark ∈ {buyhold, equal_weight, cash}`; `cash` uses FRED `DTB3` daily; SPA test unchanged.
2. **Cost models** (new modules beside the existing Binance-spot and IBKR-tiered ones):
   - `alpaca_zero`: $0 commission, half-spread from quotes, 1 bp PFOF slippage, MOC = official close, whole-share constraint for `cls` orders, fractional for others.
   - `perp_binance`, `perp_hyperliquid`: maker/taker bps, funding cash flows at archived 8h stamps, mark-price liquidation, tiered margin, borrow = 0.
   - `cme_micro`: $/contract + exchange + NFA, tick-size rounding, whole contracts.
   - `impact`: `k · σ_1m · sqrt(q / V_1m)` with participation cap 1% of bar volume; output "capacity at 3× cost bar" per family.
3. **Universe modules**: PIT perp listing from Binance Vision file dates; US stocks via QC ETF-constituent universes exported as symbol lists with as-of dates.
4. **Resolution**: bar loader accepts 1m/1h; funding and OI aligned to bar timestamps; auction fields joined at 15:50–16:00.
5. **Literature registry** replaces the memo generator's brief space: one YAML record per paper in §14 (mechanism, forced party, instrument, resolution, published gross/net numbers). The generator now only proposes parameterisations inside a registry entry; triage rejects anything without a registry parent.
6. **Kill-test fixes carried forward**: the $0.35 minimum bug and the compounded-return-over-per-trade-cost ratio are unit-tested against the new models; drawdown probability in gate 11 is reported as P(≥25% below launch within 12 months) with the horizon in the label.
7. **Trial log**: new families registered under `p2_` prefix; gate 4 deflation continues to count the cumulative 1,541 runs.
8. **QuantConnect port**: `gates.py` and the sandbox splitter as project files; results only leave QC.
9. **Exposure-matched benchmark** (`benchmark=exposure`): buy-and-hold of the eligible universe scaled bar by bar to the strategy's average gross exposure, remainder in cash; the comparator for every long-only stock-selection family.
10. **Availability columns** on every alternative-data loader (FINRA, EDGAR, SEC FTD): `event_time`, `published_at`, `first_observed_at`, `ingested_at`, `source_hash`; the PIT assertion reads `published_at`.
11. **Audit cases as tests**: a $1,000 whole-share order's commission; a four-leg carry round trip; funding that reverses sign; one leg filled and the other not; a split on a carry unit; a delisting; a Form 4 amendment published after the signal; a funding-interval change. Four are covered by the week-1 tests; the other four are owed.

---

## 11. Pre-registration order and stopping rules (unchanged from the handover's policy)

Order: C1 → E1 → E2 → C3 → C5 → E5 → E4 → E7 → C2 → C4 → E3 → E6 → F1 → F2 → P1–P3.
Policy: 2 promotions/week, 5/quarter, 250 variants/family, 3× cost bar, hard stop at 8 gated candidates; `qr trial verify` before every report.
Controls per venue: hold-BTC-perp (crypto), hold-T-bill (cash-benchmarked), hold-SPY (long-only), synthetic noise (200 variants) re-run under every new cost model.

---

## 12. Twelve-week timeline

| Week | Deliverable |
|---|---|
| 1 | Accounts (§4.1), data pulls (§4.2), recorders live (§4.3), gate-5 cash comparator + perp cost model merged with tests |
| 2 | C1 pre-registered and through gates 0–9; BRAIN account active with first 20 alphas |
| 3 | E1 imbalance pull (Databento credit) + Alpaca paper account wired; E1 pre-registered |
| 4 | C1 verdict; E2 pre-registered on QC; C3 recorder has 3 weeks of liquidation data |
| 5 | E1 and E2 verdicts; C5 pre-registered; independent-model review of the new cost models (repeat the `docs/16` pattern) |
| 6 | Any passer enters incubation (gate 10: ≥63 daily observations, decisions logged before outcomes); F1 research starts on QC futures |
| 7–8 | E5, E4, E7 verdicts; C3 first kill-test on 6 weeks of recorded liquidations |
| 9 | Incubation half-way check for the first passer; funded-evaluation purchase decision (D2b) |
| 10 | C2, C4, E3, E6 verdicts |
| 11 | F1/F2 verdicts; BRAIN points review |
| 12 | Programme 2 report: per-family verdicts, capacity, incubation vs backtest slippage, capital ladder (income target → capital at 5/10/20% net) for the next quarter. Live at ≤25% equity only for a family past gate 10, which is week 19 at the earliest for a week-6 passer |

---

## 13. Verification (how each step proves itself)

- **Engine**: `pytest -q` green; synthetic noise self-test fails gates 4–5 under each new cost model; planted-edge test passes; `qr trial verify` chain intact and run count printed.
- **Cost models**: re-price 100 historical Binance perp fills and 100 Alpaca paper fills against model output; error < 1 bp.
- **Data PIT-ness**: for FINRA/EDGAR/Databento joins, assert `feature_timestamp ≤ decision_timestamp` on every row (existing QA gate extended).
- **Gate 5 cash comparator**: hold-T-bill control returns SPA p ≈ 0.5 on itself; hold-SPY control fails when benchmarked against buy-and-hold (as before).
- **Track 1 paper**: 20 trading days on Hyperliquid/Binance testnet; realised funding received vs modelled within 5%; fills vs modelled within 2 bps.
- **Track 2 paper**: Alpaca paper fills for MOC/LOC vs official close: exact; PFOF slippage measured.
- **Independent review**: a separate model session reviews cost models and gate changes before any live order (as `docs/16` did).
- **Audit cases** (engine change 11): each is a test with a hand-computed expected dollar answer, not a comparison against the engine's own formula.
- **Reporting rule (handover §8)**: re-derive every figure from the trial log; check flags against the record, not the report.

---

## 14. Sources verified today

Venues and rules
- IBKR Lite eligibility (US and Singapore): interactivebrokers.com/en/trading/why-ibkr-lite.php
- IBKR margin account $2,000 minimum and short-selling requirements: interactivebrokers.com/en/trading/margin-stocks.php
- IBKR micro futures commissions from $0.25/contract: interactivebrokers.com/en/pricing/commissions-futures.php
- FINRA pattern-day-trader rule eliminated 4 June 2026: finra.org/rules-guidance/notices/26-10; sec.gov SR-FINRA-2025-017
- Alpaca international, $0 commission, fractional from $1: alpaca.markets/international; EEA passporting (July 2026): businesswire 20260707116782
- Alpaca MOC/LOC rules (`cls`, 15:50 ET cutoff, whole shares): docs.alpaca.markets/docs/orders-at-alpaca
- Alpaca data plans ($0 IEX; $99 Algo Trader Plus): alpaca.markets/data
- Binance USDⓈ-M fees 0.02/0.05% (0.018/0.045 with BNB); futures unavailable in US/UK/EU/CA/AU: finder.com, datawallet.com summaries of binance.com/en/fee/futureFee
- Bybit 0.02/0.055%: bybit.com/en/announcement-info/fee-rate
- Hyperliquid fees and rebates: hyperliquid.gitbook.io/hyperliquid-docs/trading/fees; restrictions (US, Ontario): datawallet.com/crypto/hyperliquid-supported-and-restricted-countries
- CME micro margins: cmegroup.com/markets/equities/sp/micro-e-mini-sandp-500.margins.html
- Topstep API and automation rules: help.topstep.com/en/articles/11187768-topstepx-api-access
- Apex automation policy and 4.0 fees: quantvps.com/blog/apex-trader-funding-automated-trading-bots; proptradingvibes.com/blog/apex-trader-funding-rules-overview
- HyroTrader rules and API: hyrotrader.com/blog/hyrotrader-vs-breakout
- FTMO EAs allowed, fee refunded: tradingfinder.com/props/ftmo/rules
- Prop-firm regulation Q3 2026 (SEC actions, NFA I-26-12): track360.io/blog/prop-firm-regulation-news-roundup-q3-2026
- WorldQuant BRAIN consultant programme: worldquantbrain.com/consultant; worldquant.com/brain/iqc-guidelines
- Numerai staking and payouts: docs.numer.ai; github.com/numerai/docs staking.md
- Polymarket fees: docs.polymarket.com/trading/fees.md; US launch and access: coindesk.com 2026/04/28; predscope.com/guide/polymarket-us
- Kalshi historical data endpoints: docs.kalshi.com/getting_started/historical_data

Data
- QuantConnect pricing (Free $0; Researcher $60/mo): quantconnect.com/pricing; newtrading.io/quantconnect-review (13 Mar 2026)
- QuantConnect US Equities survivorship-free since 1998: quantconnect.com/data/algoseek-us-equities
- QuantConnect US ETF Constituents (2,650 ETFs, June 2009→, free in cloud): quantconnect.com/data/quantconnect-us-etf-constituents
- QuantConnect Binance crypto futures (718 pairs, Aug 2020→) and margin-rate data: quantconnect.com/data/binance-cryptofuture-price-data; …/binance-cryptofuture-margin-rate-data
- QuantConnect datasets overview (Morningstar, Reg SHO, Quiver insider, SEC filings, CME futures, Bybit/dYdX futures): quantconnect.com/docs/v2/writing-algorithms/datasets/overview
- LEAN engine Apache 2.0, local build: github.com/QuantConnect/Lean; LEAN CLI paid-tier requirement: lean.io/docs/v2/lean-cli/key-concepts/getting-started
- Databento: $125 credit and $/GB model: databento.com/pricing; Nasdaq imbalance since 2018: databento.com/datasets/XNAS.ITCH; NYSE imbalance feeds: databento.com/blog/NYSE-imbalance-feeds
- Binance Vision futures folders: s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data/futures/um/{daily,monthly}/
- Bybit public archive: public.bybit.com
- Hyperliquid archive: hyperliquid.gitbook.io/hyperliquid-docs/historical-data
- FINRA short interest schedule: finra.org/filing-reporting/regulatory-filing-systems/short-interest; data: finra.org/finra-data/browse-catalog/equity-short-interest/data
- FINRA daily short sale volume + Query API: finra.org/finra-data/browse-catalog/short-sale-volume-data
- SEC fails-to-deliver (Feb 2004 → Aug 2026): sec.gov/data-research/sec-markets-data/fails-deliver-data
- FTSE Russell semi-annual reconstitution from 2026, December schedule: lseg.com/en/ftse-russell/russell-reconstitution
- Open Source Asset Pricing (Oct 2025 release): openassetpricing.com
- Norgate Platinum ~$630/yr with historical constituents: norgatedata.com/prices.php (via alvarezquanttrading.com review)
- Sharadar bundle contents (prices 1998→, fundamentals 1990→, insiders 2005→, S&P 500 constituents 1957→): data.nasdaq.com/databases/SFA; quantrocket.com/sharadar

Mechanisms
- Schmeling, Schrimpf & Todorov, "Crypto carry", BIS WP 1087 (forthcoming Management Science): bis.org/publ/work1087.htm
- Azka Fayez Junior, "Failure of Cross-Sectional Alpha Screening on Cryptocurrency Perpetual Futures" (SSRN 6701738, Mar 2026)
- Bogousslavsky & Muravyev, "Who trades at the close?", JFM 66 (2023): ssrn.com/abstract=3485840
- Baltussen, Da, Lammers & Martens, "Hedging demand and market intraday momentum", JFE 142 (2021): ssrn.com/abstract=3760365
- Etula, Rinne, Suominen & Vaittinen, "Dash for Cash", RFS 33 (2020): doi.org/10.2139/ssrn.2528692
- Greenwood & Sammon, "The Disappearing Index Effect", JF 80 (2025): onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13410
- Lou, Polk & Skouras, "A tug of war", JFE (2019): personal.lse.ac.uk/polk/research/TugOfWar.pdf
- Cohen, Malloy & Pomorski, "Decoding inside information", JF (2012): ssrn.com/abstract=1692517
- Chen & Velikov, "Zeroing in on the expected returns of anomalies", JFQA: ssrn.com/abstract=3073681
- Hurst, Ooi & Pedersen, "A century of evidence on trend-following investing", JPM 44 (2017): ssrn.com/abstract=2993026
- PEAD 2025 evidence: anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again; quantpedia.com/strategies/post-earnings-announcement-effect
- Prediction-market arbitrage: arxiv.org/abs/2508.03474; arxiv.org/abs/2605.00864; arxiv.org/abs/2608.00666
- Carver, "Advanced Futures Trading Strategies" (2023) and pysystemtrade: qoppac.blogspot.com; github.com/robcarver17
