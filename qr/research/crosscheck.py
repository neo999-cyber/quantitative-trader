"""A second, independent engine — because one engine only ever agrees with itself.

`run_backtest` works in weight space: it drifts weights, differences them and
charges the result. This module works in **share space**: it holds units of each
coin and a cash balance, sells and buys to reach the target notional, and pays
the fee out of cash. The two arrive at an equity curve by completely different
arithmetic, so when they agree to within rounding the accounting is right, and
when they diverge one of them has a bug.

`compare()` is what the test suite and the Hypothesis Report call. vectorbt is
wired up as an optional third opinion (`vectorbt_equity`), skipped when it is
not installed, because the research extra is heavy and the gates do not need it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.execution.costs import BPS, CostModel
from qr.research.runner import BacktestResult


@dataclass
class Comparison:
    weight_equity: pd.Series
    share_equity: pd.Series
    max_relative_error: float
    agrees: bool
    tolerance: float

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({"weights": self.weight_equity, "shares": self.share_equity})


def share_ledger(
    panel: Panel,
    held: pd.DataFrame,
    costs: CostModel,
    initial_equity: float = 10_000.0,
) -> pd.Series:
    """Simulate the book as units and cash, one bar at a time.

    `held[t]` is the weight the portfolio is meant to be carrying **through**
    bar *t*, which is exactly what `run_backtest` shifts into place. Here it is
    reached by trading at the close of *t−1*, then marked at the close of *t*.
    """
    close = panel.close
    symbols = list(close.columns)
    prices = close.to_numpy(dtype=float)
    targets = held.reindex_like(close).fillna(0.0).to_numpy(dtype=float)

    units = np.zeros(len(symbols))
    cash = float(initial_equity)
    cost_rate = costs.linear_bps * BPS
    equity_path = np.empty(len(close))

    for t in range(len(close)):
        price = prices[t]
        tradable = np.isfinite(price) & (price > 0)
        # Mark the book at this bar's close before deciding anything.
        marked = np.where(tradable, units * np.nan_to_num(price), 0.0).sum()
        equity = cash + marked
        equity_path[t] = equity

        if t + 1 >= len(close):
            continue
        # Trade into the book we must be holding over the next bar, at this close.
        want_value = targets[t + 1] * equity
        want_units = np.where(tradable, want_value / np.where(tradable, price, 1.0), units)
        delta = want_units - units
        traded_notional = np.abs(delta * np.where(tradable, price, 0.0)).sum()
        cash -= (delta * np.where(tradable, price, 0.0)).sum() + traded_notional * cost_rate
        units = want_units

    return pd.Series(equity_path / initial_equity, index=close.index, name="share_equity")


def compare(
    panel: Panel,
    result: BacktestResult,
    costs: CostModel,
    tolerance: float = 5e-3,
    initial_equity: float = 10_000.0,
) -> Comparison:
    """Do the weight engine and the share engine tell the same story?"""
    shares = share_ledger(panel, result.held, costs, initial_equity)
    weights = result.equity
    both = pd.concat([weights, shares], axis=1).dropna()
    if both.empty:
        return Comparison(weights, shares, np.nan, False, tolerance)
    error = float(((both.iloc[:, 0] - both.iloc[:, 1]).abs() / both.iloc[:, 1].abs()).max())
    return Comparison(weights, shares, error, error <= tolerance, tolerance)


def vectorbt_equity(
    panel: Panel, result: BacktestResult, costs: CostModel, initial_equity: float = 10_000.0
) -> pd.Series | None:
    """A third opinion from vectorbt, or None when it is not installed."""
    try:
        import vectorbt as vbt
    except Exception:  # pragma: no cover - the research extra is optional
        return None
    close = panel.close.ffill()
    portfolio = vbt.Portfolio.from_orders(
        close=close,
        # vectorbt fills at the close of the bar the size is given on, so the
        # position it holds over bar t+1 is size[t] — which is `weights`, not
        # the already-shifted `held` that the weight engine carries.
        size=result.weights.reindex_like(close).fillna(0.0),
        size_type="targetpercent",
        fees=costs.linear_bps * BPS,
        init_cash=initial_equity,
        group_by=True,
        cash_sharing=True,
        # Without this, a rebalance can fail to buy because the sells that free
        # the cash have not been processed yet.
        call_seq="auto",
        freq=panel.interval,
    )
    value = portfolio.value()
    series = value if isinstance(value, pd.Series) else value.iloc[:, 0]
    return (series / initial_equity).rename("vectorbt_equity")
