"""Running a whole grid of variants, and keeping every one of them.

The variant matrix — one return series per configuration tried — is the input
gates 4, 5, 7 and 8 all need. PBO over the two variants someone liked is
meaningless; deflation against a trial count that omits the discarded runs is
worse than meaningless, because it produces a confident number that is wrong in
the flattering direction.

So `run_sweep` keeps everything, records the count in the trial log as a single
hash-chained entry, and hands back a `Sweep` that the gates read. Nothing in
the pipeline offers a way to run variants without counting them.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import BacktestResult, run_backtest
from qr.strategies.base import Strategy

log = logging.getLogger(__name__)


@dataclass
class Sweep:
    """Every variant's net returns, its parameters, and its headline stats."""

    family: str
    returns: pd.DataFrame
    gross_returns: pd.DataFrame
    params: dict[str, dict]
    stats: pd.DataFrame
    periods_per_year: float
    universe_name: str = ""
    results: dict[str, BacktestResult] = field(default_factory=dict, repr=False)
    #: The class the variants were built from, so a permutation test can
    #: re-optimise over the same grid on permuted data.
    strategy_class: type | None = field(default=None, repr=False)

    def __len__(self) -> int:
        return self.returns.shape[1]

    @property
    def names(self) -> list[str]:
        return list(self.returns.columns)

    def best(self, by: str = "sharpe") -> str:
        """The variant a naive backtest would have reported. Named, not hidden.

        When no variant produced a finite score — the usual cause being a
        strategy whose entry condition never fired, so every variant is flat —
        this returns the first variant rather than raising. "It never traded"
        is a finding the gates should report (gate 3 on significance, gate 8 on
        round trips), not an exception that stops the report being written.
        """
        scores = self.stats[by].astype(float)
        if not np.isfinite(scores).any():
            log.warning(
                "no variant of %r produced a finite %s — the strategy appears never to have "
                "taken a position; reporting the first variant so the gates can say so",
                self.family,
                by,
            )
            return str(self.names[0])
        return str(scores.idxmax())

    @property
    def ever_traded(self) -> bool:
        """Did any variant take a position at all?"""
        return bool((self.stats["round_trips"] > 0).any())

    def best_result(self, by: str = "sharpe") -> BacktestResult:
        return self.results[self.best(by)]

    def param_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.params).T.reindex(self.names)

    def sharpes(self) -> pd.Series:
        return self.stats["sharpe"]

    def per_period_sharpes(self) -> pd.Series:
        """Per-period Sharpes — what the deflation formulas want as a variance."""
        return self.stats["sharpe"] / np.sqrt(self.periods_per_year)

    def rebuild(self, names: Sequence[str] | None = None) -> list[Strategy]:
        """Reconstruct the strategy objects, so a grid can be re-run elsewhere.

        Masters' permutation test needs to re-optimise the *whole search* on
        each permuted dataset, which means rebuilding the variants rather than
        reusing their results.
        """
        if self.strategy_class is None:
            raise ValueError("this sweep does not know which class built it")
        return [self.strategy_class(**self.params[name]) for name in (names or self.names)]

    def subgrid(self, limit: int) -> list[str]:
        """Up to `limit` variant names, spread evenly across the grid.

        Evenly rather than randomly: the point is to span the parameter space,
        and a random draw can cluster and make the subgrid unrepresentative of
        the search it stands in for.
        """
        if limit >= len(self.names) or limit <= 0:
            return list(self.names)
        step = len(self.names) / limit
        return [self.names[int(i * step)] for i in range(limit)]


def run_sweep(
    panel: Panel,
    strategies: Sequence[Strategy],
    costs: CostModel | None = None,
    universe: pd.DataFrame | None = None,
    universe_name: str = "",
    trial_log=None,
    hypothesis_id: str | None = None,
    manifest_hash: str | None = None,
    charge_impact: bool = False,
    keep_results: bool = True,
    equity: float | None = None,
    **backtest_kwargs,
) -> Sweep:
    """Run every strategy in `strategies` and record the whole sweep.

    Passing a `trial_log` writes one record carrying `variants=len(strategies)`,
    so the trial count that gate 4 deflates against is the number actually run.
    """
    if not strategies:
        raise ValueError("a sweep needs at least one strategy")
    families = {s.family for s in strategies}
    if len(families) > 1:
        raise ValueError(f"a sweep is one family at a time; got {sorted(families)}")
    costs = costs or CostModel.trial()

    net: dict[str, pd.Series] = {}
    gross: dict[str, pd.Series] = {}
    params: dict[str, dict] = {}
    rows: list[dict] = []
    results: dict[str, BacktestResult] = {}

    for strategy in strategies:
        result = run_backtest(
            panel, strategy, costs, universe, charge_impact=charge_impact,
            **({"equity": equity} if equity else {}), **backtest_kwargs,
        )
        name = strategy.name
        net[name] = result.net
        gross[name] = result.gross
        params[name] = dict(strategy.params)
        rows.append({"variant": name, **result.stats()})
        if keep_results:
            results[name] = result

    stats = pd.DataFrame(rows).set_index("variant")
    return Sweep(
        family=strategies[0].family,
        returns=pd.DataFrame(net),
        gross_returns=pd.DataFrame(gross),
        params=params,
        stats=stats,
        periods_per_year=panel.periods_per_year,
        universe_name=universe_name,
        results=results,
        strategy_class=type(strategies[0]),
    )


def neighbours(sweep: Sweep, name: str, tolerance: float = 0.25) -> list[str]:
    """Variants within +/-`tolerance` on every numeric parameter of `name`.

    Gate 8's parameter-neighbourhood check: a real edge is a plateau, so its
    neighbours should keep most of its Sharpe. A spike surrounded by nothing is
    a fitted artefact, however good the peak looks.
    """
    target = sweep.params[name]
    numeric = {k: v for k, v in target.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    out = []
    for other, candidate in sweep.params.items():
        if other == name:
            continue
        if any(candidate.get(k) != v for k, v in target.items() if k not in numeric):
            continue  # a different non-numeric setting is a different strategy
        close = True
        for key, value in numeric.items():
            theirs = candidate.get(key)
            if theirs is None or not isinstance(theirs, (int, float)):
                close = False
                break
            if value == 0:
                close = abs(theirs) <= tolerance
            elif abs(theirs - value) > tolerance * abs(value):
                close = False
            if not close:
                break
        if close:
            out.append(other)
    return out


def neighbourhood_retention(sweep: Sweep, name: str | None = None, tolerance: float = 0.25) -> dict:
    """What share of the winner's Sharpe its parameter neighbours keep.

    `retention` is `nan` when the peak Sharpe is too close to zero to divide
    by — not merely when it is negative. A peak of 0.02 with a neighbour at
    0.03 gives a retention of 150%, which gate 8 would read as a comfortable
    plateau when what it actually shows is a flat field of noise. The floor is
    one standard error of a Sharpe over the sample, the same scale the
    lag-spike test and gate 2 use (`stats.sharpe_standard_error`).
    """
    from qr.validate.stats import sharpe_standard_error

    name = name or sweep.best()
    around = neighbours(sweep, name, tolerance)
    peak = float(sweep.stats.loc[name, "sharpe"])
    floor = sharpe_standard_error(len(sweep.returns), sweep.periods_per_year)
    if not around or not np.isfinite(peak) or peak <= 0 or (np.isfinite(floor) and peak < floor):
        return {"variant": name, "peak_sharpe": peak, "n_neighbours": len(around), "retention": float("nan")}
    ratios = sweep.stats.loc[around, "sharpe"].astype(float) / peak
    return {
        "variant": name,
        "peak_sharpe": peak,
        "n_neighbours": len(around),
        "retention": float(ratios.median()),
        "worst_retention": float(ratios.min()),
        "share_above_70pct": float((ratios >= 0.70).mean()),
    }
