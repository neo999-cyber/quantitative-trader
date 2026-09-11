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

    @staticmethod
    def normalise(weights: pd.DataFrame, gross: float = 1.0) -> pd.DataFrame:
        """Scale each bar's weights to a fixed gross exposure; all-zero bars stay flat."""
        total = weights.abs().sum(axis=1)
        scale = np.where(total > 0, gross / total.where(total > 0, 1.0), 0.0)
        return weights.mul(scale, axis=0).fillna(0.0)


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
