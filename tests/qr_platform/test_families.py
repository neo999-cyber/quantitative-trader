"""The four trial families.

The cross-checks that matter here are structural: that the cross-sectional
strategies hold only what they claim to hold, that rebalancing actually holds a
selection between rebalances rather than churning every bar, and that the RSI
control is bit-for-bit the setup `centaur` already implements — otherwise the
"control" is a different strategy and proves nothing.
"""
import numpy as np
import pandas as pd
import pytest

from centaur.indicators import relative_volume as centaur_relative_volume
from centaur.indicators import rsi as centaur_rsi
from centaur.screens.pattern_matcher import SetupSpec, flag_setup
from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.library import (
    CrossSectionalMomentum,
    RSIReversal,
    ShortTermReversal,
    relative_volume,
    wilder_rsi,
)
from qr.validate.selftest import edge_world, noise_world


@pytest.fixture(scope="module")
def panel():
    return noise_world(n_symbols=8, years=4, seed=3)


@pytest.fixture(scope="module")
def trending():
    return edge_world(n_symbols=8, years=4, seed=3)


@pytest.fixture()
def free():
    return CostModel(fee_bps=0.0, half_spread_bps=0.0)


# ------------------------------------------------------- cross-sectional pair


def test_cross_sectional_momentum_holds_exactly_n_names(panel, free):
    strategy = CrossSectionalMomentum(lookback=60, skip=5, n_long=3, vol_target=None)
    weights = strategy.target_weights(panel)
    live = weights[(weights.abs().sum(axis=1) > 0)]
    assert (live > 0).sum(axis=1).max() == 3
    assert live.sum(axis=1).max() == pytest.approx(1.0)


def test_momentum_buys_the_winners_and_reversal_buys_the_losers(panel):
    momentum = CrossSectionalMomentum(lookback=30, skip=0, n_long=2, rebalance=1, vol_target=None)
    reversal = ShortTermReversal(lookback=30, n_long=2, rebalance=1, vol_target=None)
    # Same score, opposite ends of the ranking.
    score = momentum.signal(panel)
    bar = score.dropna().index[100]
    picked_high = momentum.target_weights(panel).loc[bar]
    picked_low = reversal.target_weights(panel).loc[bar]
    best = score.loc[bar].nlargest(2).index
    worst = score.loc[bar].nsmallest(2).index
    assert set(picked_high[picked_high > 0].index) == set(best)
    assert set(picked_low[picked_low > 0].index) == set(worst)


def test_the_skip_window_excludes_the_most_recent_bars(panel):
    """12-1 means 12 months ending one month ago, not 12 months to today."""
    strategy = CrossSectionalMomentum(lookback=60, skip=21)
    close = panel.close
    expected = close.shift(21) / close.shift(81) - 1.0
    pd.testing.assert_frame_equal(strategy.signal(panel), expected)


def test_a_weekly_rebalance_trades_far_less_than_a_daily_one(panel, free):
    weekly = CrossSectionalMomentum(lookback=60, skip=5, n_long=3, rebalance=7, vol_target=None)
    daily = CrossSectionalMomentum(lookback=60, skip=5, n_long=3, rebalance=1, vol_target=None)
    weekly_turnover = run_backtest(panel, weekly, free).stats()["ann_turnover"]
    daily_turnover = run_backtest(panel, daily, free).stats()["ann_turnover"]
    assert weekly_turnover < daily_turnover / 2


def test_a_selection_is_held_between_rebalances(panel):
    strategy = CrossSectionalMomentum(lookback=60, skip=5, n_long=3, rebalance=7, vol_target=None)
    weights = strategy.target_weights(panel)
    live = weights[weights.abs().sum(axis=1) > 0]
    changes = (live > 0) != (live > 0).shift(1)
    changed_bars = changes.any(axis=1)
    # Changes cluster on rebalance bars; most bars carry the previous book.
    assert changed_bars.mean() < 0.35


def test_the_cross_sectional_families_respect_the_universe(panel, free):
    universe = pd.DataFrame(False, index=panel.index, columns=panel.symbols)
    universe[panel.symbols[:3]] = True
    for strategy in (
        CrossSectionalMomentum(lookback=60, skip=5, n_long=5, vol_target=None),
        ShortTermReversal(lookback=7, n_long=5, vol_target=None),
    ):
        weights = strategy.target_weights(panel, universe)
        assert (weights[panel.symbols[3:]] == 0).all().all()


def test_vol_targeting_applies_to_the_cross_sectional_families(panel, free):
    scaled = run_backtest(panel, CrossSectionalMomentum(lookback=60, vol_target=0.10), free)
    unscaled = run_backtest(panel, CrossSectionalMomentum(lookback=60, vol_target=None), free)
    assert scaled.gross.std() < unscaled.gross.std()


def test_cross_sectional_momentum_finds_a_trending_world(trending, panel, free):
    """The family must work where the effect is planted, and not where it isn't.

    Asserted over a small grid rather than one configuration: a single lookback
    landing badly on one sample says nothing about the family, and picking the
    configuration that happens to work would be the exact sin the rest of this
    repository exists to prevent.
    """
    grid = [
        CrossSectionalMomentum(lookback=lb, skip=0, n_long=3, rebalance=7) for lb in (30, 60, 90)
    ]
    on_trend = [run_backtest(trending, s, free).sharpe() for s in grid]
    on_noise = [run_backtest(panel, s, free).sharpe() for s in grid]
    assert np.median(on_trend) > 0.5
    assert np.median(on_trend) > np.median(on_noise)


# -------------------------------------------------------------- the RSI control


def test_the_panel_rsi_matches_centaurs_series_rsi(panel):
    mine = wilder_rsi(panel.close, 14)
    for symbol in panel.symbols:
        theirs = centaur_rsi(panel.close[symbol], 14)
        assert np.allclose(mine[symbol].dropna(), theirs.dropna(), atol=1e-10)


def test_relative_volume_matches_centaurs(panel):
    mine = relative_volume(panel["volume"], 20)
    for symbol in panel.symbols:
        theirs = centaur_relative_volume(panel["volume"][symbol], 20)
        assert np.allclose(mine[symbol].dropna(), theirs.dropna(), atol=1e-12)


def test_relative_volume_excludes_today_from_its_own_baseline(panel):
    """A baseline including today leaks today's volume into its own threshold."""
    volume = panel["volume"]
    computed = relative_volume(volume, 20)
    expected = volume / volume.shift(1).rolling(20, min_periods=20).mean()
    pd.testing.assert_frame_equal(computed, expected)


@pytest.fixture()
def firing_series():
    """A path engineered to fire: a sustained decline on elevated volume.

    It has to be engineered, because on a random walk the setup essentially
    never fires — see `test_the_setup_almost_never_fires_on_a_random_walk`,
    which is a fact about the control rather than about this fixture.
    """
    n = 200
    index = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    rng = np.random.default_rng(0)
    close = np.full(n, 100.0)
    volume = np.full(n, 1_000_000.0)
    close[:80] = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.005, 80)))  # calm uptrend
    for t in range(80, 120):  # the capitulation: 40 down days on heavy volume
        close[t] = close[t - 1] * 0.985
        volume[t] = 1_500_000
    close[120:] = close[119] * np.exp(np.cumsum(rng.normal(0.001, 0.01, n - 120)))
    return pd.Series(close, index=index), pd.Series(volume, index=index)


def test_the_setup_almost_never_fires_on_a_random_walk():
    """Worth stating plainly, because it decides the control's fate at gate 8.

    "Three consecutive down closes, each on above-average volume" is a short
    sharp move; "RSI(14) below 30" needs a sustained decline. On 900 bars of
    random walk the first happens 19 times and the second 32 times, and they
    coincide **zero** times. A setup that produces no trades cannot clear the
    50-round-trip minimum however good its win rate looks on the few it gets.
    """
    index = pd.date_range("2021-01-01", periods=900, freq="D", tz="UTC")
    rng = np.random.default_rng(0)
    returns = rng.normal(0, 0.03, len(index))
    close = pd.Series(100 * np.exp(np.cumsum(returns)), index=index)
    volume = pd.Series(1e6 * (1 + 4 * np.abs(returns)) * rng.lognormal(0, 0.2, len(index)), index=index)
    panel = Panel.from_frames(
        {"X": pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": volume})}
    )
    assert RSIReversal().setup(panel)["X"].sum() <= 2


def test_the_control_is_bit_for_bit_the_centaur_setup(firing_series):
    close, volume = firing_series
    theirs = flag_setup(
        pd.DataFrame(
            {"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close, "Volume": volume}
        ),
        SetupSpec(),
    )
    panel = Panel.from_frames(
        {"X": pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": volume})}
    )
    ours = RSIReversal().setup(panel)["X"]
    assert theirs.sum() > 0, "the fixture must actually fire, or this proves nothing"
    assert (theirs.to_numpy() == ours.to_numpy()).all()


def test_the_control_holds_a_position_for_the_stated_number_of_bars(firing_series):
    close, volume = firing_series
    panel = Panel.from_frames(
        {"X": pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": volume})}
    )
    strategy = RSIReversal(hold=5)
    fired = strategy.setup(panel)["X"]
    weights = strategy.target_weights(panel)["X"]
    first = fired.idxmax()
    position = weights.loc[first:].head(5)
    assert (position > 0).all()


def test_overlapping_signals_extend_rather_than_double_the_position(firing_series):
    close, volume = firing_series
    panel = Panel.from_frames(
        {"X": pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": volume})}
    )
    weights = RSIReversal(hold=10).target_weights(panel)
    assert weights.max().max() <= 1.0 + 1e-9


def test_the_control_needs_volume(panel):
    without_volume = Panel({k: v for k, v in panel.fields.items() if k != "volume"}, panel.interval)
    with pytest.raises(ValueError, match="needs a volume field"):
        RSIReversal().setup(without_volume)


def test_the_control_is_mostly_flat(panel, free):
    """A screen that fires rarely is not a portfolio strategy, which is the
    first of several reasons it is in the trial as a control."""
    result = run_backtest(panel, RSIReversal(), free)
    assert result.stats()["time_in_market"] < 0.5


# ------------------------------------------------------------------ the registry


def test_every_trial_family_is_reachable_from_the_cli():
    from qr.cli import FAMILIES, _family_class

    for name in FAMILIES:
        cls = _family_class(name)
        assert cls.family == name or name == "buy_and_hold"
        assert cls().family == cls.family


def test_the_four_trial_families_are_registered():
    from qr.cli import FAMILIES

    assert {"tsmom", "xsmom", "reversal", "rsi_reversal"} <= set(FAMILIES)


def test_fixed_params_apply_to_every_grid_variant_and_a_clash_is_refused():
    # Found 2026-09-16: `--param rebalance=24` beside `--grid` was silently
    # dropped and the C1 v2 run decided hourly instead of daily.
    import pytest

    from qr.cli import _build_grid, _family_class

    cls = _family_class("funding_carry")
    grid = _build_grid(cls, ["lookback=[72,168]", "n_max=[5,10]"], ["rebalance=24", "percentile_window=365"])
    assert len(grid) == 4
    assert {s.params["rebalance"] for s in grid} == {24}
    assert {s.params["percentile_window"] for s in grid} == {365}
    with pytest.raises(SystemExit, match="rebalance"):
        _build_grid(cls, ["rebalance=[1,24]"], ["rebalance=24"])
    single = _build_grid(cls, None, ["entry=-1.0", "exit=-2.0", "ceiling=1.0", "n_max=40", "lookback=7"])
    assert len(single) == 1 and single[0].params["n_max"] == 40
