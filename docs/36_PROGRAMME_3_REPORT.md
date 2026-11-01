# Programme 3 — the report (the 31 October deliverable, delivered 1 November 2026)

*1 November 2026. Every figure below is re-derived from the trial log (`qr trial verify`: 1,050 records, 2,591
trials, chain verified, every registered document matching its stamp), the reports under `$QR_ROOT/reports/p3/`
and `reports/p3/`, and the dated log in `docs/31` §7–§22. This is the report `docs/31` §4 set for 31 October:
"P3-A verdict, P3-B measurement, the ladder with its number, Launchpool's first measured events, and the
maker-fill result". It arrives a day late because the registered read waited for the owner's word.*

## 1. The answer

Programme 3 asked for four things by 31 October (`docs/31` §4): a registered verdict on the one
prediction-market mechanism with a named forced party; a measured maker-cost model for this account or a
documented reason it cannot be measured; a yield ladder with a number and a risk tier chosen by the owner; and
one measured structural, small-size-advantaged income or its refutation. What it has:

1. **The prediction-market wedge (P3-A) has no verdict yet, and the verdict it is heading for is a fail.**
   Three registrations: v1 (weekly ladders, daily data) **failed** in-sample on 21 September — 2.6 points a
   share against a 3-point bar, t 2.0, the placebo below it, the finding being that whatever is there comes
   from DVOL. v2 (monthly markets, the intraday recording) was **deferred by construction** on 27 October: the
   recording holds 17 settlement ladders against a minimum of 30 and cannot reach it before 2027. v3 (the daily
   ladders, the tenor-matched Deribit surface as σ) was **read once on 1 November** (run seq 1047, the window
   13–30 October as registered): **23 asset × settlement-date clusters with a fill at k = 5 against the memo's
   minimum of 30**, so by its own rule it is **deferred to 30 November with the window extended to 29 November**
   (notes 1046, 1048, 1049). What the run showed is in §2; it is disclosed because it was seen, and it is not a
   verdict.
2. **The maker cost is measured, and it is the programme's one unambiguous positive deliverable.** Stage 0 on
   the mirrored tape (Binance 15-minute fill 96.3%, median mark 0.92 bps; 1 October) and stage 1 live on the
   owner's account (`docs/33`: 1,169 post-only orders over ten sessions, 94.2% filled within 15 minutes,
   60-second mark +1.06 bps, fee 2.00 bps a side, −$6.37 of the $25 budget). `CostModel.maker_measured()`
   is 3.2 bps a side, about 6.5 a round trip, fill rate 0.942. Every later test (C2 v2, Programme 4) ran on it.
3. **The yield ladder has its number and its tier.** The owner chose tiers 1–2 only on 21 September
   (`docs/31` §7). The stress simulator (§13 B, `reports/p3/ladder_stress.md`) says the **T-bill at 4.0% beats
   every stablecoin tier in expectation** on $1,300: the stated yields above it are smaller than the expected
   cost of the tails that pay them. The one tier-3 instrument the project can run itself, the funding-carry
   holding, was put to the owner with its numbers on 28 October (`docs/34`): 1.6% a year on the capital at 1×
   over the last year against a 4.0% bill, −2.4 points, with the exchange as counterparty for the whole amount;
   the CME timer that was to say *when* failed in Programme 4, so the holding is untimed. The decision is open
   and the owner's; the sleeve stays in the bill until it is taken.
4. **The small-size income is refuted at this size, three ways.** Launchpool, measured from Binance's own
   pool numbers (§11): 2.0% for 2025 on a stablecoin stake, 0.07% in 2026, the per-user cap binding only above
   $30 million — no small-size advantage; the claim withdrawn. HODLer Airdrops, the replacement: the
   announcement recorder has run 41 days and caught 22 announcements, every one an Alpha trading competition;
   **no HODLer airdrop and no Launchpool was announced in the window**, so there was nothing to measure and
   nothing to join. Polymarket liquidity rewards (P3-B, §12): $200 resting in the median market earns 3¢ a day
   against a $1-a-day payout floor; it clears the floor only alone in the thinnest markets, where adverse
   selection is the whole question. Not re-sized on 27 October because the v2 read that was to carry it did not
   happen.

**Programme 3's counter is four of four:** one fail (v1), one fail (P3-C, below), one deferred by construction
(v2), one deferred by sample (v3, decided 30 November). Nothing passed, nothing is sized, no money moved, no
live order was placed outside stage 1's $25 mandate. Programme 2 stands at twelve for twelve; Programme 4 at
two fails and one parked.

## 2. The v3 read as seen on 1 November — recorded, not judged

Seventeen sessions on one pass of the stream, decisions on the hour, the price-through fill with a 4-hour
TTL, one market per asset × settlement date, $25 a market. 858 daily-ladder markets in the window, 627
resolved at read time, no surface fallback (the tenor σ was always within two hours).

| session | attempts | filled | fill rate | edge / share | t (clustered) | win | hold (d) | settled / exited early | book Sharpe |
|---|---|---|---|---|---|---|---|---|---|
| **family k5** (T = 1 and to resolution coincide) | 55 | 23 | 0.42 | **−6.5 pt** | −0.86 | 0.43 | 0.33 | −8.3 / −5.9 | −0.34 |
| family k8 T1 | 25 | 19 | 0.76 | −15.6 | −1.48 | 0.37 | 0.27 | −32.4 / −5.8 | −3.8 |
| family k8 resolution | 25 | 19 | 0.76 | −16.2 | −1.53 | 0.37 | 0.28 | −32.4 / −6.7 | −4.3 |
| mirror k5 | 26 | 13 | 0.50 | −12.2 | −1.80 | 0.31 | 0.12 | −32.0 / −8.6 | −4.1 |
| mirror k8 | 7 | 3 | 0.43 | −17.4 | −0.53 | — | — | — | — |
| placebo k5 (realised vol) | 61 | 17 | 0.28 | −1.4 | −0.24 | 0.35 | 0.48 | −58.0 / +2.2 | −3.1 |
| placebo k8 | 45 | 23 | 0.51 | +8.0 | 1.11 | 0.52 | 0.79 | +28.6 / +5.0 | +4.5 |
| DVOL arm k5 T1 | 64 | 10 | 0.16 | +3.2 | 0.46 | 0.60 | 0.70 | +19.9 / +1.3 | +1.6 |
| DVOL arm k5 resolution | 64 | 10 | 0.16 | +9.7 | 1.36 | 0.60 | 1.00 | +19.9 / +8.6 | +4.6 |
| DVOL arm k8 T1 | 50 | 15 | 0.30 | +14.2 | 1.62 | 0.67 | 0.49 | +8.4 / +16.3 | +6.4 |
| DVOL arm k8 resolution | 50 | 15 | 0.30 | +13.3 | 1.51 | 0.67 | 0.56 | +8.4 / +15.0 | +5.5 |
| naive short ≤ 20¢ | 75 | 5 | 0.07 | +0.8 | 3.00 | 1.00 | 1.22 | — | — |

Family k5 by asset: BTC +5.6 points on 13 fills, ETH −18.5 on 9, SOL one fill at −56. Exits: 11 by the
wedge rule, 6 crossed at the TTL, 6 at settlement; mean hold eight hours.

**What it looks like, with 23 fills and no test applied.** The fill rule binds far less than on the monthly
markets, as the memo's prior said: 42% at k = 5, 76% at k = 8, fills in minutes. The edge is the wrong sign:
a maker who sells the "overpriced" YES at the ask loses about six points a share at k = 5 and sixteen at k = 8,
and the mirror, which buys the under-priced side, loses too. When both sides of the same model lose, the
spread and the adverse selection are larger than any mispricing the model sees. The placebo sits at zero at
k = 5 and at plus eight, inside noise, at k = 8. The DVOL arm, the term-structure control, is positive at every
setting on fewer fills, inside noise. That is the pattern the memo named in advance as the failure mode: if a
30-day vol prices these one-to-seven-day contracts at least as well as the tenor-matched one, the wedge is a
volatility-term-structure artefact and not retail overpricing. The 30 November read decides on the extended
window, as registered, with no variant added and no parameter moved; a second shortfall is reported as
underpowered and closes the family (note 1049). Engine observation, no ticket: positions open at the window's
end in markets settling after it were exited inside the window by the rule or at the known settlement; the
same boundary applies on 29 November.

## 3. P3-C, the "virtual world" question — FAIL

`p3_forecastability_v1` (seq 938, 1 October; a first run voided for a look-ahead the memo's leak rule caught):
nine target × model pairs over January 2023 → May 2026, 43 features from price, funding, open interest,
options, sentiment, stablecoin supply, the chain and the dollar. Direction and the 7-day return at the base
rate for ridge, gradient boosting and a zero-shot foundation model; the money test loses 20–35% a year after
costs. Variance is forecastable: gradient boosting beats GARCH (t 3.4) and does not beat DVOL (t 2.0 against a
bar of 3). For the third time in the project the market's own number is the best forecast available, and v3
above says the same thing from the other side: DVOL prices the daily ladders at least as well as the
tenor-matched surface.

## 4. Per family

| Family | Registered | Run | Verdict | Why |
|---|---|---|---|---|
| P3-A v1 `p3_threshold_wedge_v1` | 21 Sep | seq 933 | **FAIL** | 2.6 pt vs 3; t 2.0 vs 3; DSR 0.28; book Sharpe negative; the placebo below (DVOL is the content) |
| P3-A v2 `p3_threshold_wedge_v2_intraday` | 21 Sep (934) | none | **deferred by construction** (note 982) | 17 settlement ladders vs 30; the daily ladders fail the recorder's 7-day rule; cannot reach the minimum before 2027 |
| P3-A v3 `p3_threshold_wedge_v3_daily` | 13 Oct (951) | seq 1047, 1 Nov | **deferred by sample** → 30 Nov | 23 clusters with a fill vs 30; what was seen is §2 |
| P3-C `p3_forecastability_v1` | 1 Oct (935) | seq 938 | **FAIL** | base rate on direction and return; variance beats GARCH, not DVOL |
| Maker-fill study, stages 0–1 | `docs/24`, `docs/27` | 1–11 Oct | **PASSED** (a measurement) | 94.2% filled, +1.06 bps mark, 3.2 bps a side |
| P3-B liquidity rewards | not a candidate | sized 21 Sep | **refuted at $200** | 3¢ a day vs a $1 floor |
| Launchpool / HODLer Airdrops | not a candidate | measured 21 Sep; recorded since | **refuted / nothing to measure** | 2.0% in 2025, no small-size advantage; zero airdrops announced in 41 days |
| Yield ladder | owner's decision 21 Sep | simulator 1 Oct | **tiers 1–2; the bill wins** | T-bill +4.0% expected against every tier |
| Carry holding (tier 3) | not registered | decision pack 27–28 Oct | **open, the owner's** | 1.6% at 1× vs 4.0%; untimed after the CME timer's fail |

## 5. What the programme bought for its money

Cost: $0 in data and compute beyond the Hetzner box already running, and $25 at risk in stage 1, of which
$6.37 was spent. For that:

- **A measured maker cost on the owner's own account**, the quantity Programmes 1 and 2 had to assume.
- **The only private dataset the project owns:** two months of Polymarket top-of-book and prints for every
  BTC/ETH/SOL threshold market, the daily ladders from 13 October (5.9 GB, mirrored), the Deribit hourly
  surface from the same day, DVOL and the price indices, and the Binance tape (13.9 GB, the only copy, on the
  laptop). The 30 November read runs on it at $0.
- **The ladder stress simulator, the carry execution leg rehearsed end to end on the testnets, and a
  dead-man's switch** on the perp leg.
- **Three findings worth keeping:** (i) the market's own volatility number beats every model built here and
  prices the daily ladders at least as well as a tenor-matched surface; (ii) on the daily ladders the paper's
  wedge is inside the spread and the adverse selection at this fill model — both sides of the model lose;
  (iii) at $1,300 the T-bill beats every stablecoin tier in expectation, and the one carry the project can run
  itself trails the bill today on parked capital.

## 6. What a serious attempt would require

- **For the wedge:** the 30 November read on thirty or more clusters. If it fails, the mechanism is closed for
  this account: the honest remaining variants are the taker side (which the naive short already proxies at
  +0.8 points on five fills) or two-sided quoting for rewards, which is P3-B and sits below the payout floor at
  $200. A serious attempt is $5,000 or more on Polymarket so that rewards clear the floor, a σ implied from
  the market's own prints rather than borrowed from Deribit, and weeks of prints per market.
- **For forecasting:** nothing. The question is answered for this account; the next input would be a dataset
  the market does not already price.
- **For the ladder:** nothing. It is parking, and the bill is the number.
- **For the carry:** the owner's decision; its three values and what fixes them are in `docs/34`.

## 7. What keeps running, and what does not

Running on the box at $0: `qr-pm-polymarket` and `qr-pm-deribit` (the daily ladders admitted since 13 October
04:53 UTC), `qr-surface.timer` (hourly), `qr-yield.timer` (the ladder snapshot and the announcement recorder,
daily), the ETF-flow collectors, the recorder health check with its push, and the desk sheet at 06:40 UTC.
Stopped: the tape and liquidation recorders, the stage-1 timers (mandate ended 11 October). Dated: **30
November** — mirror the recording and the surface, run `scripts/p3a_wedge_v3.py --start 2026-10-13 --end
2026-11-29` once, write the addendum to this report. Nothing else is dated. No new candidate is registered
without a new input and the owner's yes.

## 8. Reproducibility

`qr trial verify` walks the chain and checks every registered memo against its stamp. The v3 run: record
1047; its summary and trade table under `$QR_ROOT/reports/p3/p3_threshold_wedge_v3_daily_2026-10-13_2026-10-30_*`;
its console log `reports/p3/p3a_v3_run_2026-11-01.log`; notes 1046 (the read date), 1048 (the deferral and
the disclosure), 1049 (the second-shortfall rule). v1: `docs/31` §9 and seq 933. v2's deferral: note 982 and
`reports/p3/p3a_v2_dryrun_2026-10-13.md`. P3-C: seq 938 and `reports/p3/p3c_insample_*`. Stage 1: `docs/33`
and the journal mirrored at `~/qr/lake/study/box/stage1.sqlite`. The ladder: `reports/p3/ladder_stress.md`. The
carry: `reports/carry/funding_history_2026-10-27.md` and `docs/34`. The recorders' code and units: `deploy/`,
`scripts/record_yields.py`, `scripts/desk_sheet.py`.
