import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.data.universe import UniverseSpec, membership
from qr.execution.costs import BPS, CostModel
from qr.research.crosscheck import compare, vectorbt_equity, vectorbt_status
from qr.research.runner import drift, leakage_probe, run_backtest
from qr.strategies.base import Strategy
from qr.strategies.library import BuyAndHold, RandomEntry, TSMOM


@pytest.fixture()
def panel(frames):
    return Panel.from_frames(frames)


@pytest.fixture()
def universe(panel):
    return membership(panel, UniverseSpec(n=3, lookback=30, min_history=60))


@pytest.fixture()
def free():
    return CostModel(fee_bps=0.0, half_spread_bps=0.0)


class Always(Strategy):
    """Hold one named symbol at full weight, always."""

    family = "always"

    def __init__(self, symbol: str = "BTCUSDT") -> None:
        super().__init__(symbol=symbol)

    def target_weights(self, panel, universe=None):
        weights = pd.DataFrame(0.0, index=panel.index, columns=panel.symbols)
        weights[self.params["symbol"]] = 1.0
        return self.mask_to_universe(weights, panel, universe)


class Oracle(Strategy):
    """Buys only the bars it already knows go up. The leakage probe must catch it."""

    family = "oracle"

    def target_weights(self, panel, universe=None):
        future = panel.returns()
        weights = (future > 0).astype(float)
        return self.normalise(self.mask_to_universe(weights, panel, universe))


def test_positions_are_held_one_bar_after_the_signal(panel, free):
    result = run_backtest(panel, Always("BTCUSDT"), free)
    assert (result.held.iloc[0] == 0).all()
    assert result.held.iloc[1:].to_numpy() == pytest.approx(result.weights.iloc[:-1].to_numpy())


def test_a_single_asset_book_earns_that_asset_lagged(panel, free):
    result = run_backtest(panel, Always("BTCUSDT"), free)
    expected = panel.returns()["BTCUSDT"].fillna(0.0)
    # Bar t earns the asset's return using the weight set at t-1, which is 1
    # from the second bar onwards.
    assert result.gross.iloc[2:].to_numpy() == pytest.approx(expected.iloc[2:].to_numpy())


def test_costs_are_zero_when_nothing_trades(panel, free):
    result = run_backtest(panel, Always("BTCUSDT"), CostModel.binance_spot())
    # One entry at the start, then drift-only rebalancing back to full weight.
    assert result.turnover.iloc[1] == pytest.approx(1.0)
    assert result.costs.iloc[3:].sum() == pytest.approx(0.0, abs=1e-12)


def test_turnover_is_measured_against_the_drifted_book():
    index = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    prev = pd.DataFrame([[0.5, 0.5]] * 3, index=index, columns=["A", "B"])
    returns = pd.DataFrame([[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]], index=index, columns=["A", "B"])
    drifted = drift(prev, returns)
    # A doubles, so it is two thirds of the book before any trading happens.
    assert drifted.loc[index[1], "A"] == pytest.approx(2 / 3)
    assert drifted.loc[index[1], "B"] == pytest.approx(1 / 3)


def test_net_is_gross_minus_costs(panel):
    costs = CostModel.binance_spot()
    result = run_backtest(panel, TSMOM(lookback=30), costs)
    pd.testing.assert_series_equal(result.net, (result.gross - result.costs).rename("net"))
    ratio = result.stats()["net_over_gross"]
    # NaN when gross is negative: there is no fraction of a loss to survive.
    assert np.isnan(ratio) or ratio <= 1.0


def test_doubling_costs_lowers_net_return(panel):
    cheap = CostModel.binance_spot()
    dear = cheap.stressed(2.0)
    strategy = TSMOM(lookback=30)
    assert run_backtest(panel, strategy, dear).net.sum() < run_backtest(panel, strategy, cheap).net.sum()


def test_a_strategy_cannot_hold_a_symbol_outside_the_universe(panel, universe, free):
    result = run_backtest(panel, Always("LATEUSDT"), free, universe)
    outside = ~universe["LATEUSDT"]
    assert (result.weights.loc[outside.to_numpy(), "LATEUSDT"] == 0).all()


def test_a_delisted_pair_earns_nothing_after_its_last_bar(panel, free):
    result = run_backtest(panel, Always("DEADUSDT"), free)
    after = result.held.index > pd.Timestamp("2023-08-15", tz="UTC")
    assert (result.held.loc[after, "DEADUSDT"] == 0).all()
    assert result.gross.loc[after].abs().sum() == pytest.approx(0.0)


class ForwardLooking(Strategy):
    """Reaches forward inside `target_weights`, where the runner's shift cannot
    protect against it. This is the leak gate 1 has to catch."""

    family = "forward"

    def target_weights(self, panel, universe=None):
        tomorrow = panel.returns().shift(-1)
        return self.normalise(self.mask_to_universe((tomorrow > 0).astype(float), panel, universe))


def test_the_probe_spikes_at_the_reported_lag_for_a_forward_looking_strategy(panel, free):
    """A real leak is aligned by the honest shift, so it collapses either side."""
    probe = leakage_probe(panel, ForwardLooking(), free)
    honest = probe.loc[1, "gross_sharpe"]
    assert honest > 10.0
    assert honest > probe.loc[0, "gross_sharpe"]
    assert honest > probe.loc[2, "gross_sharpe"]
    assert probe.attrs["spike_ratio"] > 5.0


def test_an_honest_strategy_peaks_at_lag_zero_not_at_the_reported_lag(panel, free):
    """Peeking helps any return-based signal, which is why peek_ratio is not a
    leak detector — an honest TSMOM scores several times its lag-1 Sharpe at
    lag 0, and flagging that would flag everything."""
    probe = leakage_probe(panel, TSMOM(lookback=30), free)
    assert probe.attrs["peek_ratio"] > 1.5
    assert probe.attrs["spike_ratio"] < 1.5


def test_the_leakage_probe_is_flat_for_a_strategy_with_no_signal(panel, free):
    probe = leakage_probe(panel, BuyAndHold(), free)
    # Buy-and-hold carries no timing signal, so shifting it changes almost nothing.
    assert probe["gross_sharpe"].std() < 0.2
    assert probe.attrs["spike_ratio"] < 1.5


def test_vol_targeting_lands_near_its_target(panel, free):
    result = run_backtest(panel, TSMOM(lookback=60, vol_target=0.20, vol_lookback=30), free)
    realised = result.gross.std(ddof=1) * np.sqrt(panel.periods_per_year)
    assert 0.12 < realised < 0.30


def test_vol_targeting_off_leaves_the_book_fully_invested(panel, free):
    scaled = run_backtest(panel, TSMOM(lookback=60, vol_target=0.10), free)
    unscaled = run_backtest(panel, TSMOM(lookback=60, vol_target=None), free)
    assert unscaled.weights.abs().sum(axis=1).max() == pytest.approx(1.0)
    assert scaled.gross.std() < unscaled.gross.std()


def test_stats_are_finite_and_self_consistent(panel):
    result = run_backtest(panel, TSMOM(lookback=30), CostModel.binance_spot())
    stats = result.stats()
    assert 0 <= stats["time_in_market"] <= 1
    assert stats["round_trips"] > 0
    assert stats["max_drawdown"] <= 0
    assert result.equity.iloc[-1] == pytest.approx(float((1 + result.net).prod()))


def test_the_share_ledger_engine_agrees_with_the_weight_engine(panel, universe):
    costs = CostModel.binance_spot()
    for strategy in (BuyAndHold(), TSMOM(lookback=45), RandomEntry(n_held=2, hold=10, seed=3)):
        result = run_backtest(panel, strategy, costs, universe)
        comparison = compare(panel, result, costs)
        assert comparison.agrees, f"{strategy.name}: {comparison.max_relative_error:.2e}"


def test_a_broken_vectorbt_is_never_mistaken_for_an_absent_one():
    """An installed-but-unimportable vectorbt must say so, not go quiet.

    vectorbt 1.1 imports plotly's removed `scattermapbox`, so anything that
    pulls plotly >= 6 disables the third engine. If that reads as "not
    installed", the cross-check stops running and still looks like a tick.
    """
    _, status = vectorbt_status()
    assert not status.startswith("broken"), status
    assert status in {"ok"} or status.startswith("absent")


def test_vectorbt_agrees_too_when_it_is_installed(panel, universe):
    module, status = vectorbt_status()
    if module is None:
        pytest.skip(status)
    costs = CostModel.binance_spot()
    result = run_backtest(panel, TSMOM(lookback=45), costs, universe)
    equity = vectorbt_equity(panel, result, costs)
    assert equity is not None
    both = pd.concat([result.equity, equity], axis=1).dropna()
    assert ((both.iloc[:, 0] - both.iloc[:, 1]).abs() / both.iloc[:, 1]).max() < 5e-3


def test_the_grid_helper_enumerates_every_variant():
    grid = TSMOM.grid(lookback=[30, 60, 90], skip=[0, 5])
    assert len(grid) == 6
    assert len({s.name for s in grid}) == 6


def test_strategy_names_are_stable_and_describe_their_params():
    strategy = TSMOM(lookback=90, skip=0, vol_target=0.2)
    assert strategy.describe()["family"] == "tsmom"
    assert "lookback90" in strategy.name
    assert TSMOM(lookback=90, skip=0, vol_target=0.2).name == strategy.name
