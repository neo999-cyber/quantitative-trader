"""Late-day hedging momentum, long-only (`docs/prereg/p2_late_day_momentum_v1.md`): family E2.

Baltussen, Da, Lammers and Martens (JFE 2021): the last half hour goes the
way of the day, because leveraged ETFs and option hedgers must trade with
the day's move before the close. On the `intraday-xnas` panel each session
is two bars; on the day bar (`is_late == 0`) the family reads
`ret_to_decision` and, when the day is up by at least `k`, sets a full
long target that the runner holds over the late bar; on the late bar it
sets zero, so nothing is held overnight. `side="reverse"` is the mirror
control: buy the down days.
"""
from __future__ import annotations

import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy


class LateDayMomentum(Strategy):
    family = "late_day_momentum"

    def __init__(self, k: float = 0.0, side: str = "long") -> None:
        if k < 0:
            raise ValueError("k is a non-negative return threshold")
        if side not in ("long", "reverse"):
            raise ValueError("side is 'long' (with the day) or 'reverse' (the control)")
        super().__init__(k=float(k), side=side)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        sig = panel.get("ret_to_decision")
        late = panel.get("is_late")
        if sig is None or late is None:
            raise ValueError("this panel carries no ret_to_decision / is_late: build one with `qr data intraday-build`")
        k = self.params["k"]
        fire = (sig >= k) if self.params["side"] == "long" else (sig <= -k)
        weights = fire.fillna(False).astype(float).where(late == 0.0, 0.0)
        if universe is not None:
            weights = weights.where(universe.reindex_like(weights).fillna(False).astype(bool), 0.0)
        return weights.where(panel.tradable(), 0.0)
