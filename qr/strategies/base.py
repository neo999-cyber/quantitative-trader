"""The `Strategy` interface.

One rule, and the whole platform depends on it:

> `target_weights(panel, universe)` returns, for each bar *t*, the portfolio it
> wants to **hold over bar t+1**, using only information available at or before
> the close of bar *t*.

The runner, not the strategy, applies the one-bar shift. Putting the lag in one
place means a leak is a bug in one file rather than an assumption spread over
every strategy, and it makes the gate-1 leakage probe (re-run at lag +1 and
lead −1 and watch what Sharpe does) meaningful.

A strategy also has to describe itself: `describe()` is what goes into the
pre-registration document, and `param_grid()` is what a sweep enumerates —
which is how the trial log knows how many variants were really tried.
"""
from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Sequence

import numpy as np
import pandas as pd

from qr.data.panel import Panel


class Strategy(ABC):
    """Signals in, target weights out."""

    #: Short family name, shared by every variant. Gate 4 clusters on it.
    family: str = "unnamed"

    def __init__(self, **params: Any) -> None:
        self.params: dict[str, Any] = dict(params)

    # -- the contract ------------------------------------------------------

    @abstractmethod
    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        """Weights for bar *t*, held over bar *t+1*. Must not read past *t*."""

    # -- description -------------------------------------------------------

    @property
    def name(self) -> str:
        if not self.params:
            return self.family
        bits = "_".join(f"{k}{_short(v)}" for k, v in sorted(self.params.items()))
        return f"{self.family}_{bits}"

    def describe(self) -> dict[str, Any]:
        return {"family": self.family, "name": self.name, "params": dict(self.params)}

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f'{k}={v!r}' for k, v in sorted(self.params.items()))})"

    # -- sweeps ------------------------------------------------------------

    @classmethod
    def grid(cls, **ranges: Sequence[Any]) -> list["Strategy"]:
        """Every combination in `ranges`, as strategies. `len()` is the trial count."""
        keys = sorted(ranges)
        return [cls(**dict(zip(keys, combo))) for combo in itertools.product(*(ranges[k] for k in keys))]

    # -- helpers for subclasses -------------------------------------------

    @staticmethod
    def mask_to_universe(weights: pd.DataFrame, panel: Panel, universe: pd.DataFrame | None) -> pd.DataFrame:
        """Zero anything outside the universe or on a bar that did not trade."""
        allowed = panel.tradable()
        if universe is not None:
            allowed = allowed & universe.reindex_like(allowed).fillna(False)
        return weights.where(allowed, 0.0).fillna(0.0)

    def trades_on(self, index: pd.DatetimeIndex) -> pd.Series:
        """The bars this variant is allowed to trade on.

        All of them unless the variant carries `rebalance_on`. The runner reads
        this and holds the drifted book in between — see `run_backtest`, and see
        `schedule` for why the drift is not applied here.
        """
        return rebalance_mask(index, self.params.get("rebalance_on"))

    def schedule(self, weights: pd.DataFrame, panel: Panel) -> pd.DataFrame:
        """Validate this variant's rebalance parameter. Does **not** drift.

        It used to drift, and the drift was a bar out of phase with the engine
        that consumes it. `run_backtest` holds the book from bar *t-1* and
        drifts it by bar *t*'s return; a strategy can only drift its own bar
        *t-1* target by bar *t-1*'s return, because bar *t*'s has not happened
        yet. The two books therefore disagreed by one day's move on every bar
        between rebalances, and the engine charged that disagreement as a trade:
        a book scheduled to rebalance twelve times a year traded on all 365,
        for nine times the cost.

        No arrangement of this method can fix that — matching the engine would
        require next bar's return — so the drift now lives in the engine, where
        the phase is right by construction, and this method only keeps the
        parameter honest.

        A strategy with no `rebalance_on` parameter trades every bar, which is
        what every crypto family does and what a proportional-fee venue can
        afford.

        **The parameter is `rebalance_on`, not `rebalance`, deliberately.**
        `CrossSectionalMomentum` and `ShortTermReversal` already take a
        `rebalance` parameter meaning *a number of bars*, and this one is a
        calendar frequency string. Two meanings behind one name in one
        `self.params` dict is a `KeyError` waiting for whoever wires the next
        family up — it did not fire only because those two classes happen to
        return through a different path and never reach this method.
        """
        freq = self.params.get("rebalance_on")
        if freq and freq not in _PERIOD:
            raise ValueError(f"unknown rebalance_on {freq!r}; expected one of {sorted(_PERIOD)}")
        return weights

    @staticmethod
    def normalise(weights: pd.DataFrame, gross: float = 1.0) -> pd.DataFrame:
        """Scale each bar's weights to a fixed gross exposure; all-zero bars stay flat."""
        total = weights.abs().sum(axis=1)
        scale = np.where(total > 0, gross / total.where(total > 0, 1.0), 0.0)
        return weights.mul(scale, axis=0).fillna(0.0)


#: Calendar frequencies `rebalance_on` accepts, mapped to the pandas period
#: they group by. Not a number of bars — see `Strategy.schedule`.
_PERIOD = {"MS": "M", "M": "M", "W": "W", "QS": "Q", "Q": "Q", "YS": "Y", "D": "D"}


def rebalance_mask(index: pd.DatetimeIndex, freq: str | None) -> pd.Series:
    """True on the bars a strategy is allowed to trade.

    `freq` is a pandas offset alias — "MS" for the first bar of each month, "W"
    for weekly — or None for "every bar", which is what the crypto families do
    and what a venue charging proportionally can afford.
    """
    if freq is None:
        return pd.Series(True, index=index)
    if freq not in _PERIOD:
        raise ValueError(
            f"unknown rebalance frequency {freq!r}; expected one of {sorted(_PERIOD)}. "
            f"Note this is a calendar frequency, not a number of bars — the `rebalance` "
            f"parameter on the cross-sectional families is the latter."
        )
    marks = pd.Series(False, index=index)
    if len(index) == 0:
        return marks
    # The first bar *at or after* each period boundary, which is a real trading
    # day; the boundary itself is often a weekend or a holiday.
    naive = pd.DatetimeIndex(index).tz_localize(None) if index.tz is not None else pd.DatetimeIndex(index)
    period = pd.Series(naive, index=index).dt.to_period(_PERIOD[freq])
    first_of_period = ~period.duplicated()
    marks.loc[first_of_period.to_numpy()] = True
    marks.iloc[0] = True
    return marks


def hold_between(
    weights: pd.DataFrame, returns: pd.DataFrame, trades_on: pd.Series
) -> pd.DataFrame:
    """Trade only on `trades_on`; let the book drift in between.

    This is what makes a monthly strategy monthly, and it is not the same thing
    as holding the target weights constant. A book left alone does not stay at
    its target: the winners grow and the losers shrink. Repeating the target
    every bar would tell the engine to trade back to it **daily**, which at a
    $0.35 per-order minimum and a $1,000 account is roughly 13% a year in
    commissions charged for a strategy that was supposed to trade twelve times.

    So between rebalances the target *is* the drifted book — no trade — and on
    a rebalance bar it snaps back to the model's weights. Turnover then appears
    exactly where a real account would generate it.

    Computed per block rather than per bar: within a block each weight grows
    with its own asset's cumulative return and the row is renormalised, which is
    the closed form of compounding the drift day by day.
    """
    index = weights.index
    out = pd.DataFrame(0.0, index=index, columns=weights.columns)
    growth = (1.0 + returns.reindex_like(weights).fillna(0.0)).to_numpy()
    target = weights.to_numpy(dtype=float)
    marks = np.flatnonzero(trades_on.reindex(index).fillna(False).to_numpy())
    if len(marks) == 0:
        return out

    values = out.to_numpy().copy()
    bounds = list(marks) + [len(index)]
    for start, stop in zip(bounds[:-1], bounds[1:]):
        base = target[start]
        values[start] = base
        if stop - start <= 1 or not np.any(base):
            continue
        # Cumulative growth of each asset since the rebalance bar. Row `start`
        # is the freshly set book, held over bar `start`; the book held over
        # bar `start + 1` is that one grown by bar `start`'s return, and so
        # on — each row is grown by the bars it was held *through*, never by
        # the bar it is held *over*. (Until 2026-09-15 this read
        # `growth[start + 1 : stop]`, growing row t by row t's own return: a
        # one-bar look-ahead worth about half the variance per bar to every
        # scheduled book — every Programme 1 monthly and weekly family.)
        cumulative = np.cumprod(growth[start : stop - 1], axis=0)
        grown = base * cumulative
        totals = np.abs(grown).sum(axis=1, keepdims=True)
        gross = np.abs(base).sum()
        with np.errstate(divide="ignore", invalid="ignore"):
            values[start + 1 : stop] = np.where(totals > 0, grown / totals * gross, 0.0)
    return pd.DataFrame(values, index=index, columns=weights.columns)


def _short(value: Any) -> str:
    if isinstance(value, bool):
        return "T" if value else "F"
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value).replace(".", "p")


@dataclass(frozen=True)
class VolTarget:
    """Scale a book so its ex-ante volatility sits near a target.

    Sized from a trailing estimate that ends on the decision bar, capped so a
    quiet patch cannot lever the book into a crash. Crypto's volatility moves by
    an order of magnitude across a cycle, so an unscaled strategy is really a
    bet on regime rather than on its own signal.
    """

    annual_target: float = 0.20
    lookback: int = 30
    max_leverage: float = 1.0
    min_periods: int = 10

    def scale(self, weights: pd.DataFrame, panel: Panel) -> pd.DataFrame:
        returns = panel.returns()
        # Ex-ante portfolio vol from the weights we are about to hold, using the
        # realised covariance proxy of a trailing window that ends at t.
        port = (weights.fillna(0.0) * returns.fillna(0.0)).sum(axis=1)
        realised = port.rolling(self.lookback, min_periods=self.min_periods).std()
        annualised = realised * np.sqrt(panel.periods_per_year)
        factor = (self.annual_target / annualised.replace(0.0, np.nan)).clip(upper=self.max_leverage)
        return weights.mul(factor.fillna(0.0), axis=0)

    def describe(self) -> dict[str, Any]:
        return {
            "annual_target": self.annual_target,
            "lookback": self.lookback,
            "max_leverage": self.max_leverage,
        }
