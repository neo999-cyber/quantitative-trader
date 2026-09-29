# Programme 2 — the report (week 12's deliverable, delivered in week 1)

*17 September 2026. Every figure below is re-derived from the trial log
(`qr trial verify`: 649 records, 2,071 trials, chain verified), the gate
reports under `$QR_ROOT/reports/`, and the QuantConnect mirrors; the
dated week log in `docs/20` has the workings. This is the "per family,
capacity, incubation slippage, capital ladder" report the plan set for
week 12. It arrives in week 1 because the eight-candidate counter filled
in three days, not twelve weeks.*

## 1. The answer

Eight pre-registered mechanism candidates went through the gates on the
instruments, resolutions, point-in-time data and comparators that
Programme 1 lacked. **None passed gates 1–8; no holdout was opened; no
family enters incubation; nothing is sized.** Under the stopping rule
restated in `docs/20` — eight gated candidates, none surviving, the same
3× cost bar — the finding is the same as Programme 1's on a different
premise: *with public data, a $1,000 account and taker execution, no
edge was found.*

Four of the eight showed the predicted sign and did not reach
significance; three were killed by costs or by their own control; one was
a timing rule over a real carry that the carry itself beat.

## 2. Per family

| # | Family | Hypothesis | Stopped at | Best net Sharpe | Key number | Capacity (gate 2) | What the controls said |
|---|---|---|---|---|---|---|---|
| 1 | C1 funding carry | `p2_funding_carry_v1` / `_v2` | v1 gate 1 (gross Sharpe 9.7 > 8 ceiling); v2 **gate 6**, permutation p = 0.99 | 3.09 (v2, hourly unit, daily decisions) | funding 97% of gross; the permuted worlds pay the entry rule *more* — it does not time the crashes it was meant to avoid | ~$10M | always-in carry: Sharpe 2.42, p = 0.63 — hold-the-carry is real; the rule adds nothing |
| 2 | E1 auction imbalance fade | `p2_auction_imbalance_v1` (+ `_100k`, `_mirror`) | **gate 2** (costs 50% of gross), gate 5 SPA 0.51 | 0.66 | 9 bps gross an event (pre-registered 5–15), 6 bps round trip; not monotone in the threshold | $1M ($3M at $100k) | mirror (buy side) loses, 108% of gross to costs |
| 3 | E5 insider clusters | `p2_insider_cluster_v1` (QuantConnect) | **gate 5 / 8** — SPA 0.19, alpha t 1.31 vs exposure benchmark | 0.69 = benchmark's 0.69 | 16.7%/yr from four-stock concentration and a 47% drawdown; beta 1.05 | not measurable externally | random-name control 0.33; family − control t 1.77 |
| 4 | E2 late-day momentum | `p2_late_day_momentum_v1` | **gate 2** (gross negative) | −1.04 | last half hour of QQQ uncorrelated with the day (r = 0.006); days up ≥ 1% earn −2.7 bps | — | reverse also loses (t −2.48) |
| 5 | E4 post-earnings drift | `p2_pead_v1` (QuantConnect) | **gates 3, 4, 5** — t 1.37, DSR 0.76, SPA 0.76 | 0.36 vs benchmark 0.69 | alpha −2.9%/yr (t −0.50), beta 1.28; 68% drawdown | — | top > random (0.15) > bottom (0.03): a drift, not an edge |
| 6 | C5 OI-conditioned reversal | `p2_oi_reversal_v1` | **gate 3** — t 1.68; DSR 0.63, SPA 0.46, permutation 0.35 | 0.84 (gross 1.07) | 16.9%/yr at 20% vol, 2,291 round trips; 8/9 CV paths positive | ~$30k | unconditioned reversal loses (t −0.80): OI points the right way |
| 7 | C2 cross-venue funding spread | `p2_venue_spread_v1` | **gate 3** — t 1.76; DSR 0.71, SPA vs cash 0.97 | 0.62 (gross 1.16) | 2%/yr at 3% vol, open 30% of the time; costs take 45% of gross | $1k | always-in loses (t −2.45): the mean spread does not pay two taker legs |
| 8 | E7 short squeeze (SI + FTD) | `p2_short_squeeze_v1` (QuantConnect) | **gates 3, 4, 5** — t 1.88, DSR 0.75, SPA 0.88 | 0.70 | alpha t 1.34; the 20-day holds lose outright | — | random-name control alpha t **2.49** — higher than any variant |

Reading across the rows:

- **Costs were decisive once** (E1, at exactly the pre-registered gross)
  and *half*-decisive twice (C2's 45%, C5's 22% drag). At $0 commission
  the bar is the spread, and the spread is what the small account pays.
- **The exposure-matched comparator did its job.** E5 and E4 would have
  passed against cash and against buy-and-hold of a rising index; against
  an equal-weight book of the same eligible names, both are beta.
- **Four candidates carried a sign** (C1's carry; C5's, C2's, E7's t of
  1.7–1.9). None is significant after deflation, and the one with a
  Sharpe worth having (C1's always-in carry, 2.4) is a *holding*, not a
  rule: the permutation null shows the entry/ceiling logic does not time
  the crashes it exists for. That holding is available to anyone with
  two accounts and is not an edge in the sense the programme defined.
- **The controls were the sharpest tool.** Six of eight verdicts were
  decided or confirmed by a mirror, an always-in book, a random draw or
  an unconditioned rule, before the statistics were needed.

## 3. What the programme bought for its money

$77.30 of Databento credit (minute bars and imbalances for 31 Nasdaq
names, QQQ), $0 elsewhere: SEC Form 4 and 8-K, FINRA short interest and
Reg SHO, SEC fails-to-deliver, Binance and Bybit funding and open
interest, QuantConnect's free tier. Alpaca paper account verified; no
live order was ever sent; no funded evaluation was bought.

Engine: **ten defects** found and fixed by the runs themselves, each with
a test (`docs/22`), plus a permutation null that preserves cross-symbol
correlation, an exposure-matched benchmark, a whole-share $0-commission
cost model, three synthetic instruments (carry unit, cross-venue unit,
overnight/late-day session bars), point-in-time loaders with availability
stamps for every event source, and a QuantConnect path that is scriptable
from a logged-in page. `pytest`: 796 tests.

## 4. Incubation slippage, capital ladder

Not applicable. Nothing reached incubation, so there is no backtest-vs-
paper slippage to report; and no family has a return to put on a capital
ladder. The honest ladder is the one in `docs/18`: at every size up to
$100,000 the index fund is the better way to own the basket, and the
programme found no reason to revise that.

## 5. What a serious attempt would require (unchanged in kind, sharper in detail)

1. **Maker execution on both perp legs**, verified rebates, and a fill
   model this engine currently refuses to assume. C2's spread and C1's
   carry are real; at 25 bps a round trip they are not tradable, at ~4
   bps they might be. That is an execution project, not a research one.
2. **Capital of ≥ $2,000 with shorting** for the long/short versions of
   E5 and E4 (the papers' specification), and the 20-position books that
   would let concentration stop dominating the drawdown.
3. **A longer open-interest sample** or a second venue's OI for C5 — the
   one crypto rule with a control in the right direction and a CV that
   held (8/9 paths); its 3.75 years need 8.3 to reach significance if the
   effect is what the sample says.
4. **Order-book data** for the auction and squeeze families: E1 at 9 bps
   gross an event needs the spread to be crossed by a resting order, and
   E7 needs a universe that exists at the time (half its names were not
   tradable in LEAN).
5. **The independent review** (`docs/22`, ten defects) before anything
   above is trusted; it is running on Codex as this is written.

## 6. What keeps running, and what does not

- Running: the OKX/Bybit liquidation recorders (C3, on the Hetzner box)
  and the ETF flow collector (`docs/17`). Both are cheap, need nothing,
  and were never counted. C3 has a kill test written in `docs/20` §6 for
  six weeks of data; it is a new input when that file is long enough.
- Not running: any pre-registration, any gate run, any autopilot. The
  counter is at eight; the next registration needs a new instrument, a
  new data source, or a new cost model — a *new input*, per the rule —
  and the owner's yes.

## 7. Reproducibility

`export QR_ROOT=~/qr/lake; qr trial verify` walks the chain. Every
pre-registration is under `docs/prereg/` with its sequence number in the
week log; every gate report is `reports/<hypothesis>.json` with its
variant-return matrix beside it; the QuantConnect equity curves are under
`mirror/quantconnect/<family>/` and re-scored by
`scripts/external_gates.py --family e5|e4|e7 --no-log`. The data is
rebuilt from the mirrors by the `qr data` commands named in `docs/20`.
