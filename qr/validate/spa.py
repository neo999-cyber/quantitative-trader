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
    from arch.bootstrap import SPA, StepM

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
        stepm = StepM(bench_loss, model_losses, size=stepm_size, reps=reps, block_size=block_size, seed=seed)
        stepm.compute()
        survivors = [str(name) for name in stepm.superior_models]

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
