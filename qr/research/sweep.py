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

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import BacktestResult, run_backtest
from qr.strategies.base import Strategy


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

    def __len__(self) -> int:
        return self.returns.shape[1]

    @property
    def names(self) -> list[str]:
        return list(self.returns.columns)

    def best(self, by: str = "sharpe") -> str:
        """The variant a naive backtest would have reported. Named, not hidden."""
        return str(self.stats[by].idxmax())

    def best_result(self, by: str = "sharpe") -> BacktestResult:
        return self.results[self.best(by)]

    def param_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.params).T.reindex(self.names)

    def sharpes(self) -> pd.Series:
        return self.stats["sharpe"]

    def per_period_sharpes(self) -> pd.Series:
        """Per-period Sharpes — what the deflation formulas want as a variance."""
        return self.stats["sharpe"] / np.sqrt(self.periods_per_year)


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
        result = run_backtest(panel, strategy, costs, universe, charge_impact=charge_impact)
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
    """What share of the winner's Sharpe its parameter neighbours keep."""
    name = name or sweep.best()
    around = neighbours(sweep, name, tolerance)
    peak = float(sweep.stats.loc[name, "sharpe"])
    if not around or not np.isfinite(peak) or peak <= 0:
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
