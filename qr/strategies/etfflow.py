"""Forced buying after US spot-ETF flow days (`docs/prereg/p4_etf_flow_pressure_v1.md`): Programme 4's first family.

On the `etfflow-um` instrument (`qr/data/etfflow.py`) each issuer row's standardised flow sits on the one
bar a rule may act on it — the bar closing at 09:00 New York on the entry session. The rule, on that bar:
long when `z ≥ k`, short when `z ≤ −k`, nothing otherwise; the target is kept for `hold` bars (seven for
the cash session, 09:00–16:00 New York; twenty-four for a day), so the runner's one-bar shift fills at
09:00 and is flat at the close or a day later. Entry sessions are at least a day apart, so one position is
ever open; a new target on the bar an old one ends is a hold, not a round trip.

`timing="t2"` reads the issuer's row the morning after it is published (the primary arm);
`timing="t1"` reads it a session earlier, as an aggregator's evening table would allow (the diagnostic
arm: a control on the mechanism's speed, not a candidate). The controls: `control="mirror"` flips the
sides; `control="placebo"` permutes the flows among the entry bars within each calendar month (same
days, same vol structure, the flows on the wrong days; a fixed seed); `control="always_long"` is long on
every eligible entry day whatever the flow — what gate 5 compares against beyond cash.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy

HOLD_BARS = {"session": 7, "24h": 24}
TIMINGS = ("t2", "t1")
CONTROLS = ("none", "mirror", "placebo", "always_long")
PLACEBO_SEED = 20261027


class EtfFlowPressure(Strategy):
    family = "etf_flow_pressure"

    def __init__(
        self, k: float = 1.0, hold: str = "session", timing: str = "t2", control: str = "none", gross: float = 1.0
    ) -> None:
        if k < 0:
            raise ValueError("k is a non-negative threshold on the standardised flow")
        if hold not in HOLD_BARS:
            raise ValueError(f"hold is one of {sorted(HOLD_BARS)}")
        if timing not in TIMINGS:
            raise ValueError("timing is 't2' (the issuer's row, primary) or 't1' (the diagnostic arm)")
        if control not in CONTROLS:
            raise ValueError(f"control is one of {CONTROLS}")
        if gross <= 0:
            raise ValueError("gross > 0")
        super().__init__(k=float(k), hold=hold, timing=timing, control=control, gross=float(gross))

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        p = self.params
        z = panel.get(f"etf_flow_z_{p['timing']}")
        if z is None:
            raise ValueError("this panel carries no etf_flow_z_*: build one with `qr data etfflow-build`")
        if p["control"] == "placebo":
            z = shuffle_within_month(z, PLACEBO_SEED)
        if p["control"] == "always_long":
            side = z.notna().astype(float)
        else:
            side = np.sign(z).where(z.abs() >= p["k"], 0.0).fillna(0.0)
            if p["control"] == "mirror":
                side = -side
        n = HOLD_BARS[p["hold"]]
        held = side.rolling(n, min_periods=1).sum().clip(-1.0, 1.0).fillna(0.0)
        return self.mask_to_universe(held * p["gross"], panel, universe)


def shuffle_within_month(z: pd.DataFrame, seed: int) -> pd.DataFrame:
    """The placebo: each column's values permuted among its own bars within each calendar month."""
    rng = np.random.default_rng(seed)
    out = z.copy()
    for col in z.columns:
        s = z[col].dropna()
        if s.empty:
            continue
        shuffled = s.copy()
        for _, grp in s.groupby([s.index.year, s.index.month]):
            shuffled.loc[grp.index] = rng.permutation(grp.to_numpy())
        out[col] = shuffled.reindex(z.index)
    return out
