"""The synthetic self-test: does the validation engine actually work?

Every gate in this package is a claim about what it can detect. Those claims
are worth exactly nothing until the engine is pointed at data whose right
answer is known in advance, so this module builds two worlds:

* **`noise_world()`** — geometric random walks. There is no edge. A strategy
  family searched over 200 variants will nonetheless produce a winner with a
  handsome in-sample Sharpe, because searching 200 variants of anything does.
  The engine **must fail it**, and gates 4 *and* 5 must both be among the
  failures: the rejection has to come from pricing the search and from
  measuring the selection, not from an incidental threshold elsewhere. A noise
  winner often also trips gate 3 on its raw t-statistic, and an engine relying
  on that would wave through the next one whose t happened to land higher.

* **`edge_world()`** — the same volatility with genuine serial dependence
  planted in it, so a trend follower has something real to find. The engine
  **must pass it** through gate 8. The edge is calibrated to an annual Sharpe
  of about 1.7: good, but not so obvious that passing it proves nothing.

A pipeline that fails the first test is dangerous — it will certify noise. One
that fails the second is merely useless — it rejects everything, which at least
loses money slowly. Both are bugs, and `run_selftest()` reports either.

This is the single most important test in the repository. Nothing that comes
out of the gates means anything if it does not hold.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.research.sweep import Sweep, run_sweep
from qr.strategies.base import Strategy
from qr.strategies.library import TSMOM
from qr.validate.gates import FAIL, PASS, WARN, GateContext, GateReport, GateThresholds, run_gates
from qr.validate.trial_log import TrialLog

#: The gates whose job it is to catch a searched-over-noise winner: gate 4
#: prices the search, gate 5 measures whether selecting the winner told you
#: anything. The self-test insists **both** reject the noise world, which is
#: why the noise world always runs every gate rather than stopping at the
#: first failure.
DEFLATION_GATES = (4, 5)
DEFLATION_GATES_SET = set(DEFLATION_GATES)


def _panel_from_returns(
    returns: np.ndarray, index: pd.DatetimeIndex, symbols: Sequence[str], start_price: float = 100.0
) -> Panel:
    frames = {}
    for j, symbol in enumerate(symbols):
        close = start_price * np.exp(np.cumsum(returns[:, j]))
        frames[symbol] = pd.DataFrame(
            {
                "open": np.concatenate([[start_price], close[:-1]]),
                "high": close * 1.005,
                "low": close * 0.995,
                "close": close,
                "volume": 1e4,
                "quote_volume": 1e8,
                "trades": 500.0,
            },
            index=index,
        )
    return Panel.from_frames(frames)


def noise_world(
    n_symbols: int = 8, years: int = 6, vol: float = 0.04, seed: int = 0, drift: float = 0.0
) -> Panel:
    """Geometric random walks: no serial dependence, therefore no edge."""
    index = pd.date_range("2019-01-01", periods=int(years * 365), freq="D", tz="UTC")
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, vol, (len(index), n_symbols))
    return _panel_from_returns(returns, index, [f"N{i}USDT" for i in range(n_symbols)])


def edge_world(
    n_symbols: int = 8,
    years: int = 6,
    vol: float = 0.03,
    persistence: float = 0.97,
    strength: float = 0.10,
    seed: int = 0,
) -> Panel:
    """The same volatility with a slow-moving drift: real, findable momentum.

    Returns are shock plus an AR(1) state driven by the same shocks, so past
    returns genuinely predict future ones. This is what a trend follower claims
    exists in markets; here it is put there on purpose.

    `strength` is calibrated so a good TSMOM variant earns an annual Sharpe of
    roughly **1.7** — excellent but attainable. An earlier default planted an
    edge worth Sharpe 21, which every gate waved through and which therefore
    tested nothing: an engine that only recognises unmissable edges would pass
    that self-test and still reject everything real.
    """
    index = pd.date_range("2019-01-01", periods=int(years * 365), freq="D", tz="UTC")
    rng = np.random.default_rng(seed)
    n = len(index)
    returns = np.zeros((n, n_symbols))
    for j in range(n_symbols):
        shocks = rng.normal(0.0, vol, n)
        state = 0.0
        for t in range(n):
            state = persistence * state + (1.0 - persistence) * shocks[t] * strength
            returns[t, j] = state + shocks[t]
    return _panel_from_returns(returns, index, [f"E{i}USDT" for i in range(n_symbols)])


def default_grid(n_variants: int = 200) -> list[Strategy]:
    """A TSMOM grid of roughly `n_variants` configurations.

    The point of 200 is that it is a realistic amount of searching, and enough
    that the best-of-200 in-sample Sharpe on pure noise looks convincing.
    """
    lookbacks = list(range(10, 210, 5))  # 40
    skips = [0, 2, 5, 10, 20]  # 5  -> 200
    grid = TSMOM.grid(lookback=lookbacks, skip=skips)
    return grid[:n_variants]


@dataclass
class SelfTestCase:
    """One world, its sweep, and the gate report the engine produced."""

    name: str
    expected: str
    report: GateReport
    sweep: Sweep
    best_variant: str
    in_sample_sharpe: float

    @property
    def actual(self) -> str:
        return self.report.verdict

    @property
    def stopped_at(self) -> int | None:
        stopped = self.report.stopped_at
        return stopped.number if stopped else None

    @property
    def failed_gates(self) -> set[int]:
        return {r.number for r in self.report.results if r.verdict == FAIL}

    @property
    def passed(self) -> bool:
        if self.expected == FAIL:
            # Rejecting noise is not enough: the **deflation** gates have to be
            # the ones doing it. A searched-over-noise winner will often also
            # trip gate 3 on its raw t-statistic, and an engine that caught it
            # only there would be relying on a threshold rather than on pricing
            # the search — and would wave through the next noise winner whose
            # t-statistic happened to land above 3.
            return self.actual == FAIL and DEFLATION_GATES_SET <= self.failed_gates
        return self.actual in {PASS, WARN}

    def describe(self) -> dict[str, object]:
        return {
            "world": self.name,
            "expected": self.expected,
            "actual": self.actual,
            "failed_gates": sorted(self.failed_gates) or None,
            "deflation_caught_it": DEFLATION_GATES_SET <= self.failed_gates,
            "best_variant": self.best_variant,
            "in_sample_sharpe": round(self.in_sample_sharpe, 3),
            "self_test": "OK" if self.passed else "BROKEN",
        }


@dataclass
class SelfTestReport:
    cases: list[SelfTestCase] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(case.passed for case in self.cases)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([case.describe() for case in self.cases])

    def failure_summary(self) -> str:
        broken = [c for c in self.cases if not c.passed]
        if not broken:
            return ""
        lines = []
        for case in broken:
            stopped = case.report.stopped_at
            lines.append(
                f"{case.name}: expected {case.expected}, got {case.actual}"
                + (f" (stopped at gate {stopped.number}: {stopped.detail})" if stopped else "")
            )
        return "\n".join(lines)


def _run_world(
    name: str,
    panel: Panel,
    expected: str,
    grid: Sequence[Strategy],
    costs: CostModel,
    trial_log: TrialLog | None,
    permutations: int,
    thresholds: GateThresholds,
    stop_on_fail: bool,
) -> SelfTestCase:
    hypothesis_id = f"selftest_{name}"
    if trial_log is not None:
        trial_log.prereg(
            hypothesis_id,
            f"Self-test world {name!r}: TSMOM over {len(grid)} variants. "
            f"Expected verdict {expected}.",
        )
    sweep = run_sweep(panel, list(grid), costs, universe_name=f"selftest_{name}")
    if trial_log is not None:
        trial_log.run(
            hypothesis_id,
            family=sweep.family,
            params={"grid": f"{len(grid)} variants"},
            universe=sweep.universe_name,
            metrics={"best_sharpe": float(sweep.sharpes().max())},
            variants=len(grid),
        )

    best = sweep.best()
    context = GateContext(
        hypothesis_id=hypothesis_id,
        panel=panel,
        strategy=next(s for s in grid if s.name == best),
        costs=costs,
        result=sweep.results[best],
        sweep=sweep,
        trial_log=trial_log,
        thresholds=thresholds,
        permutations=permutations,
    )
    # A world expected to fail always runs every gate: the point is not that
    # something rejected it but that deflation and selection did, and a run
    # that stops at gate 3 cannot show that.
    report = run_gates(context, upto=8, stop_on_fail=stop_on_fail and expected != FAIL)
    return SelfTestCase(
        name=name,
        expected=expected,
        report=report,
        sweep=sweep,
        best_variant=best,
        in_sample_sharpe=float(sweep.stats.loc[best, "sharpe"]),
    )


def run_selftest(
    n_variants: int = 200,
    costs: CostModel | None = None,
    trial_log: TrialLog | None = None,
    permutations: int = 100,
    thresholds: GateThresholds | None = None,
    seed: int = 0,
    stop_on_fail: bool = True,
) -> SelfTestReport:
    """Run both worlds through the gates and check the engine got them right."""
    costs = costs or CostModel.trial()
    thresholds = thresholds or GateThresholds()
    grid = default_grid(n_variants)

    return SelfTestReport(
        [
            _run_world(
                "noise", noise_world(seed=seed), FAIL, grid, costs, trial_log, permutations, thresholds, stop_on_fail
            ),
            _run_world(
                "planted_edge", edge_world(seed=seed), PASS, grid, costs, trial_log, permutations, thresholds, stop_on_fail
            ),
        ]
    )
