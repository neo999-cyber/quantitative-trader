# 12 — A video on trading with AI agents, and the rule inside it (12 November 2026)

The owner sent a clip (`~/Downloads/trade.mp4`, 105 seconds, not copied into the repo) and said: "check this video
and what it says. we need to try this model here. with small tweaks." This note records what it says, what of it can
be tested, what this project already knows about its parts, and the tweaks proposed. **Nothing is registered and
nothing has run.**

## 1. The source, and how it was read

A portrait clip from the channel "Titans Of Tomorrow" (@titans.of.tomorrow), headed "He Managed $4 Billion — Here's
How To Use AI to Trade": a podcast host and a guest. The guest is not named in the clip and is not identified here.
It was read from its burned-in captions — the caption line cropped five times a second, one crop kept per distinct
caption (100 cards), and every stretch where a caption stayed up longer than usual looked at frame by frame for a
card missed (none). The audio was not transcribed: the machine has `whisper-cli` but no speech model, and none was
downloaded. The clip is an excerpt; what the guest said before or after it is not known.

## 2. What it says (in this note's words)

The host asks how a trader can put AI to work. The guest's answer, in order:

- Start from back-testing or technical analysis, and have **agents** do the legwork. With current models one can
  simply ask for a handful of agents, choose five stocks and **paper trade for a while**, and build a process from it.
- **Agent one, fundamentals:** earnings, analyst coverage, and any news on the company's earnings forecast.
- **Agent two, news and X:** what is happening around the company, the bull and bear cases, a gauge of sentiment.
- **Agent three, technicals,** with his own rule: only names above their 200-day moving average with that average
  rising; then wait for the rate of change to have "reset close to zero after being higher" — a consolidation inside
  an uptrend; he trades on a three-month horizon and wants to ride a trend of that length.
- Then let the agents run, **monitor the paper positions** against what they report — the fundamentals, the
  sentiment, the catalysts coming up (a product event, for instance) — and ask the AI how to build a good process
  from it.

Five agents are asked for and three are described; five is also the number of stocks. No performance figure, no
back-test, no product and no data source is given. It is a workflow and one chart rule, offered as a starting point.

## 3. What can be tested, and what cannot

| part | on history | forward |
|---|---|---|
| the chart rule (trend filter, momentum reset, three-month hold) | **yes** — prices only, no hindsight in the signal | yes |
| the agents' reading of earnings, news, sentiment, catalysts | **no** — a language model asked about a past date already knows what followed, and an archive of X is paid | **yes** — each day's reading recorded that day, as a point-in-time feature |
| "paper trade five names and see" | — | yes, but five names on a three-month hold is about twenty trades a year: a diary, not evidence |

The project's standing rule already says it: every model output enters as a point-in-time feature, never as a trade.

## 4. What this project already knows about the parts

- **Trend rules.** Time-series momentum failed the gates on crypto (`tsmom_v1`, Sharpe 0.75, gate 3) and on ETFs,
  where it was the closest Programme 1 came to a pass (`etf_tsmom_v1`, Sharpe 0.68, stopped at gate 5: it did not beat
  holding). The clip's rule is a cousin: the same filter with a timed entry.
- **Timing against holding.** Programme 4's timer lost to the holding it timed in every year; the question a timed
  entry must answer is whether it adds anything to simply holding names that pass the filter.
- **Direction from models.** Six models, two of them foundation models, scored at the base rate on direction
  (P3-C, P5). A reader of news is a different input from a reader of prices, which is why only a forward record can
  speak to it.
- **Event rules on US stocks.** Earnings drift and insider clusters were registered and failed in Programme 2.
- **What exists to build on.** The gates and the trial log; `qr forward`, the paper record gate 10 reads; the
  31 Nasdaq names with minute and daily bars from May 2018 (`nasdaq31`, survivors, stated) and twelve ETFs from
  1993; an Alpaca paper key; `centaur/`'s catalyst summariser (untouched).

The honest prior: the rule alone fails the gates as a way to beat holding the same names, most likely at gate 5, on
power as much as on effect — about six years of in-sample bars and five positions cannot show a small edge at
t ≥ 2. The agents are an open question that only time can answer.

## 5. The tweaks proposed

1. **Split what can be tested from what can only be watched.** The rule is registered and run once through the gates
   on history. The agents run forward only, writing dated readings; they never place a trade.
2. **Make the rule exact, and make one threshold fit every name.** The rate of change is measured in units of each
   name's own volatility, so "was higher" and "close to zero" mean the same for a quiet stock and a wild one. A small
   pre-registered grid (two windows, two "was higher" levels, two "close to zero" bands: eight variants), the
   three-month hold and the exit below the average fixed.
3. **A universe instead of five hand-picked names.** Five slots, as in the clip, filled by the rule from the 31 Nasdaq
   names; and the twelve ETFs as a second arm with no hindsight in who is in the list and nineteen years of bars.
4. **Controls a pass must survive.** Entering on the trend filter alone (does the reset add anything?); entering on
   strength instead of the reset; a placebo with the timing drawn at random; the benchmark exposure-matched holding of
   the same names.
5. **The agents as recorded features on a paper book the rule runs.** Three readings a day for each open or
   candidate name — fundamentals, news and sentiment, catalysts — as scores with their sources; after six months, one
   pre-registered question: did the positions the agents liked do better than the ones they did not? No paid X feed:
   sentiment from what a web search surfaces.

## 6. What is built, and what waits for the owner

**Built, on synthetic prices only** (`qr/strategies/trend.py`, `tests/qr_platform/test_trend_reset.py`): the family
`trend_reset` with its three controls, registered with `qr gates`; the book checked on hand-sized arrays, the signals
against a slow reference, the look-ahead rule by truncation, the universe mask. No real series has been read by it.

**Waits:** (1) the market — the 31 Nasdaq names with the ETF arm is the recommendation; it needs a daily
session-close instrument built from the lake's own minute bars and adjusted for splits, $0; (2) the memo, then
registration, which opens Programme 6 and spends a counter, then "run it"; (3) whether the agents' forward diary
starts, and on what engine — a scheduled routine in Claude Code on the owner's plan, or the Anthropic API at a cost
to be priced first.
