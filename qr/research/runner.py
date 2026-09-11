"""The backtest runner: target weights in, an honest equity curve out.

The accounting, in order, for each bar *t*:

1. The book held over bar *t* is the target set at *t−1*. That one shift is the
   only place a strategy's signal meets the future, and it lives here so it
   cannot be got wrong per strategy.
2. Positions drift with prices: a winner's weight grows over the bar. Turnover
   is measured against the **drifted** book, not the previous target, otherwise
   a buy-and-hold strategy appears to trade every bar.
3. Costs are charged on that turnover, at the bar the trade happens.

`gross` is before costs, `net` after — gate 2 compares the two, so both are
kept rather than recomputed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.strategies.base import Strategy


@dataclass
class BacktestResult:
    """Everything a gate might ask for, computed once."""

    name: str
    gross: pd.Series
    net: pd.Series
    costs: pd.Series
    turnover: pd.Series
    weights: pd.DataFrame
    held: pd.DataFrame
    periods_per_year: float
    meta: dict[str, Any] = field(default_factory=dict)

    # -- curves ------------------------------------------------------------

    @property
    def equity(self) -> pd.Series:
        return (1.0 + self.net).cumprod().rename("equity")

    @property
    def gross_equity(self) -> pd.Series:
        return (1.0 + self.gross).cumprod().rename("gross_equity")

    @property
    def drawdown(self) -> pd.Series:
        curve = self.equity
        return (curve / curve.cummax() - 1.0).rename("drawdown")

    # -- statistics --------------------------------------------------------

    def sharpe(self, gross: bool = False) -> float:
        return annualised_sharpe(self.gross if gross else self.net, self.periods_per_year)

    def stats(self) -> dict[str, float]:
        net, gross = self.net, self.gross
        years = len(net) / self.periods_per_year if len(net) else np.nan
        total = float((1.0 + net).prod())
        active = self.held.abs().sum(axis=1) > 0
        return {
            "bars": float(len(net)),
            "years": float(years),
            "cagr": float(total ** (1 / years) - 1) if years and total > 0 else np.nan,
            "ann_return": float(net.mean() * self.periods_per_year),
            "ann_vol": float(net.std(ddof=1) * np.sqrt(self.periods_per_year)),
            "sharpe": self.sharpe(),
            "gross_sharpe": self.sharpe(gross=True),
            "max_drawdown": float(self.drawdown.min()) if len(net) else np.nan,
            "hit_rate": float((net[active] > 0).mean()) if active.any() else np.nan,
            "ann_turnover": float(self.turnover.mean() * self.periods_per_year),
            "total_costs": float(self.costs.sum()),
            "cost_drag_ann": float(self.costs.mean() * self.periods_per_year),
            "net_over_gross": _net_over_gross(net, gross, self.periods_per_year),
            "time_in_market": float(active.mean()) if len(active) else np.nan,
            "round_trips": float(_round_trips(self.held)),
        }


def _net_over_gross(net: pd.Series, gross: pd.Series, ppy: float) -> float:
    """Gate 2's headline number: the share of gross return that survives costs."""
    gross_ann = gross.mean() * ppy
    if not np.isfinite(gross_ann) or gross_ann <= 0:
        return np.nan
    return float((net.mean() * ppy) / gross_ann)


def _round_trips(held: pd.DataFrame) -> int:
    """Count position openings — the N that gate 8's "50-100 trades" refers to."""
    live = held.abs() > 1e-12
    return int((live & ~live.shift(1, fill_value=False)).to_numpy().sum())


def annualised_sharpe(returns: pd.Series, periods_per_year: float) -> float:
    clean = returns.dropna()
    if len(clean) < 2:
        return np.nan
    sd = clean.std(ddof=1)
    if not np.isfinite(sd) or sd == 0:
        return np.nan
    return float(clean.mean() / sd * np.sqrt(periods_per_year))


def drift(weights_prev: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """Where yesterday's book sits after today's move, before any trading.

    Weights grow with their asset and are renormalised by the portfolio's own
    return, which is what actually happens in an account.
    """
    grown = weights_prev * (1.0 + returns.fillna(0.0))
    port = 1.0 + (weights_prev * returns.fillna(0.0)).sum(axis=1)
    port = port.replace(0.0, np.nan)
    return grown.div(port, axis=0).fillna(0.0)


def run_backtest(
    panel: Panel,
    strategy: Strategy,
    costs: CostModel | None = None,
    universe: pd.DataFrame | None = None,
    equity: float = 10_000.0,
    charge_impact: bool = False,
    lag: int = 1,
) -> BacktestResult:
    """Run one strategy over one panel.

    `lag` is the leakage switch gate 1 uses: 1 is the honest setting (act on the
    next bar), 2 delays a further bar and should degrade smoothly, and 0 lets
    the strategy trade on information from the bar it is predicting — if Sharpe
    explodes at `lag=0` relative to `lag=1`, the signal is reading the future.
    """
    costs = costs or CostModel.binance_spot()
    returns = panel.returns()
    targets = strategy.target_weights(panel, universe)
    targets = targets.reindex_like(panel.close).fillna(0.0)
    targets = Strategy.mask_to_universe(targets, panel, universe)

    # The shift is the only place a signal meets the future — but a shifted
    # target can land on a bar where the pair no longer trades, and a book that
    # "holds" a delisted coin neither earns nor can be sold. Re-masking after
    # the shift liquidates it at its last close, which is the honest reading of
    # a bucket that simply stops: no price, no position.
    held = targets.shift(lag).fillna(0.0).where(panel.tradable(), 0.0)
    gross = (held * returns.fillna(0.0)).sum(axis=1).rename("gross")

    drifted = drift(held.shift(1).fillna(0.0), returns)
    turnover_matrix = (held - drifted).abs()
    turnover = turnover_matrix.sum(axis=1).rename("turnover")

    adv = volume_adv(panel) if charge_impact else None
    vol = panel.returns().rolling(30, min_periods=5).std() if charge_impact else None
    cost = costs.charge(turnover_matrix, equity=equity if charge_impact else None, adv_notional=adv, volatility=vol)
    net = (gross - cost).rename("net")

    return BacktestResult(
        name=strategy.name,
        gross=gross,
        net=net,
        costs=cost,
        turnover=turnover,
        weights=targets,
        held=held,
        periods_per_year=panel.periods_per_year,
        meta={
            "strategy": strategy.describe(),
            "costs": costs.describe(),
            "lag": lag,
            "symbols": panel.symbols,
            "start": str(panel.index[0]) if len(panel) else None,
            "end": str(panel.index[-1]) if len(panel) else None,
        },
    )


def volume_adv(panel: Panel, lookback: int = 30) -> pd.DataFrame | None:
    quote = panel.get("quote_volume")
    if quote is None:
        return None
    return quote.rolling(lookback, min_periods=5).median()


def leakage_probe(
    panel: Panel,
    strategy: Strategy,
    costs: CostModel | None = None,
    universe: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Gate 1's one-switch test, as a table.

    Run the same strategy at lag 0, 1 and 2. An honest signal degrades smoothly
    from 1 to 2 and gains only modestly at 0; one that reads the future posts a
    Sharpe at lag 0 that it cannot come close to at lag 1.
    """
    rows = []
    for lag in (0, 1, 2):
        result = run_backtest(panel, strategy, costs, universe, lag=lag)
        rows.append({"lag": lag, "sharpe": result.sharpe(), "gross_sharpe": result.sharpe(gross=True)})
    frame = pd.DataFrame(rows).set_index("lag")
    frame.attrs["leak_ratio"] = _leak_ratio(frame.loc[0, "gross_sharpe"], frame.loc[1, "gross_sharpe"])
    return frame


def _leak_ratio(peek: float, honest: float) -> float:
    """How much better peeking is. Infinite when only the peeking version works."""
    if not np.isfinite(peek) or not np.isfinite(honest):
        return np.nan
    if honest > 0:
        return float(peek / honest)
    return np.inf if peek > 0 else np.nan
