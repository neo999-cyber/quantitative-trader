"""How much money, which is a different question from whether it works.

Everything upstream asks whether an edge is real. This asks what to do with
one, and it is the step where people who got all the research right still
blow up: the edge was genuine, the size was not.

Sizing here is the **minimum of four independent caps**, and the answer is
always accompanied by which one bound. That is deliberate — the same shape as
gate 2 naming the cost that dominates — because "trade at 0.4x" is a number
and "trade at 0.4x because the drawdown constraint binds, not the edge" is a
direction.

The four:

1. **Fractional Kelly.** Full Kelly leverage for a continuous book is
   `SR / σ`. Full Kelly is not a target: at full Kelly the probability of
   eventually halving your money is one half, which is a property of the
   arithmetic and not a risk anyone accepts. We cap at half.
2. **Drawdown.** For a book with log drift *m* and volatility *s*, the
   probability of ever drawing down more than *D* is `(1 − D) ** (2m / s²)`.
   Solve for the largest leverage that keeps it under the tolerance.
3. **Volatility target.** A flat ceiling on annualised book volatility, so
   the size is knowable in advance rather than a function of an estimate.
4. **Single-name gap.** No one position may cost more than 1% of equity if
   it gaps against you. This is the 1% rule, restated for a weight book
   rather than a stop-loss, because a continuous book has no stop to measure
   from.

**The Sharpe that goes in must be out-of-sample.** Sizing off the in-sample
Sharpe is the single most expensive mistake available here: it is the number
that was maximised, so it is the number least entitled to set your exposure.
`size()` will not accept it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SizingPolicy:
    """The four caps, as numbers someone chose and can be argued with."""

    #: Fraction of full Kelly. Half is the conventional ceiling; a quarter is
    #: the conventional working value.
    kelly_fraction: float = 0.25
    #: The drawdown we are sizing to avoid, and how much chance of ever
    #: touching it we accept. "Ever" rather than "this year": the finite
    #: horizon reading gives a friendlier number for the same risk, and the
    #: friendlier number is not the one to size on.
    max_drawdown: float = 0.25
    drawdown_tolerance: float = 0.10
    #: Annualised volatility ceiling for the whole book.
    volatility_target: float = 0.15
    #: The 1% rule: the most any single position may cost, and the adverse
    #: one-day gap it is measured against.
    max_single_name_loss: float = 0.01
    gap_move: float = 0.20


@dataclass(frozen=True)
class Sizing:
    """A leverage, the cap that produced it, and every cap that did not."""

    leverage: float
    binding: str
    caps: dict[str, float]
    sharpe: float
    volatility: float
    drawdown_probability: float
    notional: float | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        out = {
            "leverage": self.leverage,
            "binding_cap": self.binding,
            "sizing_sharpe": self.sharpe,
            "sizing_volatility": self.volatility,
            "drawdown_probability": self.drawdown_probability,
            **{f"cap_{k}": v for k, v in self.caps.items()},
        }
        if self.notional is not None:
            out["notional"] = self.notional
        return out


def drawdown_probability(leverage: float, sharpe: float, volatility: float, depth: float) -> float:
    """P(the book ever draws down more than `depth`), under a lognormal book.

    At half Kelly and a 25% depth this returns 0.42, which is worth sitting
    with: the conventional "safe" Kelly fraction carries a better-than-even
    chance of a drawdown most people would abandon the strategy at. The
    formula is `exp(-2·m·L / s²)` with `L = -ln(1 - depth)`, which for a full
    Kelly book and a halving gives exactly one half — the familiar result,
    and a check that this is the right expression.
    """
    if leverage <= 0 or volatility <= 0 or not np.isfinite(sharpe):
        return float("nan")
    if not 0.0 < depth < 1.0:
        raise ValueError(f"depth must be in (0, 1), got {depth}")
    mu = sharpe * volatility
    m = leverage * mu - 0.5 * (leverage * volatility) ** 2
    s = leverage * volatility
    if m <= 0:
        return 1.0
    return float(min(1.0, (1.0 - depth) ** (2.0 * m / s**2)))


def _drawdown_cap(sharpe: float, volatility: float, policy: SizingPolicy) -> float:
    """The largest leverage whose eventual-drawdown probability stays in budget.

    Solved in closed form. Writing `q = 2m/s²` for a book at leverage `f`,
    `q = (2·SR/(f·σ)) - 1`, and the constraint `(1-D)**q <= tol` fixes the
    smallest acceptable `q`, hence the largest `f`.
    """
    if sharpe <= 0 or volatility <= 0:
        return 0.0
    tol = min(max(policy.drawdown_tolerance, 1e-12), 1.0 - 1e-12)
    needed_q = math.log(tol) / math.log(1.0 - policy.max_drawdown)
    if needed_q + 1.0 <= 0:
        return float("inf")
    return float(2.0 * sharpe / (volatility * (needed_q + 1.0)))


def size(
    sharpe: float,
    volatility: float,
    *,
    max_weight: float = 1.0,
    equity: float | None = None,
    policy: SizingPolicy | None = None,
) -> Sizing:
    """Leverage for a book with this out-of-sample Sharpe and this volatility.

    `max_weight` is the largest absolute weight the strategy ever put on one
    name, which is what the single-name gap cap is measured against.
    """
    policy = policy or SizingPolicy()
    notes: list[str] = []

    if not np.isfinite(sharpe) or not np.isfinite(volatility) or volatility <= 0:
        return Sizing(0.0, "undefined", {}, sharpe, volatility, float("nan"), None,
                      ["no finite Sharpe and volatility to size from"])
    if sharpe <= 0:
        return Sizing(0.0, "no edge", {}, sharpe, volatility, float("nan"), None,
                      [f"out-of-sample Sharpe is {sharpe:.2f}; there is nothing to size"])

    full_kelly = sharpe / volatility
    caps = {
        "kelly": policy.kelly_fraction * full_kelly,
        "drawdown": _drawdown_cap(sharpe, volatility, policy),
        "volatility_target": policy.volatility_target / volatility,
    }
    if max_weight > 0 and policy.gap_move > 0:
        caps["single_name"] = policy.max_single_name_loss / (max_weight * policy.gap_move)
    else:
        notes.append("no single-name weight supplied, so the 1% rule was not applied")

    binding = min(caps, key=lambda k: caps[k])
    leverage = float(max(0.0, caps[binding]))
    realised = drawdown_probability(leverage, sharpe, volatility, policy.max_drawdown)

    if binding != "kelly" and caps["kelly"] > leverage * 1.5:
        notes.append(
            f"the {binding.replace('_', ' ')} cap is {caps['kelly'] / leverage:.1f}x tighter "
            f"than the Kelly cap, so the constraint is risk tolerance rather than the edge"
        )
    return Sizing(
        leverage=leverage,
        binding=binding,
        caps={k: float(v) for k, v in caps.items()},
        sharpe=float(sharpe),
        volatility=float(volatility),
        drawdown_probability=realised,
        notional=None if equity is None else float(equity * leverage),
        notes=notes,
    )
