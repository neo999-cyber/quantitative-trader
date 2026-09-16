"""OI-conditioned reversal in mid-cap perpetuals (`docs/prereg/p2_oi_reversal_v1.md`): family C5.

Crowded positioning unwinds: a coin whose open interest rose while its price
ran is held by levered latecomers, and the unwind is a reversal. The SSRN
post-mortem of March 2026 (Azka Fayez Junior) finds plain OHLCV/funding
sorts on large caps carry nothing, so the universe is ranks 31–150 by
volume and the sort is conditioned on OI change. Weekly: among names whose
OI rose by at least `oi_min` over `oi_lookback` bars, rank by the trailing
`lookback`-bar return; long the bottom `n_side` (losers), short the top
`n_side` (winners), equal weight, gross 1.0, net 0. Perps make the short
leg native; funding is settled gross by the runner on both legs.
"""
from __future__ import annotations

import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy


class OIReversal(Strategy):
    family = "oi_reversal"

    def __init__(self, lookback: int = 7, oi_lookback: int = 7, oi_min: float = 0.10, n_side: int = 5, rebalance_on: str | None = "W") -> None:
        if lookback < 1 or oi_lookback < 1 or n_side < 1:
            raise ValueError("lookback, oi_lookback, n_side are counts >= 1")
        super().__init__(lookback=int(lookback), oi_lookback=int(oi_lookback), oi_min=float(oi_min), n_side=int(n_side), rebalance_on=rebalance_on)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        oi = panel.get("open_interest")
        if oi is None:
            raise ValueError("this panel carries no `open_interest`: ingest metrics with `qr data funding-ingest --metrics`")
        p = self.params
        ret = panel.close.pct_change(p["lookback"], fill_method=None)
        oi_change = oi.pct_change(p["oi_lookback"], fill_method=None)
        eligible = panel.tradable() & ret.notna() & oi_change.notna() & (oi_change >= p["oi_min"])
        if universe is not None:
            eligible &= universe.reindex_like(eligible).fillna(False).astype(bool)
        score = ret.where(eligible)
        n_side = p["n_side"]
        ranked = score.rank(axis=1, ascending=True, method="first")
        live = score.notna().sum(axis=1)
        enough = (live >= 2 * n_side).to_numpy()[:, None]
        long = (ranked <= n_side) & enough                       # the losers
        short = ranked.gt(live.to_numpy()[:, None] - n_side) & enough  # the winners
        picked = long.astype(float) - short.astype(float)
        weights = self.normalise(self.mask_to_universe(picked, panel, universe))
        return self.schedule(weights, panel)
