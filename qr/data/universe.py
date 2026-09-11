"""Point-in-time universe construction.

"Top 30 pairs by quote volume" is a survivorship trap unless the 30 are chosen
with the information available on the day. Two rules make it honest:

1. **Rank on a trailing window that ends before the decision bar.** Membership
   for bar *t* is decided from volume up to and including *t−1*, never *t*.
2. **Rank over every pair the bucket has ever carried**, so pairs that were
   large in 2021 and delisted in 2022 are in the 2021 universe and drop out of
   the 2022 one — which is what actually happened to a portfolio holding them.

The output is a boolean membership frame, `date x symbol`, which the strategy
layer intersects with its positions. Membership changes only on rebalance dates
so the universe itself does not generate turnover every bar.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from qr.data.panel import Panel


@dataclass(frozen=True)
class UniverseSpec:
    """The universe definition that goes into the pre-registration document."""

    n: int = 30
    lookback: int = 30
    min_history: int = 90
    rebalance: str = "MS"
    min_quote_volume: float = 0.0
    name: str = "binance_spot_top30"

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "n": self.n,
            "lookback_bars": self.lookback,
            "min_history_bars": self.min_history,
            "rebalance": self.rebalance,
            "min_quote_volume": self.min_quote_volume,
        }


def rank_asof(
    quote_volume: pd.DataFrame,
    asof: pd.Timestamp,
    spec: UniverseSpec,
    history: pd.DataFrame | None = None,
) -> list[str]:
    """The top `n` symbols as they looked on `asof`, using only earlier bars.

    `history` is a count of bars available per symbol at each date; a symbol
    with less than `min_history` of them is excluded, which keeps a pair that
    listed yesterday out of a momentum universe that needs a year of prices.
    """
    past = quote_volume.loc[quote_volume.index < asof]
    if past.empty:
        return []
    window = past.tail(spec.lookback)
    # Median, not mean: one listing-day volume spike should not buy a seat.
    score = window.median(axis=0, skipna=True)
    traded_recently = window.notna().sum(axis=0) >= max(1, spec.lookback // 2)
    score = score[traded_recently & (score > spec.min_quote_volume)]
    if history is not None:
        available = history.loc[history.index < asof]
        if not available.empty:
            enough = available.iloc[-1] >= spec.min_history
            score = score[enough.reindex(score.index).fillna(False)]
    return list(score.sort_values(ascending=False).head(spec.n).index)


def membership(panel: Panel, spec: UniverseSpec = UniverseSpec()) -> pd.DataFrame:
    """Boolean `date x symbol` membership, rebalanced on `spec.rebalance`.

    Between rebalances membership is held constant, and it is always
    intersected with tradability, so a pair that delists mid-month leaves the
    universe on its last bar rather than on the next rebalance date.
    """
    quote_volume = panel.get("quote_volume")
    if quote_volume is None:
        raise ValueError("a volume-ranked universe needs a `quote_volume` field")
    history = panel.close.notna().cumsum()
    index = panel.index
    dates = pd.DatetimeIndex(
        sorted({*pd.date_range(index[0], index[-1], freq=spec.rebalance, tz="UTC"), index[0]})
    )
    dates = dates[(dates >= index[0]) & (dates <= index[-1])]

    out = pd.DataFrame(False, index=index, columns=panel.symbols)
    for asof in dates:
        chosen = rank_asof(quote_volume, asof, spec, history)
        if not chosen:
            continue
        out.loc[out.index >= asof, :] = False
        out.loc[out.index >= asof, chosen] = True
    return out & panel.tradable(spec.min_quote_volume)


def as_instruments(membership_frame: pd.DataFrame) -> pd.DataFrame:
    """Per-symbol summary of a membership frame: first, last and total bars in."""
    rows = []
    for symbol in membership_frame.columns:
        col = membership_frame[symbol]
        if not col.any():
            continue
        rows.append(
            {
                "symbol": symbol,
                "first_in": col.idxmax(),
                "last_in": col[::-1].idxmax(),
                "bars_in": int(col.sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)
