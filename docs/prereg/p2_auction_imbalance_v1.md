# Pre-registration: `p2_auction_imbalance_v1` — closing-auction imbalance fade, long-only, overnight

*Drafted 16 September 2026, before any run. Register only after the
close-to-open panel (`qr data auction-build`) has been built and its QA read,
and before any backtest of this family.*

## Mechanism

Index funds, ETFs and end-of-day rebalancers must trade at the close, and
they show their hand: from 15:50 ET Nasdaq publishes, every five seconds,
the paired quantity and the imbalance of its closing cross. A large
imbalance on the sell side means the auction will clear below where the
continuous market would have; the closing price is pushed, and the push
reverts — about half by the next open, fully within the next day
(Bogousslavsky & Muravyev, "Who trades at the close?", JFM 2023, who also
measure the close's share of volume rising from 3% to 7.5% between 2010 and
2018). The forced party is the rebalancer, whose order is a function of
flows and index rules, not of price; the counterparty earns a concession.
This family takes the other side of a **sell** imbalance: buy at the close,
sell at the next open.

Long-only, because the account cannot short below $2,000 of equity
(`docs/20` §6). The symmetric leg — short into a buy imbalance — is the
natural pair and is pre-registered separately when shorting exists; it is
not run here and this document does not claim it.

## Predicted sign and size

**Positive against exposure-matched buy-and-hold.** Gross return per
event **5 to 15 bps** (close to next open, on the names traded); net of
the frozen cost model (6 bps a round trip) a **positive but small** edge,
net Sharpe **0.3 to 1.0** above the exposure-matched benchmark; the
effect **larger for larger |imbalance / paired|** (monotone across the
threshold grid). A net Sharpe above 2 is a reason to look for a timestamp
leak (an imbalance message that was not public at 15:55), not to
celebrate.

## Data

Databento `XNAS.ITCH`: schema `imbalance` (every closing-cross message,
receive-time stamped) and `ohlcv-1m` / `ohlcv-1d` for the same names,
2018-05-01 to 2026-09-01, bought on 16 September 2026 for $6.27 + $48.99 +
$21.94 (+ $0.10) of the account's credit; hashes and job ids in the mirror's
sidecars. The feature is `qr/data/imbalance.py::closing_snapshots`: for
each snapshot cutoff the last message received at or before it (one-second
grace), `published_at` = its receive time, `age_seconds` its staleness.

## Universe

`nasdaq31`: QQQ and the 30 Nasdaq-listed stocks that were Nasdaq-100
members throughout 2018–2026 — AAPL MSFT NVDA AMZN META GOOGL GOOG TSLA AVGO
COST NFLX AMD PEP CSCO ADBE INTU QCOM TXN ISRG AMGN CMCSA INTC BKNG AMAT MU
LRCX ADI GILD SBUX MDLZ — a fixed basket, no ranking. Nasdaq-listed only,
because the Nasdaq closing cross is the primary auction for them and an
empty secondary cross for Arca-listed names (SPY, DIA, IWM were bought and
read: median paired quantity zero). Stated limits: META's raw symbol begins
June 2022 (FB before it); the names are ones that stayed in the index, a
survivorship on liquidity and not on the overnight return this family
trades, and it is written down here rather than corrected. A name whose
share price exceeds the slice a $1,000 book can buy (BKNG at ~$5,000)
holds zero shares under the whole-share rule; the 20-position book at
$100,000 is reported beside it for the reason `docs/prereg/p2_insider_cluster_v1.md`
gives.

## Instrument and panel

Market `auction-xnas`: one synthetic price per name whose bar-*t* return is
**open(t) / close(t−1) − 1**, the overnight return, so that a book set at
the close of *t−1* and held over bar *t* earns exactly what the rule
claims and nothing of the intraday move. Fills: entry at the official close
(the Nasdaq closing cross for these names) with an MOC/LOC `cls` order in
whole shares; exit at the official open with an MOO. Quote volume is the
day's Nasdaq dollar volume. The panel carries `imb_1550`, `imb_1555`,
`imb_1558` = signed imbalance / paired at each cutoff (negative = sell
imbalance), and `paired_usd`, each stamped at bar *t−1* only if
`published_at` ≤ the cutoff of day *t−1* — the point-in-time assertion.

## Rule and parameters

At the decision cutoff on day *t−1*: eligible names are those with a
snapshot no older than 10 seconds, paired value ≥ $5M, and imbalance ratio
≤ −`k` (a sell imbalance of at least `k` of the paired quantity). Buy up
to `n_max` of them, the largest |ratio| first, equal weight, gross 1.0 of
equity spread across the positions taken (a day with one signal holds one
name at 1/n_max, the rest cash). Sell all at the next open. No position
is held past the open.

| Parameter | Range | Swept? |
|---|---|---|
| `k` (minimum sell imbalance / paired) | 0.10, 0.20, 0.30, 0.50 | yes |
| `snapshot` | 15:50, 15:55 | yes |
| `n_max` | 4, 8 | yes |
| `min_paired_usd` | $5M | fixed |
| `max_age_seconds` | 10 | fixed |

**16 variants.** Gate 4 deflates against them.

Invocation, in-sample:

    qr gates --family auction_fade --hypothesis p2_auction_imbalance_v1 \
      --market auction-xnas --costs alpaca --basket nasdaq31 --equity 1000 \
      --benchmark exposure --risk-free fred --end 2025-08-31 \
      --grid 'k=[0.10,0.20,0.30,0.50]' --grid 'snapshot=["15:50","15:55"]' \
      --grid 'n_max=[4,8]' --param side=sell --all-gates --upto 8

then once, `--holdout-start 2025-09-01 --upto 11`, opened only if gates
1–8 pass.

## Cost model

`CostModel.alpaca_zero()`: $0 commission, 2 bps half-spread (a stated
placeholder until measured from these names' quotes), 1 bp PFOF slippage,
whole shares — 3 bps a side, **6 bps a round trip**, 12 bps stressed.
Every trade is a round trip, so the cost bar is the whole test: a 5-bps
event advantage does not survive it and a 15-bps one does.

## Benchmark

**Exposure-matched buy-and-hold** of `nasdaq31`, equal weight, scaled to
the best variant's mean gross exposure with the rest at FRED DTB3. The book
is long stocks overnight, so cash would credit beta; full buy-and-hold
would debit the daytime hours it never holds.

## Controls

- **Random-night control**: the same book and sizing on names drawn at
  random each day from the eligible universe (gate 6's random-entry null,
  200 draws) — overnight drift in large caps is positive, and the control
  says how much of the family is that.
- **Buy-imbalance mirror**, long-only: buy into a *buy* imbalance ≥ `k`,
  same sizing. The mechanism predicts this loses; if it earns as much as
  the family, the family is overnight drift, not the auction.

## Out-of-sample period

**1 September 2025 to 31 August 2026**, opened exactly once, after gates
1–8. In-sample is 2018-05-01 to 2025-08-31.

## What would falsify this

- Net return negative at 1× costs, or Sharpe ≤ 0 at 2× → gate 2.
- SPA *p* against the exposure-matched benchmark above 0.5 → gate 5.
- Random-night null *p* above 0.1 → gate 6: the auction adds nothing to
  overnight drift.
- The buy-imbalance mirror earning as much as the family → recorded as a
  fail of the mechanism whatever the gates say.
- No monotone relation between `k` and the event advantage → the
  imbalance is not the driver.
- Holdout Sharpe negative or below half the deflated Sharpe → gate 9.
- Incubation: MOC fills more than 2 bps from the official close, or more
  than one in ten `cls` orders rejected → the execution is not as modelled.

## Prior

The most likely outcome: **a real gross advantage of 5–10 bps on the
largest sell imbalances that the 6-bps round trip halves**, a family that
passes gates 3–5 and warns at gate 2 on the cost share; the interesting
number is the capacity, since $5M paired auctions in 30 names cannot absorb
a large book without moving the cross.

## Amendment, 16 September 2026 — before registration, before any run

The panel was built (`qr data auction-build`, market `auction-xnas`, 31
instruments, manifest `483ed989…`) and read before this document was
registered:

1. **Split nights found and left empty**: AAPL 2020, NVDA 2021 and 2024,
   AMZN, GOOGL, GOOG and TSLA 2022, TSLA 2020, AVGO 2024, NFLX 2025, ISRG
   2021, LRCX 2024, and **BKNG 6 April 2026 (25:1)** — 13 nights of about
   2,095; each costs the bar after it as well.
2. **`META` before 9 June 2022 was a different security** (the Roundhill
   Metaverse ETF held the ticker; a $12.29 close was followed by a $196
   open). The name's history starts on 9 June 2022 (`SYMBOL_START`); the
   earlier rows are not in the panel. This is a data fact about raw
   tickers, recorded here so no reader mistakes 1,060 sessions for a gap.
3. Snapshots at 15:55 exist for 2,077 of 2,095 sessions per name (the
   missing ones are early-close days, when the cross runs at 13:00 and the
   15:55 cutoff has nothing fresh); a session without a fresh snapshot has
   no signal, which is the rule as written.
4. The mirror control is the family's own class with `side=buy`
   (`p2_auction_imbalance_v1_mirror`), registered beside it. `--equity 1000`
   is in the invocation so whole shares bind as the cost model says.
5. Mean 15:55 imbalance ratio across names is +0.04 to +0.10 (QQQ +0.18):
   buy imbalances are the norm in these names, so sell imbalances of the
   sizes swept are the minority events the rule fires on. No range was
   changed after reading this.
