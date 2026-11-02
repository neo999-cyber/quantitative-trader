"""Zero-shot TimesFM arms for the forecastability engine (`qr.research.forecast.walk_forward`).

Built 2 November 2026 for a draft memo (`docs/prereg/p5_forecastability_tsfm_v1.md`), not registered. Nothing here
downloads anything until an arm is constructed; the tests use stand-ins. Weights, when the owner says yes, land under
`~/qr/models/hf` (HF_HOME, unless already set) so they are one folder, deletable, and apart from any other cache.

Two models, two licences — the distinction decides what a pass could be used for:

- **TimesFM-3** (`google/timesfm-3.0-pytorch`, 330 M parameters, 9 quantiles, past covariates): the weights are under
  the *TimesFM Non-Commercial License v1.0*: testing, evaluation and research only, results "not used in commercial
  decisions", no "revenue-generating activity". Its outputs may be scored here; they may not drive a trade.
- **TimesFM-2.5** (`google/timesfm-2.5-200m-pytorch`, 200 M, univariate, Apache-2.0): the arm whose forecast could
  be acted on.

The arm interface is the engine's: `forecast(history, steps)` returns the median path (`steps` values); an arm with
`uses_covariates = True` also takes `covariates` of shape (k, len(history)), aligned on the same days and ending on
the forecast day. Both are truncated to the last `context` points before the model sees them.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

TIMESFM3_CHECKPOINT = "google/timesfm-3.0-pytorch"
TIMESFM25_CHECKPOINT = "google/timesfm-2.5-200m-pytorch"
#: The Hugging Face commits the weights are pinned to (read from the hub API on 2 November 2026, before the
#: download): the same bytes on every run, whatever the repo's `main` later points at.
TIMESFM3_REVISION = "43046b85ec22d584a13f8098c2ed39c889e129c2"      # 2 September 2026; model.safetensors 1,322,898,824 bytes
TIMESFM25_REVISION = "1d952420fba87f3c6dee4f240de0f1a0fbc790e3"     # 2 October 2025; model.safetensors 925,181,104 bytes
TIMESFM3_LICENCE = ("TimesFM Non-Commercial License v1.0: research and evaluation only; outputs may not be used in "
                    "commercial decisions or any revenue-generating activity. Commercial use needs Google Cloud "
                    "(BigQuery AI.FORECAST) or a licence from Google.")
DEFAULT_CONTEXT = 1024
MODELS_DIR = Path.home() / "qr" / "models" / "hf"


def _models_home() -> None:
    os.environ.setdefault("HF_HOME", str(MODELS_DIR))


def _window(history: np.ndarray, covariates: np.ndarray | None, context: int) -> tuple[np.ndarray, np.ndarray | None]:
    """The last `context` points of the history and, when given, of the covariates (k, L) — same L, same end."""
    h = np.asarray(history, dtype=np.float32).reshape(-1)
    if covariates is not None:
        c = np.asarray(covariates, dtype=np.float32)
        c = np.atleast_2d(c)
        if c.shape[1] != h.shape[0]:
            raise ValueError(f"covariates must have one column per history point: {c.shape} vs {h.shape}")
        c = c[:, -context:]
        c = np.where(np.isfinite(c), c, 0.0)
    else:
        c = None
    return h[-context:], c


class TimesFM3Arm:
    """Zero-shot TimesFM-3 on the target's own history; with `covariates=True`, the memo's features as past covariates.

    `backend` is "auto" (MLX on Apple silicon when importable, else PyTorch on the CPU or the device given), "mlx" or
    "torch". The research licence is recorded on the instance as `licence`.
    """

    def __init__(self, checkpoint: str = TIMESFM3_CHECKPOINT, context: int = DEFAULT_CONTEXT, covariates: bool = False,
                 backend: str = "auto", device: str | None = None, forecaster=None, revision: str | None = TIMESFM3_REVISION):
        self.context = int(context)
        self.uses_covariates = bool(covariates)
        self.checkpoint = checkpoint
        self.revision = revision
        self.licence = TIMESFM3_LICENCE
        self.backend = backend
        if forecaster is not None:                      # a stand-in, for tests
            self.model = forecaster
            return
        _models_home()
        if backend in ("auto", "mlx"):
            try:
                from timesfm3.mlx import TimesFM3Forecaster  # type: ignore
                self.model = TimesFM3Forecaster.from_pretrained(checkpoint, revision=revision)
                self.backend = "mlx"
                return
            except ImportError:
                if backend == "mlx":
                    raise
        from timesfm3 import TimesFM3Forecaster  # type: ignore
        self.model = TimesFM3Forecaster.from_pretrained(checkpoint, device=device or "cpu", revision=revision)
        self.backend = "torch"

    def forecast(self, history: np.ndarray, steps: int, covariates: np.ndarray | None = None) -> np.ndarray:
        h, c = _window(history, covariates if self.uses_covariates else None, self.context)
        kw = {"contexts": [h], "horizon": int(steps), "return_quantiles": False}
        if c is not None:
            kw["past_only_covariates"] = [c]
        out = next(iter(self.model.predict_batch(**kw)))
        path = np.asarray(out.forecast, dtype=float).reshape(-1)
        return path[: int(steps)]


class TimesFM25Arm:
    """Zero-shot TimesFM-2.5 (Apache-2.0) on the target's own history, univariate, the median path."""

    uses_covariates = False

    def __init__(self, checkpoint: str = TIMESFM25_CHECKPOINT, context: int = DEFAULT_CONTEXT, model=None,
                 revision: str | None = TIMESFM25_REVISION):
        self.context = int(context)
        self.checkpoint = checkpoint
        self.revision = revision
        if model is not None:                           # a stand-in, for tests
            self.model = model
            return
        _models_home()
        import timesfm  # type: ignore
        self.model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(checkpoint, revision=revision)
        # returns are signed: `infer_is_positive` stays off (the model card's example turns it on for demand series)
        self.model.compile(timesfm.ForecastConfig(max_context=self.context, max_horizon=256, normalize_inputs=True,
                                                  use_continuous_quantile_head=True, force_flip_invariance=True,
                                                  infer_is_positive=False, fix_quantile_crossing=True))

    def forecast(self, history: np.ndarray, steps: int) -> np.ndarray:
        h, _ = _window(history, None, self.context)
        point, _quantiles = self.model.forecast(horizon=int(steps), inputs=[h])
        return np.asarray(point, dtype=float).reshape(-1)[: int(steps)]


def make_arm(name: str, **kw):
    """The arm for a `TSFM_MODELS` name: `timesfm3`, `timesfm3_cov` or `timesfm25`."""
    if name == "timesfm3":
        return TimesFM3Arm(covariates=False, **kw)
    if name == "timesfm3_cov":
        return TimesFM3Arm(covariates=True, **kw)
    if name == "timesfm25":
        return TimesFM25Arm(**kw)
    raise ValueError(name)
