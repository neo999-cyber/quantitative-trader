"""Known answers, not plausible ones.

Every other test file here checks that a piece of the engine behaves sensibly.
None of them checked that the whole thing produces the number you get with a
pencil — and for months it did not. A book scheduled to rebalance twelve times
a year was charged for 365 trades, every ETF family ran that way, and it was
caught by accident while designing an unrelated strategy around order counts.
467 tests passed throughout.

The difference matters. A test that asserts turnover is "reasonable" passes on
a 9x error. A test that asserts a three-asset, five-bar book returns exactly
what arithmetic says cannot.

Three kinds of check live here:

* **worked examples** — small enough to compute by hand, asserted to the last
  decimal place;
* **invariants** — identities that must hold for every strategy and every
  schedule, so a defect in one family is caught by the whole suite;
* **conservation** — net is gross minus costs, and the equity curve is the
  product of the net returns, with nothing lost in between.
"""
import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import drift, run_backtest
from qr.strategies.base import Strategy, rebalance_mask
from qr.strategies.library import (
    BuyAndHold,
    CrossSectionalMomentum,
    LongShortMomentum,
    RSIReversal,
    ShortTermReversal,
    TSMOM,
)


def panel_from(prices: dict[str, list[float]], start="2024-01-01") -> Panel:
    """A panel with exactly these closes. No noise, no generator, no surprises."""
    index = pd.date_range(start, periods=len(next(iter(prices.values()))), freq="D", tz="UTC")
    frames = {}
    for symbol, series in prices.items():
        close = pd.Series(series, index=index, dtype=float)
        frames[symbol] = pd.DataFrame(
            {
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": pd.Series(1e6, index=index),
                "quote_volume": close * 1e6,
            }
        )
    return Panel.from_frames(frames)


class Fixed(Strategy):
    """Holds exactly the weights it is given, on the bars it is given them."""

    family = "fixed"

    def __init__(self, weights: pd.DataFrame, rebalance_on: str | None = None) -> None:
        super().__init__(rebalance_on=rebalance_on)
        self._weights = weights

    def target_weights(self, panel, universe=None):
        return self._weights.reindex_like(panel.close).fillna(0.0)


# ----------------------------------------------------------- worked examples


def test_a_five_bar_two_asset_book_returns_what_arithmetic_says():
    """Half in each of two assets, held throughout, no costs.

    A: 100 -> 110 -> 121   (+10% twice)
    B: 100 -> 90  -> 99    (-10%, then +10%)

    Bar 2 gross = 0.5(+0.10) + 0.5(-0.10) = 0.0 exactly.
    Bar 3 the book has drifted to 55/45 of a 100 total, so
          gross = (55(+0.10) + 45(+0.10)) / 100 = +0.10.
    """
    panel = panel_from({"A": [100, 110, 121], "B": [100, 90, 99]})
    weights = pd.DataFrame(0.5, index=panel.index, columns=["A", "B"])
    free = CostModel(fee_bps=0.0, half_spread_bps=0.0)

    result = run_backtest(panel, Fixed(weights), free)

    # Bar 1 is NaN (no prior return); the book is set at bar 1 and held.
    assert np.isclose(result.gross.iloc[1], 0.0, atol=1e-12)
    assert np.isclose(result.gross.iloc[2], 0.10, atol=1e-12)
    assert np.isclose(float((1 + result.net.fillna(0.0)).prod()), 1.10, atol=1e-12)


#: The engine holds a target from the bar *after* it is emitted — `lag=1`, the
#: only honest setting. The first three worked examples below were written
#: without it and all three failed, which is the entire argument for having
#: them: the hand arithmetic and the engine disagreed, and this time it was the
#: hand arithmetic. A fixture therefore needs one more bar than the trade it is
#: trying to describe.
LAG = 1


def test_turnover_is_the_distance_from_the_drifted_book_to_the_target():
    """Hold A, then switch the whole book to B. That switch is 2.0 of turnover.

    One unit sold and one bought, which is what |Delta weight| summed across
    the book means and is the quantity every cost in the model is charged on.
    Prices are constant, so no drift muddies it.
    """
    panel = panel_from({"A": [100] * 4, "B": [100] * 4})
    weights = pd.DataFrame(
        [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]], index=panel.index, columns=["A", "B"]
    )
    result = run_backtest(panel, Fixed(weights), CostModel(fee_bps=0.0, half_spread_bps=0.0))

    assert np.isclose(result.turnover.iloc[1], 1.0, atol=1e-12)  # buying in
    assert np.isclose(result.turnover.iloc[3], 2.0, atol=1e-12)  # the switch
    assert np.isclose(float(result.turnover.sum()), 3.0, atol=1e-12)


def test_a_flat_rate_venue_charges_the_rate_times_the_turnover():
    """10 bps of fee and 2 of half-spread on 3.0 of turnover is 36 bps. Exactly."""
    panel = panel_from({"A": [100] * 4, "B": [100] * 4})
    weights = pd.DataFrame(
        [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]], index=panel.index, columns=["A", "B"]
    )
    result = run_backtest(panel, Fixed(weights), CostModel(fee_bps=10.0, half_spread_bps=2.0))
    assert np.isclose(float(result.costs.sum()), 3.0 * 12e-4, atol=1e-15)


def test_a_per_order_floor_charges_the_floor_once_per_order():
    """$1,000 account, one $1,000 order at $100 a share: 10 shares.

    10 x $0.0035 = 3.5 cents, so the $0.35 minimum applies — one order, one
    floor, 35 bps of the notional traded.
    """
    panel = panel_from({"A": [100, 100, 100]})
    weights = pd.DataFrame([[0.0], [1.0], [1.0]], index=panel.index, columns=["A"])
    model = CostModel.ibkr_etf(half_spread_bps=0.0)
    result = run_backtest(panel, Fixed(weights), model, equity=1_000.0)
    assert np.isclose(float(result.turnover.sum()), 1.0, atol=1e-12)
    assert np.isclose(float(result.costs.sum()), 0.35 / 1_000.0, atol=1e-12)


# ----------------------------------------------------------------- invariants


ALL_STRATEGIES = [
    BuyAndHold(),
    TSMOM(lookback=20),
    CrossSectionalMomentum(lookback=30, skip=0, n_long=2, rebalance=1),
    ShortTermReversal(lookback=5, n_long=2, rebalance=1),
    RSIReversal(down_days=2, rsi_max=40.0, hold=3),
    LongShortMomentum(lookback=30, skip=0, n_side=2, rebalance_on=None),
]


@pytest.fixture(scope="module")
def market():
    from qr.validate.selftest import noise_world

    return noise_world(n_symbols=8, years=4, seed=17)


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: s.family)
def test_net_is_gross_minus_costs_for_every_strategy(strategy, market):
    """The one identity the whole battery reads through. Nothing may leak."""
    result = run_backtest(market, strategy, CostModel.trial())
    assert np.allclose(result.net, result.gross - result.costs, atol=1e-15)


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: s.family)
def test_the_equity_curve_is_the_product_of_the_net_returns(strategy, market):
    result = run_backtest(market, strategy, CostModel.trial())
    assert np.allclose(result.equity, (1.0 + result.net.fillna(0.0)).cumprod(), atol=1e-12)


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: s.family)
def test_costs_are_never_negative(strategy, market):
    """A cost model that pays you is a sign error, and would flatter everything."""
    result = run_backtest(market, strategy, CostModel.trial())
    assert float(result.costs.min()) >= 0.0
    assert float(result.cost_parts.to_numpy().min()) >= -1e-15


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: s.family)
def test_the_split_sums_to_the_charge(strategy, market):
    result = run_backtest(market, strategy, CostModel.trial())
    assert np.allclose(result.cost_parts.sum(axis=1), result.costs, atol=1e-15)


@pytest.mark.parametrize("strategy", ALL_STRATEGIES, ids=lambda s: s.family)
def test_nothing_is_held_in_a_bar_the_panel_calls_untradable(strategy, market):
    result = run_backtest(market, strategy, CostModel.trial())
    forbidden = result.held.where(~market.tradable(), 0.0)
    assert float(forbidden.abs().to_numpy().max()) == 0.0


@pytest.mark.parametrize("freq,per_year", [("MS", 12), ("QS", 4), ("W", 52), ("YS", 1)])
def test_a_scheduled_book_trades_on_its_schedule_and_no_other_bar(freq, per_year, market):
    """The invariant the phase bug violated, stated for every frequency.

    A book may trade only on its rebalance bars. Not approximately, not
    "mostly" — the count of bars carrying turnover cannot exceed the count of
    scheduled bars. Written as a property over frequencies rather than a case,
    because the defect it guards was found in one family and present in five.
    """
    strategy = BuyAndHold(rebalance_on=freq)
    result = run_backtest(market, strategy, CostModel.etf_trial(), equity=1_000.0)

    scheduled = int(rebalance_mask(market.index, freq).sum())
    traded = int((result.turnover > 1e-12).sum())
    assert traded <= scheduled, f"{traded} bars traded against {scheduled} scheduled"

    years = len(market) / market.periods_per_year
    assert traded / years <= per_year + 1


def test_the_schedule_is_the_identity_when_every_bar_is_a_rebalance_bar(market):
    """Provable, and therefore assertable: a crypto family cannot be affected."""
    model = CostModel.trial()
    for strategy, daily in [
        (BuyAndHold(), BuyAndHold(rebalance_on="D")),
        (TSMOM(lookback=20), TSMOM(lookback=20, rebalance_on="D")),
    ]:
        a = run_backtest(market, strategy, model)
        b = run_backtest(market, daily, model)
        assert np.allclose(a.net, b.net, atol=1e-15)
        assert np.allclose(a.turnover, b.turnover, atol=1e-15)


def test_holding_the_drifted_book_costs_nothing_between_rebalances():
    """No prices move, so a monthly book pays only on its rebalance bars.

    With constant prices the drift is the identity, which makes the expected
    answer knowable: one charge per scheduled bar, and nothing in between.
    """
    n = 90
    panel = panel_from({"A": [100.0] * n, "B": [50.0] * n})
    strategy = BuyAndHold(rebalance_on="MS")
    result = run_backtest(panel, strategy, CostModel.etf_trial(), equity=1_000.0)

    marks = rebalance_mask(panel.index, "MS")
    traded_bars = result.turnover[result.turnover > 1e-12].index
    # The book is empty before the first rebalance, so it can only trade on a
    # marked bar, and only on the first one is there anything to buy.
    assert set(traded_bars) <= set(marks[marks].index)


@pytest.mark.parametrize("lag", [0, 1, 2])
def test_the_leakage_probe_lags_leave_the_schedule_intact(lag, market):
    """Gate 1 re-runs the book at three lags; none may break the calendar."""
    result = run_backtest(market, BuyAndHold(rebalance_on="MS"), CostModel.etf_trial(),
                          equity=1_000.0, lag=lag)
    scheduled = int(rebalance_mask(market.index, "MS").sum())
    assert int((result.turnover > 1e-12).sum()) <= scheduled


# --------------------------------------------------------------- conservation


def test_a_book_that_never_trades_costs_nothing(market):
    """Zero turnover, zero cost — for a model with no holding charge."""
    weights = pd.DataFrame(0.0, index=market.index, columns=market.symbols)
    result = run_backtest(market, Fixed(weights), CostModel.etf_trial(), equity=1_000.0)
    assert float(result.costs.sum()) == 0.0
    assert float(result.turnover.sum()) == 0.0
    assert np.allclose(result.net.fillna(0.0), 0.0)


def test_the_drift_of_a_book_conserves_its_own_value(market):
    """Drifted weights must still describe the same portfolio, rescaled.

    If drift did not renormalise by the portfolio's own return, a book would
    silently gain or lose gross exposure every bar, and every turnover figure
    after it would be measuring that instead of a trade.
    """
    weights = pd.DataFrame(1.0 / len(market.symbols), index=market.index, columns=market.symbols)
    drifted = drift(weights, market.returns())
    live = drifted[drifted.abs().sum(axis=1) > 0]
    assert np.allclose(live.sum(axis=1), 1.0, atol=1e-12)
