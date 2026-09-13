"""Stage 3 of `docs/10_NEXT.md`: cheap kill tests, in the sandbox.

A memo that survives triage has a named payer and a runnable crude version.
This stage runs that crude version **on the discovery side only** and asks
three questions, in order, stopping at the first no:

* Does the effect exist at all?
* Is it at least **3x** trading costs? Not 1.2x — that lesson was expensive
  and is written up in `docs/08`.
* Does the turnover survive the per-order floor at the account size Step 0
  found?

Three properties are worth stating because each one was a mistake available to
make here.

**It runs on the sandbox, and the sandbox alone.** The whole point of Stage 1
is that looking is free *there*. A kill test that peeked at validation data
would spend the evidence it exists to protect, so `run()` refuses a panel that
is not stamped `discovery` rather than trusting its caller to have passed the
right one.

**It is not a gate and its numbers are not results.** Nothing here is
deflated, permuted, cross-validated or compared to buy-and-hold. A candidate
that passes has earned a pre-registration, which is where the actual test
starts. The gap between "survived the kill tests" and "has an edge" is the
entire validation engine, and a kill-test number quoted as though it were a
verdict is the most likely way this stage does damage.

**The bar is deliberately blunt.** The third of a strategy's gross return that
a marginal cost model would argue about is not the question; the question is
whether the effect is in a different league from its costs. An idea that needs
a careful cost model to look viable will not survive gate 2, so killing it here
for a few seconds of compute is strictly cheaper than finding out later.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.data.sandbox import sandbox_side
from qr.execution.costs import CostModel
from qr.research.mechanism import MechanismMemo
from qr.research.policy import ResearchPolicy
from qr.research.runner import run_backtest
from qr.validate.trial_log import TrialLog


@dataclass(frozen=True)
class KillTest:
    """What Stage 3 found. `passed` is the only field a caller should branch on."""

    candidate_id: str
    passed: bool
    failed_at: str = ""
    reason: str = ""
    stats: dict[str, Any] = field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate_id,
            "passed": self.passed,
            "failed_at": self.failed_at,
            **{k: v for k, v in self.stats.items() if not isinstance(v, dict)},
        }


def _per_trade_edge_bps(gross_return: float, round_trips: float) -> float:
    """Gross return per round trip, in basis points.

    This is the number the 3x bar is applied to, and it is the right one:
    costs are paid per trade, so an effect worth 40 bps a year is a different
    proposition when it comes from four trades than from four hundred. Dividing
    the whole-period gross return by the whole-period round trips keeps the two
    on the same footing without needing a per-trade attribution the crude
    version cannot supply.
    """
    if round_trips <= 0:
        return float("nan")
    return (gross_return / round_trips) / 1e-4


def run(
    memo: MechanismMemo,
    panel: Panel,
    policy: ResearchPolicy,
    costs: CostModel | None = None,
    universe: pd.DataFrame | None = None,
    equity: float | None = None,
) -> KillTest:
    """Run the memo's crude version in the sandbox and decide whether it lives."""
    side = sandbox_side(panel)
    if side != "discovery":
        raise ValueError(
            "kill tests run on the discovery sandbox and nowhere else; this panel is stamped "
            f"{side or 'nothing'}. Exploration is free there precisely because it is confined "
            "to there — see qr/data/sandbox.py."
        )

    costs = costs or CostModel.trial()
    strategy = memo.crude_version.build()
    kwargs = {"equity": equity} if equity else {}
    result = run_backtest(panel, strategy, costs, universe, **kwargs)
    stats = result.stats()

    gross_total = float((1.0 + result.gross).prod() - 1.0)
    round_trips = float(stats["round_trips"])
    edge_bps = _per_trade_edge_bps(gross_total, round_trips)
    round_trip_cost_bps = 2.0 * costs.linear_bps
    expected_positive = memo.crude_version.expected_sign == "positive"

    common = {
        "gross_total_return": gross_total,
        "gross_sharpe": stats["gross_sharpe"],
        "net_sharpe": stats["sharpe"],
        "round_trips": round_trips,
        "edge_bps_per_round_trip": edge_bps,
        "round_trip_cost_bps": round_trip_cost_bps,
        "cost_multiple": edge_bps / round_trip_cost_bps if round_trip_cost_bps else float("nan"),
        "ann_turnover": stats["ann_turnover"],
        "net_over_gross": stats["net_over_gross"],
        "bars": stats["bars"],
        "sandbox_side": side,
    }

    # 1. Does it exist at all — and in the direction the memo committed to?
    #    The sign check is what stops a memo being retrofitted to its result:
    #    "forced buying lifts prices into month end" and "forced selling
    #    depresses them" are different claims with different payers, and a
    #    candidate that predicted one and found the other has been refuted,
    #    not confirmed with a minus sign.
    if round_trips < 1:
        return KillTest(memo.candidate_id, False, "exists", "the crude version never traded", common)
    if not np.isfinite(gross_total) or (gross_total > 0) != expected_positive:
        return KillTest(
            memo.candidate_id,
            False,
            "exists",
            f"memo predicted a {memo.crude_version.expected_sign} effect; gross return is "
            f"{gross_total:+.2%}. A sign flip is a refutation, not a discovery.",
            common,
        )

    # 2. Is it in a different league from its costs?
    if abs(edge_bps) < policy.min_cost_multiple * round_trip_cost_bps:
        return KillTest(
            memo.candidate_id,
            False,
            "costs",
            f"{abs(edge_bps):.1f} bps per round trip against {round_trip_cost_bps:.1f} bps of "
            f"cost — {abs(edge_bps) / round_trip_cost_bps:.1f}x, and the bar is "
            f"{policy.min_cost_multiple:.0f}x.",
            common,
        )

    # 3. Does anything survive the costs actually charged? `net_over_gross` is
    #    gate 2's headline and it is free to compute here, so a candidate that
    #    would die at gate 2 dies now instead.
    survival = stats["net_over_gross"]
    if not np.isfinite(survival) or survival <= 0:
        return KillTest(
            memo.candidate_id,
            False,
            "floor",
            "costs take the whole gross return at this account size",
            common,
        )

    return KillTest(
        memo.candidate_id,
        True,
        "",
        f"{abs(edge_bps):.1f} bps per round trip on {round_trips:.0f} trips, "
        f"{abs(edge_bps) / round_trip_cost_bps:.1f}x costs, {survival:.0%} of gross surviving",
        common,
    )


def record(log: TrialLog, test: KillTest):
    """Into the chain, passed or failed.

    A failed kill test is the cheapest result this project produces and one of
    the most reusable: it is why a candidate was not promoted, and without it
    the same idea returns next month looking new.
    """
    return log.append(
        "killtest",
        test.candidate_id,
        {"passed": test.passed, "failed_at": test.failed_at, "reason": test.reason, "stats": test.stats},
    )
