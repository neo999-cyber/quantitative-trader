# Programme 5 — foundation-model forecasting (opened 2 November 2026)

## 1. What it is

The owner's input of 2 November 2026: Google Research's TimesFM-3, released 31 August 2026 — "a lot of
investors seem to be using this; I want to use them here." One registered question: does a zero-shot
foundation model that takes **past covariates natively** forecast what Programme 3's P3-C
(`p3_forecastability_v1`, seq 935, run 938) found nothing could — the direction, the 7-day return and the
next day's variance of BTCUSDT — against P3-C's own bars? The targets, the 43 inputs, the sample, the
protocol, the controls and the bars are P3-C's by reference (`docs/prereg/p3_forecastability_v1.md`), so
the two results read side by side. Programmes 1–4 are twenty-eight pre-registered rules and no pass; this one
changes the model class, not the question.

## 2. The counter — one registered

| hypothesis | seq | status |
|---|---|---|
| `p5_forecastability_tsfm_v1` — three zero-shot TimesFM arms on P3-C's three targets | 1052 | **registered 2 November 2026** on the owner's "download and register it"; weights downloaded and pinned (note 1051); run script built on fixtures; **not run** — the run needs the owner's "run it" |

The document is stamped in the hash chain (`qr trial verify` walks it and checks the file against its stamp);
a change to it is an amendment file, never an edit.

## 3. The facts that shaped the memo (read before drafting; `docs/prereg/p5_forecastability_tsfm_v1.md`)

- **The licence decides what a pass could be used for.** TimesFM-3's weights are under the *TimesFM
  Non-Commercial License v1.0*: research and evaluation only, results "not used in commercial decisions",
  no "revenue-generating activity". Trading one's own money on its forecast is such a decision, so a pass on a
  TimesFM-3 arm is a research finding and cannot be traded on downloaded weights; the commercial routes are
  Google Cloud's metered BigQuery `AI.FORECAST` or a licence from Google. TimesFM-2.5's weights are
  Apache-2.0 (univariate), so the money test runs on that arm alone. The code (`timesfm` 3.0.2) is Apache-2.0.
- **Pretraining overlap.** The corpus (`Salesforce/GiftEvalPretrain` plus Wikipedia pageviews to November
  2023, Google Trends to end-2022 and synthetic series) contains the Monash `bitcoin_with_missing` set — daily
  bitcoin series, the price among them, ending in 2021. The test window begins January 2023; the memo's leak
  rule makes that a condition and names the amendment if a later corpus check finds a crypto series past
  2022-12-31.
- **The public record.** TimesFM-2.5 beats a random walk on daily US-stock returns only rarely in a 2026
  rolling-origin study; the original TimesFM earned a negative net return on daily crypto in a fine-tuning
  paper's baseline; no study tests TimesFM-3 on returns yet. P3-C scored a zero-shot foundation model
  (Chronos-Bolt) at the base rate on the same targets. The honest expectation is the same result.
- **The one new claim**: the covariate arm. If it does not beat the univariate TimesFM-3 arm, the claim that
  covariates help is false even if both pass on their own.

## 4. Build log

**2 November 2026.** In this order:

1. **The code, on fixtures, before any download** (commit `ab14a3e`): `qr/research/tsfm.py` — the
   `timesfm3`, `timesfm3_cov` and `timesfm25` arms behind the engine's `forecast(history, steps[, covariates])`
   interface, the last 1,024 days of context, nothing downloaded until an arm is constructed, weights routed to
   `~/qr/models/hf` through `HF_HOME`; the engine's zero-shot branch (`qr/research/forecast.py`,
   `walk_forward(..., arm=)`) generalised to pass the features known at the forecast day as past covariates of
   shape (k, len(history)), P3-C's `MODELS` and path untouched; fixture tests (`tests/qr_platform/test_tsfm.py`):
   the window, the shapes, the covariate alignment, no row after *t*, the Chronos path unchanged.
2. **On the owner's yes ("ok download and register it"):** `timesfm[mlx,torch]==3.0.2` into the venv (adds
   `mlx` 0.32.4 and `mlx-metal` 0.32.4; torch was already 2.14.1); both checkpoints **pinned to the commits the
   hub served that morning** — `google/timesfm-3.0-pytorch` at `43046b85ec22d584a13f8098c2ed39c889e129c2`
   (2 September 2026) and `google/timesfm-2.5-200m-pytorch` at `1d952420fba87f3c6dee4f240de0f1a0fbc790e3`
   (2 October 2025) — so every run reads the same bytes whatever `main` later points at; the weights
   (safetensors only, no pickle) downloaded into `~/qr/models/hf/hub`: `google/timesfm-3.0-pytorch` `model.safetensors` 1,322,898,824 bytes (SHA-256
   `a7592b0a8432baee54483254e5647856911ce69e09d09a9bb65904b2d98f17da`), `google/timesfm-2.5-200m-pytorch`
   925,181,104 bytes (`2f776efe6245e42b24bc4153ffdf61810140210e4bd3b01fb21f7aa779ab6ce8`); 2.1 GB on disk, deletable;
   the record is `reports/p5/tsfm_download_record_2026-11-02.json`.
   A smoke test on a **synthetic** random-walk series with 43 synthetic covariates — shapes, finite values,
   timing — touched no series of ours: shapes right, values finite; 35 ms a forecast (`timesfm3`, MLX), 663 ms
   (`timesfm3_cov`, MLX — 44 variates through the variate attention), 279 ms (`timesfm25`, PyTorch on the
   CPU; its code has no MLX port). Recorded as a trial-log note (seq 1051), uncounted.
3. **Registration**: `qr trial prereg p5_forecastability_tsfm_v1 --file docs/prereg/p5_forecastability_tsfm_v1.md`
   → seq 1052, after the download facts and the measured timing were written into the draft and before
   any model saw a series of ours.
4. **The run script**, `scripts/p5_tsfm_forecast.py`, built before registration on fixtures and modelled on
   `scripts/p3c_forecast.py`: the two TimesFM-3 arms share one loaded model; P3-C's scorers, permuted-target and
   extra-lag controls on every pair; the money test only on a `timesfm25` pair above its statistical bar (the
   licence rule), P3-C's `money_test` imported unchanged; the covariate-beats-univariate check in the verdict;
   the arms' checkpoint, revision, backend and licence in the summary and in the trial-log record; outputs
   `reports/p5/p5_<sample>_{summary.json,forecasts.parquet,report.md}`. Two tests on its seams. It reads the
   lake only when run.

## 5. What a result means

A `timesfm25` pair above its bar **and** through the money test (net Sharpe ≥ 1.0, alpha t ≥ 2 against cash,
DSR ≥ 0.90) goes to the owner as a candidate under the standing sleeve rule (`docs/35` §6: a first gate pass
sends the $200 sleeve forward for a month at the stage-1 size). A TimesFM-3 pair above its bar is reported as a
research finding with no money test; the memo states what acting on it would take (BigQuery's metered
TimesFM, costed against the sleeve, a separate decision of the owner's). A fail closes the question for this
model class as P3-C closed it for Chronos; the holdout stays shut.

## 6. What runs on the owner's word

Once, in-sample:

    QR_ROOT=~/qr/lake .venv/bin/python scripts/p5_tsfm_forecast.py

One trial-log record, `variants = 9`; the holdout (`--holdout`) opens once and only after an in-sample pass.
Compute: about 11,200 primary forecasts (nine pairs × about 1,247 test days) and twice that again for the two
controls — about three hours on the laptop at the measured speeds, two of them the covariate arm.

## 7. The rules, unchanged

Nothing runs, is registered or spends without the owner's yes; the owner moves money, never the code; Claude
never places, closes or starts live orders and never handles key values; every engine run is counted in the
trial log and never registered after; the holdout opens once. TimesFM-3's outputs may be scored here and may
not drive a trade.
