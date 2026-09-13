"""The research policy — the quota that makes an unattended Stage 4 legitimate.

What is tested here is refusal. A policy whose limits can be talked around by
the code that is subject to them is decoration, so every check raises rather
than returns, the declaration cannot be quietly replaced, and the stopping rule
counts from where it was declared rather than from a past the plan already
diagnosed.
"""
from datetime import datetime, timedelta, timezone

import pytest

from qr.research.policy import (
    PolicyBreach,
    ResearchPolicy,
    StoppingRuleReached,
    budget,
    candidates_tested,
    check_grid,
    check_promotion,
    clears_the_bar,
    current,
    declare,
    require,
)
from qr.validate.trial_log import TrialLog

NOW = datetime(2026, 9, 13, tzinfo=timezone.utc)


@pytest.fixture()
def log(tmp_path):
    return TrialLog(tmp_path / "trial.jsonl")


# ------------------------------------------------------------- the declaration


def test_a_policy_is_declared_once_and_then_refused(log):
    declare(log, ResearchPolicy())
    with pytest.raises(PolicyBreach, match="already in force"):
        declare(log, ResearchPolicy(max_promotions_per_week=9, max_promotions_per_quarter=99))
    assert current(log).max_promotions_per_week == 2


def test_a_forced_change_leaves_the_supersession_in_the_chain(log):
    declare(log, ResearchPolicy())
    first = current(log).fingerprint()
    declare(log, ResearchPolicy(max_promotions_per_quarter=6), force=True)
    records = log.records(kind="policy")
    assert records[-1].payload["supersedes"] == first
    assert log.verify() == 2


def test_an_undeclared_policy_is_an_error_not_a_default(log):
    with pytest.raises(PolicyBreach, match="no research policy"):
        require(log)


def test_a_policy_that_permits_nothing_is_refused():
    with pytest.raises(ValueError, match="stopped project"):
        ResearchPolicy(max_promotions_per_week=0)


def test_a_quarterly_cap_below_the_weekly_one_does_nothing_and_is_refused():
    with pytest.raises(ValueError, match="quarterly cap does nothing"):
        ResearchPolicy(max_promotions_per_week=5, max_promotions_per_quarter=2)


def test_a_bar_below_break_even_is_refused():
    with pytest.raises(ValueError, match="does not cover its own costs"):
        ResearchPolicy(min_cost_multiple=0.8)


# ---------------------------------------------------- the count starts from now


def test_the_nine_families_that_already_failed_do_not_count_against_the_stopping_rule(log):
    """They had no mechanism. They are the diagnosis, not nine attempts at the cure."""
    for i in range(9):
        log.prereg(f"old_family_{i}", "a pattern, not a mechanism")
    declare(log, ResearchPolicy(max_candidates=8))

    policy = current(log)
    assert candidates_tested(log, policy) == 0
    check_promotion(log, policy, now=NOW)  # does not raise


def test_the_stopping_rule_fires_on_the_eighth_mechanism(log):
    declare(log, ResearchPolicy(max_candidates=8, max_promotions_per_week=99, max_promotions_per_quarter=99))
    policy = current(log)
    for i in range(8):
        log.prereg(f"mechanism_{i}", "somebody is forced to trade")

    assert candidates_tested(log, policy) == 8
    with pytest.raises(StoppingRuleReached, match="index fund"):
        check_promotion(log, policy, now=NOW)


def test_the_same_hypothesis_registered_twice_is_one_candidate(log):
    declare(log, ResearchPolicy(max_candidates=2, max_promotions_per_week=99, max_promotions_per_quarter=99))
    policy = current(log)
    log.prereg("funding_carry_v1", "first")
    log.prereg("funding_carry_v1", "an edit to the same document")
    assert candidates_tested(log, policy) == 1


# -------------------------------------------------------------------- the quota


def test_the_weekly_cap_stops_a_third_promotion(log):
    declare(log, ResearchPolicy(max_promotions_per_week=2))
    policy = current(log)
    log.prereg("a", "x")
    log.prereg("b", "x")
    with pytest.raises(PolicyBreach, match="weekly cap"):
        check_promotion(log, policy, now=NOW)


def test_last_months_promotions_do_not_count_against_this_week(log):
    declare(log, ResearchPolicy(max_promotions_per_week=2, max_promotions_per_quarter=5))
    policy = current(log)
    log.prereg("a", "x")
    log.prereg("b", "x")
    # Eight days later the weekly window has rolled past both.
    check_promotion(log, policy, now=NOW + timedelta(days=8))


def test_the_quarterly_cap_binds_even_when_the_week_is_clear(log):
    declare(log, ResearchPolicy(max_promotions_per_week=2, max_promotions_per_quarter=3))
    policy = current(log)
    for name in ("a", "b", "c"):
        log.prereg(name, "x")
    with pytest.raises(PolicyBreach, match="last quarter"):
        check_promotion(log, policy, now=NOW + timedelta(days=30))


# -------------------------------------------------------------------- the bar


def test_the_kill_test_bar_is_three_times_costs_not_a_margin():
    policy = ResearchPolicy(min_cost_multiple=3.0)
    assert clears_the_bar(policy, gross_edge_bps=60.0, round_trip_cost_bps=19.0)
    assert not clears_the_bar(policy, gross_edge_bps=23.0, round_trip_cost_bps=19.0)


def test_a_zero_cost_model_is_refused_rather_than_passed():
    with pytest.raises(ValueError, match="missing one"):
        clears_the_bar(ResearchPolicy(), gross_edge_bps=10.0, round_trip_cost_bps=0.0)


def test_a_grid_wider_than_the_cap_is_refused():
    policy = ResearchPolicy(max_variants_per_family=250)
    check_grid(policy, 200, "tsmom_v1")
    with pytest.raises(PolicyBreach, match="every family that comes after"):
        check_grid(policy, 425, "tsmom_v1")


# ------------------------------------------------------------------- reporting


def test_budget_reports_what_is_left(log):
    declare(log, ResearchPolicy(max_candidates=8, max_promotions_per_week=2))
    policy = current(log)
    log.prereg("funding_carry_v1", "x")

    state = budget(log, policy, now=NOW)
    assert state["candidates_tested"] == 1
    assert state["candidates_remaining"] == 7
    assert state["promotions_this_week"] == 1
    assert state["stopping_rule_reached"] is False
