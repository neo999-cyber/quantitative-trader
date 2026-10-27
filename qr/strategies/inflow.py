"""Coins moving onto exchanges precede selling (`docs/prereg/p4_exchange_inflow_v1.md`): Programme 4's third family.

On the `inflow-um` instrument (`qr/data/inflow.py`) each daily bar carries the previous day's net exchange
inflow standardised against its trailing ninety days. The rule on bar t: when `z ≥ k` and nothing is open,
short the perp (weight `gross`) for `h` bars — a target set on bar t fills at its close and is held over
bars t + 1 … t + h, the exit at the close of t + h. A signal while a position is open is not acted on: one
position at a time, no extension.

Controls: `control="mirror"` is the long side after extreme outflows (`z ≤ −k`), its own arm; `control="placebo"`
reads the flow series shifted 180 days later (the same signals on the wrong days); `control="random"` shorts on
as many days as the family's `k` would fire, drawn at random among the days a z exists, with a fixed seed —
the sample's own drift, which a short strategy has to overcome.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy

CONTROLS = ("none", "mirror", "placebo", "random")
PLACEBO_SHIFT_DAYS = 180
RANDOM_SEED = 20261027
FEATURE = "cm_netflow_z"


class ExchangeInflowFade(Strategy):
    family = "exchange_inflow_fade"

    def __init__(self, k: float = 1.5, h: int = 3, control: str = "none", gross: float = 1.0) -> None:
        if k <= 0:
            raise ValueError("k is a positive threshold on the standardised net inflow")
        if int(h) < 1:
            raise ValueError("h is a hold of at least one bar")
        if control not in CONTROLS:
            raise ValueError(f"control is one of {CONTROLS}")
        if gross <= 0:
            raise ValueError("gross > 0")
        super().__init__(k=float(k), h=int(h), control=control, gross=float(gross))

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        p = self.params
        z = panel.get(FEATURE)
        if z is None:
            raise ValueError("this panel carries no cm_netflow_z: build one with `qr data inflow-build`")
        if p["control"] == "placebo":
            z = z.shift(PLACEBO_SHIFT_DAYS)
        side = 1.0 if p["control"] == "mirror" else -1.0
        out = pd.DataFrame(0.0, index=z.index, columns=z.columns)
        rng = np.random.default_rng(RANDOM_SEED)
        for col in z.columns:
            series = z[col]
            if p["control"] == "mirror":
                fire = (series <= -p["k"]).to_numpy()
            else:
                fire = (series >= p["k"]).to_numpy()
            if p["control"] == "random":
                candidates = np.flatnonzero(series.notna().to_numpy())
                n = int(fire.sum())
                chosen = np.sort(rng.choice(candidates, size=min(n, len(candidates)), replace=False)) if n and len(candidates) else np.array([], dtype=int)
                fire = np.zeros(len(series), dtype=bool)
                fire[chosen] = True
            out[col] = _one_at_a_time(fire, p["h"]) * side * p["gross"]
        return self.mask_to_universe(out, panel, universe)


def _one_at_a_time(fire: np.ndarray, h: int) -> np.ndarray:
    """Targets of 1 on the `h` bars from each acted-on signal; a signal inside an open hold is skipped."""
    target = np.zeros(len(fire))
    open_until = -1
    for i in np.flatnonzero(fire):
        if i < open_until:
            continue
        target[i:i + h] = 1.0
        open_until = i + h
    return target
