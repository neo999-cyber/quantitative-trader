"""The discovery sandbox — Stage 1 of `docs/10_NEXT.md`.

The sandbox is a promise: look at this slice as much as you like, because
nothing from it ever reaches the record. A promise is only worth the
enforcement behind it, so what is tested here is the enforcement — that the
boundary cannot be redrawn quietly, that the split was decided by a hash
rather than by a person, and that a result computed on the sandbox cannot be
reported no matter which way it is carried towards a report.
"""
import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.data.sandbox import (
    SIDE_ATTR,
    SandboxRedeclared,
    SandboxSpec,
    current,
    declare,
    require,
    restrict,
    sandbox_side,
)
from qr.validate.selftest import noise_world
from qr.validate.trial_log import TrialLog


@pytest.fixture(scope="module")
def panel():
    return noise_world(n_symbols=24, years=4, seed=7)


@pytest.fixture()
def log(tmp_path):
    return TrialLog(tmp_path / "trial.jsonl")


# ------------------------------------------------------- nobody chose the split


def test_the_split_is_a_hash_so_it_is_reproducible():
    spec = SandboxSpec(market="binance/spot")
    names = [f"SYM{i}USDT" for i in range(200)]
    first, _ = spec.split_symbols(names)
    second, _ = SandboxSpec(market="binance/spot").split_symbols(names)
    assert first == second


def test_a_different_salt_draws_a_different_line():
    names = [f"SYM{i}USDT" for i in range(200)]
    a, _ = SandboxSpec(market="binance/spot").split_symbols(names)
    b, _ = SandboxSpec(market="binance/spot", salt="other").split_symbols(names)
    assert a != b


def test_the_fraction_is_roughly_honoured():
    names = [f"SYM{i}USDT" for i in range(2_000)]
    discovery, validation = SandboxSpec(market="binance/spot", symbol_fraction=0.25).split_symbols(names)
    assert len(discovery) + len(validation) == len(names)
    assert 0.22 < len(discovery) / len(names) < 0.28


def test_the_two_sides_never_share_a_symbol():
    names = [f"SYM{i}USDT" for i in range(500)]
    discovery, validation = SandboxSpec(market="binance/spot").split_symbols(names)
    assert not set(discovery) & set(validation)


def test_a_sandbox_of_everything_or_nothing_is_refused():
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        SandboxSpec(market="m", symbol_fraction=1.0)
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        SandboxSpec(market="m", symbol_fraction=0.0)


def test_a_period_split_needs_a_date():
    with pytest.raises(ValueError, match="needs a period_end"):
        SandboxSpec(market="tiingo/etf", mode="period")


# ------------------------------------------------------------- the restriction


def test_restrict_splits_the_panel_and_stamps_the_side(panel):
    spec = SandboxSpec(market="binance/spot")
    discovery = restrict(panel, spec, "discovery")
    validation = restrict(panel, spec, "validation")

    assert not set(discovery.symbols) & set(validation.symbols)
    assert set(discovery.symbols) | set(validation.symbols) == set(panel.symbols)
    assert sandbox_side(discovery) == "discovery"
    assert sandbox_side(validation) == "validation"
    assert sandbox_side(panel) is None, "an unrestricted panel must not claim a side"


def test_a_period_split_cuts_the_time_axis_not_the_symbols(panel):
    cutoff = str(panel.index[len(panel.index) // 2].date())
    spec = SandboxSpec(market="tiingo/etf", mode="period", period_end=cutoff)
    discovery = restrict(panel, spec, "discovery")
    validation = restrict(panel, spec, "validation")

    assert discovery.symbols == validation.symbols == panel.symbols
    assert discovery.index.max() <= pd.Timestamp(cutoff, tz="UTC")
    assert validation.index.min() > pd.Timestamp(cutoff, tz="UTC")
    assert len(discovery) + len(validation) == len(panel)


def test_both_mode_is_a_rectangle(panel):
    cutoff = str(panel.index[len(panel.index) // 2].date())
    spec = SandboxSpec(market="binance/spot", mode="both", period_end=cutoff)
    discovery = restrict(panel, spec, "discovery")
    assert len(discovery.symbols) < len(panel.symbols)
    assert discovery.index.max() <= pd.Timestamp(cutoff, tz="UTC")


def test_an_empty_side_is_an_error_rather_than_a_silent_nothing(panel):
    spec = SandboxSpec(market="binance/spot", mode="period", period_end="1999-01-01")
    with pytest.raises(ValueError, match="empty"):
        restrict(panel, spec, "discovery")


# --------------------------------------------------------- declared exactly once


def test_a_boundary_is_declared_once_and_then_refused(log):
    spec = SandboxSpec(market="binance/spot")
    declare(log, spec)
    with pytest.raises(SandboxRedeclared, match="already has a sandbox"):
        declare(log, SandboxSpec(market="binance/spot", symbol_fraction=0.4))
    assert current(log, "binance/spot").symbol_fraction == 0.25


def test_a_forced_redeclaration_leaves_the_supersession_in_the_chain(log):
    declare(log, SandboxSpec(market="binance/spot"))
    first = current(log, "binance/spot").fingerprint()
    declare(log, SandboxSpec(market="binance/spot", symbol_fraction=0.4), force=True)

    records = log.records(kind="sandbox")
    assert len(records) == 2
    assert records[-1].payload["supersedes"] == first
    assert current(log, "binance/spot").symbol_fraction == 0.4
    assert log.verify() == 2


def test_two_markets_get_two_independent_boundaries(log):
    declare(log, SandboxSpec(market="binance/spot"))
    declare(log, SandboxSpec(market="tiingo/etf", mode="period", period_end="2018-12-31"))
    assert current(log, "binance/spot").mode == "symbols"
    assert current(log, "tiingo/etf").mode == "period"


def test_exploring_without_a_declared_boundary_is_refused(log):
    with pytest.raises(SandboxRedeclared, match="no discovery sandbox"):
        require(log, "binance/spot")


def test_the_boundary_survives_a_round_trip_through_the_log(log):
    spec = SandboxSpec(
        market="tiingo/etf", mode="both", symbol_fraction=0.3, period_end="2015-06-30", note="why"
    )
    declare(log, spec)
    assert current(log, "tiingo/etf") == spec


# ------------------------------------------------- nothing from it is reportable


def _context(panel, log=None):
    from qr.execution.costs import CostModel
    from qr.research.runner import run_backtest
    from qr.strategies.library import TSMOM
    from qr.validate.gates import GateContext

    strategy = TSMOM(lookback=30)
    return GateContext(
        hypothesis_id="tsmom_v1",
        panel=panel,
        strategy=strategy,
        costs=CostModel.trial(),
        result=run_backtest(panel, strategy, CostModel.trial()),
        trial_log=log,
    )


def test_gate_zero_fails_a_discovery_panel_even_with_a_preregistration(panel, log):
    from qr.validate.gates import gate_0_preregistration

    log.prereg("tsmom_v1", "a perfectly good pre-registration")
    spec = SandboxSpec(market="binance/spot")
    result = gate_0_preregistration(_context(restrict(panel, spec, "discovery"), log))

    assert result.verdict == "FAIL"
    assert "sandbox" in result.detail
    # The validation side of the same panel, same pre-registration, passes.
    assert gate_0_preregistration(_context(restrict(panel, spec, "validation"), log)).verdict != "FAIL"


def test_a_report_refuses_to_be_written_from_the_sandbox(tmp_path, panel, log):
    from qr.validate.gates import run_gates
    from qr.validate.report import write_report

    log.prereg("tsmom_v1", "a perfectly good pre-registration")
    discovery = restrict(panel, SandboxSpec(market="binance/spot"), "discovery")
    report = run_gates(_context(discovery, log), upto=2, stop_on_fail=False)

    assert report.context["sandbox_side"] == "discovery"
    with pytest.raises(ValueError, match="not reportable"):
        write_report(report, tmp_path / "reports", log)


def test_an_ordinary_run_is_untouched_by_any_of_this(tmp_path, panel, log):
    """The sandbox must cost nothing to anyone not using it."""
    from qr.validate.gates import run_gates
    from qr.validate.report import write_report

    log.prereg("tsmom_v1", "a perfectly good pre-registration")
    report = run_gates(_context(panel, log), upto=2, stop_on_fail=False)
    assert report.context["sandbox_side"] is None
    md, js = write_report(report, tmp_path / "reports", log)
    assert md.exists() and js.exists()
