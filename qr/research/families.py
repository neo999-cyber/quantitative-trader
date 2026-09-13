"""The four trial families, bound to their pre-registration documents.

The grid defined here **is** the grid the pre-registration declares, and a test
parses the variant count out of each document and checks it matches. That
coupling is the point: a parameter range quietly widened in code after the
prediction was registered is the most comfortable form of p-hacking there is,
because nothing looks wrong at any single step.

`qr families` runs all four, each with its own registered grid and the same
frozen cost model, universe and holdout.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from qr.config import REPO_ROOT
from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.sweep import Sweep, run_sweep
from qr.strategies.base import Strategy
from qr.strategies.library import (
    BuyAndHold,
    CrossSectionalMomentum,
    LongShortMomentum,
    RSIReversal,
    ShortTermReversal,
    TSMOM,
)
from qr.validate.gates import GateContext, GateReport, GateThresholds, run_gates
from qr.validate.trial_log import TrialLog

PREREG_DIR = REPO_ROOT / "docs" / "prereg"


@dataclass(frozen=True)
class FamilySpec:
    """One registered hypothesis: what to run, and where the prediction lives."""

    hypothesis_id: str
    strategy_class: type[Strategy]
    grid: dict[str, Sequence[Any]]
    summary: str
    control: bool = False

    @property
    def prereg_path(self) -> Path:
        return PREREG_DIR / f"{self.hypothesis_id}.md"

    @property
    def n_variants(self) -> int:
        return math.prod(len(values) for values in self.grid.values())

    @property
    def swept_parameters(self) -> list[str]:
        return sorted(k for k, v in self.grid.items() if len(v) > 1)

    def strategies(self) -> list[Strategy]:
        return self.strategy_class.grid(**{k: list(v) for k, v in self.grid.items()})

    def declared_variants(self) -> int | None:
        """The variant count the pre-registration document claims, if it says."""
        if not self.prereg_path.exists():
            return None
        match = re.search(r"\*\*([\d,]+) variants?\b", self.prereg_path.read_text(encoding="utf-8"))
        return int(match.group(1).replace(",", "")) if match else None


#: The four families of the one-week trial. Three hypotheses and one control.
TRIAL_FAMILIES: list[FamilySpec] = [
    FamilySpec(
        hypothesis_id="tsmom_v1",
        strategy_class=TSMOM,
        grid={"lookback": list(range(10, 210, 5)), "skip": [0, 2, 5, 10, 20]},
        summary="time-series momentum, vol-targeted",
    ),
    FamilySpec(
        hypothesis_id="xsmom_v1",
        strategy_class=CrossSectionalMomentum,
        grid={
            "lookback": [30, 60, 90, 120, 180, 252],
            "skip": [0, 5, 10, 21],
            "n_long": [3, 5, 8],
            "rebalance": [7, 14],
        },
        summary="cross-sectional momentum, 12-1 convention",
    ),
    FamilySpec(
        hypothesis_id="reversal_v1",
        strategy_class=ShortTermReversal,
        grid={"lookback": [3, 5, 7, 10, 14, 21], "n_long": [3, 5, 8], "rebalance": [3, 7, 14]},
        summary="weekly short-term reversal",
    ),
    FamilySpec(
        hypothesis_id="rsi_reversal_v1",
        strategy_class=RSIReversal,
        grid={"down_days": [2, 3, 4], "rsi_max": [25.0, 30.0, 35.0], "hold": [3, 5, 10]},
        summary="3-down-day RSI setup (the control, expected to fail)",
        control=True,
    ),
]

#: The ETF trial's four families, registered in `docs/prereg/etf_*.md`. Three
#: hypotheses and one control, and the control is the interesting change: the
#: crypto trial's cleanest finding was that none of 425 configurations beat
#: buy-and-hold, so buy-and-hold is here as a fully gated hypothesis rather
#: than as a benchmark computed inside gate 5 where it never faces gate 3, gate
#: 6 or the holdout.
#:
#: Every grid carries `rebalance_on`, which the crypto families do not have and
#: could not afford to need. A venue charging per order rather than per dollar
#: makes the trading *calendar* a first-class parameter: the same strategy
#: rebalanced daily rather than monthly pays four times the commission at this
#: account size, which is the difference between a live strategy and a donation.
ETF_FAMILIES: list[FamilySpec] = [
    FamilySpec(
        hypothesis_id="etf_tsmom_v1",
        strategy_class=TSMOM,
        grid={
            "lookback": [60, 90, 120, 180, 252],
            "skip": [0, 5, 20],
            "vol_lookback": [30, 60],
            "vol_target": [0.10],
            "max_leverage": [1.0],
            "rebalance_on": ["MS"],
        },
        summary="multi-asset time-series momentum, monthly",
    ),
    FamilySpec(
        hypothesis_id="etf_xsmom_v1",
        strategy_class=CrossSectionalMomentum,
        grid={
            "lookback": [60, 120, 180, 252],
            "n_long": [3, 4, 6],
            "skip": [0],
            "rebalance": [21],
            "vol_lookback": [60],
            "vol_target": [0.10],
            "max_leverage": [1.0],
        },
        summary="cross-sectional rotation across asset classes, monthly",
    ),
    FamilySpec(
        hypothesis_id="etf_reversal_v1",
        strategy_class=ShortTermReversal,
        grid={
            "lookback": [3, 5, 10, 21],
            "n_long": [2, 3, 4],
            "rebalance": [5],
            "vol_lookback": [60],
            "vol_target": [0.10],
            "max_leverage": [1.0],
        },
        summary="short-term reversal on ETFs, weekly",
    ),
    FamilySpec(
        hypothesis_id="etf_buyhold_v1",
        strategy_class=BuyAndHold,
        grid={"gross": [1.0], "rebalance_on": ["MS"]},
        summary="equal-weighted basket, monthly (the control)",
        control=True,
    ),
]

#: Phase two of the ETF work, and the first family in the project whose claim
#: is not market exposure. Kept in its own list rather than appended to
#: `ETF_FAMILIES` because it is a separate trial with a separate cost model —
#: it shorts, so it carries a borrow fee and is priced at $10,000, an account
#: that may legally hold a short book.
LONG_SHORT_FAMILIES: list[FamilySpec] = [
    FamilySpec(
        hypothesis_id="ls_xsmom_v1",
        strategy_class=LongShortMomentum,
        grid={
            "lookback": [60, 120, 180, 252],
            "n_side": [2, 3, 4],
            "skip": [21],
            "rebalance_on": ["MS"],
            "vol_target": [0.10],
            "vol_lookback": [60],
            "max_leverage": [1.0],
        },
        summary="dollar-neutral cross-sectional momentum, monthly",
    ),
]

BY_ID = {
    spec.hypothesis_id: spec
    for spec in TRIAL_FAMILIES + ETF_FAMILIES + LONG_SHORT_FAMILIES
}


@dataclass
class FamilyRun:
    """One family's sweep and gate report."""

    spec: FamilySpec
    sweep: Sweep
    report: GateReport
    best_variant: str

    def row(self, trial_log: TrialLog | None = None) -> dict[str, Any]:
        from qr.validate.report import headline_verdict

        verdict, _ = headline_verdict(self.report, trial_log)
        stopped = self.report.stopped_at
        stats = self.sweep.results[self.best_variant].stats()
        return {
            "hypothesis": self.spec.hypothesis_id,
            "control": "yes" if self.spec.control else "",
            "variants": self.spec.n_variants,
            "verdict": verdict,
            "stopped_at": stopped.number if stopped else None,
            "best_variant_sharpe": round(stats["sharpe"], 3),
            "net_over_gross": round(stats["net_over_gross"], 3) if pd.notna(stats["net_over_gross"]) else None,
            "round_trips": int(stats["round_trips"]),
        }


def run_family(
    spec: FamilySpec,
    panel: Panel,
    costs: CostModel | None = None,
    universe: pd.DataFrame | None = None,
    universe_name: str = "binance_spot_top30",
    trial_log: TrialLog | None = None,
    manifest_hash: str | None = None,
    holdout_panel: Panel | None = None,
    holdout_universe: pd.DataFrame | None = None,
    thresholds: GateThresholds | None = None,
    permutations: int = 200,
    vol_preserving_permutations: int | None = None,
    progress=None,
    equity: float | None = None,
    calendar: str = "continuous",
    upto: int = 11,
    stop_on_fail: bool = True,
) -> FamilyRun:
    """Sweep one family's registered grid and run it through the gates."""
    costs = costs or CostModel.trial()
    strategies = spec.strategies()
    kw = {"equity": equity} if equity else {}
    sweep = run_sweep(panel, strategies, costs, universe, universe_name, **kw)

    if trial_log is not None:
        trial_log.run(
            spec.hypothesis_id,
            family=sweep.family,
            params={"grid": {k: list(v) for k, v in spec.grid.items()}},
            universe=universe_name,
            metrics={"best_sharpe": float(sweep.sharpes().max())},
            variants=spec.n_variants,
            manifest_hash=manifest_hash,
        )

    best = sweep.best()
    context = GateContext(
        hypothesis_id=spec.hypothesis_id,
        panel=panel,
        strategy=next(s for s in strategies if s.name == best),
        costs=costs,
        result=sweep.results[best],
        sweep=sweep,
        universe=universe,
        trial_log=trial_log,
        manifest_hash=manifest_hash,
        holdout_panel=holdout_panel,
        holdout_universe=holdout_universe,
        thresholds=thresholds or GateThresholds(),
        permutations=permutations,
        vol_preserving_permutations=vol_preserving_permutations,
        equity=equity,
        calendar=calendar,
    )
    return FamilyRun(spec, sweep, run_gates(context, upto=upto, stop_on_fail=stop_on_fail, progress=progress), best)


def summarise(runs: Sequence[FamilyRun], trial_log: TrialLog | None = None) -> pd.DataFrame:
    return pd.DataFrame([run.row(trial_log) for run in runs])
