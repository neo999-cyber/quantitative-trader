"""Gates 10 and 11: the two that decide whether money moves.

Everything before them is an argument about history. Gate 10 is the only
check that reads bars nobody had when the strategy was written, and gate 11
is the only one whose output is a dollar amount. They are tested harder than
the rest for the same reason they are last.
"""
import numpy as np
import pandas as pd
import pytest

from qr.execution.costs import CostModel
from qr.portfolio.sizing import Sizing, SizingPolicy, prob_ever_below_launch, size
from qr.research.runner import run_backtest
from qr.strategies.library import TSMOM
from qr.validate import forward
from qr.validate.gates import (
    FAIL,
    PASS,
    SKIP,
    WARN,
    GateContext,
    gate_10_forward,
    gate_11_sizing,
)
from qr.validate.selftest import edge_world
from qr.validate.trial_log import TrialLog


@pytest.fixture(scope="module")
def world():
    return edge_world(n_symbols=4, years=3, seed=1)


@pytest.fixture()
def log(tmp_path):
    return TrialLog(tmp_path / "trial_log.jsonl")


def context(panel, log, **kwargs):
    strategy = TSMOM(lookback=60)
    costs = CostModel.trial()
    return GateContext(
        hypothesis_id="h1",
        panel=panel,
        strategy=strategy,
        costs=costs,
        result=run_backtest(panel, strategy, costs),
        trial_log=log,
        **kwargs,
    )


def returns_with_sharpe(n, sharpe, sd=0.01, periods_per_year=365.0, seed=0):
    """`n` returns whose *realised* annualised Sharpe is exactly `sharpe`.

    Drawing from a distribution with the right mean is not the same thing: at
    n=70 the sample Sharpe of a draw with a true Sharpe of 0.8 lands anywhere
    from -4 to +5. These tests are about the gate's arithmetic, so the input
    has to be the number, not a lottery ticket for it.
    """
    x = np.random.default_rng(seed).normal(size=n)
    x = (x - x.mean()) / x.std(ddof=1) * sd
    return x + sharpe * sd / np.sqrt(periods_per_year)


def incubate(log, n, sharpe=0.8, sd=0.01, cost=0.0001, expected_cost=0.0001,
             weights=None, expected=None, seed=0):
    """Write `n` days of paper record into the chain."""
    net = returns_with_sharpe(n, sharpe, sd=sd, seed=seed)
    start = pd.Timestamp("2026-01-01")
    for i in range(n):
        log.forward(
            "h1",
            date=str((start + pd.Timedelta(days=i)).date()),
            net_return=float(net[i]),
            cost=cost,
            expected_cost=expected_cost,
            weights=weights if weights is not None else {"A": 0.5, "B": 0.5},
            expected_weights=expected if expected is not None else {"A": 0.5, "B": 0.5},
        )


# --------------------------------------------------------------- the record


def test_a_bar_with_no_expectation_is_unknown_rather_than_agreement(log):
    """The dangerous default: a live book with nothing to compare against
    must not read as a book that matched perfectly."""
    log.forward("h1", "2026-01-01", 0.001, 0.0001, weights={"A": 1.0})
    records = forward.frame(log, "h1")
    assert np.isnan(records["weight_error"].iloc[0])


def test_a_position_the_research_never_asked_for_counts_as_much_as_a_missing_one(log):
    log.forward("h1", "2026-01-01", 0.0, 0.0, weights={"A": 0.5, "Z": 0.4},
                expected_weights={"A": 0.5})
    assert forward.frame(log, "h1")["weight_error"].iloc[0] == pytest.approx(0.4)


def test_a_corrected_day_does_not_replace_the_original(log):
    """Append-only means a second line for the same day is a correction on
    the record, not a quiet overwrite of the day that went badly."""
    log.forward("h1", "2026-01-01", -0.05, 0.0001)
    log.forward("h1", "2026-01-01", +0.05, 0.0001)
    records = forward.frame(log, "h1")
    assert len(records) == 1
    assert records["net_return"].iloc[0] == pytest.approx(-0.05)
    assert len(log.records(kind="forward", hypothesis_id="h1")) == 2


# ----------------------------------------------------------------- gate 10


def test_no_record_at_all_is_a_skip_not_a_pass(world, log):
    assert gate_10_forward(context(world, log)).verdict == SKIP


def test_a_short_record_is_incubating_rather_than_failed(world, log):
    incubate(log, 20)
    result = gate_10_forward(context(world, log))
    assert result.verdict == SKIP
    assert "20 of 63" in result.detail


def test_a_book_that_does_not_match_the_research_fails_as_a_defect(world, log):
    """And says so: this is the failure that more incubation cannot fix."""
    incubate(log, 70, weights={"A": 0.5, "B": 0.5}, expected={"A": 0.5, "B": 0.3})
    result = gate_10_forward(context(world, log))
    assert result.verdict == FAIL
    assert "wiring defect" in result.detail
    assert "not a decay" in result.detail


def test_wiring_is_checked_before_the_edge(world, log):
    """A book that is both mis-wired and profitable must still fail, or the
    check is decorative."""
    incubate(log, 70, sharpe=4.0, weights={"A": 1.0}, expected={"B": 1.0})
    assert gate_10_forward(context(world, log)).verdict == FAIL


def test_costs_above_the_model_invalidate_gate_2_and_say_so(world, log):
    incubate(log, 70, cost=0.0005, expected_cost=0.0001)
    result = gate_10_forward(context(world, log))
    assert result.verdict == FAIL
    assert "cost model" in result.detail and "gate 2" in result.detail


def test_a_decayed_edge_fails_on_the_ratio(world, log):
    ctx = context(world, log)
    incubate(log, 70, sharpe=ctx.result.sharpe() * 0.3)
    result = gate_10_forward(ctx)
    assert result.verdict == FAIL
    assert result.stats["forward_over_in_sample"] == pytest.approx(0.3, rel=1e-6)


def test_a_dented_edge_warns_rather_than_fails(world, log):
    """Between 50% and 70% of in-sample is another month's question, not a
    verdict. The band has to exist or every ordinary wobble kills a strategy."""
    ctx = context(world, log)
    incubate(log, 70, sharpe=ctx.result.sharpe() * 0.6)
    result = gate_10_forward(ctx)
    assert result.verdict == WARN
    assert "another month" in result.detail


def test_a_negative_forward_sharpe_fails(world, log):
    incubate(log, 70, sharpe=-0.5)
    assert gate_10_forward(context(world, log)).verdict == FAIL


def test_a_pass_refuses_to_claim_more_than_the_sample_supports(world, log):
    """The verdict text is the check. Three months cannot confirm an edge and
    the gate must not imply that it did."""
    ctx = context(world, log)
    incubate(log, 70, sharpe=ctx.result.sharpe())
    result = gate_10_forward(ctx)
    assert result.verdict == PASS
    assert "consistent with the research" in result.detail
    assert "strongest claim" in result.detail
    assert "confirm" not in result.detail


# ----------------------------------------------------------------- sizing


def test_full_kelly_halves_your_money_with_probability_one_half():
    """A known answer — but not one that could ever have failed alone.

    `docs/16` made the point: this was the module's proof of correctness, and
    it was taken from the same literature as the formula, so it cannot detect
    the error that was actually present (the expression was right and the
    *label* was wrong). It is kept because it is true, and joined below by a
    second known answer and a simulation that does not share its provenance.
    """
    sharpe, vol = 0.8, 0.2
    full_kelly = sharpe / vol
    assert prob_ever_below_launch(full_kelly, sharpe, vol, 0.5) == pytest.approx(0.5, abs=1e-9)


def test_half_kelly_halves_your_money_with_probability_one_eighth():
    """The second published anchor: at c of full Kelly, q = 2/c - 1, so half
    Kelly gives (1/2)**3. Two points pin the exponent as well as the level."""
    sharpe, vol = 0.8, 0.2
    p = prob_ever_below_launch(0.5 * sharpe / vol, sharpe, vol, 0.5)
    assert p == pytest.approx(0.125, abs=1e-9)


def test_a_simulated_book_reproduces_the_closed_form():
    """The independent check: no formula, just paths.

    A geometric random walk at quarter Kelly, run for forty years of daily
    steps, and the fraction of paths that ever closed 25% below where they
    started. Discrete steps can only miss barrier crossings that happen
    between closes, so the simulation is biased slightly low and the assertion
    is one-sided about that; what it cannot do is agree by construction.
    """
    sharpe, vol, depth = 0.8, 0.2, 0.25
    leverage = 0.25 * sharpe / vol
    closed_form = prob_ever_below_launch(leverage, sharpe, vol, depth)

    steps, paths, per_year = 40 * 252, 20_000, 252
    m = leverage * sharpe * vol - 0.5 * (leverage * vol) ** 2
    s = leverage * vol
    rng = np.random.default_rng(20260914)
    barrier = np.log(1.0 - depth)

    hit = 0
    for chunk in range(0, paths, 2_000):
        n = min(2_000, paths - chunk)
        steps_arr = rng.normal(m / per_year, s / np.sqrt(per_year), size=(n, steps))
        log_equity = np.cumsum(steps_arr, axis=1)
        hit += int((log_equity.min(axis=1) <= barrier).sum())
    simulated = hit / paths

    assert simulated == pytest.approx(closed_form, abs=0.02)
    assert simulated <= closed_form + 0.01, "discrete steps cannot cross more often than continuous ones"


def test_the_below_launch_cap_actually_hits_its_budget():
    """Solve for the cap, then measure the risk at that cap. They must agree."""
    policy = SizingPolicy(loss_from_launch=0.25, loss_tolerance=0.10)
    plan = size(0.9, 0.2, max_weight=0.0, policy=policy)
    at_cap = prob_ever_below_launch(plan.caps["below_launch"], 0.9, 0.2, 0.25)
    assert at_cap == pytest.approx(0.10, rel=1e-6)


def test_a_malformed_policy_is_refused_at_construction():
    """It used to be accepted and turned into a leverage downstream."""
    with pytest.raises(ValueError, match="loss_from_launch"):
        SizingPolicy(loss_from_launch=1.5)
    with pytest.raises(ValueError, match="loss_tolerance"):
        SizingPolicy(loss_tolerance=0.0)


def test_the_kelly_ceiling_can_actually_bind():
    """At 0.25 it never could: the launch-loss cap lands at 0.222 of full
    Kelly under the default budget, so the Kelly cap was decoration. It binds
    now when the loss budget is loosened, which is the only time it should."""
    # The volatility ceiling is lifted out of the way so the comparison is
    # between the two caps under discussion and not a third one.
    loose = SizingPolicy(loss_tolerance=0.50, volatility_target=10.0)
    plan = size(1.0, 0.2, max_weight=0.0, policy=loose)
    assert plan.binding == "kelly"
    tight = SizingPolicy(volatility_target=10.0)
    assert size(1.0, 0.2, max_weight=0.0, policy=tight).binding == "below_launch"
    # And the crossover is where the algebra says: the launch-loss cap passes
    # the Kelly ceiling when q = 2/kelly_fraction - 1 = 3, i.e. tol = 0.75**3.
    assert 0.75**3 == pytest.approx(0.4219, abs=1e-4)


def test_sizing_is_the_minimum_of_the_caps_and_names_the_one_that_bound():
    plan = size(1.5, 0.10, max_weight=0.25, equity=1000)
    assert plan.leverage == pytest.approx(min(plan.caps.values()))
    assert plan.caps[plan.binding] == pytest.approx(plan.leverage)


def test_a_negative_edge_gets_no_size():
    plan = size(-0.3, 0.2, max_weight=0.1)
    assert plan.leverage == 0.0
    assert "nothing to size" in plan.notes[0]


def test_notional_follows_the_account():
    assert size(0.8, 0.15, max_weight=0.2, equity=10_000).notional == pytest.approx(
        size(0.8, 0.15, max_weight=0.2, equity=1_000).notional * 10
    )


# ----------------------------------------------------------------- gate 11


def test_gate_11_refuses_to_size_off_the_in_sample_sharpe(world, log):
    """The whole point of the gate. There is an in-sample Sharpe available
    and it must not be used."""
    ctx = context(world, log)
    assert ctx.result.sharpe() > 0
    result = gate_11_sizing(ctx)
    assert result.verdict == SKIP
    assert "will not size off" in result.detail


def test_gate_11_sizes_off_the_holdout_when_gate_9_has_opened_it(world, log):
    log.append("holdout", "h1", {"stats": {"holdout_sharpe": 0.8, "holdout_volatility": 0.15}})
    result = gate_11_sizing(context(world, log, equity=1000))
    assert result.verdict == PASS
    assert result.stats["sizing_basis"] == "the holdout"
    assert result.stats["leverage"] > 0
    assert "$" in result.detail


def test_gate_11_prefers_the_forward_record_over_the_holdout(world, log):
    log.append("holdout", "h1", {"stats": {"holdout_sharpe": 0.8, "holdout_volatility": 0.15}})
    incubate(log, 70)
    result = gate_11_sizing(context(world, log, equity=1000))
    assert "forward record" in result.stats["sizing_basis"]


def test_gate_11_fails_a_holdout_with_no_edge(world, log):
    log.append("holdout", "h1", {"stats": {"holdout_sharpe": -0.2, "holdout_volatility": 0.15}})
    result = gate_11_sizing(context(world, log))
    assert result.verdict == FAIL
    assert "nothing to size" in result.detail


def test_gate_11_warns_when_the_size_is_too_small_to_bother(world, log):
    log.append("holdout", "h1", {"stats": {"holdout_sharpe": 0.05, "holdout_volatility": 2.0}})
    result = gate_11_sizing(context(world, log, equity=1000))
    assert result.verdict == WARN
    assert "too small" in result.detail
