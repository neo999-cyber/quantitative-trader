"""Funding carry on the carry-unit panel (`qr/data/carry.py`): family C1.

The claim, stated so it can be wrong: **the levered long pays to stay, and a
delta-neutral book that takes the other side collects what it pays, net of
the basis it gives up and the two legs' costs.** BIS Working Paper 1087
("Crypto carry") measures the carry at over 10% a year on average and finds
its profit is mostly the funding; it also finds that a *high* carry predicts
crashes and margin spikes, which is why this family has a ceiling as well as
a floor.

Every position is a unit of long spot / short perp, so the book is
dollar-neutral to the coin by construction and the benchmark is cash
(`--benchmark cash`). Long-only in units: the reverse trade (short spot) is
not available on a spot account and is not claimed.

Parameters, all pre-registered before any run:

* `lookback` — days of the perp's funding averaged into the signal.
* `entry` — annualised funding above which a unit is opened, as a decimal.
  The pre-registration ties it to the frozen cost model: three round trips
  of cost per year is the floor the sandbox already enforces.
* `exit` — annualised funding below which a unit is closed. Below entry, so
  a unit is not flipped daily by noise around the threshold.
* `ceiling` — the trailing percentile of the signal above which a unit is
  *not* opened, the paper's crash-risk filter. 1.0 switches it off.
* `n_max` — at most this many units, the highest funding first.
* `rebalance` — days between decisions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy
from qr.strategies.library import _hold_between_rebalances, _rebalance_mask

SETTLEMENTS_PER_YEAR = 365.0  # daily funding sums, annualised


class FundingCarry(Strategy):
    family = "funding_carry"

    def __init__(
        self,
        lookback: int = 7,
        entry: float = 0.10,
        exit: float = 0.03,
        ceiling: float = 0.95,
        n_max: int = 10,
        rebalance: int = 1,
        percentile_window: int = 365,
    ) -> None:
        if lookback < 1 or n_max < 1 or rebalance < 1 or percentile_window < 30:
            raise ValueError("lookback, n_max, rebalance are counts >= 1; percentile_window >= 30")
        if exit >= entry:
            raise ValueError(f"exit ({exit}) must sit below entry ({entry}) or units flip on noise")
        if not 0.0 < ceiling <= 1.0:
            raise ValueError("ceiling is a percentile in (0, 1]")
        super().__init__(
            lookback=lookback,
            entry=entry,
            exit=exit,
            ceiling=ceiling,
            n_max=n_max,
            rebalance=rebalance,
            percentile_window=percentile_window,
        )

    def signal(self, panel: Panel) -> pd.DataFrame:
        """Trailing mean of the perp's daily funding, annualised. Positive = longs pay."""
        rate = panel.get("perp_funding_rate")
        if rate is None:
            raise ValueError(
                "this panel carries no `perp_funding_rate`: it is not a carry-unit panel. "
                "Build one with `qr data carry-build` (spot + futures/um bars + funding)."
            )
        window = self.params["lookback"]
        return rate.rolling(window, min_periods=window).mean() * SETTLEMENTS_PER_YEAR

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        p = self.params
        score = self.signal(panel)
        eligible = panel.tradable() & score.notna()
        if universe is not None:
            eligible &= universe.reindex_like(eligible).fillna(False).astype(bool)

        # The crash filter: a unit is not opened when the coin's own funding
        # sits in the top tail of its trailing year. Rolling rank, no lookahead.
        if p["ceiling"] < 1.0:
            window = p["percentile_window"]
            pct = score.rolling(window, min_periods=max(30, window // 4)).rank(pct=True)
            too_hot = (pct > p["ceiling"]).fillna(False)
        else:
            too_hot = pd.DataFrame(False, index=score.index, columns=score.columns)

        # Hysteresis: open above `entry`, keep until below `exit`. Done per
        # bar in order because the state is the previous bar's book.
        open_ok = eligible & (score >= p["entry"]) & ~too_hot
        keep_ok = eligible & (score >= p["exit"])
        marks = _rebalance_mask(panel.index, p["rebalance"])
        held = pd.DataFrame(False, index=score.index, columns=score.columns)
        prev = pd.Series(False, index=score.columns)
        for i, stamp in enumerate(score.index):
            if not marks[i]:
                held.iloc[i] = prev
                continue
            row_keep = prev & keep_ok.iloc[i]
            candidates = open_ok.iloc[i] & ~row_keep
            room = p["n_max"] - int(row_keep.sum())
            chosen = row_keep.copy()
            if room > 0 and candidates.any():
                ranked = score.iloc[i].where(candidates).sort_values(ascending=False)
                chosen[ranked.index[:room]] = True
            elif room < 0:
                # more kept than allowed (n_max shrank between variants): keep the strongest
                ranked = score.iloc[i].where(row_keep).sort_values(ascending=False)
                chosen[:] = False
                chosen[ranked.index[: p["n_max"]]] = True
            held.iloc[i] = chosen
            prev = chosen
        weights = held.astype(float).where(panel.tradable(), 0.0)
        return self.normalise(weights, gross=1.0)

    def trades_on(self, index: pd.DatetimeIndex) -> pd.Series:
        return pd.Series(_rebalance_mask(index, self.params["rebalance"]), index=index)
