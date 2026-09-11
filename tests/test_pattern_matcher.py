import numpy as np

from centaur.screens.pattern_matcher import SetupSpec, flag_setup, backtest_setup, scan_universe, pooled_stats
from conftest import make_ohlcv, inject_setup


def test_setup_fires_only_where_injected():
    df = inject_setup(make_ohlcv(400, seed=11, vol=0.004), at=200)
    sig = flag_setup(df)
    assert bool(sig.iloc[200])
    # never fires on a bar that closed up
    up_bars = df["Close"].diff() > 0
    assert not (sig & up_bars).any()


def test_setup_requires_volume():
    df = inject_setup(make_ohlcv(400, seed=11, vol=0.004), at=200, vol_mult=0.5)
    assert not bool(flag_setup(df).iloc[200])


def test_backtest_excludes_incomplete_forward_window():
    df = inject_setup(make_ohlcv(400, seed=12, vol=0.004), at=399)  # fires on the very last bar
    assert bool(flag_setup(df).iloc[-1])
    stats = backtest_setup(df)
    # the last-bar occurrence has no 5-day forward return, so it must not be counted
    assert stats.last_occurrence != str(df.index[-1].date())


def test_backtest_stats_are_consistent():
    df = make_ohlcv(400, seed=13, vol=0.004)
    for at in (120, 200, 280):
        df = inject_setup(df, at=at)
    stats = backtest_setup(df)
    assert stats.occurrences >= 3
    assert 0.0 <= stats.win_rate <= 1.0
    assert stats.worst <= stats.median_return <= stats.best
    assert np.isclose(stats.edge, stats.mean_return - stats.baseline_mean)


def test_scan_universe_returns_only_live_hits():
    hist = {
        "HIT": inject_setup(make_ohlcv(400, seed=21, vol=0.004), at=399),
        "QUIET": make_ohlcv(400, seed=22, drift=0.002, vol=0.004),
        "SHORT": make_ohlcv(30, seed=23),
    }
    hits = scan_universe(hist, SetupSpec())
    assert [h.ticker for h in hits] == ["HIT"]
    h = hits[0]
    assert h.rsi < 30 and h.consecutive_down >= 3 and h.relative_volume > 1
    assert h.signals and h.signals[0].startswith("technical:")


def test_scan_universe_applies_liquidity_floor():
    hist = {"HIT": inject_setup(make_ohlcv(400, seed=21, vol=0.004), at=399)}
    assert scan_universe(hist, min_avg_dollar_volume=1e15) == []


def test_pooled_stats_counts_across_universe():
    a = inject_setup(make_ohlcv(400, seed=31, vol=0.004), at=150)
    b = inject_setup(make_ohlcv(400, seed=32, vol=0.004), at=250)
    p = pooled_stats({"A": a, "B": b})
    assert p.occurrences >= backtest_setup(a).occurrences + backtest_setup(b).occurrences - 0
