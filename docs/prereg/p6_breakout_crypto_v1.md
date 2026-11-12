# Pre-registration: `p6_breakout_crypto_v1` — Qullamaggie's momentum breakout, long-only, Binance spot

*Drafted 12 November 2026 on the owner's "go with recommendation" — the recommendation in
`docs/research/13_four_videos_momentum_school.md` §6: of the four videos the owner sent, test the one rule that is
new, exact and free, Qullamaggie's breakout, on the crypto spot lake. **Registered the same day on that word**
through `qr trial prereg --file`, with its four control sweeps, before any return was computed; it is Programme 6's
second hypothesis. The run needs the owner's separate "run it". What was looked at before drafting: the video's
captions (`docs/research/13` §1); counts only (`reports/p6/p6_breakout_counts_2026-11-12.md`: the positions each
variant and control opens in-sample, on how many names, the share of the book invested); one count of how many bars
pass each condition in turn; one rehearsal of the invocation below on synthetic prices in a scratch lake with its own
log; the rule's run time on the real panel (0.25 s an evaluation). **Three things were changed after the first count
and before any return:** (1) "close no more than one average range above the day's low" passed 106 of 757 breakout
bars — at a close entry it rejects the big candles breakouts are made of; it was replaced by his own two rules, *not
up more than the average range on the day* and *a stop never more than one average range away*; (2) "close in the
top 30% of the day's range" was dropped — it is Bonde's (the same conference), not his; (3) the base's tightness was
at 2.5–4.0 average ranges, where it rejected almost nothing (the median 5-bar base on eligible bars spans 2.0 ranges),
and is now 2.0–2.5 ranges, scaled by √(base/5) so a 10-bar base is judged like a 5-bar one. With the first design two
variants opened 37 positions against a minimum of 60; with this one every variant opens 149–235. No return of the
rule, of a control or of the universe has been computed on a real series.*

## Where it comes from, and what this memo is not

Kristjan Kullamägi ("Qullamaggie") teaches one setup in *Qullamaggie Swing Trading School* (four hours of his 2020
streams): the biggest gainers over one, three and six months; among them a stock that made a big move, went
sideways on a rising 10-, 20- or 50-day average and got tight; buy the breakout on volume, stop at the day's low;
sell a third to a half after three to five days, stop to break-even, trail the rest on the 10-day average; at most
25% of the account a name; trade only while the market's 10- and 20-day averages rise. He reports a 20–30% win
rate, winners of 5–30× risk and ~268% a year 2013–2019, all self-reported in the video, and says the setup works on
crypto, showing BTC and ETH. Three of the four videos the owner sent teach the same school.

This memo tests **his rule, made exact, on the one dataset here with the character his universe needs** (fast,
volatile, survivorship-free: the Binance spot bucket keeps delisted pairs). It does not test him on US stocks — the
31 Nasdaq names are the megacaps he says not to trade, and a small/mid-cap US set with historical constituents is a
paid item. Like `p6_trend_reset_v1` it has no forced party behind it; it is registered because the owner asked
for the videos' strategies to be tried and the test costs $0. **The prior is a fail.**

## The rule, and what would have to be true

The rule is `MomentumBreakout` in `qr/strategies/breakout.py` (its docstring is the specification), all inputs known
at the close of bar *t*:

- **universe**: the ranked Binance spot universe, top 100 by 30-day quote volume, 15% volatility floor, pegs and
  leveraged tokens out, rebalanced monthly (`binance_spot_top100`); a name leaving it is sold at that close;
- **leader**: in the top 7% of the universe that day by its 21-, 63- or 126-bar change (any of the three);
- **range**: average daily range over 20 bars (mean of high/low − 1) at least 5%;
- **trend**: close > SMA20 > SMA50, SMA20 above its level five bars before;
- **market**: BTCUSDT's SMA10 above its SMA20 with at least one of them rising on the bar;
- **base**: over the `base` bars before *t*, highest high − lowest low, over the prior close, at most `tight` ×
  average range × √(`base`/5);
- **breakout**: close above that highest high; quote volume ≥ 1.5× its 20-bar average before *t*; the day's change
  no more than the average range;
- **entry** at the close of *t*, ¼ of equity, if one of four slots is free; several candidates strongest first
  (the best momentum percentile, then the 126-bar change);
- **stop**: max(the day's low, close × (1 − average range)), on a close below it;
- **partial**: on the fifth close after entry half is sold, the stop moves to the entry price;
- **trail**: after the partial, the rest is sold on the first close below SMA(`trail`) or below the entry price.

The book is simulated inside the rule and reports its positions' values as prices move (the runner trades every bar
to its target; a fixed ¼ target would sell a winner back to size daily).

For it to pay beyond owning the same coins, three things must hold together: momentum leaders in crypto continue
over days to weeks; **the continuation is concentrated at breakouts from tight bases**, so the setup adds to simply
owning leaders; and the breakout day is the moment, so its timing beats a random eligible day and is not beaten by
the next one. Each has a control. Against it: crypto momentum failed here as a ranking (`xsmom_v1`) and as a trend
rule (`tsmom_v1`), both at the gates; a 25-bar-per-year breakout rate on ~100 coins makes about 25 trades a year, so
the sample is ~180 trades a variant; and the book is in cash most of the time.

## Predicted sign and size

- **Absolute net return: undetermined in sign**; 2020–21 favours any long momentum book in crypto, 2018 and 2022
  punish it, and the book is 9–16% invested on average.
- **Against the exposure-matched holding of the universe: possibly ahead** — equal-weight holdings of crypto's top
  100 lost heavily in 2018 and 2022 — so gate 5 is not where it is predicted to fail. **The prediction is a FAIL at
  gate 3, 4 or 6**: deflated Sharpe below 0.90 over eight variants and the trial count, or a permutation or
  random-entry *p* above 0.1.
- **The setup adds nothing to owning leaders**: the rule's median variant within noise of the `leaders` control
  (|t| < 2 on the volatility-matched daily difference).
- **The placebo within noise of the rule** (|t| < 2); the `late` entry within noise either side.
- A net Sharpe above 2.5, or the rule ahead of its placebo by more than twenty points a year, is a reason to look
  for a leak before believing it.

## Data and instrument

Binance's public spot bucket as mirrored in the lake: daily klines for every USDT pair, 2017-08-17 → 2026-08-31,
delisted pairs kept to their last bar; `quote_volume` from the bucket; no adjustment (crypto has no splits). The
in-sample panel restricts to the 371 names the universe ever admits; 98 members on the median bar.

## Universe, costs, benchmark

Universe as above (`--n 100`, the CLI's 30-bar volume window and 180-bar minimum history). Costs: the crypto trial's
frozen spot model (`--costs spot`: VIP 0 with the BNB discount, 7.5 bps fee + 2 bps half-spread + impact, 9.5 bps a
side; gate 2 at twice that) — Binance spot charges the same 7.5 bps to makers and takers at this tier, so the
"measured maker cost" of the recommendation (the perpetuals' 3.2 bps) does not apply to spot, and this is stated as a
change from it. Benchmark for gate 5: the universe equal-weighted, scaled to the best variant's mean exposure, the
rest in cash at the bill (`--benchmark exposure --risk-free fred`).

## Variants

**8 variants** — `base` ∈ {5, 10} bars, `tight` ∈ {2.0, 2.5}, `trail` ∈ {10, 20}. Fixed: four slots, the partial on
the fifth close, volume 1.5×, the top 7%, ADR 5%, the three momentum windows, BTCUSDT as the market. Three swept
parameters (gate 8's limit is five).

## Sample, holdout, minimum

In-sample **2018-01-01 → 2025-04-30** (2,677 bars; the universe needs 180 bars of history and the momentum windows
126, so the first entries are possible from mid-2018 and the early-2018 bars are flat, stated). Holdout **2025-05-01 →
2026-08-31**, opened exactly once, after gates 1–8 pass and conditions (2)–(4) hold, on the owner's word; its panel
starts empty, so the universe and the windows warm up for about 180 bars and the rule can trade from late October
2025 — ten months; the flat months dilute its Sharpe, a cost on one side only, stated.

**Minimum**: a variant must open at least 60 positions in-sample to carry a verdict. By the count every variant opens
149–235 on 100–132 names.

## What a pass is, and what would falsify it

A **pass** needs all of:

1. the candidate through gates 1–8;
2. **the setup adds to owning leaders** — the rule's median variant against the `leaders` control's: the daily
   difference in net return, the control scaled to the rule's volatility, has a Newey–West t (30 lags) ≥ 2;
3. **the day matters** — the same against the placebo's median variant, t ≥ 2;
4. **the breakout day, not the next** — the same difference against the `late` control's median variant is not
   negative.

The **median variant** is rank ⌈n/2⌉ by net Sharpe within its sweep, so no side of a comparison is a best-of-n. The
control is scaled to the rule's volatility because the books are invested to different degrees (by the count the
rule 9–16%, `leaders` 39%, the placebo 7–12%): a raw difference would mostly measure exposure.
`scripts/p6_breakout_compare.py` computes the three from the returns the sweeps write; it was written and rehearsed
before registration and runs nothing. The `nofilter` sweep is reported beside them: if the rule passes and `nofilter`
is level with it, the pass is labelled **filter-free**; if `nofilter` loses, the filter is part of the edge.

Falsified by any of: net return at or below zero at 1× costs, or Sharpe ≤ 0 at 2× → gate 2; deflated Sharpe below
0.90 → gate 4; SPA *p* against the exposure-matched holding above 0.5 → gate 5; the permutation or random-entry
*p* above 0.1 → gate 6; alpha t below 2 → gate 8; a t below 2 against `leaders` (the setup is decoration on
momentum); a t below 2 against the placebo (any eligible day will do); `late` ahead (the breakout day is not the
point); holdout Sharpe negative or below half the in-sample → gate 9.

A pass sends the rule to a **paper** forward record (`qr forward`) at the stage-1 size, not to money; live size is a
separate decision of the owner's under the sleeve rule (`docs/35` §6). A fail closes the rule on crypto and, with
`p6_trend_reset_v1`, answers the videos' momentum school here.

## Counting

One candidate, eight variants, one run, one record. The four control sweeps are registered runs, counted in the log,
not candidates. Programme 6's counter: **two** (`p6_trend_reset_v1` is the first). Run time: the rehearsal took ten
minutes on 61 synthetic coins over 1,216 bars, almost all of it gate 6's 200 permutations over eight variants; the
real panel is 371 coins over 2,677 bars, so under an hour a sweep is the estimate, measured on the run. $0.

## Invocation

Each line as typed (the grids quoted), with `QR_ROOT=~/qr/lake`:

    qr gates --family momentum_breakout --hypothesis p6_breakout_crypto_v1 --market spot --n 100 --costs spot \
      --benchmark exposure --risk-free fred --start 2018-01-01 --end 2025-04-30 \
      --grid 'base=[5,10]' --grid 'tight=[2.0,2.5]' --grid 'trail=[10,20]' --param control=none --all-gates --upto 8

The controls are the same line with the hypothesis id and the last parameters changed:

    p6_breakout_crypto_v1_leaders   --param base=5 --param tight=2.0 --grid 'trail=[10,20]' --param control=leaders   (2 variants: base and tight do not enter)
    p6_breakout_crypto_v1_placebo   the candidate's three grids, --param control=placebo
    p6_breakout_crypto_v1_late      the candidate's three grids, --param control=late
    p6_breakout_crypto_v1_nofilter  the candidate's three grids, --param control=nofilter

After the five sweeps: `python scripts/p6_breakout_compare.py` for conditions (2)–(4). Then, once and only after a
pass, the candidate's line with `--holdout-start 2025-05-01 --holdout-end 2026-08-31 --upto 11`. The candidate's line
was rehearsed end to end on synthetic prices in a scratch lake with its own log (every gate ran; the noise failed).
