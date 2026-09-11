"""RULE 5 - the sleep test.  Position size is dictated by the math, not the gut."""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict


@dataclass
class PositionSize:
    equity: float
    risk_pct: float
    max_risk_dollars: float
    entry: float
    stop: float
    risk_per_share: float
    shares: int
    position_value: float
    position_pct_of_equity: float
    actual_risk_dollars: float

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        return (
            f"risk ${self.max_risk_dollars:,.2f} ({self.risk_pct:.1%} of ${self.equity:,.0f}) / "
            f"${self.risk_per_share:.2f} per share => {self.shares} shares "
            f"(${self.position_value:,.0f}, {self.position_pct_of_equity:.1%} of equity, "
            f"actual risk ${self.actual_risk_dollars:,.2f})"
        )


def position_size(equity: float, risk_pct: float, entry: float, stop: float) -> PositionSize:
    """`shares = floor(equity * risk_pct / |entry - stop|)`.

    $10,000 account, 1% risk, entry $150, stop $145 -> $100 / $5 = 20 shares.
    """
    if equity <= 0:
        raise ValueError("equity must be positive")
    if not 0 < risk_pct <= 0.05:
        raise ValueError("risk_pct must be between 0 and 5% (veterans use 1-2%)")
    if entry <= 0 or stop <= 0:
        raise ValueError("entry and stop must be positive prices")
    risk_per_share = abs(entry - stop)
    if risk_per_share == 0:
        raise ValueError("stop cannot equal entry")
    max_risk = equity * risk_pct
    shares = int(math.floor(max_risk / risk_per_share))
    return PositionSize(
        equity=equity, risk_pct=risk_pct, max_risk_dollars=max_risk, entry=entry, stop=stop,
        risk_per_share=risk_per_share, shares=shares, position_value=shares * entry,
        position_pct_of_equity=(shares * entry) / equity, actual_risk_dollars=shares * risk_per_share,
    )
