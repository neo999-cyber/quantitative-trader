# Pre-registration: `p3_forecastability_v1` — can anything we can observe forecast Bitcoin?

*Drafted 1 October 2026 on the owner's decision to spend Programme 3's
third and last registration on this question, and **registered the same
day on the owner's yes** to this text (and to the foundation-model arm's
download), through `qr trial prereg --file`, before any model was fitted. What was looked at before drafting: which inputs exist
and from when (coverage dates only). No target was computed and no input
was plotted against a return.*

## The question, stated so it can fail

The owner's question: "we have ten years of everything — why can't we
calculate what the fluctuations will be, the way weather is forecast?"
This memo makes that a test. If the strongest standard forecasters,
fed every point-in-time input this project can obtain for free, cannot
beat the no-information benchmarks out of sample after the search is paid
for, then the answer is "because the information is already in the
price", measured, and the project stops asking. If something beats the
benchmarks, that is the finding of the programme and gets its own family.

## Targets (frozen)

For BTCUSDT (Binance USDⓈ-M perpetual daily bars, 00:00 UTC), three
targets, each decided at the close of day *t* for the future only:

1. **Direction, 1 day**: sign of the next day's close-to-close return.
2. **Return, 7 days**: the next 7 days' log return (overlapping; the
   statistics use HAC with 7 lags).
3. **Volatility, 1 day**: the next day's realised variance from the hourly
   bars (24 squared hourly log returns), in log.

## Inputs (frozen; all point-in-time; all $0)

Every feature is computed from data available at the close of day *t*;
calendar-day lags are explicit; nothing is revised after the fact.

| Group | Series | Source | From |
|---|---|---|---|
| Price | log returns 1/2/3/5/10/21/63 d; realised vol 5/21/63 d; distance from 21/63/252-d highs; day-of-week | lake (perp daily, hourly) | 2020-01 |
| Derivatives | funding rate (last, 3-d, 7-d mean), open interest (level, 1/7-d change) | lake (perp daily) | 2020-09 |
| Options | DVOL close, its 1/7-d change, DVOL − 21-d realised vol | lake (`reference/dvol_BTC`) | 2021-03 |
| Sentiment | Fear & Greed index (level, 7-d change) | alternative.me, mirrored | 2018-02 |
| Stablecoins | total USD-pegged supply (DefiLlama), 7/30-d change | `stablecoins.llama.fi`, mirrored | 2017-11 |
| On-chain | hash rate, active addresses, transaction count (7/30-d changes) | `api.blockchain.info/charts`, mirrored | 2009 |
| Macro | DXY (DTWEXBGS), 10-y yield (DGS10), 3-m bill (DTB3): levels and 5-d changes, lagged one day for publication | FRED, mirrored | 2006 |

Excluded, and why: ETF flows (recorded only since September 2026),
liquidations (two weeks), Google Trends (revised and renormalised after
the fact, not point-in-time), any paid feed, and any LLM-derived
feature (not point-in-time).

**Sample**: 2021-03-24 (DVOL's first day) → 2026-05-31 in-sample;
**holdout 2026-06-01 → 2026-09-30**, opened once after the in-sample
verdict, only if the in-sample passes anything. About 1,900 days.

## Models (frozen)

Three model families per target, nine (target, model) pairs:

- **Floor**: ridge regression / regularised logistic regression on the
  standardised inputs (λ by inner cross-validation).
- **Workhorse**: gradient-boosted trees (`sklearn.HistGradientBoosting*`,
  depth ≤ 4, ≤ 300 trees, learning rate 0.05, early stopping on the inner
  fold; no other tuning).
- **Foundation model**: a zero-shot time-series foundation model on the
  target's own history (Chronos-Bolt-small). *It needs `torch` and
  `chronos-forecasting` installed and ~200 MB of weights downloaded from
  Hugging Face — ~2.3 GB in total. That download needs the owner's yes
  before registration; if declined, this arm is dropped and the count is
  six pairs, stated here now.*

The benchmarks, per target: direction → the in-sample base rate (BTC
rises on about 53% of days; a coin flip is the wrong null); 7-day return
→ zero (the random walk); volatility → **DVOL** converted to a daily
variance, and GARCH(1,1) fitted past-only (`arch`).

## Protocol (frozen)

Expanding-window walk-forward: fit on everything up to the end of year
*y* − 1 (first fit: 2021-03 → 2022-12), forecast year *y* day by day
with monthly refits, purge of 7 days before each test block (the 7-day
target), no feature selection anywhere, seeds fixed (20261001). Every
(target, model) pair is one variant; the nine are the search.

## Metrics and bars (frozen)

- **Direction**: out-of-sample accuracy and Brier skill against the base
  rate; passes if accuracy exceeds the base rate with HAC **t ≥ 3**.
- **7-day return**: out-of-sample R² against zero, Diebold–Mariano test
  against the random walk; passes if R² > 0 with **t ≥ 3**.
- **Volatility**: QLIKE loss against DVOL and against GARCH; passes if the
  model beats **DVOL** with Diebold–Mariano **t ≥ 3** (beating GARCH alone
  is reported, not a pass: the options market is the bar).
- **The money test**, for any pair that passes: a strategy that takes the
  forecast — long/short the perp on the direction or 7-day sign, scaled
  to 20% target vol by the vol forecast — run through the ledger engine
  with `--costs perp`, against cash, gates 1–8, DSR over 9. Passes only if
  net Sharpe ≥ 1.0, alpha t ≥ 2, DSR ≥ 0.90.

## What would falsify this

- No (target, model) pair clears its statistical bar out of sample.
- A pair clears the bar but the money test fails (an edge the account
  cannot carry through costs is recorded as such, not passed).
- The holdout reverses an in-sample pass.

## Controls

- **Shuffled targets**: the same pipeline with the target series
  permuted within years; the nine "skills" it produces are the null
  distribution against which any pass is also read.
- **Lagged leak check**: every input is shifted one extra day; a pass that
  disappears is a timestamp leak, not a forecast.

## Prior

The literature on this is one-sided: daily direction is not forecastable
beyond the base rate once costs and multiple testing are counted;
volatility is forecastable, and the options market already forecasts it
better than the standard models. Honest expectation: direction fails,
the 7-day return fails, the volatility model beats GARCH and does not beat
DVOL. That would be the third time this project finds that the market's
own number is the best one available — and it would close the question
with a measured answer instead of an argument.

## Engine

`scripts/p3c_forecast.py` (to build after registration): loaders for the
three new mirrors (`qr/data/{stablecoins,onchain,feargreed}.py` — the
Fear & Greed loader exists), the feature table, the walk-forward, the
metrics, the controls, the money test through the ledger, and the
trial-log record with `variants=9` (or 6).
