"""Stages 2 and 3, and the loop that joins them.

The generator is an LLM and is not tested here; what is tested is everything
that decides what happens to what it produces. Triage must reach its verdict
without reference to the model's own, the kill test must refuse to look at
validation data, and the loop must exit the same recorded way at every stage.
"""
import pathlib

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
        "transmission": "The funds hold these ETFs directly, so the forced trade happens in "
        "this market: the mandate is executed against the same closing print we trade.",
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


# --------------------------------------------------------------- the market


def test_a_memo_cannot_be_written_without_knowing_the_market():
    """The first ETF night produced seven memos about crypto.

    `propose()` was handed the brief and nothing else, and the feature registry
    it *is* shown talks about perpetual funding and the crypto Fear & Greed
    index — so the model inferred Binance spot and killed every equity payer
    for having no route into an altcoin. The memos were sound and about the
    wrong market. An empty market must raise rather than default.
    """
    from qr.research.mechanism import propose

    with pytest.raises(ValueError, match="which market"):
        propose("month end rebalancing", market="   ")


def test_the_market_description_names_the_instrument_and_the_universe():
    """A prompt that lists SPY and TLT cannot be read as a Binance pair list."""
    from qr.cli import _market_description
    from qr.execution.costs import CostModel

    class _Panel:
        symbols = ["SPY", "QQQ", "TLT", "LQD", "HYG"]

    text = _market_description("etf", _Panel(), CostModel.etf_trial(), 1_000.0)
    assert "ETF" in text and "SPY" in text and "TLT" in text
    assert "per-order minimum" in text
    assert "$1,000" in text
    assert "perpetual" not in text.lower()

    crypto = _market_description("crypto", _Panel(), CostModel.trial(), None)
    assert "spot" in crypto and "cannot trade the perpetual" in crypto


def test_the_night_passes_the_market_to_every_memo(panel):
    """The loop is where it would be dropped, so assert it arrives."""
    from qr.research.autopilot import run_night
    from qr.validate.trial_log import TrialLog
    import tempfile

    seen = []

    def fake(brief, market="", **kw):
        seen.append(market)
        return memo(self_verdict="killed", kill_reason="not the point of this test")

    with tempfile.TemporaryDirectory() as tmp:
        log = TrialLog(pathlib.Path(tmp) / "trial.jsonl")
        from qr.research.policy import declare as declare_policy
        from qr.data.sandbox import declare as declare_sandbox

        declare_sandbox(log, SANDBOX)
        declare_policy(log, ResearchPolicy())
        run_night(["a brief"], log, ResearchPolicy(), SANDBOX, panel,
                  market="**Instrument.** twelve US ETFs", propose=fake)

    assert seen == ["**Instrument.** twelve US ETFs"]


# ------------------------------------------------------------------- registry


def test_the_registry_separates_what_we_have_from_what_we_would_need():
    assert features.available("calendar")
    assert features.available("quote_volume")
    # Obtainable since the funding ingestor. "Available" is a claim about the
    # project, not about any particular lake — see the panel check below.
    assert features.available("funding_rate")
    assert not features.available("token_unlocks")
    assert not features.available("liquidations")


def test_a_blocked_idea_names_the_dataset_that_would_unblock_it():
    needed = features.datasets_needed(["close", "liquidations", "token_unlocks"])
    assert any("forceOrder" in d for d in needed)
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


def test_a_memo_naming_no_transmission_is_killed():
    """The transfer can be real and still not reach the market being traded."""
    verdict = triage(memo(transmission="   ", confidence=0.9))
    assert verdict.verdict == "killed"
    assert "question 2" in verdict.reason


def test_a_transmission_that_only_asserts_two_prices_move_together_is_killed():
    verdict = triage(
        memo(
            transmission="Funding on the perpetual is high, so the market tends to fall in spot "
            "shortly afterwards."
        )
    )
    assert verdict.verdict == "killed"
    assert "not an observation that two prices move together" in verdict.reason


def test_a_transmission_naming_no_agent_in_this_market_is_killed():
    """The perp is a different instrument; something has to carry the flow across."""
    verdict = triage(
        memo(
            transmission="Leveraged longs are forced to close on the perpetual, which feeds "
            "through to the spot price."
        )
    )
    assert verdict.verdict == "killed"
    assert "names no agent" in verdict.reason


def test_a_transmission_that_names_the_arbitrage_proceeds():
    verdict = triage(
        memo(
            transmission="Liquidations force selling on the perpetual. Basis arbitrageurs are "
            "long spot against short perp; as the basis collapses they sell spot to stay hedged, "
            "and that selling is the flow this strategy meets."
        )
    )
    assert verdict.proceed


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
    verdict = triage(memo(required_features=("close", "token_unlocks")))
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
        "b": memo(candidate_id="b_v1", required_features=("close", "token_unlocks")),
        "c": memo(candidate_id="c_v1"),
    }
    night = run_night(
        ["a", "b", "c"], log, policy, SANDBOX, panel, propose=lambda brief, **kw: memos[brief]
    )

    assert [o.outcome for o in night.outcomes] == ["killed", "blocked", "failed"]
    assert any("DropsTab" in d for d in night.shopping_list())
    assert log.verify() > 0


def test_the_quota_stops_the_night_before_it_spends_a_memo(tmp_path, panel):
    log, policy = _log_with_policy(tmp_path, max_promotions_per_week=1)
    log.prereg("already_promoted_v1", "an earlier candidate")
    calls = []

    def spy(brief, **kw):
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
    night = run_night(["a"], log, policy, SANDBOX, panel, propose=lambda b, **kw: memo())
    assert night.stopped_early
    assert "index fund" in night.stopped_early


def test_a_memo_that_fails_to_generate_does_not_stop_the_night(tmp_path, panel):
    log, policy = _log_with_policy(tmp_path)

    def flaky(brief, **kw):
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
    night = run_night(["c"], log, policy, SANDBOX, panel, propose=lambda b, **kw: memo(candidate_id="c_v1"))
    assert night.outcomes[0].outcome == "ready"

    promoted = []
    night = run_night(
        ["c"],
        log,
        policy,
        SANDBOX,
        panel,
        propose=lambda b, **kw: memo(candidate_id="c_v1"),
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


# ------------------------------------------------- the schema the API accepts


def _objects(node, path="root"):
    """Every object subschema in the tree, with its path."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield path, node
        for key, value in node.items():
            yield from _objects(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _objects(value, f"{path}[{i}]")


def test_every_object_in_the_memo_schema_is_closed():
    """`additionalProperties: true` is rejected outright by structured outputs.

    A live run died on exactly this: the `params` object was open so that a
    crude version could carry any primitive's arguments, and every memo came
    back a 400 before the model had written a word.
    """
    from qr.research.mechanism import MEMO_SCHEMA

    for path, node in _objects(MEMO_SCHEMA):
        assert node.get("additionalProperties") is False, f"{path} is not closed"


def test_every_object_requires_all_of_its_properties():
    """What the documented examples do, and what strict validation expects."""
    from qr.research.mechanism import MEMO_SCHEMA

    for path, node in _objects(MEMO_SCHEMA):
        assert set(node.get("required", [])) == set(node["properties"]), path


def test_the_parameter_names_come_from_the_classes_not_from_a_list():
    """So a renamed constructor argument cannot silently drift out of the schema."""
    import inspect

    from qr.research.autopilot import PRIMITIVES_FOR_SPEC
    from qr.research.mechanism import MEMO_SCHEMA

    schema = MEMO_SCHEMA["properties"]["crude_version"]["properties"]["params"]["properties"]
    for cls in PRIMITIVES_FOR_SPEC.values():
        for name in inspect.signature(cls.__init__).parameters:
            if name != "self":
                assert name in schema, f"{cls.__name__}.{name} is missing from the schema"


def test_optional_parameters_are_nullable_and_typed_from_the_annotation():
    from qr.research.mechanism import MEMO_SCHEMA

    schema = MEMO_SCHEMA["properties"]["crude_version"]["properties"]["params"]["properties"]
    assert schema["event"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    assert schema["before"]["anyOf"][0]["type"] == "integer"
    assert schema["gross"]["anyOf"][0]["type"] == "number"
    # A `None` default carries no type; the annotation says str.
    assert schema["rebalance_on"]["anyOf"][0]["type"] == "string"


def test_nulls_for_irrelevant_parameters_do_not_break_the_build():
    """The schema offers every primitive's parameters, so a memo will send nulls."""
    from qr.research.mechanism import CrudeVersion

    crude = CrudeVersion(
        primitive="calendar_event",
        params={"event": "month_end", "before": 2, "after": None, "lookback": None,
                "n_long": None, "vol_target": None, "rebalance_on": None},
        expected_sign="positive",
    )
    strategy = crude.build()
    assert strategy.params["event"] == "month_end"
    assert strategy.params["before"] == 2


def test_a_non_null_parameter_the_primitive_does_not_accept_still_kills_the_memo():
    """Dropping it in silence would be worse than refusing it."""
    verdict = triage(
        memo(
            crude_version=CrudeVersion(
                primitive="calendar_event",
                params={"event": "month_end", "lookback": 60},
                expected_sign="positive",
            )
        )
    )
    assert verdict.verdict == "killed"
    assert "does not build" in verdict.reason


def test_a_rejected_request_stops_the_night_instead_of_repeating_itself(tmp_path, panel):
    """Three identical 400s is what a live run produced before anyone read one."""
    log, policy = _log_with_policy(tmp_path)
    calls = []

    class BadRequest(Exception):
        status_code = 400

    def broken(brief, **kw):
        calls.append(brief)
        raise BadRequest("additionalProperties: true is not supported")

    night = run_night(["a", "b", "c"], log, policy, SANDBOX, panel, propose=broken)
    assert len(calls) == 1, "a request error must not be retried once per brief"
    assert "every brief would fail the same way" in night.stopped_early


def test_a_rate_limit_or_server_error_does_not_stop_the_night(tmp_path, panel):
    log, policy = _log_with_policy(tmp_path)
    calls = []

    class Overloaded(Exception):
        status_code = 529

    def flaky(brief, **kw):
        calls.append(brief)
        if len(calls) == 1:
            raise Overloaded("overloaded")
        return memo(candidate_id="b_v1")

    night = run_night(["a", "b"], log, policy, SANDBOX, panel, propose=flaky)
    assert len(calls) == 2
    assert not night.stopped_early


def test_the_schema_uses_only_keywords_the_api_is_known_to_accept():
    """Two nights were spent finding these one rejection at a time.

    `additionalProperties: true` went first, then numeric `minimum`/`maximum`
    on `confidence`. Each cost a run that had already loaded the lake. The
    whitelist is what has been *proven* to pass, not a claim about the API's
    full capability, and it fails here in a second instead.
    """
    from qr.research.mechanism import MEMO_SCHEMA, SCHEMA_KEYWORDS

    def walk(node, path="root"):
        if isinstance(node, dict):
            if {"type", "anyOf", "enum"} & set(node):
                for key in node:
                    assert key in SCHEMA_KEYWORDS, f"{path}.{key} is not a known-good keyword"
            for key, value in node.items():
                if key == "properties":
                    for name, sub in value.items():
                        walk(sub, f"{path}.{name}")
                else:
                    walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    walk(MEMO_SCHEMA)


def test_confidence_is_clamped_because_the_schema_no_longer_bounds_it():
    from qr.research.mechanism import MechanismMemo

    raw = {
        "candidate_id": "x_v1", "title": "t", "forced_trader": "f", "persistence": "p",
        "other_side": "o", "what_breaks_it": "w",
        "crude_version": {"primitive": "calendar_event", "params": {},
                          "expected_sign": "positive", "rationale": ""},
        "required_features": [], "self_verdict": "proceed", "kill_reason": "",
    }
    assert MechanismMemo.from_dict({**raw, "confidence": 7.0}).confidence == 1.0
    assert MechanismMemo.from_dict({**raw, "confidence": -3.0}).confidence == 0.0
    assert MechanismMemo.from_dict({**raw, "confidence": 0.35}).confidence == 0.35


# ------------------------------------------------------------ the shopping list


def test_the_shopping_list_counts_datasets_named_by_killed_candidates_too(tmp_path, panel):
    """Two real nights reported "0 blocked" while three memos said "blocked on data".

    Triage honours a self-kill first, and a model that notices the data is
    missing says so *by killing its own candidate*. Drawing the list only from
    `blocked` candidates threw away the most useful thing the night produced.
    """
    log, policy = _log_with_policy(tmp_path)
    memos = {
        # Self-killed, and needs liquidation data. The verdict stays killed.
        "a": memo(candidate_id="a_v1", self_verdict="killed",
                  kill_reason="we trade spot and the payer is levered",
                  required_features=("close", "liquidations")),
        # Self-killed for an unrelated reason, but also named liquidations.
        "b": memo(candidate_id="b_v1", self_verdict="killed", kill_reason="no payer",
                  required_features=("liquidations",)),
        # Proceeds, blocked on data.
        "c": memo(candidate_id="c_v1", required_features=("close", "token_unlocks")),
    }
    night = run_night(["a", "b", "c"], log, policy, SANDBOX, panel,
                      propose=lambda brief, **kw: memos[brief])

    assert [o.outcome for o in night.outcomes] == ["killed", "killed", "blocked"]
    shopping = night.shopping_list()
    liquidations = next(d for d in shopping if "forceOrder" in d)
    assert shopping[liquidations] == 2, "two candidates ran into liquidation data"
    assert any("DropsTab" in d for d in shopping)
    assert list(shopping)[0] == liquidations, "the most-wanted dataset comes first"


def test_a_killed_candidate_stays_killed_even_when_it_names_missing_data(tmp_path, panel):
    """The shopping list must not resurrect an idea that failed on its merits."""
    log, policy = _log_with_policy(tmp_path)
    dead = memo(candidate_id="d_v1", self_verdict="killed",
                kill_reason="nobody is forced", required_features=("liquidations",))
    night = run_night(["d"], log, policy, SANDBOX, panel, propose=lambda b, **kw: dead)

    assert night.outcomes[0].outcome == "killed"
    assert night.blocked() == []
    assert night.shopping_list(), "the dataset is still recorded"


def test_a_feature_this_project_has_but_this_lake_lacks_is_blocked(panel):
    """Obtainable and present are different, and conflating them is expensive.

    `funding_rate` is available to the project — the ingestor exists — but a
    lake that has not pulled it carries no such column. Sending the memo on
    would produce a strategy holding nothing, which reads exactly like a
    strategy that found nothing.
    """
    needs_funding = memo(required_features=("close", "funding_rate"))
    assert triage(needs_funding).proceed, "the project can have it"

    verdict = triage(needs_funding, panel)
    assert verdict.verdict == "blocked"
    assert "has not been pulled into this lake" in verdict.reason
    assert "funding_rate" in verdict.reason


def test_the_same_memo_proceeds_once_the_lake_has_the_column(panel):
    import numpy as np
    import pandas as pd

    from qr.data.funding import attach

    funded = attach(
        panel,
        {s: pd.DataFrame({"funding_rate": 1e-4}, index=panel.index) for s in panel.symbols},
    )
    verdict = triage(memo(required_features=("close", "funding_rate")), funded)
    assert verdict.proceed
