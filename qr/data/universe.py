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
from typing import Iterable

import numpy as np
import pandas as pd

from qr.data.panel import Panel


#: Instruments that are not a bet on a crypto asset, excluded by name because
#: no mechanical rule catches them. Leveraged tokens are matched by suffix
#: below; these are tokenised commodities, whose price is gold, not crypto.
NOT_CRYPTO_ASSETS = frozenset({"PAXGUSDT", "XAUTUSDT"})

#: Binance's leveraged tokens (BTCUP, BTCDOWN, ETHUP…). Daily-rebalanced
#: derivative products with volatility decay, not spot assets, and all now
#: delisted — but they are in the bucket, so they are in the listing.
LEVERAGED_SUFFIXES = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")


@dataclass(frozen=True)
class UniverseSpec:
    """The universe definition that goes into the pre-registration document.

    `min_annual_vol` is the important one and it exists because of what the
    first real run of `qr data universe` showed: ranking Binance's USDT pairs
    by quote volume puts **stablecoins at the top**. USDCUSDT held a top-30
    seat for 2,433 days, EURUSDT for 1,339, BUSDUSDT for 1,354; six of the
    thirty slots on 2026-08-31 were pegs, fiat or gold. They rank high because
    they are conversion rails, not because anyone speculates on them.

    A crypto strategy holding USDC is holding cash. Leaving those pairs in
    would hand every family a spurious risk-off skill — rotate into the peg
    during a drawdown and the equity curve flatters itself — that is an
    artifact of the universe, not a property of the strategy.

    The volatility floor is mechanical and point-in-time, which is why it is
    preferred to a list of names: a list would need maintaining and would be a
    standing temptation to edit after seeing results.

    Both the window and the level are chosen for **margin**, not to sit just
    above the things being excluded. A peg runs near 1% annualised, EUR near
    8%; Bitcoin's calmest 90-day stretches still run 25-30% and everything
    else in a crypto top-30 runs far higher. A floor of 15% therefore sits in
    a wide empty gap. The window is 90 bars rather than the 30 the volume
    ranking uses, because a 30-bar estimate of an 8% asset reads above 10%
    often enough to let EUR through for a month at a time — which it did, on
    the first attempt.
    """

    n: int = 30
    lookback: int = 30
    min_history: int = 90
    rebalance: str = "MS"
    min_quote_volume: float = 0.0
    #: Annualised realised volatility a pair must exceed to be speculable.
    min_annual_vol: float = 0.15
    #: Bars behind the volatility estimate. Longer than the volume window on
    #: purpose: this filter needs a stable number, not a responsive one.
    vol_lookback: int = 90
    exclude_leveraged: bool = True
    exclude_symbols: frozenset[str] = NOT_CRYPTO_ASSETS
    name: str = "binance_spot_top30"

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "n": self.n,
            "lookback_bars": self.lookback,
            "min_history_bars": self.min_history,
            "rebalance": self.rebalance,
            "min_quote_volume": self.min_quote_volume,
            "min_annual_vol": self.min_annual_vol,
            "vol_lookback_bars": self.vol_lookback,
            "exclude_leveraged": self.exclude_leveraged,
            "exclude_symbols": sorted(self.exclude_symbols),
        }

    def excluded_by_name(self, symbol: str) -> bool:
        if symbol in self.exclude_symbols:
            return True
        return self.exclude_leveraged and symbol.endswith(LEVERAGED_SUFFIXES)


#: The ETF trial's basket: twelve US-listed ETFs spanning the four things a
#: multi-asset trend or rotation strategy needs something to rotate *between* —
#: equities, duration, credit and real assets. Named rather than ranked,
#: because a dozen instruments that all still trade have no membership problem
#: to solve, which removes a whole class of error the crypto universe needed
#: two filters and an amendment to handle.
#:
#: What it does **not** remove is selection of the basket itself. Picking
#: today's well-known ETFs is a choice made with hindsight — none of these has
#: closed, and the ones that closed are not on the list because nobody
#: remembers them. That bias is real, it is smaller than crypto's (these are
#: the largest funds in their categories by a wide margin, chosen for coverage
#: rather than for performance), and it belongs in the pre-registration where
#: it can be argued with rather than in a comment here.
ETF_BASKET: tuple[str, ...] = (
    # equities
    "SPY",   # US large cap
    "QQQ",   # US tech / growth
    "IWM",   # US small cap
    "EFA",   # developed ex-US
    "EEM",   # emerging markets
    # duration and credit
    "TLT",   # 20+ year treasuries
    "IEF",   # 7-10 year treasuries
    "LQD",   # investment-grade credit
    "HYG",   # high yield
    # real assets
    "GLD",   # gold
    "DBC",   # broad commodities
    "VNQ",   # US REITs
)


def fixed_basket(panel: Panel, symbols: Iterable[str] = ETF_BASKET) -> pd.DataFrame:
    """Membership for a named basket: in the list, and trading on the day.

    There is no ranking and no rebalance schedule, because there is no
    selection decision being made through time — which is the whole reason a
    fixed basket is the right universe for the second trial. Membership still
    intersects tradability, so an ETF is out of the book before its inception
    and after any delisting, exactly as a delisted crypto pair was.
    """
    wanted = [s for s in symbols if s in panel.close.columns]
    out = pd.DataFrame(False, index=panel.index, columns=panel.symbols)
    if wanted:
        out.loc[:, wanted] = True
    return out & panel.tradable()


def rank_asof(
    quote_volume: pd.DataFrame,
    asof: pd.Timestamp,
    spec: UniverseSpec,
    history: pd.DataFrame | None = None,
    volatility: pd.DataFrame | None = None,
) -> list[str]:
    """The top `n` symbols as they looked on `asof`, using only earlier bars.

    `history` is a count of bars available per symbol at each date; a symbol
    with less than `min_history` of them is excluded, which keeps a pair that
    listed yesterday out of a momentum universe that needs a year of prices.

    `volatility` is trailing annualised realised volatility, and a pair below
    `spec.min_annual_vol` is dropped as unspeculable — that is what keeps the
    stablecoins out. Like the volume ranking it reads only bars before `asof`,
    so a coin that depegs tomorrow is still excluded today.
    """
    past = quote_volume.loc[quote_volume.index < asof]
    if past.empty:
        return []
    window = past.tail(spec.lookback)
    # Median, not mean: one listing-day volume spike should not buy a seat.
    score = window.median(axis=0, skipna=True)
    traded_recently = window.notna().sum(axis=0) >= max(1, spec.lookback // 2)
    score = score[traded_recently & (score > spec.min_quote_volume)]

    score = score[[s for s in score.index if not spec.excluded_by_name(str(s))]]

    if volatility is not None and spec.min_annual_vol > 0:
        past_vol = volatility.loc[volatility.index < asof]
        if not past_vol.empty:
            recent = past_vol.iloc[-1].reindex(score.index)
            # NaN volatility means not enough bars to judge; that is the
            # min_history check's job, not this one, so it is not a rejection.
            score = score[(recent >= spec.min_annual_vol) | recent.isna()]

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
    # Trailing annualised volatility over the same window the volume ranking
    # uses, so both filters see exactly the same bars.
    volatility = (
        panel.returns().rolling(spec.vol_lookback, min_periods=max(20, spec.vol_lookback // 3)).std()
        * np.sqrt(panel.periods_per_year)
    )
    index = panel.index
    dates = pd.DatetimeIndex(
        sorted({*pd.date_range(index[0], index[-1], freq=spec.rebalance, tz="UTC"), index[0]})
    )
    dates = dates[(dates >= index[0]) & (dates <= index[-1])]

    out = pd.DataFrame(False, index=index, columns=panel.symbols)
    for asof in dates:
        chosen = rank_asof(quote_volume, asof, spec, history, volatility)
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
