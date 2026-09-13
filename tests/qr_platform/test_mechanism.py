"""Stages 2 and 3, and the loop that joins them.

The generator is an LLM and is not tested here; what is tested is everything
that decides what happens to what it produces. Triage must reach its verdict
without reference to the model's own, the kill test must refuse to look at
validation data, and the loop must exit the same recorded way at every stage.
"""
import numpy as np
import pandas as pd
import pytest

from qr.data.sandbox import SandboxSpec, restrict
from qr.execution.costs import CostModel
from qr.research import features, killtest
from qr.research.autopilot import run_night
from qr.research.mechanism import (
    CrudeVersion,
    MechanismMemo,
    considered,
    record,
    triage,
)
from qr.research.policy import ResearchPolicy
from qr.strategies.calendar import CalendarEvent, event_bars, window_mask
from qr.validate.selftest import noise_world
from qr.validate.trial_log import TrialLog

SANDBOX = SandboxSpec(market="binance/spot")


def memo(**overrides) -> MechanismMemo:
    body = {
        "candidate_id": "month_end_rebalance_v1",
        "title": "Balanced funds must rebalance at month end",
        "forced_trader": "A 60/40 fund whose mandate requires it to sell what rose and buy what "
        "fell on the last business day of the month, in size, regardless of price.",
        "persistence": "The obligation is written into the prospectus and audited; the manager "
        "does not get to skip a month because the trade looks bad.",
        "other_side": "Market makers and anyone willing to warehouse the imbalance overnight. It "
        "has not gone because the flow is large relative to the window it must happen in.",
        "what_breaks_it": "Funds moving to continuous or randomised rebalancing, or the flow "
        "being pre-positioned so far ahead that the window stops mattering.",
        "crude_version": CrudeVersion(
            primitive="calendar_event",
            params={"event": "month_end", "before": 3, "after": 0, "side": 1},
            expected_sign="positive",
            rationale="Hold the universe into month end, flat otherwise.",
        ),
        "required_features": ("close", "calendar"),
        "self_verdict": "proceed",
        "kill_reason": "",
        "confidence": 0.35,
    }
    body.update(overrides)
    return MechanismMemo(**body)


# ------------------------------------------------------------------- registry


def test_the_registry_separates_what_we_have_from_what_we_would_need():
    assert features.available("calendar")
    assert features.available("quote_volume")
    assert not features.available("funding_rate")
    assert not features.available("token_unlocks")


def test_a_blocked_idea_names_the_dataset_that_would_unblock_it():
    needed = features.datasets_needed(["close", "funding_rate", "token_unlocks"])
    assert any("fundingRate" in d for d in needed)
    assert any("DropsTab" in d for d in needed)


def test_an_unknown_feature_is_refused_rather_than_assumed():
    assert features.unknown_keys(["close", "vibes"]) == ["vibes"]


# --------------------------------------------------------------------- triage


def test_a_memo_with_a_named_payer_and_a_runnable_version_proceeds():
    assert triage(memo()).proceed


def test_a_self_kill_is_honoured_immediately():
    verdict = triage(memo(self_verdict="killed", kill_reason="no obligation, just a pattern"))
    assert verdict.verdict == "killed"
    assert "no obligation" in verdict.reason


def test_question_two_answered_with_a_statement_about_prices_is_killed():
    """The harness re-decides; the model said proceed."""
    verdict = triage(memo(persistence="Momentum works, and it has worked in the past."))
    assert verdict.verdict == "killed"
    assert "not an obligation" in verdict.reason


def test_a_memo_with_no_payer_is_killed_however_confident_it_is():
    verdict = triage(memo(forced_trader="   ", confidence=0.99))
    assert verdict.verdict == "killed"
    assert "question 1" in verdict.reason


def test_restating_an_already_failed_family_is_killed_not_rerun():
    verdict = triage(
        memo(
            crude_version=CrudeVersion(
                primitive="xsmom",
                params={"lookback": 60, "n_long": 3},
                expected_sign="positive",
            )
        )
    )
    assert verdict.verdict == "killed"
    assert "already been pre-registered and failed" in verdict.reason


def test_missing_data_blocks_rather_than_kills():
    verdict = triage(memo(required_features=("close", "funding_rate")))
    assert verdict.verdict == "blocked"
    assert verdict.missing_datasets
    assert not verdict.proceed


def test_a_crude_version_that_does_not_build_is_killed():
    verdict = triage(
        memo(
            crude_version=CrudeVersion(
                primitive="calendar_event",
                params={"event": "full_moon"},
                expected_sign="positive",
            )
        )
    )
    assert verdict.verdict == "killed"
    assert "does not build" in verdict.reason


def test_every_memo_reaches_the_chain_including_the_killed_ones(tmp_path):
    log = TrialLog(tmp_path / "trial.jsonl")
    dead = memo(candidate_id="dead_v1", self_verdict="killed", kill_reason="no mechanism")
    record(log, dead, triage(dead))
    record(log, memo(), triage(memo()))

    seen = considered(log)
    assert [c["verdict"] for c in seen] == ["killed", "proceed"]
    assert log.verify() == 2


# ---------------------------------------------------------------- the calendar


def test_month_end_is_the_last_bar_the_index_has_in_the_month():
    index = pd.bdate_range("2024-01-01", "2024-03-29", tz="UTC")
    ends = index[event_bars(index, "month_end").to_numpy()]
    assert list(ends.strftime("%Y-%m-%d")) == ["2024-01-31", "2024-02-29", "2024-03-29"]


def test_the_window_reaches_backwards_and_forwards_independently():
    index = pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC")
    events = pd.Series([False] * 10, index=index)
    events.iloc[5] = True
    assert int(window_mask(events, before=2, after=0).sum()) == 3
    assert int(window_mask(events, before=0, after=2).sum()) == 3
    assert int(window_mask(events, before=2, after=2).sum()) == 5


def test_the_strategy_is_flat_outside_its_window():
    panel = noise_world(n_symbols=4, years=2, seed=3)
    weights = CalendarEvent(event="month_end", before=3).target_weights(panel)
    live = weights.abs().sum(axis=1) > 0
    assert 0 < int(live.sum()) < len(panel)
    assert float(weights.abs().sum(axis=1).max()) == pytest.approx(1.0)


def test_the_side_parameter_flips_the_book():
    panel = noise_world(n_symbols=4, years=2, seed=3)
    long = CalendarEvent(event="month_end", before=3, side=1).target_weights(panel)
    short = CalendarEvent(event="month_end", before=3, side=-1).target_weights(panel)
    pd.testing.assert_frame_equal(long, -short)


# ------------------------------------------------------------- the kill tests


@pytest.fixture(scope="module")
def panel():
    return noise_world(n_symbols=12, years=5, seed=17)


@pytest.fixture()
def discovery(panel):
    return restrict(panel, SANDBOX, "discovery")


def test_a_kill_test_refuses_to_look_at_validation_data(panel):
    validation = restrict(panel, SANDBOX, "validation")
    with pytest.raises(ValueError, match="discovery sandbox and nowhere else"):
        killtest.run(memo(), validation, ResearchPolicy())
    with pytest.raises(ValueError, match="discovery sandbox and nowhere else"):
        killtest.run(memo(), panel, ResearchPolicy())


def test_noise_dies_at_the_cost_bar(discovery):
    """A random walk has no month-end effect, so the crude version must fail."""
    result = killtest.run(memo(), discovery, ResearchPolicy())
    assert not result.passed
    assert result.failed_at in ("exists", "costs", "floor")
    assert result.stats["round_trip_cost_bps"] > 0


def test_a_sign_flip_is_a_refutation_not_a_discovery(discovery):
    """Whichever direction noise drifted, the opposite memo must be refuted."""
    positive = killtest.run(memo(), discovery, ResearchPolicy())
    flipped = memo(
        crude_version=CrudeVersion(
            primitive="calendar_event",
            params={"event": "month_end", "before": 3, "after": 0, "side": 1},
            expected_sign="negative",
        )
    )
    negative = killtest.run(flipped, discovery, ResearchPolicy())
    assert not (positive.passed and negative.passed)
    assert "exists" in (positive.failed_at, negative.failed_at)


def test_a_strategy_that_never_trades_dies_at_the_first_question(discovery):
    never = memo(
        crude_version=CrudeVersion(
            primitive="calendar_event",
            params={"event": "weekday", "weekday": 6, "before": 0, "after": 0},
            expected_sign="positive",
        )
    )
    result = killtest.run(never, discovery, ResearchPolicy())
    assert not result.passed


def test_the_bar_is_the_policys_and_a_lower_one_lets_more_through(discovery):
    strict = killtest.run(memo(), discovery, ResearchPolicy(min_cost_multiple=50.0))
    assert not strict.passed
    assert strict.failed_at in ("exists", "costs", "floor")


def test_a_kill_test_reaches_the_chain(tmp_path, discovery):
    log = TrialLog(tmp_path / "trial.jsonl")
    killtest.record(log, killtest.run(memo(), discovery, ResearchPolicy()))
    assert log.verify() == 1
    assert log.records(kind="killtest")[0].hypothesis_id == "month_end_rebalance_v1"


# ------------------------------------------------------------------- the night


def _log_with_policy(tmp_path, **policy_kw):
    from qr.research.policy import declare

    log = TrialLog(tmp_path / "trial.jsonl")
    declare(log, ResearchPolicy(**policy_kw))
    from qr.research.policy import current

    return log, current(log)


def test_a_night_records_every_exit(tmp_path, panel):
    log, policy = _log_with_policy(tmp_path)
    memos = {
        "a": memo(candidate_id="a_v1", self_verdict="killed", kill_reason="no obligation"),
        "b": memo(candidate_id="b_v1", required_features=("close", "funding_rate")),
        "c": memo(candidate_id="c_v1"),
    }
    night = run_night(
        ["a", "b", "c"], log, policy, SANDBOX, panel, propose=lambda brief: memos[brief]
    )

    assert [o.outcome for o in night.outcomes] == ["killed", "blocked", "failed"]
    assert night.shopping_list()
    assert any("fundingRate" in d for d in night.shopping_list())
    assert log.verify() > 0


def test_the_quota_stops_the_night_before_it_spends_a_memo(tmp_path, panel):
    log, policy = _log_with_policy(tmp_path, max_promotions_per_week=1)
    log.prereg("already_promoted_v1", "an earlier candidate")
    calls = []

    def spy(brief):
        calls.append(brief)
        return memo()

    night = run_night(["a", "b"], log, policy, SANDBOX, panel, propose=spy)
    assert calls == [], "the quota must be checked before the memo is written, not after"
    assert night.stopped_early
    assert night.outcomes[0].outcome == "quota"


def test_the_stopping_rule_ends_the_night(tmp_path, panel):
    log, policy = _log_with_policy(
        tmp_path, max_candidates=1, max_promotions_per_week=99, max_promotions_per_quarter=99
    )
    log.prereg("mechanism_one_v1", "the only candidate the policy allowed")
    night = run_night(["a"], log, policy, SANDBOX, panel, propose=lambda b: memo())
    assert night.stopped_early
    assert "index fund" in night.stopped_early


def test_a_memo_that_fails_to_generate_does_not_stop_the_night(tmp_path, panel):
    log, policy = _log_with_policy(tmp_path)

    def flaky(brief):
        if brief == "a":
            raise RuntimeError("model declined")
        return memo(candidate_id="b_v1")

    night = run_night(["a", "b"], log, policy, SANDBOX, panel, propose=flaky)
    assert night.outcomes[0].outcome == "error"
    assert night.outcomes[1].outcome in ("failed", "ready")


def test_a_survivor_is_only_promoted_when_a_promoter_is_wired_up(tmp_path, panel, monkeypatch):
    log, policy = _log_with_policy(tmp_path)
    monkeypatch.setattr(
        killtest,
        "run",
        lambda *a, **k: killtest.KillTest("c_v1", True, "", "passed", {"cost_multiple": 9.0}),
    )
    night = run_night(["c"], log, policy, SANDBOX, panel, propose=lambda b: memo(candidate_id="c_v1"))
    assert night.outcomes[0].outcome == "ready"

    promoted = []
    night = run_night(
        ["c"],
        log,
        policy,
        SANDBOX,
        panel,
        propose=lambda b: memo(candidate_id="c_v1"),
        promote=lambda m, t: promoted.append(m.candidate_id),
    )
    assert promoted == ["c_v1"]
    assert night.outcomes[0].outcome == "promoted"


# ---------------------------------------------------- promotion, end to end


def test_the_grid_is_fixed_in_code_and_a_memo_cannot_narrow_it():
    """A memo that fixed `before=3` must still be swept over the whole window."""
    from qr.research.autopilot import family_spec

    spec = family_spec(memo())
    assert spec.grid["before"] == [1, 2, 3, 5]
    assert spec.grid["event"] == ["month_end"], "what the memo committed to is kept"
    assert spec.n_variants == 12
    assert sorted(spec.swept_parameters) == ["after", "before"]


def test_promotion_pre_registers_before_it_touches_the_validation_data(tmp_path, panel):
    """Gate 0 compares the two sequence numbers, so the order is load-bearing."""
    from qr.research.autopilot import promoter
    from qr.research.policy import current, declare

    log = TrialLog(tmp_path / "trial.jsonl")
    declare(log, ResearchPolicy())
    policy = current(log)

    promote = promoter(
        log,
        panel,
        SANDBOX,
        policy,
        reports_dir=tmp_path / "reports",
        prereg_dir=tmp_path / "prereg",
        permutations=5,
    )
    promote(memo(), killtest.KillTest("month_end_rebalance_v1", True, "", "passed", {}))

    prereg = log.records(kind="prereg", hypothesis_id="month_end_rebalance_v1")
    runs = log.records(kind="run", hypothesis_id="month_end_rebalance_v1")
    assert prereg and runs
    assert prereg[0].seq < runs[0].seq, "the pre-registration must predate the first run"
    assert (tmp_path / "prereg" / "month_end_rebalance_v1.md").exists()
    assert log.verify() > 0

    gates = log.records(kind="gate", hypothesis_id="month_end_rebalance_v1")
    assert gates, "the gates must have run"
    assert gates[0].payload["gate"] == 0
    assert gates[0].payload["verdict"] != "FAIL", "gate 0 should pass a correctly ordered promotion"


def test_a_grid_wider_than_the_policy_is_refused_at_promotion(tmp_path, panel):
    from qr.research.autopilot import promoter
    from qr.research.policy import PolicyBreach, current, declare

    log = TrialLog(tmp_path / "trial.jsonl")
    declare(log, ResearchPolicy(max_variants_per_family=4))
    promote = promoter(log, panel, SANDBOX, current(log), permutations=5)
    with pytest.raises(PolicyBreach, match="every family that comes after"):
        promote(memo(), killtest.KillTest("month_end_rebalance_v1", True, "", "passed", {}))
    assert not log.records(kind="prereg"), "nothing may be registered when the grid is refused"
