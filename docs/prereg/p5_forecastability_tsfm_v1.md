# Pre-registration: `p5_forecastability_tsfm_v1` — does a multivariate foundation model forecast what nothing else did?

*Drafted 2 November 2026 on the owner's input ("a lot of investors seem to be
using this; I want to use them here", the TimesFM-3 release of 31 August
2026), and **registered the same day on the owner's yes** ("ok download and
register it") to the weight downloads and to this text, through `qr trial
prereg --file`, after the weights were downloaded, pinned and smoke-tested on
a synthetic series and before any model saw a series of ours. Registering it
opens Programme 5 and spends its first counter; the run needs the owner's
separate "run it". What was looked at before drafting: the model cards, the
licence text, the pretraining-corpus file list, the package source, and this
project's own P3-C result. No target was computed and no model has touched
any series of ours.*

## Why this is a new test and not a re-run

`p3_forecastability_v1` (seq 935, run 938, 1 October 2026) answered the
forecastability question for three model families, one of them a zero-shot
foundation model (Chronos-Bolt-small on the target's own history): direction
48.6% against a 49.2% base rate, 7-day return R² −0.01, variance equal to
DVOL. TimesFM-3 changes one thing that memo could not test: it takes
**past covariates natively**, so the 43 point-in-time inputs that the tree
model used can be given to a foundation model in one call. That is the
only new claim here. Everything else — targets, inputs, sample, protocol,
bars, controls — is P3-C's, frozen, so the two results read side by side.

## What the public record already says (read before drafting)

- TimesFM-2.5 beat a random walk on daily US-stock returns only rarely in a
  2026 rolling-origin study; the original TimesFM earned a negative net
  return on daily crypto in a fine-tuning paper's baseline. No study tests
  TimesFM-3 on returns yet.
- The pretraining corpus (`Salesforce/GiftEvalPretrain`, plus Wikipedia
  pageviews to November 2023, Google Trends to end-2022, synthetic series)
  **contains the Monash `bitcoin_with_missing` dataset** — 18 daily bitcoin
  series including the price, ending in 2021 — and `fred_md` (US macro,
  monthly). So the model has seen bitcoin's daily price up to 2021. The
  test months start in January 2023; the leak rule below makes that a
  condition, not a coincidence.
- The honest expectation, as for P3-C: direction and the 7-day return at the
  base rate; variance beats GARCH and does not beat DVOL.

## The licence, which decides what a pass could be used for

- **TimesFM-3 weights**: *TimesFM Non-Commercial License v1.0*. Permitted:
  "testing, evaluation, or research not tied to commercial gain, production
  deployment, or revenue generation", with results "not used in commercial
  decisions". Excluded: "any revenue-generating activity". Trading one's
  own money on its forecast is a revenue-generating decision. **A pass on
  a TimesFM-3 arm is a research finding and cannot be traded on these
  weights.** Commercial use exists only through Google Cloud (BigQuery
  `AI.FORECAST`, metered) or a licence from Google at its discretion.
- **TimesFM-2.5 weights**: Apache-2.0. Univariate. **The only arm whose
  forecast could be acted on**, so the money test runs on it alone.
- The code (`timesfm` 3.0.2, PyPI) is Apache-2.0.

## Targets, inputs, sample, protocol, metrics, bars (frozen — P3-C's, by reference)

Identical to `docs/prereg/p3_forecastability_v1.md` §Targets, §Inputs,
§Sample, §Protocol, §Metrics: the three BTCUSDT targets (direction 1 d,
return 7 d, log realised variance 1 d), the 43 inputs, test months
2023-01 → 2026-05 in-sample with the 7-day purge and monthly refits,
holdout 2026-06 → 2026-09 opened once only after an in-sample pass, the
bars (direction: accuracy above the base rate at HAC t ≥ 3; 7-day: R² > 0
at DM t ≥ 3; variance: beats **DVOL** at DM t ≥ 3), the permuted-target
and extra-lag controls on every pair, DSR over the variants.

## Models (frozen)

Three zero-shot arms, nine (target, model) pairs, no fitting anywhere:

| Arm | Model | Input | Context | Licence |
|---|---|---|---|---|
| `timesfm3` | google/timesfm-3.0-pytorch, 330 M | the target's own known history | last 1,024 days | non-commercial |
| `timesfm3_cov` | the same | the history **plus the 43 inputs as past-only covariates**, aligned day for day and ending on the forecast day | last 1,024 days | non-commercial |
| `timesfm25` | google/timesfm-2.5-200m-pytorch, 200 M | the target's own known history | last 1,024 days | Apache-2.0 |

The forecast used is the median path; a direction forecast is the 1-step
return passed through P3-C's monotone map; the 7-day return is the sum of
the 7-step path; the variance target is forecast in log as in P3-C.
`infer_is_positive` is off (returns are signed). Backend, as installed: the
TimesFM-3 arms on MLX (Apple silicon), the TimesFM-2.5 arm on PyTorch on the
CPU (its code has no MLX port); the backend is recorded in the run's summary
and the arms' checkpoint, commit and licence with it. The same weights on
either backend differ at floating-point rounding, not at the level of any
bar.

## Weights, pinned

Both checkpoints are read at the Hugging Face commits the hub served on the
morning of 2 November 2026, before the download, so every run uses the same
bytes whatever the repos' `main` later points at (`TIMESFM3_REVISION` and
`TIMESFM25_REVISION` in `qr/research/tsfm.py`; the arms pass `revision=` to
the loaders). Safetensors only, no pickled weights; `timesfm` 3.0.2 with
`mlx` 0.32.4 and `torch` 2.14.1; on disk under `~/qr/models/hf/hub`, 2.1 GB,
deletable.

| checkpoint | commit | `model.safetensors` | SHA-256 |
|---|---|---|---|
| `google/timesfm-3.0-pytorch` | `43046b85ec22d584a13f8098c2ed39c889e129c2` (2 September 2026) | 1,322,898,824 bytes | `a7592b0a8432baee54483254e5647856911ce69e09d09a9bb65904b2d98f17da` |
| `google/timesfm-2.5-200m-pytorch` | `1d952420fba87f3c6dee4f240de0f1a0fbc790e3` (2 October 2025) | 925,181,104 bytes | `2f776efe6245e42b24bc4153ffdf61810140210e4bd3b01fb21f7aa779ab6ce8` |

## Leak rule (frozen)

1. The history an arm sees ends at the close of day *t* and contains no
   value dated after *t* (P3-C's rule; the test that caught run 936 stays).
2. Covariates given to `timesfm3_cov` are the lagged feature rows up to and
   including day *t*, never a later row — enforced in `walk_forward` and by
   `tests/qr_platform/test_tsfm.py`.
3. **Pretraining overlap**: the test window must begin after the last date
   of any financial series in the pretraining corpus. The Monash bitcoin set
   ends in 2021; test months begin 2023-01. If a later check of the corpus
   finds a bitcoin or crypto series extending past 2022-12-31, the test
   window moves to start after it and the memo is amended before any run.
4. Indirect overlap (macro series the model saw, shared shocks) is
   acknowledged and not correctable; it biases toward a pass, which is the
   conservative direction for a kill test.

## The money test (frozen)

Only on `timesfm25` pairs that pass their statistical bar (the licence rule
above): P3-C's strategy and gates through the ledger engine, perp costs,
cash benchmark; passes only if net Sharpe ≥ 1.0, alpha t ≥ 2, DSR ≥ 0.90.
A TimesFM-3 pair that passes its bar is **reported as a research finding
with no money test**, and the memo states now what it would take to act on
it: BigQuery's metered TimesFM, costed against the sleeve, as a separate
decision.

## What would falsify this

Every pair below its bar; or the permuted-target control matching the real
one; or the extra-lag control not degrading a passing pair; or the
covariate arm not beating the univariate TimesFM-3 arm (then the one new
claim — covariates help — is false even if both pass on their own); or a
`timesfm25` pass that fails the money test.

## Counting, cost, what the owner is asked

One run, `variants = 9`, one trial-log record; the controls are not extra
variants (same as P3-C). Downloads, done: TimesFM-3 1.32 GB and TimesFM-2.5
0.93 GB into `~/qr/models/hf`, deletable. Compute: about 11,200 primary
forecasts (nine pairs × about 1,247 test days) and twice that again for the
two controls; measured on the synthetic smoke test at 35 ms a forecast
(`timesfm3`, MLX), 663 ms (`timesfm3_cov`, MLX — 44 variates through the
variate attention) and 279 ms (`timesfm25`, PyTorch CPU): about three hours
on the laptop in all. $0 otherwise. The owner was asked three separate
things, in this order: (1) the downloads — yes, done; (2) registration of
this text, which opens Programme 5 — yes, this stamp; (3) "run it" — still
the owner's, not given at registration.
