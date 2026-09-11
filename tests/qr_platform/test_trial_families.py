"""The four registered families, and their binding to the pre-registrations.

The coupling test is the important one here. A parameter range quietly widened
in code after the prediction was registered is the most comfortable form of
p-hacking there is, because nothing looks wrong at any individual step — so the
declared variant count is parsed out of each document and checked against the
grid the code will actually run.
"""
import numpy as np
import pandas as pd
import pytest

from qr.execution.costs import CostModel
from qr.research.families import BY_ID, TRIAL_FAMILIES, FamilySpec, run_family, summarise
from qr.validate.selftest import edge_world, noise_world
from qr.validate.trial_log import TrialLog


def test_there_are_three_hypotheses_and_one_control():
    assert len(TRIAL_FAMILIES) == 4
    controls = [f for f in TRIAL_FAMILIES if f.control]
    assert [f.hypothesis_id for f in controls] == ["rsi_reversal_v1"]


def test_every_family_has_a_preregistration_document():
    for spec in TRIAL_FAMILIES:
        assert spec.prereg_path.exists(), spec.hypothesis_id


@pytest.mark.parametrize("spec", TRIAL_FAMILIES, ids=lambda s: s.hypothesis_id)
def test_the_grid_matches_the_variant_count_the_prereg_declares(spec: FamilySpec):
    declared = spec.declared_variants()
    assert declared is not None, f"{spec.hypothesis_id} does not state its variant count"
    assert spec.n_variants == declared


@pytest.mark.parametrize("spec", TRIAL_FAMILIES, ids=lambda s: s.hypothesis_id)
def test_the_prereg_states_what_would_falsify_it(spec: FamilySpec):
    text = spec.prereg_path.read_text(encoding="utf-8").lower()
    for required in ("mechanism", "what would falsify", "cost model", "out-of-sample"):
        assert required in text, f"{spec.hypothesis_id} is missing '{required}'"


@pytest.mark.parametrize("spec", TRIAL_FAMILIES, ids=lambda s: s.hypothesis_id)
def test_the_grid_builds_the_number_of_strategies_it_claims(spec: FamilySpec):
    strategies = spec.strategies()
    assert len(strategies) == spec.n_variants
    assert len({s.name for s in strategies}) == spec.n_variants


@pytest.mark.parametrize("spec", TRIAL_FAMILIES, ids=lambda s: s.hypothesis_id)
def test_no_family_sweeps_more_than_five_parameters(spec: FamilySpec):
    """Gate 8's limit, checked before a run rather than discovered during one."""
    assert len(spec.swept_parameters) <= 5


def test_the_registry_is_addressable_by_hypothesis_id():
    assert set(BY_ID) == {f.hypothesis_id for f in TRIAL_FAMILIES}
    assert BY_ID["tsmom_v1"].strategy_class.family == "tsmom"


def test_the_trial_counts_are_what_gate_four_will_deflate_against():
    assert {f.hypothesis_id: f.n_variants for f in TRIAL_FAMILIES} == {
        "tsmom_v1": 200,
        "xsmom_v1": 144,
        "reversal_v1": 54,
        "rsi_reversal_v1": 27,
    }


# ---------------------------------------------------------------- running one


@pytest.fixture(scope="module")
def small_panel():
    return noise_world(n_symbols=6, years=3, seed=4)


@pytest.fixture()
def tiny_spec():
    """A cut-down tsmom grid, so the wiring can be tested without the full sweep."""
    return FamilySpec(
        hypothesis_id="tsmom_v1",
        strategy_class=BY_ID["tsmom_v1"].strategy_class,
        grid={"lookback": [30, 60, 90], "skip": [0, 5]},
        summary="cut down for tests",
    )


def test_running_a_family_records_its_variant_count_in_the_trial_log(small_panel, tmp_path, tiny_spec):
    log = TrialLog(tmp_path / "trial_log.jsonl")
    log.prereg("tsmom_v1", "doc")
    run = run_family(
        tiny_spec, small_panel, CostModel.trial(), trial_log=log, permutations=5, upto=4
    )
    assert log.trial_count("tsmom_v1") == 6
    assert len(run.sweep) == 6
    assert run.best_variant in run.sweep.names
    assert log.verify() > 0


def test_a_family_run_summarises_to_one_row(small_panel, tmp_path, tiny_spec):
    log = TrialLog(tmp_path / "trial_log.jsonl")
    log.prereg("tsmom_v1", "doc")
    run = run_family(tiny_spec, small_panel, CostModel.trial(), trial_log=log, permutations=5, upto=4)
    frame = summarise([run], log)
    assert list(frame["hypothesis"]) == ["tsmom_v1"]
    assert frame["verdict"].isin({"PASS", "WARN", "FAIL"}).all()
    assert frame["variants"].iloc[0] == 6


def test_a_family_without_a_preregistration_fails_gate_zero(small_panel, tmp_path, tiny_spec):
    log = TrialLog(tmp_path / "trial_log.jsonl")
    run = run_family(tiny_spec, small_panel, CostModel.trial(), trial_log=log, permutations=5, upto=4)
    assert run.report.stopped_at.number == 0


def test_a_strategy_that_never_trades_is_reported_not_raised(small_panel, tmp_path):
    """"It never fired" is a finding, and the gates must get to say so.

    Reaching for idxmax over an all-NaN column raises an opaque pandas error and
    no report gets written — which would hide exactly the outcome the control's
    pre-registration predicts.
    """
    from qr.research.sweep import run_sweep
    from qr.strategies.library import RSIReversal

    sweep = run_sweep(small_panel, [RSIReversal(rsi_max=0.0)], CostModel.trial())
    assert not sweep.ever_traded
    assert sweep.sharpes().isna().all()
    assert sweep.best() == sweep.names[0]  # no exception


def test_the_control_is_marked_as_one_in_the_summary(small_panel, tmp_path):
    log = TrialLog(tmp_path / "trial_log.jsonl")
    spec = FamilySpec(
        hypothesis_id="rsi_reversal_v1",
        strategy_class=BY_ID["rsi_reversal_v1"].strategy_class,
        grid={"down_days": [3], "rsi_max": [30.0], "hold": [5]},
        summary="cut down",
        control=True,
    )
    log.prereg("rsi_reversal_v1", "doc")
    run = run_family(spec, small_panel, CostModel.trial(), trial_log=log, permutations=5, upto=3)
    assert summarise([run], log)["control"].iloc[0] == "yes"
