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

## 2. The counter — one registered, one run, one fail

| hypothesis | seq | status |
|---|---|---|
| `p5_forecastability_tsfm_v1` — three zero-shot TimesFM arms on P3-C's three targets | 1052 | registered 2 November 2026 on the owner's "download and register it" (weights pinned and downloaded, note 1051); **ran once the same evening on the owner's "ok run it" — run seq 1053, note 1054 — and FAILED in-sample** (§5): nine of nine pairs below their bars, the covariate arm no better than the univariate one on any target, no `timesfm25` pair at its bar so no money test; holdout shut |

**Programme 5: one of one run, one fail — closed unless a new input arrives.**

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
5. **Checkpointing** (commit `a64a3d7`), before the counted run: each walk-forward pass is saved under the
   lake's `reports/p5/cache/` (27 files for a full run) and a rerun of the same command resumes from it, so a
   sleeping laptop or a crash costs nothing already forecast; a heartbeat in the log; rehearsed end to end on
   fixtures with stand-in arms, including the forced money-test path and the resume.
6. **A false start** (19:47, nothing counted): the start-of-run print raised `AttributeError` on the
   TimesFM-2.5 arm's `backend` attribute before any forecast, any GARCH fit or any cache write. The rehearsal's
   stand-in arms all carried `backend`, which masked the real class's missing attribute. Fix (commit
   `413736e`): the attribute on the class, the print tolerant of its absence, and the rehearsal turned into a
   test that drives the script through the real arm classes on stand-in models
   (`tests/qr_platform/test_p5_script.py`). The log is kept as `reports/p5/p5_insample_falsestart_2026-11-02.log`.
7. **The run**, 19:49:50 → 23:32:32 local on the owner's "ok run it": §5.
8. After the run: the heartbeat's "ms each" was wall-clock since the arm's wrapper was built divided by its
   count — right for the first arm's first pair, misleading after (the log's later figures include the other
   arms' time). It now times the calls themselves. Cosmetic; nothing scored reads it.

## 5. The result — ran once, FAILED (2 November 2026, run seq 1053)

**One counted run, in-sample 2023-01-01 → 2026-05-31, 1,227 test days, 33,111 forecasts in 3 h 43 min**
(nine pairs × three passes × 1,227 days, less six on the permuted 7-day control; TimesFM-3 on MLX, TimesFM-2.5
on PyTorch on the CPU; both checkpoints at the pinned commits). `qr trial verify` after: 1,055 records, 2,600
trials, the documents match their stamps. Outputs, copied from the lake into the repo:
`reports/p5/p5_insample_{summary.json,report.md,forecasts.parquet,run.log}`.

| pair | score | permuted / extra-lag control | bar | P3-C's best on the target (run 938) |
|---|---|---|---|---|
| direction `timesfm3` | 49.4% vs base 49.2%, t 0.07; Brier skill −0.004 | 50.9% (t 0.80) / 49.9% (t 0.22) | > base at t ≥ 3 — **fail** | gbt 49.9%, t 0.39 |
| direction `timesfm3_cov` | 50.9%, t 0.90; Brier skill −0.005 | 51.7% (t 1.33) / 48.0% (t −0.74) | **fail** | |
| direction `timesfm25` | 47.8%, t −0.68; Brier skill −0.009 | 52.0% (t 1.44) / 51.7% (t 1.07) | **fail** | |
| ret7 `timesfm3` | R² −0.012, DM t −1.27 | −0.005 (−0.87) / −0.011 (−1.15) | R² > 0 at DM t ≥ 3 — **fail** | chronos −0.012, t −0.92 |
| ret7 `timesfm3_cov` | R² −0.040, DM t −2.61 | −0.028 (−3.37) / −0.042 (−2.76) | **fail** | |
| ret7 `timesfm25` | R² −0.010, DM t −0.60 | +0.003 (0.25) / −0.014 (−0.89) | **fail** | |
| logrv `timesfm3` | QLIKE 0.439 (DVOL 0.473, GARCH 0.525); DM t vs DVOL 0.79, vs GARCH 1.91 | 0.664 (−4.25) / 0.769 (−5.31) | beats DVOL at t ≥ 3 — **fail** | gbt 0.416, t 1.97 vs DVOL |
| logrv `timesfm3_cov` | 0.479; vs DVOL −0.15, vs GARCH 1.04 | 0.651 (−4.12) / 0.798 (−5.42) | **fail** | |
| logrv `timesfm25` | 0.448; vs DVOL 0.54, vs GARCH 1.61 | 0.668 (−4.20) / 0.777 (−5.62) | **fail** | |

What it says:

- **Direction and the 7-day return are at the base rate, as P3-C found.** Direction runs 47.8–50.9% against
  49.2% at |t| ≤ 0.9, and on every direction pair the permuted-target control scores at least as high as the
  real forecast — the memo's second falsifier, noise of the same size. The 7-day covariate arm is *worse* than a
  zero forecast (DM t −2.6) and its permuted control worse still.
- **Variance: beats GARCH, not DVOL — P3-C's finding verbatim.** All three arms beat GARCH at t 1.0–1.9 (below
  the bar) and none beats the implied vol (t −0.15 to 0.79). The univariate TimesFM-3 (0.439) sits between
  P3-C's GBT (0.416) and Chronos (0.477). The variance controls collapse (t −4 to −5.6), so the arms do read
  real persistence; the option market already prices it.
- **The one new claim — covariates help — is false on every target.** The covariate arm is worse on the 7-day
  return (−0.040 against −0.012) and on variance (0.479 against 0.439), and 1.5 points better on direction
  inside noise (t 0.9 against 0.07). The 43 inputs through the variate attention add noise, not signal.
- **Money test: none ran.** No `timesfm25` pair reached its bar. Nothing goes forward, the sleeve is unchanged,
  the holdout stays shut.
- **Compute, measured on the run** (from the pair timestamps, not the heartbeat): `timesfm3` 30–70 ms a
  forecast, `timesfm3_cov` 870–935 ms (the smoke test's 663 ms was optimistic by a third), `timesfm25`
  240–290 ms. $0.

What it closes: the question for this model class — a zero-shot foundation model, with or without the inputs,
on these targets — as P3-C closed it for Chronos and the fitted models. A new input would have to be a
different target or resolution with its own memo, or fine-tuning (permitted for 2.5 under Apache-2.0, research-only
for 3.0), each a new counter against a public record that is already negative. The weights (2.1 GB,
`~/qr/models/hf`) were **deleted on 3 November on the owner's word** ("delete it"; the owner ran the `rm`);
the pinned commits and SHA-256s above and in `reports/p5/tsfm_download_record_2026-11-02.json` re-fetch the same
bytes if a later memo ever needs them. The `timesfm` package stays in the venv; nothing imports it unless an arm is
built.

## 6. What a result would have meant

A `timesfm25` pair above its bar **and** through the money test (net Sharpe ≥ 1.0, alpha t ≥ 2 against cash,
DSR ≥ 0.90) would have gone to the owner as a candidate under the standing sleeve rule (`docs/35` §6: a first gate
pass sends the $200 sleeve forward for a month at the stage-1 size). A TimesFM-3 pair above its bar would have been
reported as a research finding with no money test; the memo states what acting on it would take (BigQuery's
metered TimesFM, costed against the sleeve, a separate decision of the owner's). The result was the third case:
a fail closes the question for this model class as P3-C closed it for Chronos; the holdout stays shut.

## 7. What ran on the owner's word

Once, in-sample, 2 November 2026 (run seq 1053, `variants = 9`):

    QR_ROOT=~/qr/lake .venv/bin/python scripts/p5_tsfm_forecast.py

Nothing further runs. The holdout (`--holdout`) would have opened once and only after an in-sample pass; it
did not.

## 8. The rules, unchanged

Nothing runs, is registered or spends without the owner's yes; the owner moves money, never the code; Claude
never places, closes or starts live orders and never handles key values; every engine run is counted in the
trial log and never registered after; the holdout opens once. TimesFM-3's outputs may be scored here and may
not drive a trade.
