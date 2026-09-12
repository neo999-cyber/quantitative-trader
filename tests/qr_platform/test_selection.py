"""Gates 5, 6 and 7: selection overfitting, permutation, cross-validated OOS.

Each test builds a case where the right answer is known by construction — pure
noise, a planted persistent edge, an edge that exists only in the first half —
and asserts the machinery reaches it.
"""
import math

import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.library import TSMOM
from qr.validate.cpcv import (
    combinatorial_purged_cv,
    make_splits,
    n_paths,
    walk_forward_efficiency,
)
from qr.validate.cscv import cscv, is_oos_degradation
from qr.validate.permutation import (
    PermutationResult,
    bar_permutation_test,
    permute_panel,
    random_entry_test,
    shuffle_weights,
    signal_shuffle_test,
)

T = 1500


@pytest.fixture()
def noise_variants():
    """200 variants of pure noise — the gate-4/5 self-test population."""
    rng = np.random.default_rng(0)
    return pd.DataFrame(rng.normal(0, 0.02, (T, 200)), columns=[f"v{i}" for i in range(200)])


@pytest.fixture()
def planted(noise_variants):
    """The same, with one variant carrying a real, persistent edge."""
    frame = noise_variants.copy()
    frame["v0"] = np.random.default_rng(99).normal(0.0030, 0.02, T)
    return frame


@pytest.fixture()
def first_half_only():
    """Variants whose apparent edge lives only in the first half of the sample."""
    rng = np.random.default_rng(5)
    frame = pd.DataFrame(rng.normal(0, 0.02, (T, 50)))
    frame.iloc[: T // 2, 0] += 0.004
    return frame


# ------------------------------------------------------------------ gate 5


def test_selecting_among_noise_is_a_coin_toss(noise_variants):
    result = cscv(noise_variants)
    assert result.pbo > 0.40
    assert result.verdict() == "FAIL"
    assert result.n_splits == math.comb(16, 8)


def test_a_real_edge_survives_selection(planted):
    result = cscv(planted)
    assert result.pbo < 0.10
    assert result.verdict() == "PASS"
    # It is picked in-sample almost every split, and it stays good out of sample.
    assert np.mean(result.chosen == planted.columns.get_loc("v0")) > 0.80


def test_an_edge_confined_to_half_the_sample_is_caught(first_half_only):
    assert cscv(first_half_only).verdict() == "FAIL"


def test_pbo_needs_more_than_one_variant():
    with pytest.raises(ValueError, match="at least two variants"):
        cscv(pd.DataFrame({"only": np.random.default_rng(0).normal(0, 0.02, T)}))


def test_an_odd_block_count_is_refused(noise_variants):
    with pytest.raises(ValueError, match="must be even"):
        cscv(noise_variants, n_blocks=15)


def test_too_short_a_sample_is_refused(noise_variants):
    with pytest.raises(ValueError, match="at least"):
        cscv(noise_variants.iloc[:20], n_blocks=16)


def test_block_aggregates_reproduce_a_direct_sharpe(noise_variants):
    """The fast path must be algebraically identical to the slow one."""
    from qr.validate.cscv import _sharpe_from_moments, _sharpe_matrix

    values = noise_variants.to_numpy()[:400]
    direct = _sharpe_matrix(values)
    aggregated = _sharpe_from_moments(
        np.array([len(values)]),
        values.sum(axis=0)[None, :],
        (values**2).sum(axis=0)[None, :],
    )[0]
    assert aggregated == pytest.approx(direct, rel=1e-9)


def test_subsampling_splits_is_reproducible(noise_variants):
    first = cscv(noise_variants, max_splits=500, seed=3)
    second = cscv(noise_variants, max_splits=500, seed=3)
    assert first.n_splits == 500
    assert first.pbo == second.pbo


def test_logits_are_finite_even_at_the_extremes(planted):
    result = cscv(planted)
    assert np.isfinite(result.logits).all()


def test_degradation_slope_is_negative_when_selection_overfits(noise_variants):
    assert cscv(noise_variants).degradation_slope < 0


def test_rank_correlation_is_near_zero_for_noise(noise_variants):
    degradation = is_oos_degradation(noise_variants)
    assert abs(degradation.attrs["rank_correlation"]) < 0.15
    assert len(degradation) == noise_variants.shape[1]


# ------------------------------------------------------------------ gate 6


@pytest.fixture()
def panel(frames):
    return Panel.from_frames(frames)


@pytest.fixture()
def free():
    return CostModel(fee_bps=0.0, half_spread_bps=0.0)


def test_permutation_preserves_the_return_distribution(panel):
    permuted = permute_panel(panel, seed=1)
    original, shuffled = panel.returns(), permuted.returns()
    for symbol in panel.symbols:
        a = original[symbol].dropna().sort_values().to_numpy()
        b = shuffled[symbol].dropna().sort_values().to_numpy()
        assert len(a) == len(b)
        assert b == pytest.approx(a, rel=1e-9)


def test_permutation_preserves_cross_sectional_correlation(panel):
    """Exact for pairs sharing a listing window — which is the case that matters."""
    full_history = [s for s in panel.symbols if panel.close[s].notna().all()]
    assert len(full_history) >= 2
    subset = panel.select(full_history)
    permuted = permute_panel(subset, seed=1, same_permutation=True)
    triu = np.triu_indices(len(full_history), 1)
    before = subset.returns().corr().to_numpy()[triu]
    after = permuted.returns().corr().to_numpy()[triu]
    assert after == pytest.approx(before, abs=1e-9)


def test_correlation_is_only_approximate_across_mismatched_windows(panel):
    """The documented caveat: a shared ordering cannot survive different windows.

    Filtering one global permutation down to each symbol's live bars is what
    keeps listing windows intact, and the price is that two pairs which traded
    over different spans no longer get the identical ordering.
    """
    permuted = permute_panel(panel, seed=1, same_permutation=True)
    pair = ["BTCUSDT", "LATEUSDT"]
    before = panel.returns()[pair].corr().iloc[0, 1]
    after = permuted.returns()[pair].corr().iloc[0, 1]
    assert abs(after - before) < 0.25


def test_independent_permutation_destroys_cross_sectional_correlation(panel):
    """Which is why it is not the default: it makes the null too easy to beat."""
    correlated = pd.DataFrame(
        {s: panel.close[s] for s in panel.symbols[:2]}, index=panel.index
    ).pct_change(fill_method=None)
    shared = permute_panel(panel, seed=2, same_permutation=True).returns()
    independent = permute_panel(panel, seed=2, same_permutation=False).returns()
    pair = panel.symbols[:2]
    assert abs(independent[pair[0]].corr(independent[pair[1]])) <= abs(
        shared[pair[0]].corr(shared[pair[1]])
    ) + 1e-9


def test_permutation_keeps_bars_internally_consistent(panel):
    permuted = permute_panel(panel, seed=3)
    live = permuted.close.notna()
    # Compare only where a bar exists: masking a frame leaves NaN behind, and
    # NaN >= NaN is False, which would fail this for the absent bars alone.
    assert ((permuted["high"] >= permuted["close"] - 1e-9) | ~live).all().all()
    assert ((permuted["low"] <= permuted["close"] + 1e-9) | ~live).all().all()
    assert ((permuted["high"] >= permuted["low"] - 1e-9) | ~live).all().all()


def test_permutation_preserves_listing_windows(panel):
    permuted = permute_panel(panel, seed=4)
    assert (permuted.close.isna() == panel.close.isna()).all().all()


def test_permutation_is_reproducible_from_its_seed(panel):
    a = permute_panel(panel, seed=7).close
    b = permute_panel(panel, seed=7).close
    pd.testing.assert_frame_equal(a, b)
    assert not permute_panel(panel, seed=8).close.equals(a)


def _panel_from_returns(returns: np.ndarray, index: pd.DatetimeIndex, symbols: list[str]) -> Panel:
    frames = {}
    for j, symbol in enumerate(symbols):
        close = 100 * np.exp(np.cumsum(returns[:, j]))
        # Bars that satisfy the platform's own QA: extremes bracket the bar,
        # quote volume is base volume times price.
        frames[symbol] = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1e4,
                "quote_volume": 1e4 * close,
                "trades": 100.0,
            },
            index=index,
        )
    return Panel.from_frames(frames)


@pytest.fixture(scope="module")
def calibration_index():
    return pd.date_range("2019-01-01", "2024-12-31", freq="D", tz="UTC")


@pytest.fixture(scope="module")
def random_walk(calibration_index):
    """Driftless iid returns: nothing for a trend follower to find."""
    rng = np.random.default_rng(100)
    return _panel_from_returns(
        rng.normal(0, 0.04, (len(calibration_index), 6)),
        calibration_index,
        [f"C{i}USDT" for i in range(6)],
    )


@pytest.fixture(scope="module")
def trending(calibration_index):
    """The same volatility with a slow-moving drift — genuine serial dependence."""
    rng = np.random.default_rng(0)
    n = len(calibration_index)
    out = np.zeros((n, 6))
    for j in range(6):
        shocks = rng.normal(0, 0.03, n)
        momentum = 0.0
        for t in range(n):
            momentum = 0.97 * momentum + 0.03 * shocks[t] * 8
            out[t, j] = momentum + shocks[t]
    return _panel_from_returns(out, calibration_index, [f"C{i}USDT" for i in range(6)])


def _gate6(panel: Panel, free: CostModel, n: int = 60):
    evaluate = lambda p: run_backtest(p, TSMOM(lookback=60), free).sharpe(gross=True)
    return bar_permutation_test(panel, evaluate, evaluate(panel), n_permutations=n, seed=0)


def test_a_trend_strategy_does_not_beat_permuted_random_walks(random_walk, free):
    """The null done right: iid bars leave a trend follower nothing to find."""
    result = _gate6(random_walk, free)
    assert result.verdict() == "FAIL"
    assert result.p_value > 0.10


def test_a_trend_strategy_does_beat_permutation_when_the_trend_is_real(trending, free):
    """And the converse, so the test is not just hard to pass."""
    result = _gate6(trending, free)
    assert result.verdict() == "PASS"
    assert result.p_value < 0.05
    # The null is not centred at zero — permuted series still let a vol-targeted
    # book earn something — which is exactly why the comparison is against the
    # permuted distribution rather than against zero.
    assert np.median(result.null) > 0
    assert result.observed > np.percentile(result.null, 95)


def test_the_p_value_can_never_be_zero():
    result = PermutationResult("x", observed=99.0, null=np.zeros(200), n_permutations=200)
    assert result.p_value == pytest.approx(1 / 201)
    assert result.percentile == 100.0


def test_a_worthless_strategy_sits_in_the_middle_of_its_null():
    rng = np.random.default_rng(0)
    result = PermutationResult("x", observed=0.0, null=rng.normal(0, 1, 1000), n_permutations=1000)
    assert 0.3 < result.p_value < 0.7
    assert result.verdict() == "FAIL"


def test_shuffling_weights_keeps_every_book_it_ever_held(panel, free):
    weights = run_backtest(panel, TSMOM(lookback=30), free).weights
    shuffled = shuffle_weights(weights, seed=1)
    assert shuffled.shape == weights.shape
    assert shuffled.sum().sum() == pytest.approx(weights.sum().sum())
    assert sorted(shuffled.abs().sum(axis=1).round(9)) == sorted(weights.abs().sum(axis=1).round(9))


def test_signal_shuffle_scores_the_timing(panel, free):
    result = run_backtest(panel, TSMOM(lookback=30), free)
    returns = panel.returns().fillna(0.0)

    def evaluate(weights: pd.DataFrame) -> float:
        book = weights.shift(1).fillna(0.0)
        series = (book * returns).sum(axis=1)
        sd = series.std(ddof=1)
        return float(series.mean() / sd * math.sqrt(365)) if sd > 0 else 0.0

    out = signal_shuffle_test(evaluate, result.weights, result.sharpe(gross=True), n_permutations=100)
    assert out.name == "signal_shuffle"
    assert len(out.null) == 100
    assert np.isfinite(out.p_value)


def test_random_entry_test_takes_a_seed_per_draw():
    out = random_entry_test(lambda s: float(s % 5), observed=4.5, n_permutations=20)
    assert len(out.null) == 20
    assert out.p_value == pytest.approx(1 / 21)


# ------------------------------------------------------------------ gate 7


def test_path_count_follows_the_formula():
    assert n_paths(10, 2) == math.comb(9, 1) == 9
    assert n_paths(8, 2) == 7
    assert n_paths(6, 3) == math.comb(5, 2) == 10


def test_train_and_test_never_overlap():
    for split in make_splits(1000, 10, 2, purge=20, embargo=10):
        assert len(np.intersect1d(split.train_idx, split.test_idx)) == 0


def test_purging_and_embargo_remove_adjacent_bars():
    without = make_splits(1000, 10, 2, purge=0, embargo=0)[0]
    with_purge = make_splits(1000, 10, 2, purge=30, embargo=10)[0]
    assert len(with_purge.train_idx) < len(without.train_idx)
    # The embargo is asymmetric: more is removed after a test block than before.
    stop = with_purge.test_idx.max()
    assert not np.isin(np.arange(stop + 1, stop + 11), with_purge.train_idx).any()


def test_every_split_covers_k_groups():
    splits = make_splits(1000, 10, 3)
    assert len(splits) == math.comb(10, 3)
    assert all(len(s.test_groups) == 3 for s in splits)


def test_k_outside_its_range_is_refused():
    with pytest.raises(ValueError, match="k must be in"):
        make_splits(1000, 10, 10)


def test_paths_cover_the_whole_sample_once_each():
    result = combinatorial_purged_cv(
        pd.DataFrame(np.random.default_rng(0).normal(0, 0.02, (1000, 3))), n_groups=10, k=2
    )
    assert len(result.path_sharpes) == n_paths(10, 2)
    assert result.n_splits == math.comb(10, 2)


def test_selection_among_noise_does_not_survive_cross_validation(noise_variants):
    result = combinatorial_purged_cv(noise_variants, 365, n_groups=10, k=2, purge=90, embargo=20)
    # The best-of-200 in-sample Sharpe looks real and none of it carries over.
    assert result.is_sharpe > 0.8
    assert result.ratio_to_is < 0.4
    assert result.verdict() == "FAIL"


def test_a_real_edge_survives_cross_validation(planted):
    result = combinatorial_purged_cv(planted, 365, n_groups=10, k=2, purge=90, embargo=20)
    assert result.ratio_to_is > 0.5
    assert result.share_positive == 1.0
    assert result.verdict() == "PASS"
    assert np.mean(np.array(result.selected) == planted.columns.get_loc("v0")) > 0.9


def test_summary_carries_the_worst_path_not_just_the_median(planted):
    summary = combinatorial_purged_cv(planted, 365).summary()
    assert summary["worst_path_sharpe"] <= summary["median_path_sharpe"] <= summary["best_path_sharpe"]


def test_walk_forward_efficiency_separates_an_edge_from_noise(planted, noise_variants):
    good = walk_forward_efficiency(planted, 365, n_windows=6, purge=90)
    bad = walk_forward_efficiency(noise_variants, 365, n_windows=6, purge=90)
    assert good.attrs["wfe"] > 0.5
    assert bad.attrs["wfe"] < 0.5
    assert set(good.columns) >= {"window", "variant", "oos_sharpe"}


def test_cross_validation_needs_variants():
    with pytest.raises(ValueError, match="no variants"):
        combinatorial_purged_cv(pd.DataFrame())
