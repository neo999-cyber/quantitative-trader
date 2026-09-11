# Day 4–5: four families through nine gates

Built on branch `claude/admiring-ptolemy-tfp528`. 327 tests.

> ## ⚠️ Everything below is a **dry run on synthetic data**
>
> The Binance bucket has still not been pulled, so the four families were run against geometric random walks generated in the bucket's exact format. **These results say nothing whatsoever about crypto markets.** They say the pipeline works end to end: fifteen symbols, seven years, 425 variants, nine gates, four Hypothesis Reports, one verifiable trial log.
>
> The real verdict needs `qr data pull` on your laptop (`docs/02_DATA_LAYER.md`).

## The four families

| Hypothesis | Family | Variants | Swept | Pre-registration |
|---|---|---|---|---|
| `tsmom_v1` | Time-series momentum, vol-targeted | 200 | lookback, skip | [`docs/prereg/tsmom_v1.md`](prereg/tsmom_v1.md) |
| `xsmom_v1` | Cross-sectional momentum, 12-1 | 144 | lookback, skip, n_long, rebalance | [`docs/prereg/xsmom_v1.md`](prereg/xsmom_v1.md) |
| `reversal_v1` | Weekly short-term reversal | 54 | lookback, n_long, rebalance | [`docs/prereg/reversal_v1.md`](prereg/reversal_v1.md) |
| `rsi_reversal_v1` | 3-down-day RSI setup — **the control** | 27 | down_days, rsi_max, hold | [`docs/prereg/rsi_reversal_v1.md`](prereg/rsi_reversal_v1.md) |

Each pre-registration states a mechanism, a predicted **sign and size**, the universe, the horizon, the swept ranges, the frozen cost model, the holdout, what would falsify it, and a prior — so that a pass is surprising rather than retrospectively obvious.

The grid in `qr/research/families.py` **is** the grid each document declares, and a test parses the variant count out of the Markdown and checks it matches. A range quietly widened in code after the prediction was registered is the most comfortable form of p-hacking there is, because nothing looks wrong at any single step.

The control is `centaur/screens/pattern_matcher.py`'s `SetupSpec`, ported unchanged and verified bit-for-bit against the original — Wilder RSI and relative volume checked column by column too. A control that is not the setup it claims to be proves nothing.

## Running it

```bash
for h in tsmom_v1 xsmom_v1 reversal_v1 rsi_reversal_v1; do
  qr trial prereg $h --file docs/prereg/$h.md
done

qr families --n 30 --min-history 180 \
            --start 2018-01-01 --end 2023-12-31 \
            --holdout-start 2024-01-01 --holdout-end 2024-12-31
```

`qr families` refuses to run an unregistered hypothesis. The four Hypothesis Reports land in `$QR_ROOT/reports/`.

## The dry run (synthetic data — not a market result)

| hypothesis | control | variants | verdict | stopped at | best Sharpe | net/gross | round trips |
|---|---|---|---|---|---|---|---|
| tsmom_v1 | | 200 | FAIL | gate 9 | 1.77 | 0.91 | 563 |
| xsmom_v1 | | 144 | FAIL | gate 8 | 1.65 | 0.97 | 94 |
| reversal_v1 | | 54 | FAIL | gate 8 | 1.46 | 0.93 | 474 |
| rsi_reversal_v1 | yes | 27 | FAIL | gate 3 | 0.76 | 0.89 | 108 |

All four fail, which is the correct answer for random walks. Two of the failures are worth looking at because they show the machinery doing its job:

**`tsmom_v1` passed gates 0–7 and died at the holdout.** In-sample Sharpe 1.77, deflated Sharpe 0.996 over 200 trials, permutation p = 0.010, 90% of CPCV paths retained — everything an enthusiastic backtester would want. Holdout Sharpe: **−1.05**. Nothing before gate 9 caught it, which is precisely why a physically withheld period is not optional.

**`xsmom_v1` and `reversal_v1` died at gate 8 on beta**: alpha t of 1.38 and 0.67 against betas of 0.62 and 0.61 to the equal-weighted panel. On synthetic data with a common drift that is the correct diagnosis — all the return is the drift. This is the failure mode the `tsmom_v1` pre-registration predicts as most likely on real data too.

## A pre-registered prediction of mine that was falsified

The control's pre-registration makes a specific claim about *how* it would fail:

> It will fail gate 8 on trade count, not on return. On 900 bars of random walk the three-down-days-on-volume condition fires 19 times and RSI < 30 fires 32 times, and they coincide **zero** times.

The per-symbol arithmetic is right; the inference from it was wrong. Across fifteen symbols and seven years there are ~32,000 symbol-bars, and a conjunction that never occurs in 900 of them occurs **108 times** in 32,000. The control failed at gate 3 on significance (HAC t = 1.74), not at gate 8 on trade count.

Recording this rather than editing the document, for two reasons. The document is hash-stamped in the trial log, so an edit would break its chain and be visible anyway — that is the mechanism working. And a pre-registration whose wrong predictions get quietly corrected is not a pre-registration. The prediction that *mattered* — no edge after costs — held.

The control failed gates 3, 4, 5, 6, 7 and 8. It passed gate 9 on the holdout, which on 27 variants of a rarely-firing setup is a coin landing heads.

## Two things the dry run found

**A family that never trades crashed the report.** `Sweep.best()` reached for `idxmax` over an all-NaN column and raised an opaque pandas error, so no report was written at all — hiding exactly the outcome the control's pre-registration predicted. "It never fired" is a finding; gate 8 now states it in one line, and `best()` degrades to the first variant so the gates get to speak.

**Gate 8 was counting the wrong parameters.** It counted constructor arguments, so a strategy carrying two fixed implementation knobs failed the five-parameter limit while a two-argument strategy swept over ten thousand combinations passed. It now counts what the sweep actually varied, read from the sweep itself.

## What this does and does not establish

**Does:** the pipeline runs four families end to end, under pre-registration, with a verifiable trial log, a frozen and verified cost model, a physically withheld holdout, and four Hypothesis Reports. The self-test (`qr selftest`) still passes.

**Does not:** anything about crypto. Every number above is from a random-number generator.

## Next

`qr data pull` on the laptop, then re-run `qr families` against the real lake. Day 6–7 is reading the four reports and fixing what they expose.
