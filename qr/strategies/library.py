"""Strategy library. Two entries so far; the rest land on Day 4.

Every strategy here obeys the interface contract: the weights returned for bar
*t* use only bars up to and including *t*, and the runner applies the shift.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy, VolTarget


class BuyAndHold(Strategy):
    """Equal weight across the universe. The baseline gate 5 tests against.

    Not a strawman: in crypto this is a hard benchmark over most samples, and a
    strategy that cannot beat it after costs has nothing to offer.
    """

    family = "buy_and_hold"

    def __init__(self, gross: float = 1.0) -> None:
        super().__init__(gross=gross)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        ones = pd.DataFrame(1.0, index=panel.index, columns=panel.symbols)
        return self.normalise(self.mask_to_universe(ones, panel, universe), self.params["gross"])


class TSMOM(Strategy):
    """Time-series momentum: hold what has gone up over `lookback` bars.

    The oldest and most replicated systematic effect there is, and the one most
    likely to survive costs at a daily horizon. Long-only because the trial
    models Binance **spot**: there is nothing to short.

    `skip` drops the most recent bars from the lookback window — the 12-1
    convention from the equity literature, which avoids the short-term reversal
    that sits on top of the momentum signal.
    """

    family = "tsmom"

    def __init__(
        self,
        lookback: int = 90,
        skip: int = 0,
        vol_target: float | None = 0.20,
        vol_lookback: int = 30,
        max_leverage: float = 1.0,
    ) -> None:
        super().__init__(
            lookback=lookback,
            skip=skip,
            vol_target=vol_target,
            vol_lookback=vol_lookback,
            max_leverage=max_leverage,
        )

    def signal(self, panel: Panel) -> pd.DataFrame:
        lookback, skip = self.params["lookback"], self.params["skip"]
        close = panel.close
        recent = close.shift(skip)
        past = close.shift(lookback + skip)
        return (recent / past - 1.0)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        momentum = self.signal(panel)
        raw = (momentum > 0).astype(float).where(momentum.notna(), 0.0)
        weights = self.normalise(self.mask_to_universe(raw, panel, universe))
        target = self.params["vol_target"]
        if target:
            weights = VolTarget(
                annual_target=target,
                lookback=self.params["vol_lookback"],
                max_leverage=self.params["max_leverage"],
            ).scale(weights, panel)
        return weights.fillna(0.0)


class RandomEntry(Strategy):
    """A deterministic-seed random book with the same turnover profile.

    Gate 6 needs a "would a coin toss have done this" baseline, and gate 5's SPA
    test needs a benchmark set. Seeded so a report is reproducible.
    """

    family = "random_entry"

    def __init__(self, n_held: int = 5, hold: int = 20, seed: int = 0) -> None:
        super().__init__(n_held=n_held, hold=hold, seed=seed)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        rng = np.random.default_rng(self.params["seed"])
        hold, n_held = self.params["hold"], self.params["n_held"]
        allowed = panel.tradable()
        if universe is not None:
            allowed = allowed & universe.reindex_like(allowed).fillna(False)
        raw = pd.DataFrame(0.0, index=panel.index, columns=panel.symbols)
        current: list[str] = []
        for i, stamp in enumerate(panel.index):
            candidates = list(allowed.columns[allowed.loc[stamp].to_numpy()])
            if i % hold == 0 or not set(current) <= set(candidates):
                take = min(n_held, len(candidates))
                current = list(rng.choice(candidates, size=take, replace=False)) if take else []
            raw.loc[stamp, [c for c in current if c in candidates]] = 1.0
        return self.normalise(self.mask_to_universe(raw, panel, universe))
