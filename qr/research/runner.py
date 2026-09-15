"""The backtest runner: target weights in, an honest equity curve out.

The accounting, in order, for each bar *t*:

1. The book held over bar *t* is the target set at *t−1*. That one shift is the
   only place a strategy's signal meets the future, and it lives here so it
   cannot be got wrong per strategy.
2. Positions drift with prices: a winner's weight grows over the bar it was
   held through. Turnover at *t* is measured against the book held over *t−1*
   **drifted by bar *t−1*'s move**, not the previous target, otherwise a
   buy-and-hold strategy appears to trade every bar — and not by bar *t*'s
   move, which the book held over *t* has not seen.
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
from qr.strategies.base import Strategy, hold_between


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
    #: The same drag split into commission / spread / impact / borrow, summing
    #: to `costs`. A gate that can only say "costs ate 62%" cannot say what to
    #: do about it; these four have four different remedies — a bigger account,
    #: a more liquid instrument, a smaller order and a cheaper short.
    cost_parts: pd.DataFrame | None = None
    #: Funding paid (negative) or received (positive) per bar on a perpetual
    #: book, as a fraction of equity. Already inside `gross`; kept separately
    #: so a report can say how much of a carry family's return *was* the
    #: carry. None for a venue that settles no funding.
    carry: pd.Series | None = None
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
    """Gate 2's headline number: the share of gross return that survives costs.

    `nan` when there is no gross return to divide by, **including when it is
    positive but within noise of zero**. `gross_ann > 0` on its own is not a
    sufficient guard: a gross return of 0.1% a year is positive, passes it, and
    makes this ratio a number with no information in it — which gate 2 would
    then compare against a 60% threshold and could pass. A strategy that earns
    nothing has nothing for costs to eat, and gate 2 reads `nan` as exactly
    that.

    The floor is one standard error of a Sharpe over this sample, which is the
    same scale used by the lag-spike test in `leakage_probe` and by gate 8's
    parameter plateau. See `stats.sharpe_standard_error`.
    """
    from qr.validate.stats import sharpe_standard_error

    clean = gross.dropna()
    gross_ann = gross.mean() * ppy
    if not np.isfinite(gross_ann) or gross_ann <= 0:
        return np.nan
    sd = clean.std(ddof=1)
    gross_sharpe = (clean.mean() / sd * math.sqrt(ppy)) if sd > 0 else np.inf
    if gross_sharpe < sharpe_standard_error(len(clean), ppy):
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
    held = targets.shift(lag).fillna(0.0)
    # Hold the drifted book between rebalances. This has to happen *here*,
    # after the shift, because the drift must be in the same phase as the
    # turnover calculation below — a strategy computing it for itself is always
    # one bar out and every bar of that disagreement is charged as a trade.
    # Provably the identity when every bar is a rebalance bar, so a crypto
    # family that trades daily is untouched.
    marks = strategy.trades_on(panel.index) if hasattr(strategy, "trades_on") else None
    if marks is not None and not bool(marks.all()):
        held = hold_between(held, returns, marks)
    held = held.where(panel.tradable(), 0.0)
    if costs.whole_shares:
        # A venue that fills whole shares holds what the account can buy at
        # the price it traded at, which is the previous bar's close for a
        # book set at t-1. The unbuyable remainder is cash, not a cost.
        traded_at = panel.get("close_unadjusted")
        traded_at = (traded_at if traded_at is not None else panel.close).shift(lag)
        held = whole_share_weights(held, traded_at, equity)
    gross = (held * returns.fillna(0.0)).sum(axis=1).rename("gross")
    # Funding is a cash flow on what is held, and it can be income, so it is
    # part of the gross return rather than a cost: a carry family earns
    # nothing else, and gate 2's net-over-gross ratio has to be able to see
    # it. Only a venue that settles funding gets it; on a spot panel the same
    # feature is a fact about the perp's crowd, not a payment.
    carry = None
    funding = panel.get("funding_rate") if costs.funding else None
    if funding is not None:
        carry = funding_pnl(held, funding)
        gross = (gross + carry).rename("gross")

    # The book the trade at the close of t-1 starts from: what was held over
    # bar t-1, grown by bar t-1's move. (Until 2026-09-15 it was grown by bar
    # t's move — the bar the *new* book is held over — which put turnover
    # one bar out of phase with `hold_between` once that was corrected, and
    # matched it only because both looked one bar ahead.)
    drifted = drift(held.shift(1).fillna(0.0), returns.shift(1))
    turnover_matrix = (held - drifted).abs()
    turnover = turnover_matrix.sum(axis=1).rename("turnover")

    adv = volume_adv(panel) if charge_impact else None
    vol = panel.returns().rolling(30, min_periods=5).std() if charge_impact else None
    # The traded price, for a venue that charges per share rather than per
    # dollar. `close_unadjusted` where the loader supplies it: a back-adjusted
    # price is not what the order fills at, and share counts come from the fill.
    prices = panel.get("close_unadjusted")
    if prices is None:
        prices = panel.close
    needs_equity = charge_impact or costs.per_share_usd > 0
    # Gross short weight per bar. A borrow fee accrues on what is held, not on
    # what is traded, so it is the one cost that a book standing perfectly
    # still still pays.
    short_exposure = held.clip(upper=0.0).abs().sum(axis=1)
    parts = costs.components(
        turnover_matrix,
        equity=equity if needs_equity else None,
        adv_notional=adv,
        volatility=vol,
        prices=prices,
        short_exposure=short_exposure,
        periods_per_year=panel.periods_per_year,
    )
    cost = parts.sum(axis=1).rename("cost")
    net = (gross - cost).rename("net")

    return BacktestResult(
        name=strategy.name,
        gross=gross,
        net=net,
        costs=cost,
        cost_parts=parts,
        carry=carry,
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


def whole_share_weights(held: pd.DataFrame, prices: pd.DataFrame, equity: float) -> pd.DataFrame:
    """Floor each position to the whole shares `equity` buys at `prices`.

    A 25% slice of a $1,000 account is $250; of a $700 share that is 0.36
    shares and no on-close order can be placed, so the position is zero. Of a
    $60 share it is 4 shares, $240, 24%. Sign is kept for a short.
    """
    price = prices.reindex_like(held)
    with np.errstate(divide="ignore", invalid="ignore"):
        shares = (held.abs() * float(equity)).div(price.where(price > 0))
    shares = np.floor(shares.fillna(0.0))
    return (shares * price.fillna(0.0) / float(equity)) * np.sign(held)


def funding_pnl(held: pd.DataFrame, funding_rate: pd.DataFrame) -> pd.Series:
    """Per-bar funding flow on a held perpetual book, as a fraction of equity.

    The venue's sign convention: a **positive** rate is paid by longs to
    shorts, so a long weight loses it and a short weight receives it —

        pnl_t = − Σ_s  w_{s,t} · f_{s,t}

    `funding_rate` is the rate settled over the bar the position was held
    for. On daily bars that is the day's three settlements summed
    (`qr.data.funding.daily_funding`), which is complete by 16:00 UTC and so
    is known before the bar closes; on 8-hour bars it is the single
    settlement. A bar with no published rate settles nothing, which is the
    right reading of a bucket that is silent rather than an assumption that
    it was zero.
    """
    rate = funding_rate.reindex_like(held).fillna(0.0)
    return -(held * rate).sum(axis=1).rename("carry")


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
