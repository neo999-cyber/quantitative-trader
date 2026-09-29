"""The gate pipeline and the Hypothesis Report.

Small panels and small grids throughout: these tests check the wiring and the
verdict logic. Whether the engine reaches the *right* answer on data whose
answer is known is `test_selftest.py`, which is the claim that matters.
"""
import json

import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.research.sweep import run_sweep
from qr.strategies.base import Strategy
from qr.strategies.library import TSMOM
from qr.validate.gates import (
    FAIL,
    PASS,
    SKIP,
    WARN,
    GateContext,
    GateThresholds,
    gate_0_preregistration,
    gate_1_data_integrity,
    gate_2_cost_survival,
    gate_3_significance,
    gate_4_deflation,
    gate_5_selection,
    gate_9_holdout,
    run_gates,
)
from qr.validate.report import (
    GATE_NAMES,
    headline_verdict,
    to_json,
    to_markdown,
    write_report,
)
from qr.validate.selftest import edge_world, noise_world
from qr.validate.trial_log import TrialLog


class Oracle(Strategy):
    """Reaches forward inside `target_weights`, so the runner's honest one-bar
    shift aligns the peek exactly onto the bar it predicted. Gate 1 exists for
    this, and the giveaway is the implausible Sharpe at the *reported* lag."""

    family = "oracle"

    def target_weights(self, panel, universe=None):
        tomorrow = panel.returns().shift(-1)
        return self.normalise(self.mask_to_universe((tomorrow > 0).astype(float), panel, universe))


@pytest.fixture(scope="module")
def small_noise():
    return noise_world(n_symbols=4, years=3, seed=1)


@pytest.fixture(scope="module")
def small_edge():
    return edge_world(n_symbols=4, years=3, seed=1)


@pytest.fixture()
def log(tmp_path):
    return TrialLog(tmp_path / "trial_log.jsonl")


@pytest.fixture()
def free():
    return CostModel(fee_bps=0.0, half_spread_bps=0.0)


def context(panel, strategy=None, costs=None, **kwargs) -> GateContext:
    strategy = strategy or TSMOM(lookback=60)
    costs = costs or CostModel.trial()
    return GateContext(
        hypothesis_id=kwargs.pop("hypothesis_id", "h1"),
        panel=panel,
        strategy=strategy,
        costs=costs,
        result=run_backtest(panel, strategy, costs, kwargs.get("universe")),
        permutations=kwargs.pop("permutations", 20),
        **kwargs,
    )


# ------------------------------------------------------------------ gate 0


def test_no_preregistration_is_a_failure(small_edge, log):
    result = gate_0_preregistration(context(small_edge, trial_log=log))
    assert result.verdict == FAIL
    assert "exploratory" in result.detail


def test_preregistration_after_the_first_run_is_a_failure(small_edge, log):
    log.run("h1", "tsmom", {"lookback": 60}, "u")
    log.prereg("h1", "we predict trends persist")
    result = gate_0_preregistration(context(small_edge, trial_log=log))
    assert result.verdict == FAIL
    assert "written after seeing results" in result.detail


def test_preregistration_before_any_run_passes(small_edge, log):
    log.prereg("h1", "we predict trends persist")
    log.run("h1", "tsmom", {"lookback": 60}, "u")
    assert gate_0_preregistration(context(small_edge, trial_log=log)).verdict == PASS


def test_without_a_trial_log_gate_zero_is_skipped_not_passed(small_edge):
    assert gate_0_preregistration(context(small_edge)).verdict == SKIP


# ------------------------------------------------------------------ gate 1


def test_a_strategy_that_reads_the_future_fails_gate_one(small_edge, free):
    result = gate_1_data_integrity(context(small_edge, Oracle(), free))
    assert result.verdict == FAIL
    assert "reading the bar it predicts" in result.detail
    assert result.stats["lag1_gross_sharpe"] > 8.0
    assert result.stats["spike_ratio"] > 1.5


def test_an_honest_strategy_passes_gate_one_despite_a_large_peek_ratio(small_edge, free):
    """Peeking helps every return-based signal; only the spike is evidence."""
    result = gate_1_data_integrity(context(small_edge, TSMOM(lookback=60), free))
    assert result.verdict == PASS
    assert result.stats["peek_ratio"] > 1.3
    assert result.stats["spike_ratio"] < 1.5


def test_bad_bars_fail_gate_one_before_the_leakage_probe(small_edge, free):
    frames = {"E0USDT": pd.DataFrame({
        "open": [1.0, 1.0], "high": [0.1, 1.0], "low": [1.0, 1.0],
        "close": [1.0, 1.0], "volume": [1.0, 1.0],
    }, index=small_edge.index[:2])}
    ctx = context(small_edge, TSMOM(lookback=60), free, raw_frames=frames)
    result = gate_1_data_integrity(ctx)
    assert result.verdict == FAIL
    assert "QA failed" in result.detail


# ------------------------------------------------------------------ gate 2


def test_ruinous_costs_fail_gate_two(small_edge):
    expensive = CostModel(fee_bps=500.0, half_spread_bps=200.0)
    result = gate_2_cost_survival(context(small_edge, TSMOM(lookback=30), expensive))
    assert result.verdict == FAIL


def test_gate_two_records_both_gross_and_net(small_edge, free):
    result = gate_2_cost_survival(context(small_edge, TSMOM(lookback=60), free))
    assert "gross_sharpe" in result.stats and "net_sharpe" in result.stats
    assert result.stats["cost_model"]["fee_bps"] == 0.0


def test_gate_two_charges_double_costs_too(small_edge):
    result = gate_2_cost_survival(context(small_edge, TSMOM(lookback=30), CostModel.trial()))
    assert "sharpe_at_2x_costs" in result.stats


# ------------------------------------------------------------------ gate 3


def test_noise_fails_significance(small_noise, free):
    result = gate_3_significance(context(small_noise, TSMOM(lookback=60), free))
    assert result.verdict in {FAIL, WARN}
    assert np.isfinite(result.stats["hac_tstat"])


def test_gate_three_reports_the_bootstrap_interval(small_edge, free):
    ctx = context(small_edge, TSMOM(lookback=60), free)
    ctx.bootstrap_reps = 300
    result = gate_3_significance(ctx)
    assert result.stats["sharpe_ci_lower"] < result.stats["sharpe_ci_upper"]


# ------------------------------------------------------------------ gate 4


def test_deflation_uses_the_sweep_size_as_the_trial_count(small_noise, free):
    grid = TSMOM.grid(lookback=[20, 40, 60, 80, 100], skip=[0, 5])
    sweep = run_sweep(small_noise, grid, free)
    ctx = context(small_noise, sweep.results[sweep.best()].meta and TSMOM(lookback=60), free, sweep=sweep)
    ctx.result = sweep.results[sweep.best()]
    result = gate_4_deflation(ctx)
    assert result.stats["trials"] == float(len(grid)) == 10.0


def test_a_larger_search_deflates_the_same_result_harder(small_edge, free):
    """Held to the same winner, more trials must mean a higher bar.

    Comparing two *different* sweeps would not show this: a larger grid also
    finds a better variant, and in a world where an edge exists that can more
    than offset the extra deflation. The invariant is about the formula, so the
    returns are held fixed and only the trial count moves.
    """
    from qr.validate.stats import deflated_sharpe

    grid = TSMOM.grid(lookback=[40, 60])
    sweep = run_sweep(small_edge, grid, free)
    net = sweep.results[sweep.best()].net.dropna()
    variance = float(sweep.per_period_sharpes().var(ddof=1))

    few, bar_few = deflated_sharpe(net, 5, sharpe_variance=variance)
    many, bar_many = deflated_sharpe(net, 500, sharpe_variance=variance)
    assert bar_many > bar_few
    assert many < few


def test_without_a_sweep_deflation_falls_back_to_the_sampling_variance(small_edge, free, log):
    log.run("h1", "tsmom", {"lookback": 60}, "u", variants=50)
    ctx = context(small_edge, TSMOM(lookback=60), free, trial_log=log)
    result = gate_4_deflation(ctx)
    assert result.stats["trials"] == 50.0
    assert result.stats["sharpe_variance"] == pytest.approx(1 / len(ctx.result.net.dropna()), rel=0.01)


# ------------------------------------------------------------------ gate 5


def test_gate_five_is_skipped_when_nothing_was_selected(small_edge, free):
    assert gate_5_selection(context(small_edge, TSMOM(lookback=60), free)).verdict == SKIP


def test_selecting_among_noise_fails_gate_five(small_noise, free):
    grid = TSMOM.grid(lookback=list(range(10, 210, 5)))
    sweep = run_sweep(small_noise, grid, free)
    ctx = context(small_noise, next(s for s in grid if s.name == sweep.best()), free, sweep=sweep)
    ctx.result = sweep.results[sweep.best()]
    result = gate_5_selection(ctx)
    assert result.verdict in {WARN, FAIL}
    assert "pbo" in result.stats


# ------------------------------------------------------------------ gate 9


def test_a_holdout_can_only_be_opened_once(small_edge, free, log):
    holdout = noise_world(n_symbols=4, years=2, seed=9)
    ctx = context(small_edge, TSMOM(lookback=60), free, trial_log=log, holdout_panel=holdout)
    first = gate_9_holdout(ctx)
    assert first.verdict in {PASS, WARN, FAIL}
    second = gate_9_holdout(ctx)
    assert second.verdict == FAIL
    assert "already opened" in second.detail


def test_no_holdout_is_a_skip_not_a_pass(small_edge, free):
    assert gate_9_holdout(context(small_edge, TSMOM(lookback=60), free)).verdict == SKIP


# ------------------------------------------------- the pipeline and the report


def test_the_pipeline_stops_at_the_first_failure(small_edge, free, log):
    ctx = context(small_edge, Oracle(), free, trial_log=log)
    report = run_gates(ctx, upto=8)
    # Gate 0 fails first (no pre-registration), so nothing else even runs.
    assert [r.number for r in report.results] == [0]
    assert report.verdict == FAIL


def test_running_all_gates_anyway_is_possible_for_diagnosis(small_edge, free, log):
    log.prereg("h1", "doc")
    ctx = context(small_edge, Oracle(), free, trial_log=log)
    report = run_gates(ctx, upto=3, stop_on_fail=False)
    assert [r.number for r in report.results] == [0, 1, 2, 3]
    assert report.stopped_at.number == 1


def test_every_gate_result_is_written_to_the_trial_log(small_edge, free, log):
    log.prereg("h1", "doc")
    ctx = context(small_edge, TSMOM(lookback=60), free, trial_log=log)
    report = run_gates(ctx, upto=2, stop_on_fail=False)
    recorded = log.records(kind="gate", hypothesis_id="h1")
    assert len(recorded) == len(report.results)
    assert log.verify() > 0


def warned_report(number: int = 3) -> "GateReport":
    """A report with exactly one WARN and no FAIL.

    Built rather than harvested from a backtest: whether a given sample happens
    to produce a warning is luck, and a test that skips when it does not is a
    test that silently stops running.
    """
    from qr.validate.gates import GateReport, GateResult

    return GateReport(
        "h1",
        [
            GateResult(0, "pre-registration", PASS, "registered"),
            GateResult(number, "single-strategy significance", WARN, "t = 2.7"),
        ],
        {"trials": 1, "strategy": {"name": "x", "family": "x", "params": {}}, "costs": {}},
    )


def test_an_unjustified_warning_counts_as_a_failure(log):
    verdict, reason = headline_verdict(warned_report(), log)
    assert verdict == FAIL
    assert "no written justification" in reason


def test_a_justified_warning_is_allowed_through(log):
    log.note("h1", "gate 3: accepted, the sample is short by design and the CI still excludes zero")
    verdict, reason = headline_verdict(warned_report(), log)
    assert verdict == WARN
    assert "justified warnings" in reason


def test_a_note_about_a_different_gate_does_not_justify_this_one(log):
    log.note("h1", "gate 7: unrelated justification")
    assert headline_verdict(warned_report(3), log)[0] == FAIL


def test_without_a_trial_log_a_warning_cannot_be_justified():
    assert headline_verdict(warned_report(), None)[0] == FAIL


def test_a_clean_report_passes(log):
    from qr.validate.gates import GateReport, GateResult

    clean = GateReport("h1", [GateResult(0, "pre-registration", PASS, "registered")], {})
    assert headline_verdict(clean, log)[0] == PASS


def test_a_failure_outranks_any_justification(log):
    from qr.validate.gates import GateReport, GateResult

    log.note("h1", "gate 3: please ignore this")
    report = GateReport("h1", [GateResult(3, "significance", FAIL, "t = 0.2")], {})
    verdict, reason = headline_verdict(report, log)
    assert verdict == FAIL
    assert "stopped at gate 3" in reason


def test_the_markdown_report_carries_the_audit_trail(small_edge, free, log):
    log.prereg("h1", "doc")
    ctx = context(small_edge, TSMOM(lookback=60), free, trial_log=log, manifest_hash="a" * 64)
    report = run_gates(ctx, upto=2, stop_on_fail=False)
    text = to_markdown(report, log, ctx.result.stats())

    assert "# Hypothesis Report" in text
    assert "Trials counted" in text
    assert "a" * 32 in text  # the data manifest hash
    assert "fees verified" in text
    for name in GATE_NAMES.values():
        assert name in text


def test_the_backtest_sharpe_is_reported_below_the_deflated_one(small_edge, free, log):
    log.prereg("h1", "doc")
    ctx = context(small_edge, TSMOM(lookback=60), free, trial_log=log)
    text = to_markdown(run_gates(ctx, upto=4, stop_on_fail=False), log)
    assert text.index("Deflated Sharpe") < text.index("the backtest number")


def test_the_json_report_is_serialisable_and_has_no_nan(small_edge, free, log):
    log.prereg("h1", "doc")
    ctx = context(small_edge, TSMOM(lookback=60), free, trial_log=log)
    payload = to_json(run_gates(ctx, upto=4, stop_on_fail=False), log)
    text = json.dumps(payload)
    assert "NaN" not in text and "Infinity" not in text
    assert payload["hypothesis_id"] == "h1"
    assert {g["gate"] for g in payload["gates"]} <= set(range(12))


def test_writing_a_report_produces_both_files(small_edge, free, log, tmp_path):
    log.prereg("h1", "doc")
    ctx = context(small_edge, TSMOM(lookback=60), free, trial_log=log)
    report = run_gates(ctx, upto=2, stop_on_fail=False)
    md, js = write_report(report, tmp_path / "reports", log, ctx.result.stats())
    assert md.exists() and js.exists()
    assert json.loads(js.read_text())["hypothesis_id"] == "h1"


def test_thresholds_are_recorded_with_the_report(small_edge, free, log):
    log.prereg("h1", "doc")
    ctx = context(small_edge, TSMOM(lookback=60), free, trial_log=log)
    ctx.thresholds = GateThresholds(min_tstat=99.0)
    report = run_gates(ctx, upto=3, stop_on_fail=False)
    assert report.context["thresholds"]["min_tstat"] == 99.0
