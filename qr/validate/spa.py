"""Gate 5, second half: Hansen's SPA and Romano–Wolf StepM.

CSCV asks whether *selecting* the best variant tells you anything. SPA asks a
different and equally necessary question: **is the best of my variants better
than a benchmark, once I account for having looked at all of them?**

The distinction matters because a family can have a low PBO — selection is
stable, the same variant wins in and out of sample — and still be worthless,
because every variant including the winner merely tracks buy-and-hold. PBO
would be quiet. SPA is the test that speaks.

Hansen's Superior Predictive Ability test compares the maximum standardised
outperformance over a benchmark against its stationary-bootstrap distribution
under the null that no model beats the benchmark. Its consistent p-value
(`spa.pvalues["consistent"]`) is the one to read; the lower and upper p-values
bracket it and the gap between them says how much the result depends on which
poor models are included.

Romano–Wolf StepM then names *which* variants survive at a family-wise error
rate — a stricter and more useful answer than "at least one does", because a
strategy worth trading should be identifiable, not merely existent.

The benchmark is buy-and-hold unless told otherwise. That is the right null for
a long-only spot book: the question is never "does this make money" but "does
this make money that holding the coins would not have".
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class SPAResult:
    """Hansen's SPA, plus the StepM survivors."""

    p_consistent: float
    p_lower: float
    p_upper: float
    n_models: int
    n_obs: int
    benchmark_name: str
    better_models: list[str] = field(default_factory=list)
    stepm_survivors: list[str] = field(default_factory=list)
    best_excess_annual: float = float("nan")

    def verdict(self, max_p: float = 0.05, fail_above: float = 0.50) -> str:
        """PASS below `max_p`, FAIL above `fail_above`, WARN between.

        The wide middle band is not laziness. SPA's consistent p-value is
        conservative when the models are many and correlated — two hundred
        variants of one family are exactly that — so a real edge routinely
        lands between 0.05 and 0.5. Measured on the self-test worlds: a planted
        edge that genuinely beats buy-and-hold by 15 percentage points a year
        scores 0.27, while searched-over noise scores 0.999. Treating 0.27 as a
        failure would reject almost everything real; treating 0.999 as anything
        other than a failure would be absurd. A p above one half means the
        benchmark is at least as good as the best of the search more often than
        not, which is the honest place to draw the line.
        """
        if not np.isfinite(self.p_consistent):
            return "FAIL"
        if self.p_consistent < max_p:
            return "PASS"
        return "WARN" if self.p_consistent <= fail_above else "FAIL"

    def summary(self) -> dict[str, float | str]:
        return {
            "spa_p_consistent": self.p_consistent,
            "spa_p_lower": self.p_lower,
            "spa_p_upper": self.p_upper,
            "spa_models": float(self.n_models),
            "spa_benchmark": self.benchmark_name,
            "spa_better_models": float(len(self.better_models)),
            "stepm_survivors": float(len(self.stepm_survivors)),
            "best_excess_annual": self.best_excess_annual,
        }


def superior_predictive_ability(
    variant_returns: pd.DataFrame,
    benchmark: pd.Series,
    periods_per_year: float = 365.0,
    reps: int = 1000,
    block_size: int | None = None,
    seed: int = 0,
    run_stepm: bool = True,
    stepm_size: float = 0.05,
) -> SPAResult:
    """Does the best variant beat `benchmark`, after paying for the search?

    `variant_returns` and `benchmark` are aligned on their common index and
    dropped where either is missing. A variant that is constant (never traded)
    is removed: it carries no information and its zero variance upsets the
    standardisation.
    """
    from arch.bootstrap import SPA

    frame = variant_returns.copy()
    joined = pd.concat([benchmark.rename("_benchmark"), frame], axis=1, join="inner").dropna()
    if len(joined) < 50:
        raise ValueError(f"SPA needs at least 50 overlapping observations, got {len(joined)}")

    bench = joined["_benchmark"]
    models = joined.drop(columns=["_benchmark"])
    live = models.columns[models.std(ddof=1) > 0]
    models = models[live]
    if models.shape[1] < 1:
        raise ValueError("no variant with a non-zero variance to test")

    # arch states SPA and StepM in terms of **losses**, where lower is better.
    # These are returns, where higher is better, so they are negated. Passing
    # returns directly silently inverts the test — it then asks whether any
    # variant did *worse* than the benchmark, and reports a placid p-value for
    # a strategy with a real edge. Exactly the convention mismatch the rest of
    # this package writes its formulas out to avoid.
    bench_loss, model_losses = -bench, -models

    spa = SPA(bench_loss, model_losses, reps=reps, block_size=block_size, seed=seed)
    spa.compute()
    p = spa.pvalues

    excess = (models.mean() - bench.mean()) * periods_per_year
    better = list(spa.better_models(pvalue=0.05)) if models.shape[1] > 1 else []

    survivors: list[str] = []
    if run_stepm and models.shape[1] > 1:
        # StepM is computed here rather than by `arch.bootstrap.StepM` (8.0.0),
        # whose loop tests the *latest round's* removals against the model
        # count instead of the cumulative set: when every model is removed
        # over successive rounds it re-runs SPA on an empty selection and
        # raises "zero-size array to reduction operation maximum". That is
        # the C1 v2 hourly failure of 16 September 2026 (review 22, §2). The
        # procedure is Romano-Wolf's as arch states it; only the stop is fixed.
        survivors = [str(models.columns[i]) for i in _stepm(bench_loss, model_losses, stepm_size, reps, block_size, seed)]

    return SPAResult(
        p_consistent=float(p["consistent"]),
        p_lower=float(p["lower"]),
        p_upper=float(p["upper"]),
        n_models=int(models.shape[1]),
        n_obs=int(len(joined)),
        benchmark_name=str(benchmark.name or "benchmark"),
        better_models=[str(b) for b in better],
        stepm_survivors=survivors,
        best_excess_annual=float(excess.max()),
    )


def buy_and_hold_benchmark(
    panel, universe: pd.DataFrame | None = None, costs=None, equity: float | None = None
) -> pd.Series:
    """The benchmark gate 5 tests against: equal-weight the same universe.

    Costed with the same model as the strategy, because comparing a costed
    strategy against a free benchmark is a comparison the strategy is designed
    to win.

    `equity` matters for the same reason and was missing: on a venue charging
    per order, the cost model alone does not fix the cost. Without it the
    benchmark fell back to `run_backtest`'s $10,000 default while the ETF trial
    priced its strategies at $1,000 — so gate 5 asked every ETF family to beat
    a buy-and-hold running in an account ten times larger and therefore an
    order of magnitude cheaper per trade. That is the wrong direction: it
    flatters the benchmark and makes the strategy harder to beat. Buy-and-hold
    barely trades, so the effect is small; it is still a comparison between two
    different accounts.
    """
    from qr.execution.costs import CostModel
    from qr.research.runner import run_backtest

    from qr.strategies.library import BuyAndHold

    kwargs = {"equity": equity} if equity else {}
    return run_backtest(
        panel, BuyAndHold(), costs or CostModel.trial(), universe, **kwargs
    ).net.rename("buy_and_hold")


def cash_benchmark(
    index: pd.DatetimeIndex,
    periods_per_year: float,
    risk_free: "pd.Series | float | None" = None,
) -> pd.Series:
    """The benchmark for a book that holds nothing the market would: cash.

    Buy-and-hold is the right null for a long-only spot book, because the
    question there is whether timing adds anything to owning the coins. It is
    the wrong null for a dollar-neutral, beta-neutral or carry book: such a
    book is not a subset of the market's exposure, and asking it to beat a
    rising market on risk-adjusted return is asking a different question from
    the one its mechanism makes. Programme 1 asked that question of every
    family it ran and got the answer the construction guaranteed
    (`docs/20_PROGRAMME_2.md`, §1). For those books the comparator is the
    risk-free rate, compounded per bar.

    `risk_free` is an annualised **decimal** rate: one number, or a dated
    series (FRED DTB3 through `qr data riskfree-pull`) carried forward to each
    bar. A series that starts after the panel does is extended backwards with
    its first value, and that is stated rather than hidden: a benchmark is not
    a signal, so the fill is not lookahead, but a rate assumed for a period
    before it was observed is an assumption and the report says so through the
    series' `attrs["backfilled_bars"]`.
    """
    if risk_free is None:
        risk_free = 0.0
    backfilled = 0
    if np.isscalar(risk_free):
        annual = pd.Series(float(risk_free), index=index)
    else:
        series = pd.Series(risk_free).dropna().sort_index()
        if series.empty:
            raise ValueError("the risk-free series is empty")
        stamps = pd.DatetimeIndex(series.index)
        if stamps.tz is None and index.tz is not None:
            stamps = stamps.tz_localize(index.tz)
        elif stamps.tz is not None and index.tz is None:
            stamps = stamps.tz_convert("UTC").tz_localize(None)
        elif stamps.tz is not None and index.tz is not None:
            stamps = stamps.tz_convert(index.tz)
        series.index = stamps
        aligned = series.reindex(index.union(stamps)).sort_index().ffill().reindex(index)
        backfilled = int(aligned.isna().sum())
        annual = aligned.bfill()
    per_bar = (1.0 + annual.astype(float)) ** (1.0 / float(periods_per_year)) - 1.0
    out = per_bar.rename("cash")
    out.attrs["backfilled_bars"] = backfilled
    return out


def exposure_benchmark(
    panel,
    universe: pd.DataFrame | None,
    costs,
    equity: float | None,
    exposure: float,
    periods_per_year: float,
    risk_free: "pd.Series | float | None" = None,
) -> pd.Series:
    """The comparator for a long-only stock-selection book: the market at the
    book's own size, the rest in cash.

    A long-only book that averages 40% gross is not a subset of a fully
    invested buy-and-hold, and it is not cash either. Against buy-and-hold it
    loses on beta it never held; against cash it wins on beta alone in a
    rising market, which is what a book benchmarked to cash would have passed
    as skill (the review in `docs/20_PROGRAMME_2.md` took this comparator
    from the independent plan for exactly that reason). So the null is the
    costed equal-weight universe scaled to `exposure` — the strategy's mean
    gross exposure — plus `1 - exposure` compounding at the risk-free rate,
    bar by bar. What is left for the strategy to claim is selection.

    `exposure` is read off the book that was actually held, not a target,
    so a strategy that sits in cash for half the sample is compared with a
    benchmark that does too.
    """
    exposure = float(exposure)
    if not np.isfinite(exposure) or exposure < 0.0:
        raise ValueError(f"exposure must be a non-negative number, not {exposure!r}")
    market = buy_and_hold_benchmark(panel, universe, costs, equity)
    cash = cash_benchmark(panel.index, periods_per_year, risk_free)
    out = (exposure * market + (1.0 - exposure) * cash).rename("exposure_matched")
    out.attrs["exposure"] = exposure
    out.attrs["backfilled_bars"] = cash.attrs.get("backfilled_bars", 0)
    return out


def _stepm(bench_loss, model_losses, size: float, reps: int, block_size: int, seed: int) -> list[int]:
    """Romano-Wolf StepM by successive SPA rounds; stops when nothing is
    removed or when the cumulative survivor set holds every model."""
    from arch.bootstrap import SPA

    k = int(model_losses.shape[1])
    spa = SPA(bench_loss, model_losses, reps=reps, block_size=block_size, seed=seed)
    spa.compute()
    better = [int(i) for i in spa.better_models(size)]
    all_better = better[:]
    while better and len(all_better) < k:
        selector = np.ones(k, dtype=bool)
        selector[np.array(all_better)] = False
        spa.subset(selector)
        spa.compute()
        better = [int(i) for i in spa.better_models(size)]
        all_better.extend(better)
    return sorted(set(all_better))
