"""Spot positioning from perpetual funding: the crudest expression there is.

`docs/15` recorded the objection that killed more candidates than any other —
"the transfer is real but structurally out of reach: funding is paid on perps".
It is correct, and this family does not argue with it. **No position here
collects funding.** A spot book cannot; that needs a perpetual and Phase 4.

What it claims instead is narrower and testable: the funding rate says which
side of the leveraged book is crowded and what it is paying to stay there, and
that is a fact about positioning which spot prices may or may not reflect.

* **Funding positive** — longs pay shorts. The crowd is levered long and
  paying for it. A crowded long is fragile: it is the side that gets
  liquidated on a move down, and a position held at a cost is one whose holder
  is looking for a reason to leave.
* **Funding negative** — shorts pay longs. The crowd is short and paying, and
  the squeeze risk points the other way.

Which of those is the tradeable direction is exactly what a memo has to commit
to in advance, so `side` is a parameter with no default worth trusting: `+1`
buys the most negative funding (fade the crowded short), `-1` buys the most
positive (ride the crowded long). Both are coherent claims with different
payers and the sweep runs both — but a memo that does not name one before
seeing the result has not made a prediction.

The book is long-only and equal-weighted because that is what a spot account
can hold, and crude because this is a kill test rather than a strategy: if the
effect is real it should survive the simplest possible expression, and if it
only appears after tuning, that is the finding.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy
from qr.strategies.library import _hold_between_rebalances, _rebalance_mask


class FundingTilt(Strategy):
    """Hold the `n_long` pairs whose perp funding is most extreme, by `side`.

    Needs a panel carrying `funding_rate` — `qr data funding-ingest` puts it
    there. Raising rather than degrading to zero weights is deliberate: a
    funding strategy silently holding nothing because the feature is absent
    looks exactly like a funding strategy that found no signal, and the two
    conclusions could not be further apart.
    """

    family = "funding_tilt"

    def __init__(
        self,
        lookback: int = 7,
        n_long: int = 5,
        rebalance: int = 7,
        side: int = 1,
        min_abs_funding: float = 0.0,
    ) -> None:
        if side not in (1, -1):
            raise ValueError(f"side must be +1 (buy most negative funding) or -1; got {side}")
        if lookback < 1 or n_long < 1 or rebalance < 1:
            raise ValueError("lookback, n_long and rebalance are counts and must be >= 1")
        if min_abs_funding < 0:
            raise ValueError("min_abs_funding is a magnitude and cannot be negative")
        super().__init__(
            lookback=lookback,
            n_long=n_long,
            rebalance=rebalance,
            side=side,
            min_abs_funding=min_abs_funding,
        )

    def signal(self, panel: Panel) -> pd.DataFrame:
        """Mean daily funding over the lookback, per symbol.

        A mean of daily sums, so the unit is "funding paid per day over the
        window" and a pair that settled fewer times is not flattered.
        """
        funding = panel.get("funding_rate")
        if funding is None:
            raise ValueError(
                "this panel carries no `funding_rate`, so a funding strategy cannot be "
                "evaluated on it. Run `qr data funding-pull` then `qr data funding-ingest`; "
                "until then any result here would be a strategy holding nothing, which is "
                "indistinguishable from one that found nothing."
            )
        return funding.rolling(self.params["lookback"], min_periods=self.params["lookback"]).mean()

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        score = self.signal(panel)
        eligible = panel.tradable() & score.notna()
        if universe is not None:
            eligible &= universe.reindex_like(eligible).fillna(False).astype(bool)

        floor = float(self.params["min_abs_funding"])
        if floor > 0:
            # A mechanism about *paying to stay* has nothing to say where
            # nobody is paying much. Without a floor the ranking still returns
            # the least-boring names on a day when funding is flat everywhere,
            # which is a book held for no reason.
            eligible &= score.abs() >= floor

        masked = score.where(eligible)
        # side=+1 ranks ascending, so rank 1 is the most negative funding.
        ordered = masked if self.params["side"] == 1 else -masked
        ranks = ordered.rank(axis=1, method="first", ascending=True)
        chosen = (ranks <= self.params["n_long"]) & eligible

        marks = _rebalance_mask(panel.index, self.params["rebalance"])
        held = _hold_between_rebalances(chosen.astype(float), self.params["rebalance"])
        held = held.where(panel.tradable(), 0.0)
        return self.normalise(held, gross=1.0)

    def trades_on(self, index: pd.DatetimeIndex) -> pd.Series:
        return pd.Series(_rebalance_mask(index, self.params["rebalance"]), index=index)
