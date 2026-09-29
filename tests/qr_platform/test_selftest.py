"""The self-test: does the validation engine reach the right answer on data
whose answer is known in advance?

This is the most important test in the repository. Every other test checks that
a function computes what it says; these check that the *assembly* of those
functions rejects noise and admits a real edge. If this file fails, nothing the
gates produce means anything.
"""
import numpy as np
import pytest

from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.library import TSMOM
from qr.validate.gates import FAIL, PASS, WARN
from qr.validate.selftest import (
    DEFLATION_GATES_SET,
    default_grid,
    edge_world,
    noise_world,
    run_selftest,
)
from qr.validate.trial_log import TrialLog


@pytest.fixture(scope="module")
def report():
    """The full self-test. Slow (~20s) and the reason this module exists."""
    return run_selftest(n_variants=200, permutations=100, seed=0)


# ------------------------------------------------------------- the two worlds


def _variance_ratio(panel, window: int = 20) -> float:
    """Var of `window`-bar sums over `window` x var of one bar.

    Above 1 means returns trend, below 1 means they revert, and it is the right
    statistic here because at a realistic edge strength the lag-1
    autocorrelation is ~0.006 — smaller than what the *noise* world throws up by
    chance. That a genuine, tradable edge is invisible in the obvious statistic
    is the entire reason this machinery exists.
    """
    returns = panel.returns().dropna()
    ratios = [
        float(returns[s].rolling(window).sum().var() / (window * returns[s].var()))
        for s in panel.symbols
    ]
    return float(np.mean(ratios))


def test_the_noise_world_has_no_serial_dependence():
    assert _variance_ratio(noise_world(seed=0)) == pytest.approx(1.0, abs=0.05)


def test_the_edge_world_trends_and_the_noise_world_does_not():
    assert _variance_ratio(edge_world(seed=0)) > _variance_ratio(noise_world(seed=0))
    assert _variance_ratio(edge_world(seed=0)) > 1.05


def test_the_planted_edge_is_invisible_to_the_obvious_statistic():
    """Lag-1 autocorrelation cannot tell the two worlds apart at this strength."""
    edge_ac = np.nanmean([edge_world(seed=0).returns()[s].autocorr(1) for s in edge_world(seed=0).symbols])
    noise_ac = np.nanmean([noise_world(seed=0).returns()[s].autocorr(1) for s in noise_world(seed=0).symbols])
    assert abs(edge_ac) < 0.05 and abs(noise_ac) < 0.05


def test_the_planted_edge_is_realistic_not_unmissable():
    """An edge worth Sharpe 20 would pass any engine and prove nothing."""
    panel = edge_world(seed=0)
    costs = CostModel.trial()
    best = max(run_backtest(panel, TSMOM(lookback=lb), costs).sharpe() for lb in (20, 60, 120))
    assert 1.0 < best < 3.0


def test_searching_noise_still_produces_a_convincing_winner():
    """The premise of the whole exercise: 200 variants of nothing look good."""
    from qr.research.sweep import run_sweep

    sweep = run_sweep(noise_world(seed=0), default_grid(200), CostModel.trial())
    assert sweep.sharpes().max() > 0.9


def test_the_grid_is_the_size_it_claims():
    assert len(default_grid(200)) == 200
    assert len({s.name for s in default_grid(200)}) == 200


# ----------------------------------------------------------------- the verdict


def test_the_engine_rejects_a_searched_over_noise_winner(report):
    noise = next(c for c in report.cases if c.name == "noise")
    assert noise.actual == FAIL
    assert noise.passed


def test_noise_is_rejected_by_the_deflation_gates_specifically(report):
    """Not merely rejected: rejected by gate 4 *and* gate 5.

    A noise winner often also trips gate 3 on its raw t-statistic. An engine
    relying on that would wave through the next noise winner whose t happened
    to land higher, so the self-test insists the gates that price the search
    are the ones doing the work.
    """
    noise = next(c for c in report.cases if c.name == "noise")
    assert DEFLATION_GATES_SET <= noise.failed_gates, noise.failed_gates


def test_the_engine_admits_a_real_edge(report):
    edge = next(c for c in report.cases if c.name == "planted_edge")
    assert edge.actual in {PASS, WARN}
    assert edge.passed
    assert not edge.failed_gates


def test_the_real_edge_clears_the_deflation_gates(report):
    edge = next(c for c in report.cases if c.name == "planted_edge")
    verdicts = {r.number: r.verdict for r in edge.report.results}
    assert verdicts[4] == PASS  # survives deflation over 200 trials
    assert verdicts[6] == PASS  # beats its own permutation null
    assert verdicts[7] == PASS  # holds up across CPCV paths


def test_the_whole_self_test_passes(report):
    assert report.ok, report.failure_summary()


def test_the_report_says_which_gates_failed(report):
    frame = report.to_frame()
    assert set(frame["world"]) == {"noise", "planted_edge"}
    assert set(frame["self_test"]) == {"OK"}
    assert frame.set_index("world").loc["noise", "deflation_caught_it"]


# ------------------------------------------------- the criterion itself is real


def test_the_criterion_rejects_an_engine_that_fails_for_the_wrong_reason(report):
    """Guard the guard: if only gate 3 had failed, the self-test must say BROKEN."""
    noise = next(c for c in report.cases if c.name == "noise")
    import copy

    weakened = copy.copy(noise)
    weakened.report = copy.copy(noise.report)
    weakened.report.results = [r for r in noise.report.results if r.number <= 3]
    assert weakened.actual == FAIL
    assert not weakened.passed


def test_the_criterion_rejects_an_engine_that_rejects_everything(report):
    edge = next(c for c in report.cases if c.name == "planted_edge")
    import copy

    broken = copy.copy(edge)
    broken.report = copy.copy(edge.report)
    broken.report.results = list(edge.report.results)
    broken.report.results[3].verdict = FAIL
    try:
        assert not broken.passed
    finally:
        broken.report.results[3].verdict = PASS


def test_the_self_test_can_record_itself_in_the_trial_log(tmp_path):
    log = TrialLog(tmp_path / "trial_log.jsonl")
    run_selftest(n_variants=10, permutations=5, trial_log=log, seed=0)
    assert log.verify() > 0
    # Both worlds pre-registered before any run, and the trial count is real.
    assert len(log.records(kind="prereg")) == 2
    assert log.trial_count("selftest_noise") == 10
    assert any(r.payload.get("gate") == 4 for r in log.records(kind="gate"))
