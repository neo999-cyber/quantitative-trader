"""The account-size sweep — Step 0 of `docs/10_NEXT.md`.

Three claims are worth a test, and only three. That the crypto side cannot
move with account size, because if it does the cost model has a size
dependence nobody declared. That the ETF side must move, monotonically and in
the direction commissions actually go. And that the whole exercise leaves the
trial log byte-identical, because a sensitivity analysis that inflates the
trial count would raise gate 4's bar for every future family — charging the
project for a search it did not perform.
"""
import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.account_size import (
    ACCOUNT_SIZES,
    SizeSweep,
    costs_for,
    reading,
    run_size_sweep,
)
from qr.research.families import FamilySpec
from qr.strategies.library import CrossSectionalMomentum, ShortTermReversal
from qr.validate.selftest import edge_world
from qr.validate.trial_log import SealedTrialLog, TrialLog

SIZES = (1_000.0, 10_000.0, 100_000.0)


@pytest.fixture(scope="module")
def panel():
    return edge_world(n_symbols=6, years=3, seed=11)


@pytest.fixture(scope="module")
def etf_panel():
    """The same world at an ETF's share price and an exchange's bar count.

    The share price is the point. A commission of $0.0035 a share with a $0.35
    floor is a fixed cost per order, so what decides whether it matters is the
    *notional* of one leg — and one leg is the account divided by the number of
    names held.
    """
    world = edge_world(n_symbols=6, years=3, seed=5)
    fields = {}
    for name, frame in world.fields.items():
        # prices x100 and base volume /100 keep quote volume, and so the implied
        # VWAP, consistent with the bar (the panel withholds bars where it is not)
        if name in ("open", "high", "low", "close"):
            fields[name] = frame * 100.0
        elif name == "volume":
            fields[name] = frame / 100.0
        else:
            fields[name] = frame
    fields["close_unadjusted"] = fields["close"]
    return Panel(fields, world.interval)


@pytest.fixture()
def small_family():
    return FamilySpec(
        hypothesis_id="xsmom_v1",
        strategy_class=CrossSectionalMomentum,
        grid={"lookback": [30, 60], "n_long": [3], "rebalance": [7]},
        summary="a two-variant stand-in for the real grid",
    )


@pytest.fixture()
def weekly_family():
    return FamilySpec(
        hypothesis_id="etf_reversal_v1",
        strategy_class=ShortTermReversal,
        grid={"lookback": [5, 10], "n_long": [3], "rebalance": [5]},
        summary="a weekly rebalance, which is where a per-order floor bites",
    )


# --------------------------------------------------------------- the crypto side


def test_the_crypto_cost_model_has_nowhere_to_put_an_account_size():
    """7.5 bps is 7.5 bps on a $10 order and on a $10,000 one."""
    models = [costs_for("crypto", equity) for equity in SIZES]
    assert {m.per_share_usd for m in models} == {0.0}
    assert {m.min_commission_usd for m in models} == {0.0}
    assert len({m.linear_bps for m in models}) == 1


def test_a_crypto_family_is_bit_identical_across_account_sizes(panel, small_family):
    """Not "roughly unchanged" — identical, and by construction.

    This is the test that makes Step 0's crypto arm honest. If it ever fails,
    the finding is a defect in the cost model, not a discovery about the
    strategy, and the sweep's report must say so.
    """
    runs = run_size_sweep(small_family, panel, None, "synthetic", "crypto", sizes=SIZES)
    curves = [r.sweep.results[r.best_variant].net for r in runs]
    for other in curves[1:]:
        pd.testing.assert_series_equal(curves[0], other)
    assert reading(runs) == "size-independent"


# ------------------------------------------------------------------ the ETF side


def test_the_etf_commission_falls_with_the_account():
    """One leg of a six-name basket, priced at each account size."""
    model = CostModel.etf_trial()
    prices = pd.DataFrame({"SPY": [100.0]})
    turnover = pd.DataFrame({"SPY": [1.0 / 6.0]})
    charged = [
        float(model.commission_bps(turnover, equity, prices).iloc[0, 0]) for equity in SIZES
    ]
    assert charged[0] > charged[1] > charged[2]
    # The floor binds at $1,000 ($167 traded, $0.35 charged) and not at
    # $100,000 ($16,667 traded, 58 shares, $0.20 — under the floor per share
    # but far past it per order).
    assert charged[0] == pytest.approx(0.35 / (1_000.0 / 6.0) / 1e-4, rel=1e-6)


def test_an_etf_family_gets_cheaper_with_size_and_never_dearer(etf_panel, weekly_family):
    runs = run_size_sweep(weekly_family, etf_panel, None, "synthetic", "etf", sizes=SIZES)
    drags = [r.sweep.results[r.best_variant].stats()["cost_drag_ann"] for r in runs]
    assert drags[0] > drags[-1], "a per-order floor must cost less on a larger account"
    assert drags == sorted(drags, reverse=True)
    assert reading(runs) != "worse with size — check the cost model"


def test_the_sweep_names_the_account_size_it_priced(etf_panel, weekly_family):
    runs = run_size_sweep(weekly_family, etf_panel, None, "synthetic", "etf", sizes=SIZES)
    assert [r.equity for r in runs] == list(SIZES)
    assert "1000" in costs_for("etf", 1_000.0).name
    assert "100000" in costs_for("etf", 100_000.0).name


# ------------------------------------------------------- the log stays untouched


def test_a_sealed_log_reads_the_chain_and_refuses_to_extend_it(tmp_path):
    path = tmp_path / "trial.jsonl"
    log = TrialLog(path)
    log.prereg("xsmom_v1", "a pre-registration")
    log.run("xsmom_v1", family="xsmom", params={}, universe="synthetic", variants=425)
    before = path.read_bytes()

    sealed = SealedTrialLog(path)
    assert len(sealed.records(kind="prereg", hypothesis_id="xsmom_v1")) == 1
    assert sealed.trial_count() == 425

    record = sealed.gate("xsmom_v1", 2, "cost survival", "PASS", {})
    assert record.payload["sealed"] is True
    assert path.read_bytes() == before
    assert TrialLog(path).verify() == 2


def test_the_sweep_leaves_the_trial_count_exactly_where_it_found_it(
    tmp_path, panel, small_family
):
    path = tmp_path / "trial.jsonl"
    log = TrialLog(path)
    log.prereg("xsmom_v1", "a pre-registration")
    log.run("xsmom_v1", family="xsmom", params={}, universe="synthetic", variants=425)
    before = path.read_bytes()

    run_size_sweep(
        small_family, panel, None, "synthetic", "crypto", trial_log=log, sizes=SIZES
    )

    assert path.read_bytes() == before
    assert TrialLog(path).trial_count() == 425
    assert TrialLog(path).verify() == 2


# ---------------------------------------------------------------- the reporting


def test_the_sweep_reports_a_reading_and_never_a_verdict(panel, small_family):
    sweep = SizeSweep(sizes=SIZES)
    sweep.runs.extend(
        run_size_sweep(small_family, panel, None, "synthetic", "crypto", sizes=SIZES)
    )
    frame = sweep.frame()
    assert len(frame) == len(SIZES)
    assert list(frame["equity"]) == list(SIZES)

    readings = sweep.readings()
    assert list(readings["hypothesis"]) == ["xsmom_v1"]
    assert "verdict" not in readings.columns
    assert readings.loc[0, "reading"] == "size-independent"


def test_only_the_size_sensitive_gates_run(panel, small_family):
    """Gates 6 and 7 cost hours and cannot move with the account size."""
    runs = run_size_sweep(small_family, panel, None, "synthetic", "crypto", sizes=(1_000.0, 10_000.0))
    numbers = {r.number for r in runs[0].report.results}
    assert numbers == {2, 3, 4, 5, 11}


def test_gate_eleven_refuses_to_size_without_an_out_of_sample_sharpe(panel, small_family):
    """The sweep must not hand a leverage figure to a family that has no holdout."""
    runs = run_size_sweep(small_family, panel, None, "synthetic", "crypto", sizes=(1_000.0,))
    assert runs[0].gate(11) == "SKIP"
    assert np.isnan(runs[0].gate_stat(11, "leverage"))


def test_the_default_sizes_are_the_three_the_plan_names():
    assert ACCOUNT_SIZES == (1_000.0, 10_000.0, 100_000.0)


# ------------------------------------ the benchmark must be in the same account


def test_gate_fives_benchmark_is_priced_at_the_account_the_strategy_runs_in(etf_panel):
    """Otherwise the comparison is between two different accounts.

    `buy_and_hold_benchmark` took no equity, so on a per-order venue it fell
    back to `run_backtest`'s $10,000 default while the ETF trial priced its
    strategies at $1,000 — asking each family to beat a buy-and-hold that was
    an order of magnitude cheaper per trade.
    """
    from qr.validate.spa import buy_and_hold_benchmark

    costs = CostModel.etf_trial()
    small = buy_and_hold_benchmark(etf_panel, None, costs, equity=1_000.0)
    large = buy_and_hold_benchmark(etf_panel, None, costs, equity=100_000.0)
    assert small.sum() < large.sum(), "the smaller account must pay more commission"

    crypto = CostModel.trial()
    a = buy_and_hold_benchmark(etf_panel, None, crypto, equity=1_000.0)
    b = buy_and_hold_benchmark(etf_panel, None, crypto, equity=100_000.0)
    pd.testing.assert_series_equal(a, b)
