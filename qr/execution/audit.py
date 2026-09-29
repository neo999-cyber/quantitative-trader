"""Audit cases with hand-computable answers (`docs/20_PROGRAMME_2.md` §10, item 11).

Small, explicit functions rather than engine paths, so that each can be
checked against a number worked out on paper before the engine is trusted
with it. Gate 8's carry stresses read these.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def unmatched_leg_loss(weight: float, spot_return: float, equity: float, leg: str = "spot") -> float:
    """Dollars made or lost when only one leg of a carry unit filled.

    A unit of weight `w` is `w x equity` long spot and the same short perp.
    If the perp did not fill, the account is long the coin for the bar and
    earns `w x equity x r`; if the spot did not fill, it is short and earns
    the negative. The unit itself would have earned about nothing.
    """
    if leg not in ("spot", "perp"):
        raise ValueError(f"leg must be 'spot' or 'perp', not {leg!r}")
    sign = 1.0 if leg == "spot" else -1.0
    return sign * float(weight) * float(equity) * float(spot_return)


def redenomination_bars(ratio: pd.Series, factor_tolerance: float = 0.05, window: int = 5) -> pd.Series:
    """Bars where the unit's price is an artefact of a split-like event.

    A redenomination (1:1000 and the like) reaches a coin's spot and perp
    markets on different days, so for a few bars the ratio spot / perp is
    off by the factor and then comes back. That is not a return. The mask
    is True on the bars between a jump by factor `f` (|f - 1| > 50%) and a
    later jump by about `1 / f` within `window` bars. A jump that never
    reverses is left alone: the perp at 25x spot on 12 May 2022 (LUNA) was
    a market, and the loss on the short was real.
    """
    values = ratio.to_numpy(dtype=float)
    out = np.zeros(len(values), dtype=bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        step = values[1:] / values[:-1]
    for i, f in enumerate(step, start=1):
        if not np.isfinite(f) or abs(f - 1.0) <= 0.5:
            continue
        for j in range(i + 1, min(i + window, len(values) - 1) + 1):
            g = step[j - 1]
            if np.isfinite(g) and abs(f * g - 1.0) <= factor_tolerance:
                out[i:j] = True
                break
    return pd.Series(out, index=ratio.index)
