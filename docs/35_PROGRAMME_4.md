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
| `p4_etf_flow_pressure_v1` — forced buying after US spot-ETF flow days | 984 | registered; family and instrument built; **the run awaits the owner's yes** |
| its four control sweeps: `_t1` (the diagnostic arm), `_mirror`, `_placebo`, `_always_long` | 985–988 | registered beside it, run under their own ids |
| `p4_cot_crowding_v1` — CME leveraged-fund positioning as a timer for the carry holding | 989 | registered; not built (TFF parser, weekly feature, `CarryCrowdingTimer`; about a day) |
| `p4_exchange_inflow_v1` — coins moving onto exchanges precede selling | 990 | registered; not built (Coin Metrics loader, a free mirror refresh — the mirror ends 23 May 2026 — `ExchangeInflowFade`; half a day) |

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
4. **Not run.** The command is in the memo (§3 there); one invocation, counted, then the four controls.

## 5. What a result means

A pass sends the $200 sleeve forward for a month at the stage-1 size before any size change (`docs/31` §21:
the first gate pass gets the sleeve). A fail is the twenty-sixth, and the diagnostic arm says whether the
effect is merely faster than our data path (a live T + 1 feed to record, not a trade). Either way the series
keeps growing on the box.

## 6. Still to build

The COT timer and the exchange-inflow fade, each with its loader, its family and its tests, then one counted
run each — on the owner's word, as the ETF one was. The carry decision (`docs/34`) and the ladder stay the
owner's; the COT memo is the one that bears on it.

## 7. The rules, unchanged

Nothing runs, is registered or spends without the owner's yes; the owner moves money, never the code; Claude
never places, closes or starts live orders and never handles key values; every engine run is counted in the
trial log and never registered after; the holdout opens once.
