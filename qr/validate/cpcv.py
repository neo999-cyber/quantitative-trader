"""Gate 7: combinatorial purged cross-validation and walk-forward efficiency.

A single train/test split gives one out-of-sample Sharpe, and one number tells
you nothing about its own reliability. CPCV (López de Prado, *Advances in
Financial Machine Learning*, ch. 12) gives a **distribution** of them.

The construction, with N groups and k test groups per split:

* every combination of k groups is a test set — C(N, k) splits;
* each group appears as a test group in C(N-1, k-1) of them, so the splits
  reassemble into **phi = C(N-1, k-1) complete backtest paths**, each covering
  the whole sample exactly once;
* at N=10, k=2: 45 splits, 9 paths.

Gate 7 reads the distribution, not the mean: the median path Sharpe against the
in-sample Sharpe, and the share of paths that are positive at all. A strategy
whose median path is half its in-sample Sharpe and whose worst path is still
above zero is a different animal from one with the same average built out of
two brilliant paths and seven bad ones.

**Purging and embargo** are what make the out-of-sample real. A strategy with a
90-bar lookback computes its signal for the first test bar from bars that sit
in the training set, so train and test overlap in information even though they
do not overlap in time. `purge` drops the bars on either side of each test
block; `embargo` drops a further stretch *after* it, because volatility
clustering makes the bars just after a test block the most contaminated ones.
Skipping either turns gate 7 into a formality.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Split:
    """One CPCV split: which groups are under test, and which rows may train."""

    test_groups: tuple[int, ...]
    train_idx: np.ndarray
    test_idx: np.ndarray


@dataclass
class CPCVResult:
    """The distribution of path Sharpes, and the numbers gate 7 reads off it."""

    path_sharpes: np.ndarray
    is_sharpe: float
    n_groups: int
    k: int
    n_splits: int
    periods_per_year: float
    selected: list[int] = field(default_factory=list)

    @property
    def median_path(self) -> float:
        return float(np.median(self.path_sharpes)) if len(self.path_sharpes) else float("nan")

    @property
    def share_positive(self) -> float:
        return float(np.mean(self.path_sharpes > 0)) if len(self.path_sharpes) else float("nan")

    @property
    def ratio_to_is(self) -> float:
        """Median path Sharpe as a fraction of in-sample. Gate 7 wants >= 0.5."""
        if not np.isfinite(self.is_sharpe) or self.is_sharpe <= 0:
            return float("nan")
        return float(self.median_path / self.is_sharpe)

    def verdict(self, min_ratio: float = 0.5, min_share_positive: float = 0.90) -> str:
        if not np.isfinite(self.ratio_to_is):
            return "FAIL"
        if self.ratio_to_is >= min_ratio and self.share_positive >= min_share_positive:
            return "PASS"
        if self.ratio_to_is < 0.4:
            return "FAIL"
        return "WARN"

    def summary(self) -> dict[str, float]:
        paths = self.path_sharpes
        return {
            "paths": float(len(paths)),
            "splits": float(self.n_splits),
            "groups": float(self.n_groups),
            "k": float(self.k),
            "is_sharpe": self.is_sharpe,
            "median_path_sharpe": self.median_path,
            "worst_path_sharpe": float(np.min(paths)) if len(paths) else float("nan"),
            "best_path_sharpe": float(np.max(paths)) if len(paths) else float("nan"),
            "share_paths_positive": self.share_positive,
            "median_over_is": self.ratio_to_is,
        }


def n_paths(n_groups: int, k: int = 2) -> int:
    """phi = C(N-1, k-1): how many complete backtest paths the splits reassemble into."""
    return math.comb(n_groups - 1, k - 1)


def make_splits(
    n_obs: int, n_groups: int = 10, k: int = 2, purge: int = 0, embargo: int = 0
) -> list[Split]:
    """Every combination of `k` test groups, with the train set purged and embargoed."""
    if k < 1 or k >= n_groups:
        raise ValueError(f"k must be in [1, n_groups), got k={k}, n_groups={n_groups}")
    if n_obs < n_groups:
        raise ValueError(f"need at least {n_groups} observations, got {n_obs}")

    groups = np.array_split(np.arange(n_obs), n_groups)
    splits: list[Split] = []
    for test_groups in itertools.combinations(range(n_groups), k):
        test_idx = np.concatenate([groups[g] for g in test_groups])
        blocked = np.zeros(n_obs, dtype=bool)
        blocked[test_idx] = True
        # Purge symmetrically around every contiguous test block, then embargo
        # forward: the bars just after a test block share its volatility regime.
        for g in test_groups:
            start, stop = groups[g][0], groups[g][-1]
            blocked[max(0, start - purge) : start] = True
            blocked[stop + 1 : min(n_obs, stop + 1 + purge + embargo)] = True
        train_idx = np.flatnonzero(~blocked)
        splits.append(Split(test_groups, train_idx, test_idx))
    return splits


def _sharpe(values: np.ndarray, periods_per_year: float) -> float:
    clean = values[np.isfinite(values)]
    if len(clean) < 2:
        return float("nan")
    sd = clean.std(ddof=1)
    return float(clean.mean() / sd * math.sqrt(periods_per_year)) if sd > 0 else float("nan")


def combinatorial_purged_cv(
    variant_returns: pd.DataFrame,
    periods_per_year: float = 365.0,
    n_groups: int = 10,
    k: int = 2,
    purge: int = 0,
    embargo: int = 0,
) -> CPCVResult:
    """Select the best variant in-sample per split; measure it out-of-sample.

    What is being tested is the **selection procedure**, not one variant. For
    each split the best variant on the training groups is chosen and its returns
    over the test groups are kept; the test blocks are then reassembled into phi
    complete paths over the whole sample, and each path gets a Sharpe.

    With a single column this degenerates to plain purged CV of a fixed
    strategy, which is still a useful read — just a weaker claim.
    """
    frame = variant_returns.dropna(axis=1, how="all")
    if frame.empty:
        raise ValueError("no variants to cross-validate")
    values = np.nan_to_num(frame.to_numpy(dtype=float), nan=0.0)
    n_obs, n_variants = values.shape

    splits = make_splits(n_obs, n_groups, k, purge, embargo)
    groups = np.array_split(np.arange(n_obs), n_groups)

    # For each split: pick in-sample, record the chosen variant's test returns.
    chosen_per_split: list[int] = []
    test_returns: list[dict[int, np.ndarray]] = []
    for split in splits:
        train = values[split.train_idx]
        mean = train.mean(axis=0)
        sd = train.std(axis=0, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            sharpe = np.where(sd > 0, mean / sd, -np.inf)
        best = int(np.argmax(np.nan_to_num(sharpe, nan=-np.inf)))
        chosen_per_split.append(best)
        test_returns.append({g: values[groups[g], best] for g in split.test_groups})

    # Reassemble paths: group g appears in phi splits; path j takes the j-th.
    phi = n_paths(n_groups, k)
    per_group: dict[int, list[np.ndarray]] = {g: [] for g in range(n_groups)}
    for returns_by_group in test_returns:
        for g, series in returns_by_group.items():
            per_group[g].append(series)

    paths = np.empty(phi)
    for j in range(phi):
        stitched = np.concatenate([per_group[g][j] for g in range(n_groups)])
        paths[j] = _sharpe(stitched, periods_per_year)

    # In-sample reference: the best variant over the whole sample, which is the
    # number a naive backtest would have reported.
    full = np.array([_sharpe(values[:, i], periods_per_year) for i in range(n_variants)])
    is_sharpe = float(np.nanmax(full)) if np.isfinite(full).any() else float("nan")

    return CPCVResult(
        path_sharpes=paths,
        is_sharpe=is_sharpe,
        n_groups=n_groups,
        k=k,
        n_splits=len(splits),
        periods_per_year=periods_per_year,
        selected=chosen_per_split,
    )


def walk_forward_efficiency(
    variant_returns: pd.DataFrame,
    periods_per_year: float = 365.0,
    n_windows: int = 6,
    purge: int = 0,
) -> pd.DataFrame:
    """Anchored walk-forward: choose on everything so far, trade the next window.

    The second view gate 7 asks for, and the one closest to how the strategy
    would actually have been run. Walk-forward efficiency is the out-of-sample
    annualised return as a fraction of the in-sample one; below about 50% the
    parameters are fitted to the training window rather than to the market.

    It is reported as the **median of the per-window ratios**, not as the ratio
    of the pooled means, because the pooled form has a denominator that can
    pass through zero. The trial's first real run produced a WFE of 13.62 for
    the reversal family, which reads as a strategy that does thirteen times
    better out of sample than in — nonsense, and caused by in-sample returns
    that very nearly cancelled across windows. A near-zero denominator turns a
    ratio into a random number of arbitrary magnitude and sign; taking the
    median over windows, each with its own denominator, cannot do that unless
    most windows are degenerate. The pooled figure is still reported as
    `wfe_pooled` so the two can be compared.

    Windows whose in-sample return is not positive are dropped from the median
    rather than counted as zero: "how much of the edge survived" is not a
    question about a window that had no edge to begin with, and `wfe_windows`
    records how many were left.
    """
    frame = variant_returns.dropna(axis=1, how="all")
    values = np.nan_to_num(frame.to_numpy(dtype=float), nan=0.0)
    n_obs = len(values)
    edges = np.linspace(0, n_obs, n_windows + 1).astype(int)

    rows = []
    for w in range(1, n_windows):
        train_stop = max(0, edges[w] - purge)
        train, test = values[:train_stop], values[edges[w] : edges[w + 1]]
        if len(train) < 20 or len(test) < 5:
            continue
        mean, sd = train.mean(axis=0), train.std(axis=0, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            sharpe = np.where(sd > 0, mean / sd, -np.inf)
        best = int(np.argmax(np.nan_to_num(sharpe, nan=-np.inf)))
        rows.append(
            {
                "window": w,
                "variant": frame.columns[best],
                "is_ann_return": float(train[:, best].mean() * periods_per_year),
                "oos_ann_return": float(test[:, best].mean() * periods_per_year),
                "is_sharpe": _sharpe(train[:, best], periods_per_year),
                "oos_sharpe": _sharpe(test[:, best], periods_per_year),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        out.attrs["wfe"] = float("nan")
        out.attrs["wfe_pooled"] = float("nan")
        out.attrs["wfe_windows"] = 0
        return out
    usable = out[out["is_ann_return"] > 0]
    ratios = (usable["oos_ann_return"] / usable["is_ann_return"]) if not usable.empty else pd.Series(dtype=float)
    out["wfe_window"] = np.where(
        out["is_ann_return"] > 0, out["oos_ann_return"] / out["is_ann_return"], np.nan
    )
    is_total, oos_total = out["is_ann_return"].mean(), out["oos_ann_return"].mean()
    out.attrs["wfe"] = float(ratios.median()) if len(ratios) else float("nan")
    out.attrs["wfe_pooled"] = float(oos_total / is_total) if is_total > 0 else float("nan")
    out.attrs["wfe_windows"] = int(len(ratios))
    return out
