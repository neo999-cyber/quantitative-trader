"""The gate statistics, checked against jsharpe / arch / statsmodels and against
hand-written closed forms. A convention mismatch here is how a dead strategy
gets through gate 4, so each formula is pinned twice."""
import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

from qr.validate.stats import (
    EULER_GAMMA,
    adjusted_p_values,
    annualised_sharpe,
    deflated_sharpe,
    expected_max_sharpe,
    hac_tstat,
    haircut_sharpe,
    min_backtest_length,
    min_track_record_length,
    moments,
    probabilistic_sharpe,
    stationary_bootstrap_ci,
)


@pytest.fixture()
def edge():
    """4 years of daily returns with a real edge: true annual Sharpe ~0.96.

    Seed chosen so the *realised* Sharpe lands near the true one (1.03). Seeds
    are not innocent here — seed 7 realises −0.11 from the same generator, a
    2-sigma draw that would make a fixture named `edge` a lie. That gap between
    true and realised is the thing this whole module exists to measure.
    """
    return pd.Series(np.random.default_rng(11).normal(0.0010, 0.02, 1460))


@pytest.fixture()
def noise():
    """The same length with no edge at all; realised Sharpe 0.07."""
    return pd.Series(np.random.default_rng(13).normal(0.0, 0.02, 1460))


# ------------------------------------------------------------------ moments


def test_moments_are_per_period_and_annualise_by_root_time(edge):
    m = moments(edge)
    assert m.sharpe == pytest.approx(edge.mean() / edge.std(ddof=1))
    assert m.annualised(365) == pytest.approx(m.sharpe * math.sqrt(365))
    assert annualised_sharpe(edge, 365) == pytest.approx(m.annualised(365))


def test_kurtosis_is_non_excess(edge):
    # A normal sample must come back near 3.0, not near 0.0: the PSR formula
    # subtracts 1 from gamma4 and expects the raw fourth moment.
    assert 2.5 < moments(edge).kurtosis < 3.5


def test_too_short_a_sample_gives_nan_rather_than_a_number():
    assert math.isnan(moments(pd.Series([0.01, 0.02])).sharpe)


# ------------------------------------------------------------------ gate 3


def test_hac_tstat_matches_a_plain_t_test_at_zero_lags(edge):
    t_hac, _, lags = hac_tstat(edge, lags=0)
    t_plain = edge.mean() / (edge.std(ddof=1) / math.sqrt(len(edge)))
    assert lags == 0
    assert t_hac == pytest.approx(t_plain, rel=1e-3)


def test_hac_deflates_the_t_stat_of_autocorrelated_returns():
    # Overlapping holding periods make returns positively autocorrelated, which
    # a plain t-test reads as more evidence than there is.
    rng = np.random.default_rng(3)
    shocks = rng.normal(0.0008, 0.02, 3000)
    overlapping = pd.Series(shocks).rolling(10).mean().dropna()
    t_naive, _, _ = hac_tstat(overlapping, lags=0)
    t_hac, _, lags = hac_tstat(overlapping)
    assert lags > 0
    assert abs(t_hac) < abs(t_naive)


def test_the_default_lag_follows_the_newey_west_rule(edge):
    _, _, lags = hac_tstat(edge)
    assert lags == int(math.floor(4 * (len(edge) / 100) ** (2 / 9)))


def test_psr_matches_the_published_closed_form(edge):
    m = moments(edge)
    variance = 1 - m.skew * m.sharpe + (m.kurtosis - 1) / 4 * m.sharpe**2
    expected = sps.norm.cdf(m.sharpe * math.sqrt(m.n - 1) / math.sqrt(variance))
    assert probabilistic_sharpe(edge) == pytest.approx(float(expected))


def test_psr_agrees_with_jsharpe():
    jsharpe = pytest.importorskip("jsharpe")
    series = pd.Series(np.random.default_rng(7).normal(0.001, 0.02, 800))
    m = moments(series)
    theirs = jsharpe.probabilistic_sharpe_ratio(m.sharpe, 0.0, T=m.n, gamma3=m.skew, gamma4=m.kurtosis)
    # Not exact: jsharpe's variance term differs from Bailey-Lopez de Prado's
    # in the last decimal. Immaterial against a 0.95 threshold, but it is the
    # reason these formulas are written out here rather than imported.
    assert probabilistic_sharpe(series) == pytest.approx(theirs, abs=1e-3)


def test_negative_skew_lowers_psr_for_the_same_sharpe():
    rng = np.random.default_rng(5)
    symmetric = rng.normal(0.0010, 0.02, 1460)
    # Same mean and standard deviation, negative skew.
    skewed = -np.asarray(sps.skewnorm.rvs(a=8, size=1460, random_state=5))
    skewed = skewed - skewed.mean()
    skewed = skewed / skewed.std(ddof=1) * symmetric.std(ddof=1) + symmetric.mean()

    assert moments(pd.Series(skewed)).skew < -0.3
    assert moments(pd.Series(skewed)).sharpe == pytest.approx(moments(pd.Series(symmetric)).sharpe, rel=1e-6)
    assert probabilistic_sharpe(pd.Series(skewed)) < probabilistic_sharpe(pd.Series(symmetric))


def test_psr_rises_with_track_record_length():
    rng = np.random.default_rng(2)
    long = pd.Series(rng.normal(0.0010, 0.02, 4000))
    short = long.iloc[:400]
    assert probabilistic_sharpe(long) > probabilistic_sharpe(short)


def test_min_track_record_length_is_infinite_for_a_negative_edge(noise):
    series = noise if moments(noise).sharpe < 0 else -noise
    # jsharpe returns a finite number here by squaring away the sign; a Sharpe
    # below the benchmark never clears it, however long you wait.
    assert min_track_record_length(series) == math.inf


def test_min_track_record_length_shrinks_as_the_edge_grows():
    rng = np.random.default_rng(4)
    weak = pd.Series(rng.normal(0.0004, 0.02, 2000))
    strong = pd.Series(rng.normal(0.0030, 0.02, 2000))
    assert min_track_record_length(strong) < min_track_record_length(weak)


def test_a_sample_shorter_than_its_own_mintrl_is_the_gate_3_failure(edge):
    required = min_track_record_length(edge)
    assert required > 0
    # The gate compares this against len(edge); the point is that it can exceed it.
    assert math.isfinite(required)


def test_bootstrap_ci_brackets_the_point_estimate_and_scales_like_the_standard_error(edge):
    point = annualised_sharpe(edge, 365)
    lower, upper, draws = stationary_bootstrap_ci(edge, 365, reps=1000, seed=1)
    assert lower < point < upper
    assert len(draws) == 1000
    assert draws.mean() == pytest.approx(point, abs=0.15)
    # For near-iid returns the 95% width is about 2 x 1.96 x sqrt(ppy / T).
    assert (upper - lower) == pytest.approx(2 * 1.96 * math.sqrt(365 / len(edge)), rel=0.35)


def test_bootstrap_is_reproducible_from_its_seed(edge):
    first = stationary_bootstrap_ci(edge, 365, reps=300, seed=42)
    second = stationary_bootstrap_ci(edge, 365, reps=300, seed=42)
    assert first[:2] == second[:2]


def test_bootstrap_declines_to_guess_on_a_tiny_sample():
    lower, upper, draws = stationary_bootstrap_ci(pd.Series([0.01] * 10), 365)
    assert math.isnan(lower) and math.isnan(upper) and len(draws) == 0


# ------------------------------------------------------------------ gate 4


def test_expected_max_sharpe_matches_jsharpe():
    jsharpe = pytest.importorskip("jsharpe")
    for n in (5, 45, 200, 5000):
        assert expected_max_sharpe(n, 0.0004) == pytest.approx(
            jsharpe.expected_maximum_sharpe_ratio(n, 0.0004)
        )


def test_expected_max_sharpe_matches_its_closed_form():
    variance, n = 0.0004, 200
    a = sps.norm.ppf(1 - 1 / n)
    b = sps.norm.ppf(1 - 1 / (n * math.e))
    expected = math.sqrt(variance) * ((1 - EULER_GAMMA) * a + EULER_GAMMA * b)
    assert expected_max_sharpe(n, variance) == pytest.approx(expected)


def test_searching_harder_raises_the_bar(edge):
    assert expected_max_sharpe(1000, 0.0004) > expected_max_sharpe(45, 0.0004)
    assert expected_max_sharpe(1, 0.0004) == 0.0


def test_more_dispersed_trials_raise_the_bar():
    assert expected_max_sharpe(200, 0.0016) > expected_max_sharpe(200, 0.0004)


def test_deflation_always_costs_something(edge):
    plain = probabilistic_sharpe(edge)
    deflated, benchmark = deflated_sharpe(edge, n_trials=200, sharpe_variance=0.0004)
    assert benchmark > 0
    assert deflated < plain


def test_deflation_kills_the_best_of_two_hundred_noise_variants():
    """The gate-4 self-test in miniature: search noise, deflate, get nothing."""
    rng = np.random.default_rng(0)
    variants = [pd.Series(rng.normal(0.0, 0.02, 1460)) for _ in range(200)]
    sharpes = np.array([moments(v).sharpe for v in variants])
    winner = variants[int(np.argmax(sharpes))]

    assert probabilistic_sharpe(winner) > 0.90  # looks significant on its own
    deflated, _ = deflated_sharpe(winner, n_trials=200, trial_sharpes=sharpes)
    assert deflated < 0.90  # and is not, once the search is priced in


def test_deflation_spares_a_real_edge_found_in_one_shot():
    strong = pd.Series(np.random.default_rng(1).normal(0.0025, 0.02, 2000))
    deflated, _ = deflated_sharpe(strong, n_trials=10, sharpe_variance=0.0004)
    assert deflated > 0.95


def test_trial_sharpes_can_supply_the_variance(edge):
    sharpes = np.random.default_rng(0).normal(0.0, 0.02, 50)
    from_series, benchmark = deflated_sharpe(edge, 50, trial_sharpes=sharpes)
    from_value, benchmark2 = deflated_sharpe(edge, 50, sharpe_variance=float(sharpes.var(ddof=1)))
    assert from_series == pytest.approx(from_value)
    assert benchmark == pytest.approx(benchmark2)


def test_deflation_needs_a_variance_from_somewhere(edge):
    with pytest.raises(ValueError, match="sharpe_variance or trial_sharpes"):
        deflated_sharpe(edge, 50)
    with pytest.raises(ValueError, match="at least two variants"):
        deflated_sharpe(edge, 50, trial_sharpes=[0.1])


def test_min_backtest_length_is_two_log_n_over_sharpe_squared():
    assert min_backtest_length(45, 1.0) == pytest.approx(2 * math.log(45))
    assert min_backtest_length(45, 1.0) == pytest.approx(7.62, abs=0.01)
    assert min_backtest_length(200, 0.5) > min_backtest_length(200, 1.0)


# ------------------------------------------------------------- haircuts


def test_a_single_trial_leaves_the_sharpe_alone():
    haircut, adjusted = haircut_sharpe(1.2, n_trials=1, p_value=0.001, method="bonferroni")
    assert haircut == pytest.approx(1.2)
    assert adjusted == pytest.approx(0.001)


def test_bhy_is_stricter_than_bonferroni_over_many_trials():
    bonf, p_bonf = haircut_sharpe(1.5, 200, 1e-5, method="bonferroni")
    bhy, p_bhy = haircut_sharpe(1.5, 200, 1e-5, method="bhy")
    assert p_bhy > p_bonf
    assert bhy < bonf < 1.5


def test_holm_and_bonferroni_coincide_for_the_most_significant_variant():
    assert haircut_sharpe(1.5, 200, 1e-5, "holm") == haircut_sharpe(1.5, 200, 1e-5, "bonferroni")


def test_a_haircut_can_take_everything():
    haircut, adjusted = haircut_sharpe(0.8, n_trials=5000, p_value=0.05)
    assert adjusted == 1.0
    assert haircut == 0.0


def test_an_unknown_haircut_method_is_refused():
    with pytest.raises(ValueError, match="unknown haircut method"):
        haircut_sharpe(1.0, 10, 0.01, method="vibes")


def test_adjusted_p_values_match_statsmodels():
    multitest = pytest.importorskip("statsmodels.stats.multitest")
    p = np.array([0.001, 0.01, 0.03, 0.2, 0.7])
    assert adjusted_p_values(p, "holm") == pytest.approx(multitest.multipletests(p, method="holm")[1])
    assert adjusted_p_values(p, "bhy") == pytest.approx(multitest.multipletests(p, method="fdr_by")[1])
