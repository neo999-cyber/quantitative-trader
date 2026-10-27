"""CME crowding as a timer for the carry holding (`docs/prereg/p4_cot_crowding_v1.md`): Programme 4's second family.

On the `carrycot-um` instrument (`qr/data/cot.py`) each day carries the latest released percentile of the
leveraged-fund net short in CME bitcoin futures. The rule: hold the carry unit (long spot, short perp, weight
`gross`) while the percentile over the trailing `window` reports is below `p`; step out while it is at or
above `p`; back in at the first release below it. No hysteresis, no other knob.

Controls: `control="always_in"` holds the unit every day (the holding with no rule — what the timer has to
beat, and gate 5's buy-and-hold on this one-unit universe is the same book); `control="mirror"` holds only
while crowded; `control="placebo"` permutes the crowded flags in blocks of thirteen weeks (91 daily bars) with
a fixed seed — the same share of time out, in the wrong places.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy

WINDOWS = (26, 52)
CONTROLS = ("none", "always_in", "mirror", "placebo")
PLACEBO_BLOCK_BARS = 91
PLACEBO_SEED = 20261027


class CarryCrowdingTimer(Strategy):
    family = "carry_crowding_timer"

    def __init__(self, p: float = 90.0, window: int = 52, control: str = "none", gross: float = 1.0) -> None:
        if not 0 < p <= 100:
            raise ValueError("p is a percentile in (0, 100]")
        if int(window) not in WINDOWS:
            raise ValueError(f"window is one of {WINDOWS} reports")
        if control not in CONTROLS:
            raise ValueError(f"control is one of {CONTROLS}")
        if gross <= 0:
            raise ValueError("gross > 0")
        super().__init__(p=float(p), window=int(window), control=control, gross=float(gross))

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        pr = self.params
        pct = panel.get(f"cot_pct_{pr['window']}")
        if pct is None:
            raise ValueError("this panel carries no cot_pct_*: build one with `qr data cot-build`")
        crowded = (pct >= pr["p"]).fillna(False)
        if pr["control"] == "placebo":
            crowded = block_shuffle(crowded, PLACEBO_BLOCK_BARS, PLACEBO_SEED)
        if pr["control"] == "always_in":
            inside = pd.DataFrame(True, index=pct.index, columns=pct.columns)
        elif pr["control"] == "mirror":
            inside = crowded
        else:
            inside = ~crowded
        weights = inside.astype(float) * pr["gross"]
        return self.mask_to_universe(weights, panel, universe)


def block_shuffle(flags: pd.DataFrame, block: int, seed: int) -> pd.DataFrame:
    """Each column's bars cut into consecutive blocks of `block`, the blocks put back in a permuted order."""
    rng = np.random.default_rng(seed)
    out = flags.copy()
    n = len(flags)
    starts = list(range(0, n, block))
    for col in flags.columns:
        values = flags[col].to_numpy()
        pieces = [values[s:s + block] for s in starts]
        order = rng.permutation(len(pieces))
        out[col] = np.concatenate([pieces[i] for i in order])[:n]
    return out
