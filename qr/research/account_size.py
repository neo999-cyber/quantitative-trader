"""Step 0 of `docs/10_NEXT.md`: are the nine families failing on their merits,
or because $1,000 makes them uneconomic?

Nine pre-registered families have been run and none has passed gate 5. Two
readings of that fit the evidence. Either the ideas are bad, or the account is
too small to trade them — the ETF trial found IBKR's $0.35 per-order floor
eating 94% of a weekly strategy's gross return, which is a cost of *being
small*, not a verdict on the strategy. The two readings imply different
projects for the next six months: finding ideas, or finding capital.

So: re-score every family at $1,000 / $10,000 / $100,000. Same variants, same
data, same everything — only the account size the cost model prices orders
against changes.

**This is a sensitivity analysis on one cost parameter, not a search.** Three
things follow, and all three are enforced here rather than promised:

* Nothing is written to the trial log. The log is opened `SealedTrialLog`, so
  gate 0 can still read the pre-registration and gate 11 the holdout, and no
  `run` record inflates the count gate 4 deflates against. Re-running a known
  family with a different fee is not a new trial and must not be charged as
  one.
* No verdict is produced. `verdict()` returns a *reading* — "cost-bound",
  "cost-free", "unchanged" — never PASS. The ETF holdout was opened once and
  is spent; a family that looks better at $100,000 has earned a place in the
  next round of pre-registration and nothing else.
* Only the size-sensitive gates run: 2 (cost survival), 3, 4, 5 (selection,
  which carries the SPA test against buy-and-hold that every family has
  failed), and 11 (sizing, the one gate whose whole output is a function of
  account size). Gates 0 and 1 do not depend on equity and were run already;
  6 and 7 cost hours and would answer a question nobody asked here.

What to expect, written down so the result can disagree with it
---------------------------------------------------------------

For the crypto families the answer is **exactly nothing**, and by construction
rather than by measurement. `CostModel.trial()` is purely proportional — 7.5
bps of fee and 2 bps of half-spread per side, no per-order floor — and the
family sweeps do not charge impact, so `run_backtest` never even consults the
account size (`needs_equity` is false). Every number in the crypto rows must
be identical across the three columns, to the last bit. If any of them moves,
the cost model has a size dependence nobody declared and *that* is the finding,
not whatever the Sharpe did.

For the ETF families the commission is per share with a floor per order, so
cost in basis points falls with size and the rows must improve monotonically.
The question is whether any of them crosses from "costs eat the edge" to "an
edge is there and costs no longer hide it" — and, separately, whether the SPA
test against buy-and-hold moves at all, because a family that still cannot
beat holding the basket at $100,000 was never a cost problem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.families import FamilySpec
from qr.research.sweep import Sweep, run_sweep
from qr.validate.gates import GateContext, GateReport, gate_11_sizing, run_gates
from qr.validate.trial_log import SealedTrialLog, TrialLog

#: The three account sizes. $1,000 is the account that exists; $10,000 is the
#: smallest that may legally hold a short book; $100,000 is well past the point
#: where a per-order floor can matter, and is there to bound the answer rather
#: than because anyone expects to fund it.
ACCOUNT_SIZES: tuple[float, ...] = (1_000.0, 10_000.0, 100_000.0)

#: The gates that can move when only the account size moves. 2 and 11 depend on
#: it directly; 3, 4 and 5 depend on it through the net returns.
SIZE_SENSITIVE_GATES: tuple[int, ...] = (2, 3, 4, 5, 11)


def costs_for(asset: str, equity: float) -> CostModel:
    """The frozen cost model for one asset class, priced at one account size.

    The crypto model takes no equity argument because it has nowhere to put
    one: a Binance taker pays the same basis points on a $10 order and a
    $10,000 order. That asymmetry is the whole subject of this sweep, so it is
    stated in the code that builds the models rather than in a comment
    somewhere downstream.
    """
    if asset == "crypto":
        return CostModel.trial()
    if asset == "etf":
        return CostModel.etf_trial(equity)
    if asset == "etf-ls":
        return CostModel.etf_long_short(equity)
    raise ValueError(f"unknown asset class {asset!r}; known: crypto, etf, etf-ls")


@dataclass(frozen=True)
class SizeRun:
    """One family, re-scored at one account size."""

    hypothesis_id: str
    asset: str
    equity: float
    sweep: Sweep
    report: GateReport
    best_variant: str

    def gate(self, number: int) -> str:
        """This gate's verdict, or "-" if it did not run."""
        found = next((r for r in self.report.results if r.number == number), None)
        return found.verdict if found is not None else "-"

    def gate_stat(self, number: int, key: str) -> float:
        found = next((r for r in self.report.results if r.number == number), None)
        value = found.stats.get(key) if found is not None else None
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return float("nan")

    def row(self) -> dict[str, object]:
        stats = self.sweep.results[self.best_variant].stats()
        return {
            "hypothesis": self.hypothesis_id,
            "asset": self.asset,
            "equity": self.equity,
            "best_variant": self.best_variant,
            "gross_sharpe": stats["gross_sharpe"],
            "net_sharpe": stats["sharpe"],
            "net_over_gross": stats["net_over_gross"],
            "cost_drag_ann": stats["cost_drag_ann"],
            "ann_turnover": stats["ann_turnover"],
            "gate2": self.gate(2),
            "gate3": self.gate(3),
            "gate4": self.gate(4),
            "gate5": self.gate(5),
            "spa_p": self.gate_stat(5, "spa_p_consistent"),
            "gate11": self.gate(11),
            "leverage": self.gate_stat(11, "leverage"),
        }


@dataclass
class SizeSweep:
    """Every family at every account size, and what the comparison says."""

    runs: list[SizeRun] = field(default_factory=list)
    sizes: tuple[float, ...] = ACCOUNT_SIZES

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame([run.row() for run in self.runs])

    def by_hypothesis(self, hypothesis_id: str) -> list[SizeRun]:
        runs = [r for r in self.runs if r.hypothesis_id == hypothesis_id]
        return sorted(runs, key=lambda r: r.equity)

    def hypotheses(self) -> list[str]:
        seen: list[str] = []
        for run in self.runs:
            if run.hypothesis_id not in seen:
                seen.append(run.hypothesis_id)
        return seen

    def readings(self) -> pd.DataFrame:
        """One row per family: what moved with size, and what it means."""
        return pd.DataFrame([self._reading(h) for h in self.hypotheses()])

    def _reading(self, hypothesis_id: str) -> dict[str, object]:
        runs = self.by_hypothesis(hypothesis_id)
        smallest, largest = runs[0], runs[-1]
        sharpes = [r.sweep.results[r.best_variant].stats()["sharpe"] for r in runs]
        survival = [r.sweep.results[r.best_variant].stats()["net_over_gross"] for r in runs]
        return {
            "hypothesis": hypothesis_id,
            "asset": smallest.asset,
            "net_sharpe_small": sharpes[0],
            "net_sharpe_large": sharpes[-1],
            "net_over_gross_small": survival[0],
            "net_over_gross_large": survival[-1],
            "gate2_small": smallest.gate(2),
            "gate2_large": largest.gate(2),
            "gate5_small": smallest.gate(5),
            "gate5_large": largest.gate(5),
            "reading": reading(runs),
        }


def _invariant(runs: Sequence[SizeRun], tolerance: float = 1e-12) -> bool:
    """Did the net return series stay bit-identical across the sizes?"""
    first = runs[0].sweep.results[runs[0].best_variant].net
    for run in runs[1:]:
        other = run.sweep.results[run.best_variant].net
        if run.best_variant != runs[0].best_variant or len(other) != len(first):
            return False
        if float(np.nanmax(np.abs(other.to_numpy() - first.to_numpy()))) > tolerance:
            return False
    return True


def reading(runs: Sequence[SizeRun]) -> str:
    """What this family's three rows say — a reading, deliberately not a verdict.

    The vocabulary is small on purpose, because the decision this sweep feeds
    is binary: is the next six months about finding ideas, or finding capital?

    * ``size-independent`` — the numbers did not move at all. Only possible
      where the cost model has no size term, and where it is possible it is the
      *expected* answer; seeing it anywhere else means something is wrong.
    * ``cost-bound`` — costs ate the edge at the small account and stopped at
      the large one. The family has not been shown to work; it has been shown
      that the small account cannot afford to find out.
    * ``cheaper, still failing`` — costs fell, as they must, and the family
      still does not clear the gates. Account size was not the binding
      constraint and the idea is the problem.
    * ``worse with size`` — should be impossible. Report it as a defect.
    """
    if _invariant(runs):
        return "size-independent"
    small, large = runs[0], runs[-1]
    small_sharpe = small.sweep.results[small.best_variant].stats()["sharpe"]
    large_sharpe = large.sweep.results[large.best_variant].stats()["sharpe"]
    if np.isfinite(small_sharpe) and np.isfinite(large_sharpe) and large_sharpe < small_sharpe - 1e-9:
        return "worse with size — check the cost model"
    if small.gate(2) == "FAIL" and large.gate(2) != "FAIL":
        return "cost-bound"
    return "cheaper, still failing"


def run_size_sweep(
    spec: FamilySpec,
    panel: Panel,
    universe: pd.DataFrame | None,
    universe_name: str,
    asset: str,
    trial_log: TrialLog | None = None,
    manifest_hash: str | None = None,
    sizes: Sequence[float] = ACCOUNT_SIZES,
    calendar: str = "continuous",
    progress: Callable[[str], None] | None = None,
) -> list[SizeRun]:
    """Re-score one family at each account size. Writes nothing to the log."""
    sealed = SealedTrialLog(trial_log.path) if trial_log is not None else None
    runs: list[SizeRun] = []
    for equity in sizes:
        costs = costs_for(asset, equity)
        if progress is not None:
            progress(f"  {spec.hypothesis_id} at ${equity:,.0f} ({costs.name})…")
        # The account size reaches the backtest only through `equity`; the
        # strategies, the panel and the universe are the objects the original
        # run used. That is what makes this a one-parameter sensitivity rather
        # than a second search.
        sweep = run_sweep(
            panel,
            spec.strategies(),
            costs,
            universe,
            universe_name,
            equity=equity,
        )
        best = sweep.best()
        context = GateContext(
            hypothesis_id=spec.hypothesis_id,
            panel=panel,
            strategy=next(s for s in spec.strategies() if s.name == best),
            costs=costs,
            result=sweep.results[best],
            sweep=sweep,
            universe=universe,
            trial_log=sealed,
            manifest_hash=manifest_hash,
            equity=equity,
            calendar=calendar,
        )
        report = run_gates(context, upto=5, skip=(0, 1), stop_on_fail=False, progress=progress)
        # Gate 11 is the one gate whose entire output is a function of the
        # account size, and `run_gates` cannot reach it without also paying for
        # gates 6 to 10, which no account size can change. It SKIPs unless
        # gate 9 opened a holdout, which is the correct behaviour here too:
        # this sweep must not put a number on a family that has no
        # out-of-sample Sharpe to size from.
        report.results.append(gate_11_sizing(context))
        runs.append(SizeRun(spec.hypothesis_id, asset, float(equity), sweep, report, best))
    return runs
