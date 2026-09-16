"""Closing-auction imbalance fade, long-only (`docs/prereg/p2_auction_imbalance_v1.md`): family E1.

At the decision cutoff on day `t-1` the names with a sell imbalance of at
least `k` of the paired quantity, a paired value of at least
`min_paired_usd`, and a fresh snapshot are bought at the close, up to
`n_max` of them, the largest imbalance first, each at `1 / n_max` of equity;
all are sold at the next open. On the `auction-xnas` panel a bar's return
is that overnight move, so the book set at `t-1` and held over `t` by the
runner's one-bar shift is exactly the trade. Nothing is held past the open:
the target is zero on every bar without a signal, so the runner's turnover
counts the exit as well as the entry.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy


class AuctionFade(Strategy):
    family = "auction_fade"

    def __init__(
        self,
        k: float = 0.20,
        snapshot: str = "15:55",
        n_max: int = 4,
        min_paired_usd: float = 5e6,
        side: str = "sell",
    ) -> None:
        """`side="sell"` is the family: buy into a sell imbalance. `side="buy"`
        is the pre-registered mirror control: buy into a *buy* imbalance,
        which the mechanism says should not pay."""
        if k <= 0 or n_max < 1 or min_paired_usd < 0:
            raise ValueError("k must be positive, n_max a count >= 1, min_paired_usd >= 0")
        if snapshot not in ("15:50", "15:55", "15:58"):
            raise ValueError("snapshot must be one of 15:50, 15:55, 15:58")
        if side not in ("sell", "buy"):
            raise ValueError("side is 'sell' (the family) or 'buy' (the mirror control)")
        super().__init__(k=float(k), snapshot=snapshot, n_max=int(n_max), min_paired_usd=float(min_paired_usd), side=side)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        p = self.params
        tag = p["snapshot"].replace(":", "")
        imb = panel.get(f"imb_{tag}")
        paired = panel.get(f"paired_usd_{tag}")
        if imb is None or paired is None:
            raise ValueError(
                f"this panel carries no imb_{tag} / paired_usd_{tag}: it is not an auction panel. "
                "Build one with `qr data auction-build`."
            )
        signed = -imb if p["side"] == "sell" else imb  # positive where the rule wants to buy
        eligible = panel.tradable() & imb.notna() & (signed >= p["k"]) & (paired >= p["min_paired_usd"])
        if universe is not None:
            eligible &= universe.reindex_like(eligible).fillna(False).astype(bool)
        # the largest imbalances first, up to n_max, each at 1 / n_max
        score = signed.where(eligible)
        rank = score.rank(axis=1, ascending=False, method="first")
        chosen = eligible & (rank <= p["n_max"])
        weights = chosen.astype(float) / float(p["n_max"])
        return weights.where(panel.tradable(), 0.0)
