"""The statistics the gates are decided on.

Every formula here is written out rather than called out to, for one reason:
the conventions differ between implementations — per-period versus annualised
Sharpe, excess versus raw kurtosis, one- versus two-sided p — and a silent
convention mismatch in a deflation formula is exactly the kind of error that
lets a dead strategy through gate 4. Writing them out makes the convention
visible; the test suite then checks each one against `jsharpe`, `arch` or
`statsmodels`, so the maths is verified rather than merely mine.

Sharpe ratios inside these functions are **per period** unless a name says
`annual`. That is the convention Bailey and López de Prado's formulas use, and
mixing it with an annualised number inflates PSR to 1.0 for nearly anything.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sps

#: Euler–Mascheroni, needed for the expected maximum of N Sharpe estimates.
EULER_GAMMA = 0.5772156649015329


def _clean(returns: pd.Series | np.ndarray) -> np.ndarray:
    values = np.asarray(pd.Series(returns).astype(float).dropna())
    return values


@dataclass(frozen=True)
class SharpeMoments:
    """The four numbers every deflation formula in this module needs."""

    sharpe: float  # per period
    n: int
    skew: float  # gamma3
    kurtosis: float  # gamma4, NON-excess (3.0 for a normal)

    @property
    def annual(self) -> float:
        return self.sharpe  # annualisation is the caller's business

    def annualised(self, periods_per_year: float) -> float:
        return self.sharpe * math.sqrt(periods_per_year)


def moments(returns: pd.Series | np.ndarray) -> SharpeMoments:
    """Per-period Sharpe plus the skew and kurtosis the PSR correction uses."""
    values = _clean(returns)
    n = len(values)
    if n < 3:
        return SharpeMoments(float("nan"), n, 0.0, 3.0)
    sd = values.std(ddof=1)
    sharpe = float(values.mean() / sd) if sd > 0 else float("nan")
    return SharpeMoments(
        sharpe=sharpe,
        n=n,
        skew=float(sps.skew(values, bias=False)),
        kurtosis=float(sps.kurtosis(values, fisher=False, bias=False)),
    )


def annualised_sharpe(returns: pd.Series | np.ndarray, periods_per_year: float) -> float:
    return moments(returns).sharpe * math.sqrt(periods_per_year)


# ------------------------------------------------------------------ gate 3


def hac_tstat(returns: pd.Series | np.ndarray, lags: int | None = None) -> tuple[float, float, int]:
    """Newey–West t-statistic of the mean return, and its two-sided p-value.

    A plain t-test on a strategy's returns overstates significance whenever the
    returns are autocorrelated, which overlapping-holding-period strategies
    always are. `lags` defaults to the Newey–West rule of thumb,
    floor(4 (T/100)^(2/9)).
    """
    values = _clean(returns)
    n = len(values)
    if n < 3:
        return float("nan"), float("nan"), 0
    if lags is None:
        lags = int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0)))
    lags = max(0, min(lags, n - 2))

    import statsmodels.api as sm

    model = sm.OLS(values, np.ones(n)).fit(cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": True})
    return float(model.tvalues[0]), float(model.pvalues[0]), lags


def probabilistic_sharpe(
    returns: pd.Series | np.ndarray, benchmark: float = 0.0, moments_: SharpeMoments | None = None
) -> float:
    """PSR: P(true Sharpe > `benchmark`), correcting for skew and fat tails.

        PSR(SR*) = Phi[ (SR - SR*) sqrt(T - 1)
                        / sqrt(1 - g3 SR + (g4 - 1)/4 SR^2) ]

    `benchmark` and the returns' Sharpe are both **per period**. Negative skew
    and fat tails — what a real strategy's returns look like — widen the
    denominator and push PSR down, which is the whole point of using it over a
    plain t-test.
    """
    m = moments_ or moments(returns)
    if not np.isfinite(m.sharpe) or m.n < 3:
        return float("nan")
    variance = 1.0 - m.skew * m.sharpe + (m.kurtosis - 1.0) / 4.0 * m.sharpe**2
    if variance <= 0:
        return float("nan")
    z = (m.sharpe - benchmark) * math.sqrt(m.n - 1) / math.sqrt(variance)
    return float(sps.norm.cdf(z))


def min_track_record_length(
    returns: pd.Series | np.ndarray,
    benchmark: float = 0.0,
    alpha: float = 0.05,
    moments_: SharpeMoments | None = None,
) -> float:
    """How many periods it would take for this Sharpe to clear `benchmark` at `alpha`.

    Gate 3 compares this against the sample actually available: a strategy whose
    MinTRL exceeds its own track record has not been observed long enough to say
    anything, whatever its t-stat looks like.
    """
    m = moments_ or moments(returns)
    edge = m.sharpe - benchmark
    if not np.isfinite(edge) or edge <= 0:
        return float("inf")
    variance = 1.0 - m.skew * m.sharpe + (m.kurtosis - 1.0) / 4.0 * m.sharpe**2
    if variance <= 0:
        return float("nan")
    return float(1.0 + variance * (sps.norm.ppf(1.0 - alpha) / edge) ** 2)


def stationary_bootstrap_ci(
    returns: pd.Series | np.ndarray,
    periods_per_year: float,
    reps: int = 2000,
    block_size: float | None = None,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float, np.ndarray]:
    """Percentile CI for the annualised Sharpe, resampling blocks, not bars.

    Politis–Romano stationary bootstrap: blocks of geometrically distributed
    length preserve the autocorrelation and volatility clustering that an iid
    bootstrap destroys — and destroying them is what makes an iid CI too narrow.
    The optimal expected block length is chosen by Politis–White when not given.
    """
    from arch.bootstrap import StationaryBootstrap, optimal_block_length

    values = _clean(returns)
    if len(values) < 20:
        return float("nan"), float("nan"), np.array([])
    if block_size is None:
        block_size = float(optimal_block_length(values)["stationary"].iloc[0])
    block_size = max(1.0, block_size)

    def statistic(sample: np.ndarray) -> float:
        sd = sample.std(ddof=1)
        return (sample.mean() / sd * math.sqrt(periods_per_year)) if sd > 0 else 0.0

    bootstrap = StationaryBootstrap(block_size, values, seed=seed)
    draws = np.asarray(bootstrap.apply(statistic, reps)).ravel()
    lower, upper = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lower), float(upper), draws


# ------------------------------------------------------------------ gate 4


def expected_max_sharpe(n_trials: int, sharpe_variance: float, benchmark: float = 0.0) -> float:
    """E[max SR] over `n_trials` independent draws — the bar a winner must clear.

        E[max] = sqrt(V) [ (1 - g) Phi^-1(1 - 1/N) + g Phi^-1(1 - 1/(N e)) ]

    This is the number that makes multiple testing concrete: search 200 variants
    of pure noise whose Sharpe estimates vary with V, and the best of them is
    expected to post this Sharpe having no edge whatsoever.
    """
    if n_trials < 1 or sharpe_variance < 0:
        return float("nan")
    if n_trials == 1:
        return benchmark
    sd = math.sqrt(sharpe_variance)
    a = sps.norm.ppf(1.0 - 1.0 / n_trials)
    b = sps.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return float(benchmark + sd * ((1.0 - EULER_GAMMA) * a + EULER_GAMMA * b))


def deflated_sharpe(
    returns: pd.Series | np.ndarray,
    n_trials: int,
    sharpe_variance: float | None = None,
    trial_sharpes: np.ndarray | pd.Series | None = None,
    moments_: SharpeMoments | None = None,
) -> tuple[float, float]:
    """DSR and the benchmark it was deflated against, both per period.

    DSR is PSR measured against E[max SR] instead of against zero: "is this
    Sharpe better than the best I should expect from searching this hard over
    nothing?" `sharpe_variance` is the variance of the **per-period** Sharpe
    estimates across the trials; pass `trial_sharpes` and it is measured from
    them, which is the honest route when the sweep's results are to hand.
    """
    m = moments_ or moments(returns)
    if sharpe_variance is None:
        if trial_sharpes is None:
            raise ValueError("deflated_sharpe needs sharpe_variance or trial_sharpes")
        sharpes = np.asarray(pd.Series(trial_sharpes).astype(float).dropna())
        if len(sharpes) < 2:
            raise ValueError("trial_sharpes needs at least two variants to have a variance")
        sharpe_variance = float(sharpes.var(ddof=1))
    benchmark = expected_max_sharpe(n_trials, sharpe_variance)
    return probabilistic_sharpe(returns, benchmark=benchmark, moments_=m), benchmark


def effective_trials(variant_returns: pd.DataFrame, floor: int = 1) -> tuple[int, float]:
    """How many *independent* trials a correlated sweep really represents.

    Deflating by the raw variant count treats forty adjacent lookbacks as forty
    independent looks at the data, which they are not — their return series are
    correlated above 0.95 and they rise and fall together. Over-deflating is
    not "conservative" in any useful sense: it fails real edges for the crime
    of having been searched over a fine grid, and it rewards coarse grids that
    hide the same search behind fewer numbers.

    The estimator is the **effective rank** of the variant correlation matrix,
    exp of the entropy of its normalised eigenvalues. It equals N when the
    variants are orthogonal and collapses toward 1 as they become redundant,
    which is exactly the behaviour wanted. Returns `(effective, raw)` so a
    report can show both — and it should, because the ratio is itself worth
    seeing.
    """
    frame = variant_returns.dropna(axis=1, how="all").fillna(0.0)
    raw = frame.shape[1]
    if raw < 2:
        return max(floor, raw), float(raw)
    corr = frame.corr().to_numpy()
    corr = np.nan_to_num(corr, nan=0.0)
    eigenvalues = np.linalg.eigvalsh(corr)
    eigenvalues = eigenvalues[eigenvalues > 1e-12]
    if len(eigenvalues) == 0:
        return max(floor, 1), float(raw)
    weights = eigenvalues / eigenvalues.sum()
    entropy = float(-(weights * np.log(weights)).sum())
    effective = float(np.exp(entropy))
    return int(max(floor, min(raw, round(effective)))), float(raw)


def min_backtest_length(n_trials: int, annual_sharpe: float = 1.0) -> float:
    """Years of data needed before the best of `n_trials` means anything.

        MinBTL ~ 2 ln(N) / SR_annual^2

    Bailey et al.'s rule, and the most useful single line in the literature: at
    an annual Sharpe of 1, forty-five variants need about 7.6 years. Search more
    variants than the sample supports and the winner is a sampling artefact.
    """
    if n_trials < 2 or annual_sharpe <= 0:
        return float("nan")
    return float(2.0 * math.log(n_trials) / annual_sharpe**2)


def haircut_sharpe(
    observed_sharpe: float,
    n_trials: int,
    p_value: float,
    method: str = "bhy",
) -> tuple[float, float]:
    """Harvey–Liu haircut: what is left of a Sharpe after multiplicity.

    The observed one-sided p-value is inflated as if it were the smallest of
    `n_trials`, converted back into a t-statistic, and the Sharpe scaled by the
    ratio of adjusted to observed t. Returns (haircut Sharpe, adjusted p).

    * `bonferroni` / `holm` — for the most significant of N these coincide:
      p_adj = min(1, N p). Controls the family-wise error rate; strict.
    * `bhy` — Benjamini–Hochberg–Yekutieli, p_adj = min(1, N c(N) p) with
      c(N) = sum 1/i. Controls the false-discovery rate under dependence, which
      is the right frame when the N variants are variants of one idea.
    """
    if not np.isfinite(p_value) or not np.isfinite(observed_sharpe):
        return float("nan"), float("nan")
    n = max(1, int(n_trials))
    key = method.lower()
    if key in ("bonferroni", "holm"):
        adjusted = min(1.0, n * p_value)
    elif key == "bhy":
        c = sum(1.0 / i for i in range(1, n + 1))
        adjusted = min(1.0, n * c * p_value)
    else:
        raise ValueError(f"unknown haircut method {method!r}; use bonferroni, holm or bhy")
    if observed_sharpe <= 0:
        return observed_sharpe, adjusted

    # One-sided normal quantiles: a p of 1 means no evidence, hence no Sharpe.
    # Both p's are floored away from zero before inversion — a p of exactly 0
    # (which a bootstrap or a rounded t can produce) sends ppf to infinity, and
    # inf/inf silently yields a NaN haircut instead of the near-total one the
    # numbers actually imply.
    def _to_t(p: float) -> float:
        return float(sps.norm.ppf(1.0 - min(max(p, 1e-16), 0.5 - 1e-12)))

    t_observed = _to_t(p_value)
    t_adjusted = _to_t(adjusted) if adjusted < 1.0 else 0.0
    if t_observed <= 0:
        return 0.0, adjusted
    return float(observed_sharpe * max(0.0, t_adjusted) / t_observed), float(adjusted)


def adjusted_p_values(p_values: np.ndarray | pd.Series, method: str = "holm") -> np.ndarray:
    """Family-wise or FDR adjustment over a whole set of p-values."""
    from statsmodels.stats.multitest import multipletests

    key = {"holm": "holm", "bonferroni": "bonferroni", "bhy": "fdr_by", "bh": "fdr_bh"}[method.lower()]
    values = np.asarray(pd.Series(p_values).astype(float))
    return multipletests(values, method=key)[1]
