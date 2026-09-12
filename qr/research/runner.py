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

import math

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
    costs = costs or CostModel.trial()
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
    """Gate 1's one-switch test: the same strategy at lag 0, 1 and 2.

    Lag 1 is the honest setting. What the three numbers mean is less obvious
    than it looks, and getting it wrong makes the test useless in both
    directions:

    * **`peek_ratio` = S(0) / S(1)** is *not* a leak detector. Letting any
      return-based signal act on the bar it is predicting is an enormous and
      entirely expected advantage — an honest TSMOM scores 4 to 8 times its
      lag-1 Sharpe at lag 0. Flagging that flags everything.

    * **`spike_ratio` = S(1) / max(S(0), S(2))** is the real signature. A
      strategy that reaches forward inside its own `target_weights` — the leak
      the runner's shift cannot protect against — has its peek aligned exactly
      onto the bar it predicted, so it posts a huge Sharpe at lag 1 that
      **collapses on both sides**. Measured on a planted example: 45.9 at lag 1
      against 0.7 and 1.0 either side, where an honest strategy peaks at lag 0
      and declines monotonically.

    A spike is not proof on its own: a genuine short-horizon signal (a one-day
    reversal) also predicts exactly one bar ahead and will show one. The thing
    that separates them is magnitude — a real daily edge earns a Sharpe of 1 or
    2, a leak earns 45 — which is why gate 1 blocks on an implausible Sharpe and
    only warns on the shape.

    **`spike_z` is the statistic that decides, and `spike_ratio` is kept only
    for continuity.** A ratio divides by a Sharpe that can sit on either side of
    zero, so it produces numbers of arbitrary magnitude: measured over synthetic
    worlds, `RSIReversal` scored a spike *ratio* of `inf` on data with no edge
    planted in it at all, and 0.55 on data with a genuine one-bar reversal
    planted. It ordered the two worlds backwards. On real data it reported 5.88
    for the trial's control family, and I read that as possible evidence of a
    look-ahead in a strategy that turns out to be clean.

    The fix is to stop dividing. What the test actually asks is whether lag 1
    stands above its neighbours by more than estimation noise, which is a
    difference measured in standard errors:

        spike_z = (S(1) - max(S(0), S(2))) / sqrt(periods_per_year / n_bars)

    The denominator is one standard error of an annualised Sharpe of zero over
    this sample, so it is never zero and never near it. Two Sharpes that are
    both noise give a small `z` however their ratio behaves, and a planted
    oracle — whose neighbours really do collapse to nothing — gives a very large
    one. That is the ordering the statistic is supposed to have and the ratio
    did not.

    This is the second place in the engine where a ratio was dividing by
    something that could pass through zero, after walk-forward efficiency
    (`docs/07_ENGINE_FIXES.md` §4). Finding the first should have prompted a
    search for the rest. It did not, and this one was found only by
    investigating the strategy it had wrongly accused.
    """
    rows = []
    for lag in (0, 1, 2):
        result = run_backtest(panel, strategy, costs, universe, lag=lag)
        rows.append({"lag": lag, "sharpe": result.sharpe(), "gross_sharpe": result.sharpe(gross=True)})
    frame = pd.DataFrame(rows).set_index("lag")
    honest = frame.loc[1, "gross_sharpe"]
    neighbours = max(frame.loc[0, "gross_sharpe"], frame.loc[2, "gross_sharpe"])
    # One standard error of an annualised Sharpe of zero over this sample.
    standard_error = math.sqrt(panel.periods_per_year / max(1, len(panel)))
    frame.attrs["peek_ratio"] = _ratio(frame.loc[0, "gross_sharpe"], honest)
    frame.attrs["spike_ratio"] = _ratio(honest, neighbours)
    frame.attrs["spike_z"] = (
        float((honest - neighbours) / standard_error)
        if np.isfinite(honest) and np.isfinite(neighbours)
        else float("nan")
    )
    frame.attrs["sharpe_standard_error"] = float(standard_error)
    frame.attrs["honest_sharpe"] = float(honest)
    return frame


def _ratio(numerator: float, denominator: float) -> float:
    """`numerator / denominator`, or infinity when only the numerator works."""
    if not np.isfinite(numerator) or not np.isfinite(denominator):
        return np.nan
    if denominator > 0:
        return float(numerator / denominator)
    return np.inf if numerator > 0 else np.nan
