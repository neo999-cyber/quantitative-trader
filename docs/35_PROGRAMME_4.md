# Programme 4 — the data-expansion programme (opened 27 October 2026)

## 1. What it is

The programme `docs/31` §15 parked until its inputs were in the lake: the issuer's ETF-flow series (solved
at the issuer on 14 October, §18), the CFTC Traders in Financial Futures files (`mirror/cftc`), Coin Metrics'
exchange flows (`mirror/coinmetrics`), and — not yet drafted — the Deribit surface and Hyperliquid
positioning. Three mechanism memos were drafted on 27 October (§21), each with a named forced party or a
stated weakness, a point-in-time rule, a prediction with a size, a sample minimum, controls and falsifiers.
The owner's decision the same evening: *"register programme 4 and build the ETF one."* Programmes 1–3 are
twenty-five pre-registered rules and no pass; this one changes the inputs, not the method.

## 2. The counter — three of three

| hypothesis | seq | status |
|---|---|---|
| `p4_etf_flow_pressure_v1` — forced buying after US spot-ETF flow days | 984 | **ran once and FAILED** (run seq 991, gate 2: the gross return is not positive; §5) |
| its four control sweeps: `_t1` (the diagnostic arm), `_mirror`, `_placebo`, `_always_long` | 985–988 | run under their own ids (seq 995, 1000, 1005, 1010); none passes gate 3 |
| `p4_cot_crowding_v1` — CME leveraged-fund positioning as a timer for the carry holding | 989, amendment 1 at 1014, controls `_always_in`/`_mirror`/`_placebo`/`_eth` 1015–1018 | **ran once and FAILED** (run seq 1024, the sort 1027, controls 1028/1031/1038/1041, note 1044; §8): the timer earns 3–7 points a year less than the holding it times, in every year, and the placebo's random step-outs cost the same |
| `p4_exchange_inflow_v1` — coins moving onto exchanges precede selling | 990, amendment 1 at 1019, controls `_mirror`/`_placebo`/`_random` 1020–1022 | built and counted; **deferred by construction** (71 signal days at k = 1.5 in-sample against a minimum of 80; note seq 1023) and **parked on the owner's word** the same evening (note 1045): the free feed ends 23 May 2026, so no forward read is possible (§7) |

Nothing more is registered without a new input. The documents are stamped in the hash chain
(`qr trial verify` walks it and checks each file against its stamp); a change to a registered memo is an
amendment file, never an edit.

## 3. The ETF-flow candidate, as registered (`docs/prereg/p4_etf_flow_pressure_v1.md`)

**The data-path fact that shapes the rule.** The issuer's workbook dates a creation by the NAV date on which
the shares were issued, one session after the trade date on which the desk bought the coin (the aggregators'
"flow of 12 October" is the issuer's row of 13 October; the record day of 7 November 2024 sits on the 8th).
The row is published after that day's close and the box reads it at 06:00 UTC the next morning, so the flow
of trade date T is known to us on the morning of T + 2 sessions. That is the primary arm. A T + 1 arm — what an
aggregator's evening table would allow, a path recorded live only from 15 October — is a diagnostic sweep,
not a candidate for money.

**The rule.** `z` = the row's flow over the mean absolute flow of the sixty rows before it (twenty needed).
On the entry session, decided on the hourly bar closing at 09:00 New York: long when `z ≥ k`, short when
`z ≤ −k`; a resting maker order before the cash open, flat at the 16:00 close (seven bars) or after 24
hours. `k ∈ {0.5, 1.0, 1.5}` × hold ∈ {session, 24h}: six variants. BTCUSDT USDⓈ-M perpetual — the
instrument stage 1 measured the maker fill and fee on — at `CostModel.maker_measured(day_type="weekday")`
(2.2 bps a side, 96% filled, every entry a New York session), funding settled gross, ledger engine, benchmark
cash. In-sample 11 January 2024 → 30 June 2026; holdout 1 July → 31 October 2026 opened once after a pass;
forward from 1 November on the box's daily series. Minimum 60 primary entries at k = 1.0.

**Controls.** Placebo (flows permuted among the entry bars within each month, fixed seed), mirror (sides
reversed), base rate (long every eligible entry session), the diagnostic arm.

## 4. Build log

**27 October 2026, evening.** In this order, on the owner's yes:

1. **The code, on fixtures, before registration.** `qr/data/etfflow.py` — the instrument `etfflow-um`: the
   perp's hourly bars, the venue's funding on the bar whose close is the settlement
   (`qr.data.funding.bar_funding`), `flow_z`, the New York entry calendar (`qr.data.qa.trading_sessions`: a
   Friday's row enters Monday, the row before Good Friday the Monday after), `flow_features` placing each
   row's `z` on the one decision bar per arm, `build_etfflow_lake` with counts. `qr/strategies/etfflow.py` —
   `EtfFlowPressure` (k, hold, timing, control). The CLI: family `etf_flow_pressure`, `--costs maker`,
   `--basket btc`, `qr data etfflow-build`; two fields added to the panel whitelist. Nine tests on synthetic
   flows and bars (`tests/qr_platform/test_etfflow.py`): the scale excludes the row, the calendar, the
   decision bar in both halves of the year, the seven- and twenty-four-bar holds, the three controls, a
   session trade through the ledger paying the 16:00 settlement and scaled by the measured fill rate, the
   build round trip through the lake, the CLI wiring. The whole platform suite passes.
2. **The memo made exact and registered** (seq 984), with the four control documents (985–988) and the two
   other memos (989, 990). The exchange-inflow memo's instrument was tightened to the perp before its stamp.
3. **The instrument built** (`qr data etfflow-build --count-start 2024-01-11 --count-end 2026-06-30`; a join
   and a count, no flow read against a price): 58,440 hourly bars 2020-01-01 → 2026-08-31, 7,304
   settlements on their bars, 694 flow rows (8 January 2024 → 13 October 2026). In the registered in-sample
   window: **599 primary decision bars; |z| ≥ 0.5 on 342, ≥ 1.0 on 225, ≥ 1.5 on 152** — the minimum of 60 at
   k = 1.0 is met nearly four times over. No collisions; 31 rows after 31 August 2026 have no bar yet (the
   holdout's bars are pulled before it opens). Manifest hash `ce83ccec…`.
4. **Run on the owner's "run it"** at 14:14 UTC: the family and the four controls, five counted invocations (§5).

**27 October 2026, evening — the other two, on the owner's "build both".** In the same order: code on fixtures,
the amendments and control documents registered, then the real instruments built with counts only.

5. **The CME timer.** `qr/data/cot.py` — the Traders in Financial Futures parser (the CFTC's yearly zips, five
   columns kept, read as released), the availability rule (Saturday 00:00 UTC after the report Tuesday; the
   Tuesday after when a federal holiday falls on the Tuesday through Friday, which the memo's rule read three
   days early), the crowd ratio and its trailing 26- and 52-report percentiles, each daily carry-unit bar
   carrying the latest release known by its open; the instrument `carrycot-um`. `qr/strategies/cot.py` —
   `CarryCrowdingTimer(p, window)` with the always-in, mirror and 13-week-block placebo controls.
   `scripts/p4_cot_sort.py` — the memo's sort test (next-28-day funding, crowded against the rest, every fourth
   report), a counted run when it reads. `qr gates --costs carry_maker` prices the unit as the memo froze it
   (spot fee 7.5 plus the measured perp maker cost, 21.5 bps a round trip); `--basket eth` for the ETH arm.
   Amendment 1 (seq 1014) fixes the sample at the lake's first carry-unit bar — **in-sample 1 January 2020 →
   31 December 2024**, the 2018–2019 reports feeding the percentiles only — states the holiday rule, the
   engine form and the controls as their own ids (1015–1018). Tests on synthetic reports and units.
6. **The inflow fade.** `qr/data/inflow.py` — the Coin Metrics loader, the 90-day standardisation (the day
   excluded, sixty needed) placed on the next bar, a refresh of the community files that keeps the previous
   copy and refuses a shorter one, the instrument `inflow-um` (the perp's daily bars, the daily funding sum,
   `cm_netflow_z`). `qr/strategies/inflow.py` — `ExchangeInflowFade(k, h)`: one position at a time, a signal
   inside an open hold skipped; mirror, 180-day placebo and random-day controls. Amendment 1 (seq 1019): the
   perp's bars begin 1 January 2020, so **in-sample 2020 → 2023**, the daily-bar timing (fill at the close of
   d + 1), the controls as their own ids (1020–1022). Tests on synthetic flows and bars.
7. **The instruments, counts only.** CME: 444 BTC reports (10 April 2018 → 6 October 2026, 35 holiday-delayed),
   **261 released inside the in-sample; crowded at p = 90: 63 (26-week) and 71 (52-week) — the minimum of 35
   is met**; at p = 95: 49 and 44; at p = 80: 94 and 103. ETH: 288 reports from April 2021, 195 in-sample,
   21–22 crowded at p = 90 (thin; reported, not pooled). Inflow: the refresh fetched the community files and
   **they still end 23 May 2026** (byte-identical to the 13 October pull: the free feed has stopped); in-sample
   **71 signal days at k = 1.5 against the memo's minimum of 80 — deferred by construction**, note seq 1023,
   no run. By year the k = 1.5 days are 21, 18, 14, 18 (2020–23), 19 (2024), 13 (2025), 6 (to May 2026):
   a 2020–2024 in-sample would hold 90, with a holdout of thirteen days and no forward feed behind it.

## 5. Result — 27 October 2026, 14:14 UTC: **FAIL** in-sample

Five sweeps, each stopped at its first failing gate; reports in `reports/p4/` (the lake's copies under
`~/qr/lake/reports/`), the per-trade reading in `reports/p4/p4_etf_flow_pressure_v1_trades_2026-10-27.md`
(`scripts/p4_etf_trade_table.py`, from the saved returns, no re-run). In-sample 11 January 2024 → 30 June
2026, net of the weekday measured maker cost (2.1 bps a side), ledger engine, benchmark cash.

| sweep | entries at k = 1 | net per entry, bps (t) | best net Sharpe | stopped at |
|---|---|---|---|---|
| **the family, T + 2** (seq 991) | 225 (184 long, 41 short) | session −15.7 (−1.2); 24 h −11.0 (−0.7); every variant negative, −2 to −17 | −0.09 | gate 2: gross Sharpe −0.02, nothing to survive |
| diagnostic arm, T + 1 (995) | 226 | session +4.9 (+0.4); 24 h +16.8 (+1.0); best +23.6 at k = 1.5 (+1.3) | 0.73 | gate 3: HAC t 1.17, PSR 0.88 |
| mirror (1000) | 225 | session +11.5 (+0.9); 24 h +8.4 (+0.5) | 0.47 | gate 3: HAC t 0.71 |
| placebo, flows permuted within month (1005) | 225 | session +8.1 (+0.6); 24 h +31.4 (+2.0); best +31.5 at k = 0.5 (+2.4) | 1.38 | gate 3: HAC t 2.28 |
| base rate, long every eligible session (1010) | 599 | session −10.1 (−1.3); 24 h +0.8 (+0.1) | 0.02 | gate 2: gross not positive |

**Reading.** The registered claim — a positive session return at T + 2 after large flows, 10–20 bps an
entry — is rejected outright: at our own data path's timing the real flows did worse than holding long on
every eligible session (−16 bps against −10 for the session hold) and worse than the same flows permuted
among the month's days. The T + 1 arm's point estimates are positive (17–24 bps a day-long hold, the size the
memo named) but at t ≈ 1.2 they sit inside noise, and the placebo's permuted flows reached t 2.4 on the
same days — six tries on three hundred noisy daily bets produce that; it is why gate 4 exists, and it is
what "diagnostic positive while the primary is not" looks like when it is not evidence. Reaching the gate at
the T + 1 mean would need about four times the entries, ten years of the series. The memo's falsifiers that
fired: mean net edge below the round trip (T + 2), |t| < 2 with ≥ 60 entries (every arm), the placebo not
separated from the family (it is above it). No gate past 3 was reached, so no DSR, PBO or SPA number exists
for this family; the holdout stays shut and the forward read is unnecessary.

**Two things worth keeping.** (1) The series itself: the instrument is built, the issuer's row arrives daily,
the aggregator's T + 1 table has been recorded since 15 October; if the T + 1 effect is real it will show in
the recording at no cost, and nothing is registered on it. (2) The base-rate control: over these 599 sessions
bitcoin lost 10 bps a US cash session net and was flat over the day — an in-sample fact from a control, not a
tested claim, stated so nobody reads the family's session losses as the signal's doing.

**Programme 4 after this run: one of three run, one fail.** The sleeve stays where it is. (The second ran the same evening: §8.)

## 6. What a result means

A pass sends the $200 sleeve forward for a month at the stage-1 size before any size change (`docs/31` §21:
the first gate pass gets the sleeve). A fail is recorded as above; the series keeps growing on the box.

## 7. The other two, built — what runs on the owner's word, and what cannot

**The CME timer is ready.** Its minimum is met (§4, item 7). The run, once, counted, then the sort and the
controls:

    qr gates --family carry_crowding_timer --hypothesis p4_cot_crowding_v1 --market carrycot-um --interval 1d \
      --basket btc --costs carry_maker --engine ledger --benchmark buyhold \
      --start 2020-01-01 --end 2024-12-31 --grid "p=[80,90,95]" --grid "window=[26,52]" --upto 8
    python scripts/p4_cot_sort.py --start 2020-01-01 --end 2024-12-31

then `_always_in` (`--param control=always_in --param p=90 --param window=52`), `_mirror`, `_placebo` (the
family's grid with `--param control=…`) and `_eth` (`--basket eth`). It is the candidate that bears on the carry
decision (`docs/34`): a pass gives the holding a timer, a fail leaves it a yield with a tail, untimed.

**The inflow fade is deferred by construction** — 71 signal days at k = 1.5 in its registered in-sample
against a minimum of 80 — and its free data source has stopped at 23 May 2026, so the forward read the memo
requires after any pass has nothing to read. The owner's options: re-register a v2 on a 2020–2024 in-sample
(90 signal days; a thirteen-day holdout to May 2026; no forward feed, which makes the labelling defect
untestable), or park it. The recommendation here was to park it: a candidate that cannot be confirmed live
is not worth a counter. **The owner parked it the same evening** ("park it", note 1045): no run, the registration
stands as a record, the instrument stays in the lake, and nothing is registered on this input again until an
exchange-flow source exists that is point-in-time and still published.

## 8. Result — 27 October 2026, 15:07 UTC: the CME timer **FAILS** in-sample

Six sweeps and the sort, each counted; reports in `reports/p4/`, the per-variant reading in
`reports/p4/p4_cot_crowding_v1_rules_2026-10-27.md` (`scripts/p4_cot_rule_table.py`, from the saved returns, no
re-run), the sort in `reports/p4/p4_cot_sort_2026-10-27.md`. In-sample 1 January 2020 → 31 December 2024 on the
BTCUSDT carry unit at 21.5 bps a round trip, ledger engine, the holding as the comparator.

**What the gates said.** The family (run 1024), the holding with no rule (1028), the placebo (1038) and the ETH
arm (1041) all stopped at **gate 1**: gross Sharpe 8.3–9.3 against the engine's ceiling of 8.0 for a daily
strategy. The ceiling is meant for a directional rule whose Sharpe is implausible; here it caught a yield book —
the always-in holding reads 9.343 at every lag with a spike z of 0.0, which is what a carry income with almost
no variance looks like, not what a leak looks like. The gate's message ("the signal is reading the bar it
predicts") is wrong about the cause; recorded as an engine observation (note 1044) for a ticket, and it changes
no verdict below. **Ticket closed the same evening (`docs/20`, 27 October):** gate 1 now applies the ceiling to
the price component of gross at the honest lag (`lag1_price_sharpe`) and *warns* when the excess is funding
income, and its message states the ceiling and what the lag probe found — tested on a synthetic unit on both
engines; the verdicts in this section stand as recorded. The mirror (1031, in only while crowded, in the unit
18–41% of days) passed gates 1–4 with t 4.6 and DSR 1.0 and **failed gate 5: SPA p 0.54 against the holding** —
no variant beats simply holding the unit.

**The memo's own test, from the saved returns.** Net of costs, a year, 2020–2024:

| book | net a year | against the holding | years ahead of it | days in the unit |
|---|---|---|---|---|
| the holding, no rule (always-in) | **12.7%** | — | — | 100% |
| the timer, p = 90, 52-week window | 7.3% | −5.3 | 0 of 5 | 74% |
| the timer, p = 95, 52-week (its best) | 9.3% | −3.4 | 0 of 5 | 84% |
| the timer, p = 80, 26-week (its worst) | 5.8% | −6.9 | 0 of 5 | 65% |
| the placebo, p = 80 (random 13-week blocks out) | 7.1–7.6% | −5.0 to −5.6 | 0 of 5 | 62–66% |
| the mirror, p = 80 (in only while crowded) | 5.0–5.5% | −7.2 to −7.7 | 0 of 5 | 38–41% |

Every timer variant earns less than the holding, in every one of the five years; stepping out in the crowded
weeks costs what stepping out at random costs. The weeks the timer sits out paid as much as the rest or more.

**The sort** (the memo's first test, registered statistic: every fourth report, p = 90): crowded weeks' next
four weeks of funding 2.8 points a year lower (26-week window −2.79, t −0.50; 52-week −2.88, t −0.58) against a
predicted 3–6 points at t ≥ 2; on the other three phases the sign is the other way (+1 to +11 points). The one
large number, −12.6 points at p = 95 on the 52-week window (t −4.8), stands on eight crowded weeks and does not
repeat on any other phase. The ETH arm (21–22 crowded weeks) adds nothing: the same ceiling, 16% a year as a
holding.

**Reading.** The registered claim — crowded CME positioning predicts lower funding, and a holding that steps out
while crowded beats one that stays in — is rejected on both tests. The crowd was long the basis exactly when
the basis paid; the timer sold the yield at the wrong moments and paid 21.5 bps each time. The falsifiers that
fired: the rule's net yield below always-in after its round trips (every variant, every year); the placebo
matching (it does); crowded weeks no different from the rest (|t| < 2 at the registered statistic, the sign
unstable). The holdout stays shut; nothing goes forward.

**For the carry decision (`docs/34`).** This was the one candidate that bore on it. It leaves the holding where
the decision pack put it: a yield with a tail, untimed — 12.7% a year net over 2020–2024 on the unit's notional,
half that on the capital parked at 1×, and 2.6% gross in 2026 to August against a bill at 3.6%.

**Programme 4 after this run: two of three run, two fails; the third deferred by construction and parked.**

## 9. The rules, unchanged

Nothing runs, is registered or spends without the owner's yes; the owner moves money, never the code; Claude
never places, closes or starts live orders and never handles key values; every engine run is counted in the
trial log and never registered after; the holdout opens once.
