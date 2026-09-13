"""Gate 5: Combinatorially Symmetric Cross-Validation and the Probability of
Backtest Overfitting.

Bailey, Borwein, López de Prado and Zhu's construction, and the single most
useful test in the whole pipeline, because it measures the thing that actually
goes wrong: not "is this strategy significant" but "does picking the best
variant in-sample tell me anything about out-of-sample".

The method, in full:

1. Take the **whole variant matrix** — every configuration's return series,
   aligned on one index. One column per variant. This is why the trial log
   matters: PBO computed over the two variants you liked is meaningless.
2. Split the rows into `S` contiguous blocks (S even, 16 in the paper).
3. For every way of choosing `S/2` blocks as the in-sample set (C(S, S/2) of
   them, 12,870 at S=16), the rest is out-of-sample.
4. Pick the variant with the best in-sample Sharpe. Find its **rank** among all
   variants out-of-sample, as a relative rank omega in (0, 1).
5. Map to the logit, lambda = ln(omega / (1 - omega)). PBO is the share of
   splits where lambda <= 0 — i.e. where the in-sample winner landed in the
   bottom half out-of-sample.

A PBO near 0.5 means selection is a coin toss: you learned nothing by choosing.
Under 0.10 the selection is informative. Above 0.20 the gate fails, and the
right response is fewer variants, not a different split.

`performance_degradation()` is the paper's companion diagnostic: regress the
out-of-sample performance of the in-sample winner on its in-sample performance.
A negative slope is the signature of overfitting — the better it looked, the
worse it did.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class CSCVResult:
    """Everything gate 5 needs, plus the raw splits for a tear sheet."""

    pbo: float
    n_splits: int
    n_variants: int
    n_blocks: int
    logits: np.ndarray
    is_sharpes: np.ndarray
    oos_sharpes: np.ndarray
    chosen: np.ndarray
    degradation_slope: float = float("nan")
    degradation_intercept: float = float("nan")
    prob_oos_loss: float = float("nan")

    @property
    def median_logit(self) -> float:
        return float(np.median(self.logits)) if len(self.logits) else float("nan")

    def verdict(
        self, fail_above: float = 0.20, pass_below: float = 0.10, max_prob_oos_loss: float | None = None
    ) -> str:
        """PBO alone over-rejects; `max_prob_oos_loss` is the necessary companion.

        A high PBO says the in-sample winner is often *not* the out-of-sample
        winner. That is damning when the variants disagree about whether there
        is any edge — and merely uninteresting when they are two hundred
        near-identical parameterisations of the same real one, where the
        "winner" among near-ties is arbitrary by construction and any of them
        would have done.

        The two cases separate on whether the selected variant actually **loses**
        out of sample. Measured on the self-test worlds: pure noise gives
        PBO 0.87 with the choice losing 25% of the time; a planted edge gives
        PBO 0.25 with it losing 2% of the time. So when `max_prob_oos_loss` is
        supplied, a high PBO whose selections stay profitable is a WARN rather
        than a FAIL — the finding is "your variants are interchangeable", which
        is worth knowing and is not overfitting.
        """
        if not np.isfinite(self.pbo):
            return "FAIL"
        if self.pbo < pass_below:
            return "PASS"
        if self.pbo <= fail_above:
            return "WARN"
        if max_prob_oos_loss is not None and np.isfinite(self.prob_oos_loss):
            return "FAIL" if self.prob_oos_loss > max_prob_oos_loss else "WARN"
        return "FAIL"

    def summary(self) -> dict[str, float]:
        return {
            "pbo": self.pbo,
            "median_logit": self.median_logit,
            "splits": float(self.n_splits),
            "variants": float(self.n_variants),
            "blocks": float(self.n_blocks),
            "degradation_slope": self.degradation_slope,
            "prob_oos_loss": self.prob_oos_loss,
            "median_is_sharpe": float(np.median(self.is_sharpes)) if len(self.is_sharpes) else float("nan"),
            "median_oos_sharpe": float(np.median(self.oos_sharpes)) if len(self.oos_sharpes) else float("nan"),
        }


def _sharpe_matrix(returns: np.ndarray) -> np.ndarray:
    """Per-period Sharpe of each column. Zero-variance columns score nothing."""
    mean = np.nanmean(returns, axis=0)
    sd = np.nanstd(returns, axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(sd > 0, mean / sd, -np.inf)
    return np.nan_to_num(out, nan=-np.inf, posinf=-np.inf, neginf=-np.inf)


def _sharpe_from_moments(count: np.ndarray, total: np.ndarray, total_sq: np.ndarray) -> np.ndarray:
    """Sharpe from block aggregates, algebraically identical to _sharpe_matrix.

    A split's Sharpe only needs n, sum(x) and sum(x^2) over its rows, and those
    are additive across blocks. So every split's Sharpe for every variant comes
    out of one matrix product instead of re-scanning the returns — the
    difference between 33 seconds and a fraction of one at S=16, N=200, which
    is what makes PBO cheap enough to run on every sweep rather than on the
    ones someone remembers to check.
    """
    n = count[:, None]
    mean = total / n
    variance = (total_sq - n * mean**2) / (n - 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(variance > 0, mean / np.sqrt(np.maximum(variance, 0.0)), -np.inf)
    return np.nan_to_num(out, nan=-np.inf, posinf=-np.inf, neginf=-np.inf)


def cscv(
    variant_returns: pd.DataFrame,
    n_blocks: int = 16,
    max_splits: int | None = None,
    seed: int = 0,
) -> CSCVResult:
    """PBO over a variant matrix: rows are bars, columns are configurations.

    `n_blocks` must be even. C(16, 8) is 12,870 splits, which is fast enough;
    `max_splits` subsamples them reproducibly when a larger S is wanted.
    """
    if n_blocks % 2 != 0:
        raise ValueError(f"n_blocks must be even, got {n_blocks}")
    frame = variant_returns.dropna(axis=1, how="all")
    if frame.shape[1] < 2:
        raise ValueError("PBO needs at least two variants; one variant cannot be over-selected")
    if len(frame) < n_blocks * 2:
        raise ValueError(f"need at least {n_blocks * 2} bars for {n_blocks} blocks, got {len(frame)}")

    # A variant that holds no position returns 0, not "unknown": filling here
    # keeps the block sums exact rather than silently dropping rows per column.
    values = frame.to_numpy(dtype=float)
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    n_variants = values.shape[1]
    blocks = np.array_split(np.arange(len(values)), n_blocks)

    combos = list(itertools.combinations(range(n_blocks), n_blocks // 2))
    if max_splits is not None and len(combos) > max_splits:
        rng = np.random.default_rng(seed)
        combos = [combos[i] for i in rng.choice(len(combos), size=max_splits, replace=False)]

    # Per-block aggregates: n, sum(x), sum(x^2). Every split is a sum of these.
    block_n = np.array([len(b) for b in blocks], dtype=float)
    block_sum = np.stack([values[b].sum(axis=0) for b in blocks])
    block_sq = np.stack([(values[b] ** 2).sum(axis=0) for b in blocks])
    total_n, total_sum, total_sq = block_n.sum(), block_sum.sum(axis=0), block_sq.sum(axis=0)

    # Indicator matrix: one row per split, one column per block.
    membership = np.zeros((len(combos), n_blocks))
    for i, is_blocks in enumerate(combos):
        membership[i, list(is_blocks)] = 1.0

    logits = np.empty(len(combos))
    is_best = np.empty(len(combos))
    oos_of_best = np.empty(len(combos))
    chosen = np.empty(len(combos), dtype=int)

    # Chunked so a large S x N matrix does not have to fit in memory at once.
    chunk = max(1, int(4_000_000 / max(1, n_variants)))
    for start in range(0, len(combos), chunk):
        stop = min(start + chunk, len(combos))
        indicator = membership[start:stop]

        is_n = indicator @ block_n
        is_sum = indicator @ block_sum
        is_sq = indicator @ block_sq
        is_sharpe = _sharpe_from_moments(is_n, is_sum, is_sq)
        oos_sharpe = _sharpe_from_moments(total_n - is_n, total_sum - is_sum, total_sq - is_sq)

        best = np.argmax(is_sharpe, axis=1)
        rows = np.arange(stop - start)
        best_oos = oos_sharpe[rows, best]

        # Relative rank of the in-sample winner among all variants out-of-sample.
        # Dividing by N+1 keeps omega strictly inside (0, 1), so the logit stays
        # finite even when the winner ranks last or first.
        rank = (oos_sharpe <= best_oos[:, None]).sum(axis=1).astype(float)
        omega = np.clip(rank / (n_variants + 1.0), 1e-12, 1.0 - 1e-12)

        logits[start:stop] = np.log(omega / (1.0 - omega))
        is_best[start:stop] = is_sharpe[rows, best]
        oos_of_best[start:stop] = best_oos
        chosen[start:stop] = best

    pbo = float(np.mean(logits <= 0.0))
    slope, intercept = _fit_line(is_best, oos_of_best)
    return CSCVResult(
        pbo=pbo,
        n_splits=len(combos),
        n_variants=n_variants,
        n_blocks=n_blocks,
        logits=logits,
        is_sharpes=is_best,
        oos_sharpes=oos_of_best,
        chosen=chosen,
        degradation_slope=slope,
        degradation_intercept=intercept,
        prob_oos_loss=float(np.mean(oos_of_best <= 0.0)),
    )


def _fit_line(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Least-squares slope and intercept, or NaN when the fit is degenerate."""
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3 or np.ptp(x[mask]) == 0:
        return float("nan"), float("nan")
    slope, intercept = np.polyfit(x[mask], y[mask], 1)
    return float(slope), float(intercept)


def is_oos_degradation(variant_returns: pd.DataFrame, split: float = 0.5) -> pd.DataFrame:
    """The plain in-sample / out-of-sample split, as a second view on gate 5.

    Less rigorous than CSCV and much easier to read: one table of every
    variant's Sharpe before and after a single cut, and the rank correlation
    between them. A rank correlation near zero says selection carries no
    information, the same message PBO delivers with more machinery.
    """
    frame = variant_returns.dropna(axis=1, how="all")
    cut = int(len(frame) * split)
    values = frame.to_numpy(dtype=float)
    out = pd.DataFrame(
        {"is_sharpe": _sharpe_matrix(values[:cut]), "oos_sharpe": _sharpe_matrix(values[cut:])},
        index=frame.columns,
    )
    out = out.replace(-np.inf, np.nan)
    out.attrs["rank_correlation"] = float(out["is_sharpe"].corr(out["oos_sharpe"], method="spearman"))
    out.attrs["cut"] = cut
    return out
