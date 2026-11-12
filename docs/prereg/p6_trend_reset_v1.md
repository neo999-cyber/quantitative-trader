# Pre-registration: `p6_trend_reset_v1` — a trend filter with a momentum reset, long-only, Nasdaq megacaps

*Drafted 12 November 2026 on the owner's input — a 105-second clip on trading with AI agents
(`docs/research/12_video_ai_agents_trend_reset.md`) and "we need to try this model here. with small tweaks" — and on
the owner's choice of market the same day (the 31 Nasdaq names, with the ETFs as a second arm). **A draft until it is
registered through `qr trial prereg --file`; registration needs the owner's yes, opens Programme 6 and spends its
first counter; the run needs a separate "run it".** What was looked at before drafting: the clip; the two instruments'
prices; counts only (`reports/p6/p6_counts_2026-11-12.md`: the positions each variant opens in-sample, on how many
names, the share of the book they fill) and two checks of the instrument; one rehearsal of the invocation below on
synthetic prices in a scratch lake with its own log. Two things were changed after the first count and before any
return: the placebo was redefined (its first form held 60% of the book against the rule's 88%, so it was not the
rule's exposure with the choice of name removed), and the ETF instrument's share volume was restated (the count
showed four names where twelve were expected: the engine was withholding the rest). No return of the rule, of a
control or of the universe has been computed on a real series.*

## Where it comes from, and what this memo is not

The clip's guest (unnamed in it; the heading says he managed $4 billion) describes a workflow — agents for
fundamentals, for news and X sentiment and for technicals, five stocks paper-traded for a while — and one chart rule
of his own. He gives no number and claims no result. This memo tests **the chart rule and nothing else**. The agents
cannot be tested on history (a language model asked about a past date knows what followed) and are no part of it; a
forward diary, if the owner starts one, gets its own memo before its first reading.

It also does not meet this project's standing requirement for a new candidate, a mechanism with a forced party
behind it. It is registered because the owner asked for the rule to be tried and the test costs $0. The prior is a
fail, and the memo's job is to make a fail — or a pass — mean something.

## The rule, and what would have to be true

Trade a name only while it is above its 200-day moving average and that average is rising; enter when its rate of
change has "reset close to zero after being higher" — a pause inside an uptrend; ride it for about three months;
five names at a time.

For that to pay beyond holding the same names, three things have to hold together: trends in large stocks continue
(the momentum literature's claim, weakest in the largest names and after 2009); the continuation is **concentrated
after pauses** rather than after extensions, so that the reset is better timing than buying strength; and the names
the reset picks do better than other names in uptrends on the same days. Each has a control below. Against it: these
are the most watched stocks in the world; the sample is six years; and with five slots among thirty-one names in a
rising market the book is almost always full, so the rule is in effect a rotating holding of five megacaps whose
only possible edge is which five.

## Predicted sign and size

- **Absolute return positive, and meaningless**: the 31 names are survivors of a strong period.
- **Against the exposure-matched holding of the same names: nothing.** Alpha between −5 and +5 points a year with a
  t below 2 in magnitude; SPA *p* well above 0.05. **The prediction is a FAIL at gate 5**, as `etf_tsmom_v1` failed
  (`docs/08`), with gate 6's random-entry null and gate 8's alpha failing beside it.
- **The reset adds nothing to the filter**: the rule's median variant within noise of the `trend` control (|t| < 2
  on the daily difference).
- **The placebo within noise of the rule** (|t| < 2); no ordering predicted between the rule and its mirror — the
  rule needs to be at least level with the mirror for its own story to hold.
- **The ETF arm**: net Sharpe 0.3 to 0.7, alpha against its own exposure-matched holding at or below zero.
- A net Sharpe above 2.0, or the rule ahead of its placebo by more than ten points a year, is a reason to look for
  a leak before believing it.

## Data and instruments (built 12 November 2026, `qr data trend-build`)

**`trend-xnas`** (source `databento`): one bar per regular session for each of the 31 names, from the lake's own
Nasdaq minute bars (`XNAS.ITCH ohlcv-1m`, 2018-05-01 → 2026-08-31; 2,095 sessions a name, `META` 1,060 from
2022-06-09 when Facebook took the ticker). Open: the first regular minute's open. Close: the first print of the
closing auction's minute — 16:00 New York, 13:00 on the 18 early closes in the span (the exchange's schedule,
checked against where the auction volume sits: for AAPL and MSFT the sessions whose 13:00 minute outweighs their
16:00 minute are exactly those 18). That print is the published close to the cent on an ordinary day (AAPL
2020-08-28: 499.23 against 499.23; 2024-06-12: 213.08 against 213.07) and 19 bps away on the heaviest (2020-08-31,
AAPL's split day: 128.79 against 129.04); stated, not repaired. **Splits**: a session opening more than 40% from the
previous close is a corporate action; its ratio is the nearest whole split within 10%, earlier prices are divided by
it and earlier share volume multiplied; a night that fits none is left alone and reported. Twelve were found, all
explained: AAPL 4:1 (2020-08-31); TSLA 5:1 (2020-08-31) and 3:1 (2022-08-25); NVDA 4:1 (2021-07-20) and 10:1
(2024-06-10); AMZN 20:1 (2022-06-06); GOOGL and GOOG 20:1 (2022-07-18); ISRG 3:1 (2021-10-05); AVGO 10:1
(2024-07-15); LRCX 10:1 (2024-10-03); NFLX 10:1 (2025-11-17); BKNG 25:1 (2026-04-06). **Dividends are not in these
prices**: the rule and its benchmark hold the same panel, so the comparison is unaffected to first order and both
absolute returns are understated by the yield.

**`trend-etf`** (source `tiingo`): the twelve ETFs' daily bars as the lake holds them (adjusted for splits and
dividends; 1993–2007 → 2026-09-11), with the share volume restated in the adjusted price space. The lake's own `etf`
market is withheld by the engine as it stands (`docs/20`, 12 November 2026), which is why this arm reads `trend-etf`.

**The rule's inputs are stored on the bars** (`above_ma`, `trend_ok`, `zroc_21`, `zprior_21`, `zroc_63`,
`zprior_63`), each computed on the name's full history and known at the close of its own bar, so a panel cut at any
date arrives warmed up: the gates run the rule on sub-panels, and a rule that needs 252 bars before its first signal
would otherwise spend a one-year holdout warming up. Inputs exist from 2019-05-02 for the Nasdaq names.

## Universe

`nasdaq31` (fixed basket, as E1 registered it): QQQ and the 30 Nasdaq-listed stocks that were Nasdaq-100 members
throughout 2018–2026. **Chosen with hindsight on survival and size**, which flatters any long-only rule in absolute
terms; the benchmark holds the same names, and the ETF arm (`etf12`: DBC, EEM, EFA, GLD, HYG, IEF, IWM, LQD, QQQ,
SPY, TLT, VNQ — Programme 1's basket) has no such hindsight and sixteen years in-sample.

## Rule and parameters (frozen; `qr/strategies/trend.py`, family `trend_reset`)

- **Trend**: close above SMA(200), and SMA(200) above its own level 21 bars ago.
- **Rate of change** over `roc` bars as a log change, in units of the name's own volatility over that span (the
  standard deviation of daily log returns over 252 bars × √roc) — the first tweak: one threshold for a quiet name and
  a wild one.
- **Was higher**: the scaled rate of change reached `was_high` on some bar among the `2 × roc` before today.
- **Has reset**: its absolute value today is at most `near_zero`.
- **Entry** at the close of a bar where all three hold and the name is not held. Five slots of one fifth of the book
  each, the rest in cash. More names than free slots: the strongest prior run first.
- **Exit** after 63 bars, or at the first close at or below SMA(200). A name that still qualifies on its exit bar is
  held on.

Grid: `roc` ∈ {21, 63} × `was_high` ∈ {1.0, 1.5} × `near_zero` ∈ {0.25, 0.5} — **8 variants**; `hold` = 63 and the
five slots are fixed. Gate 4 deflates against the eight.

## Controls (registered with it, each its own id; none is a candidate)

| id | what it runs | the question |
|---|---|---|
| `p6_trend_reset_v1_trend` | `control=trend`: enter on the trend filter alone, the same slots, hold and exit; 1 variant | does waiting for the reset add anything to the filter? |
| `p6_trend_reset_v1_mirror` | `control=mirror`: enter when the scaled rate of change is at or above `was_high` today; `roc` × `was_high`, 4 variants | is it the pause, or just strength? |
| `p6_trend_reset_v1_placebo` | `control=placebo`: on each bar, as many positions as the rule opened on that bar, in names drawn at random among those in an uptrend and not held (seed 20261112); 8 variants | the rule's timing and book kept, does the choice of name matter? |
| `p6_trend_reset_v1_etf` | the rule on `trend-etf`, `etf12`, in-sample 2007-01-01 → 2022-12-31; 8 variants | does it hold where the list of names has no hindsight? |
| `p6_trend_reset_v1_etf_trend` | `control=trend` on the same; 1 variant | the ETF arm's own filter-only comparison |

## Cost model

`--costs alpaca_frac`: Alpaca's $0 commission with the 2-bps half-spread and 1 bp of slippage the Programme 2 stock
memos froze (placeholders until measured from quotes, pessimistic for these names) — **3 bps a side, 6 a round trip**
— and **fractional shares**, because a rule that holds for months sends day orders, which fill in fractions; the
whole-share rule of `alpaca` belongs to on-close orders. Equity $1,000. About four round trips a slot a year: costs
near 25 bps a year do not decide this family, and gate 2 says so either way. The engine fills at the bar's close; an
order sent in the session's last minutes fills near it, and the difference is not modelled.

## Benchmark

**Exposure-matched buy-and-hold** of the same basket, equal weight, scaled to the best variant's mean exposure
(`--benchmark exposure`), as the Programme 2 stock memos registered it. The rule is long stocks nearly all the time
(75–92% of the book across variants by the count), so cash would credit it with the market.

## Sample, holdout, minimum

In-sample **2019-07-01 → 2025-08-31** (1,551 bars; inputs complete from 2019-05-02, with the "was higher" window
still filling in the first weeks, stated). Holdout **2025-09-01 → 2026-08-31**, opened exactly once, after gates 1–8
pass and on the owner's word; its panel carries the inputs, and the book starts flat on its first bar — positions
the rule would have carried over the boundary are not carried, a cost on one side only. The ETF arm's later years
(2023 on) are not opened under this memo.

**Minimum**: a variant must open at least 60 positions in-sample to carry a verdict. By the count every variant of
the rule opens 145 to 214 on the Nasdaq names (30 or 31 of them) and 214 to 441 on the ETFs (all twelve).

## What a pass is, and what would falsify it

A **pass** needs all of:

1. the candidate through gates 1–8;
2. **the reset adds to the filter** — the rule's median variant against the `trend` control: the daily difference
   in net return has a Newey–West t (21 lags) of at least 2;
3. **the choice of name matters** — the same against the placebo's median variant, t at least 2;
4. **the pause, not strength** — the same difference against the mirror's median variant is not negative.

The **median variant** is rank ⌈n/2⌉ by net Sharpe within its sweep, so that no side of a comparison is a
best-of-n: on the rehearsal's drifting noise the rule's best of eight stood 0.44 of Sharpe above the one-variant
`trend` control and its median 0.22 above the placebo's, and a bar set on Sharpe would have been met by nothing at
all. `scripts/p6_trend_compare.py` computes the three from the returns the sweeps write; it was written and
rehearsed before registration and runs nothing. With a tracking error of 12–15% between two five-name books over
6.2 years, a t of 2 asks for about ten points a year of difference — the same height the gates set for alpha.

(5) is reported beside it: the ETF arm's gate-8 alpha against its own benchmark, and its median variant against its
own `trend` control. If (1)–(4) hold and the ETF arm's alpha is not positive, the pass is labelled
**survivor-universe only**.

Falsified by any of: net return at or below zero at 1× costs, or Sharpe ≤ 0 at 2× → gate 2; SPA *p* against the
exposure-matched holding above 0.5 → gate 5; the random-entry null's *p* above 0.1 → gate 6; alpha t below 2 →
gate 8; a t below 2 against the `trend` control (the reset is decoration); a t below 2 against the placebo (the
names are interchangeable); the mirror ahead (it is momentum, not the pause); holdout Sharpe negative or below half
the in-sample → gate 9.

A pass sends the rule to a **paper** forward record (`qr forward`), not to money: no US-stock venue is set up, and
live size is a separate decision of the owner's. A fail closes the rule; the forward diary of the agents, if one
runs, is judged on its own memo.

## Counting

One candidate, eight variants, one run, one record. The five control sweeps are registered runs, counted in the
log, not candidates. Programme 6's counter: **one**. About six minutes a sweep on the laptop (gate 6's permutations),
under forty in all. $0.

## Invocation

Each line as typed (the grids quoted: the brackets are the shell's otherwise), with `QR_ROOT=~/qr/lake`:

    qr gates --family trend_reset --hypothesis p6_trend_reset_v1 --market trend-xnas --basket nasdaq31 \
      --costs alpaca_frac --equity 1000 --benchmark exposure --risk-free fred --start 2019-07-01 --end 2025-08-31 \
      --grid 'roc=[21,63]' --grid 'was_high=[1.0,1.5]' --grid 'near_zero=[0.25,0.5]' \
      --param hold=63 --param control=none --all-gates --upto 8

The controls are the same line with the hypothesis id and the last parameters changed:

    p6_trend_reset_v1_trend      --param hold=63 --param control=trend                       (no grid: 1 variant; ties by the 63-bar prior run)
    p6_trend_reset_v1_mirror     --grid 'roc=[21,63]' --grid 'was_high=[1.0,1.5]' --param hold=63 --param control=mirror
    p6_trend_reset_v1_placebo    the candidate's three grids, --param hold=63 --param control=placebo

and the ETF arm is the candidate's line and the `trend` line with

    --hypothesis p6_trend_reset_v1_etf        --market trend-etf --basket etf12 --start 2007-01-01 --end 2022-12-31
    --hypothesis p6_trend_reset_v1_etf_trend  --market trend-etf --basket etf12 --start 2007-01-01 --end 2022-12-31

After the six sweeps: `python scripts/p6_trend_compare.py` for conditions (2)–(4). Then, once and only after a pass,
the candidate's line with `--holdout-start 2025-09-01 --holdout-end 2026-08-31 --upto 11`. The candidate's line was rehearsed end to end on synthetic prices in a scratch lake with its own log
(six minutes, gates 0–8, a fail at gates 5, 6 and 8 on drifting noise, as it should be); the controls' and the ETF
arm's lines with a short permutation count.
