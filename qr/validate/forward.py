"""The forward record: what happened after the research stopped.

Every gate before this one is an argument about the past. Gate 10 is the only
one that can be wrong in a way that costs money, because it is the only one
looking at bars nobody had when the strategy was written.

It answers three questions, and they fail for different reasons:

- **Did we build what we researched?** The live system's target weights,
  bar by bar, against what the research code says they should have been. A
  mismatch here is a defect, not a decay, and no amount of further
  incubation fixes it.
- **Did it cost what we said it would?** Realised cost against the cost
  model's forecast. The cost model decided gate 2 for every family this
  project has run; if it is optimistic by a third in the real world, gate 2
  was measuring a fiction.
- **Is the edge still there?** Forward Sharpe against in-sample Sharpe.

The third is the one people mean by "paper trading" and the weakest of the
three: three months of daily bars cannot establish that a Sharpe of 0.7 is
real. It can establish that it is gone. Gate 10 is built to refute, not to
bless, and says so in its own verdict text.

The observations live in the same hash-chained trial log as the backtests,
because the failure mode of an incubation record is the operator forgetting
the bad fortnight.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from qr.validate.trial_log import TrialLog


def frame(log: TrialLog, hypothesis_id: str) -> pd.DataFrame:
    """The forward observations for one hypothesis, oldest first.

    Columns: `net_return`, `cost`, `expected_cost`, `weight_error`. The index
    is the observation date. Duplicate dates keep the *first* record: the
    chain is append-only, so a second line for a day already recorded is a
    correction, and a correction that silently replaces the original is
    exactly what the chain exists to prevent. Both stay on the record; only
    the first counts.
    """
    rows: list[dict[str, Any]] = []
    for rec in log.records(kind="forward", hypothesis_id=hypothesis_id):
        p = rec.payload
        rows.append(
            {
                "date": pd.to_datetime(p["date"], utc=True, errors="coerce"),
                "net_return": float(p.get("net_return", np.nan)),
                "cost": float(p.get("cost", np.nan)),
                "expected_cost": (
                    np.nan if p.get("expected_cost") is None else float(p["expected_cost"])
                ),
                "weight_error": _weight_error(p.get("weights"), p.get("expected_weights")),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["net_return", "cost", "expected_cost", "weight_error"],
            index=pd.DatetimeIndex([], tz="UTC", name="date"),
        )
    out = pd.DataFrame(rows).dropna(subset=["date"]).set_index("date").sort_index(kind="stable")
    return out[~out.index.duplicated(keep="first")]


def _weight_error(live: dict[str, float] | None, expected: dict[str, float] | None) -> float:
    """Absolute notional disagreement between the book we held and the book we meant to hold.

    Summed over the union of both symbol sets, so a position the live system
    opened and the research never asked for counts just as much as one it
    missed. `NaN` when the bar carries no expectation to compare against —
    that is unknown, not zero, and gate 10 treats it as unknown.
    """
    if not expected:
        return float("nan")
    live = live or {}
    symbols = set(live) | set(expected)
    return float(sum(abs(float(live.get(s, 0.0)) - float(expected.get(s, 0.0))) for s in symbols))


@dataclass(frozen=True)
class ForwardSummary:
    """What the forward record says, before anyone decides what it means."""

    observations: int
    periods_per_year: float
    net_sharpe: float
    net_return: float
    max_drawdown: float
    realised_cost: float
    expected_cost: float
    cost_ratio: float
    max_weight_error: float
    checked_bars: int
    first: str | None
    last: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "forward_observations": float(self.observations),
            "forward_sharpe": self.net_sharpe,
            "forward_return": self.net_return,
            "forward_max_drawdown": self.max_drawdown,
            "forward_realised_cost": self.realised_cost,
            "forward_expected_cost": self.expected_cost,
            "forward_cost_ratio": self.cost_ratio,
            "forward_max_weight_error": self.max_weight_error,
            "forward_checked_bars": float(self.checked_bars),
        }


def summarise(records: pd.DataFrame, periods_per_year: float) -> ForwardSummary:
    """Reduce the record to the numbers gate 10 turns on.

    The Sharpe here is the plain annualised one. No HAC correction, no
    deflation: with the sixty-odd observations this gate is designed for,
    those refinements would dress up a number that cannot carry them. Gate 3
    and gate 4 did that work on a sample long enough to bear it.
    """
    net = records["net_return"].astype(float).dropna()
    n = int(len(net))
    if n == 0:
        return ForwardSummary(0, periods_per_year, float("nan"), 0.0, 0.0, 0.0, 0.0,
                              float("nan"), float("nan"), 0, None, None)

    sd = float(net.std(ddof=1)) if n > 1 else 0.0
    sharpe = float(net.mean() / sd * np.sqrt(periods_per_year)) if sd > 0 else float("nan")
    equity = (1.0 + net).cumprod()
    drawdown = float((equity / equity.cummax() - 1.0).min())

    realised = float(records["cost"].astype(float).fillna(0.0).sum())
    expected_col = records["expected_cost"].astype(float)
    expected = float(expected_col.sum(skipna=True)) if expected_col.notna().any() else float("nan")
    ratio = realised / expected if np.isfinite(expected) and expected > 0 else float("nan")

    errors = records["weight_error"].astype(float)
    checked = int(errors.notna().sum())
    worst = float(errors.max()) if checked else float("nan")

    return ForwardSummary(
        observations=n,
        periods_per_year=float(periods_per_year),
        net_sharpe=sharpe,
        net_return=float(equity.iloc[-1] - 1.0),
        max_drawdown=drawdown,
        realised_cost=realised,
        expected_cost=expected,
        cost_ratio=ratio,
        max_weight_error=worst,
        checked_bars=checked,
        first=str(records.index[0].date()),
        last=str(records.index[-1].date()),
    )
