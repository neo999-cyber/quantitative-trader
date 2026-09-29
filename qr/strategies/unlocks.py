"""Unlock fade in perpetuals (`docs/prereg/p2_unlock_fade_v1.md`, draft): family C6.

A vesting cliff is a scheduled seller. Keyrock's study of 16,000 unlocks
(`docs/research/10`) finds the price pressure lands in the thirty days
*before* the date and stabilises about two weeks after; team and investor
cliffs are the worst, ecosystem unlocks the exception. The perp makes the
short leg native and funding is settled gross by the engine.

Rule, each bar: among tradable perps whose next insider/investor cliff is
at least `min_pct` of documented circulating supply and lands within
`lead` days (`days_to_cliff` ≤ lead), short up to `n_max` names, the
largest `cliff_pct_next` first, equal weight, gross `gross`. A name stays
short from `lead` days before its cliff until `post` days after it, then
is released. Nothing else is held.

`side="short"` is the family. `side="long"` holds the same names long
over the same window — the mirror control that should lose — and
`category="eco"` runs the rule on the ecosystem/community cliffs
(`unlock_pct_eco_30d`), which the study says do not fall.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy


class UnlockFade(Strategy):
    family = "unlock_fade"

    def __init__(
        self,
        lead: int = 30,
        post: int = 14,
        min_pct: float = 0.01,
        n_max: int = 10,
        gross: float = 1.0,
        side: str = "short",
        category: str = "sellers",
    ) -> None:
        if lead < 1 or post < 0 or n_max < 1 or min_pct <= 0 or gross <= 0:
            raise ValueError("lead >= 1, post >= 0, n_max >= 1, min_pct > 0, gross > 0")
        if side not in ("short", "long"):
            raise ValueError("side is 'short' (the family) or 'long' (the mirror control)")
        if category not in ("sellers", "eco"):
            raise ValueError("category is 'sellers' (insider + investor cliffs) or 'eco' (the control)")
        super().__init__(
            lead=int(lead), post=int(post), min_pct=float(min_pct), n_max=int(n_max),
            gross=float(gross), side=side, category=category,
        )

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        days = panel.get("days_to_cliff")
        size = panel.get("cliff_pct_next")
        if days is None or size is None:
            raise ValueError("this panel carries no unlock calendar: build one with `qr data unlocks-build`")
        p = self.params
        if p["category"] == "eco":
            # the ecosystem control has no per-cliff countdown; the 30-day
            # window sum stands in for it with the same size floor
            eco = panel.get("unlock_pct_eco_30d")
            if eco is None:
                raise ValueError("this panel carries no `unlock_pct_eco_30d`")
            in_window = eco >= p["min_pct"]
            score = eco.where(in_window)
        else:
            # `days_to_cliff` counts down to the *next* qualifying cliff, so
            # the post-cliff hold is read off the countdown's reset: a name
            # whose countdown jumped up within the last `post` bars just
            # passed its cliff and is kept.
            qualifying = (size >= p["min_pct"]) & days.notna()
            approaching = qualifying & (days <= p["lead"])
            just_passed = pd.DataFrame(False, index=days.index, columns=days.columns)
            if p["post"] > 0:
                crossed = approaching.shift(1, fill_value=False) & ~approaching
                # a cliff passed at bar t keeps the name for `post` bars after it
                just_passed = crossed.rolling(p["post"] + 1, min_periods=1).max().fillna(0.0).astype(bool)
            in_window = approaching | just_passed
            score = size.where(approaching).fillna(0.0).where(in_window)
        eligible = panel.tradable() & in_window
        if universe is not None:
            eligible &= universe.reindex_like(eligible).fillna(False).astype(bool)
        score = score.where(eligible)
        ranked = score.rank(axis=1, ascending=False, method="first")
        picked = (ranked <= p["n_max"]).astype(float)
        sign = -1.0 if p["side"] == "short" else 1.0
        weights = self.normalise(self.mask_to_universe(picked * sign, panel, universe), p["gross"])
        return weights
