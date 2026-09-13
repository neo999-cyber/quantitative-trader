"""Step 0: the same families priced against several account sizes.

The sweep exists to answer one question -- is the account the binding
constraint, or are the ideas bad? -- and the ways it could quietly answer the
wrong question are what these tests pin down: selecting a variant, opening a
holdout, or inflating the trial count so a future family pays for a
diagnostic.
"""
import pandas as pd
import pytest

from qr.cli import build_parser, main
from qr.config import paths
from qr.execution.costs import CostModel
from qr.research.families import ETF_FAMILIES, run_family
from qr.validate.selftest import edge_world
from qr.validate.trial_log import TrialLog


@pytest.fixture()
def env(tmp_path, mirror):
    return ["--root", str(tmp_path / "lake"), "--mirror", str(mirror.root)]


def run(env, *args):
    return main(env + list(args))


# ------------------------------------------------------- the premise itself


def keeps(equity, charge_impact):
    panel = edge_world(n_symbols=4, years=2, seed=1)
    run = run_family(ETF_FAMILIES[0], panel, CostModel.trial(), equity=equity,
                     upto=2, stop_on_fail=False, permutations=0,
                     charge_impact=charge_impact)
    return run.sweep.results[run.best_variant].stats()["net_over_gross"]


def test_without_impact_a_basis_point_venue_is_scale_free():
    """The finding that shaped this command, asserted so it cannot drift back.

    Binance charges basis points with no per-order floor, so fee and spread
    are a fixed *fraction* of whatever is traded -- the account cancels out.
    Every family in the trial so far ran this way, which means an account
    sweep over them would have compared a constant with itself and reported
    "crypto does not care about account size" for a purely mechanical reason.
    """
    assert keeps(1_000, charge_impact=False) == keeps(1_000_000, charge_impact=False)


def test_with_impact_a_hundredfold_account_costs_more():
    """Square-root impact is the only channel by which account size reaches
    such a venue, which is why the sweep turns it on."""
    small, large = keeps(1_000, charge_impact=True), keeps(1_000_000, charge_impact=True)
    assert large < small, "impact did not scale with order size"


# ------------------------------------------------------------ the guardrails


def test_the_sweep_never_opens_a_holdout(env):
    """A diagnostic that burns the holdout would cost more than it tells us,
    and the holdout cannot be un-opened."""
    parsed = build_parser().parse_args(["accounts"])
    assert parsed.holdout_start is None and parsed.holdout_end is None


def test_the_sweep_stops_at_gate_2(env):
    """Gates 3 and up ask questions that do not depend on the account: a
    permutation test says the same thing at $1,000 and at $100,000. Running
    them would cost hours and buy nothing."""
    assert build_parser().parse_args(["accounts"]).upto == 2


def test_the_sweep_does_not_inflate_the_trial_count(env, tmp_path, capsys):
    """Gate 4 deflates by the trial count, so a diagnostic that counted as a
    search would make every future family pay for this one measurement."""
    assert run(env, "data", "ingest") == 0
    capsys.readouterr()
    log = TrialLog(paths(tmp_path / "lake").trial_log)
    before = log.trial_count()

    assert run(env, "accounts", "--equities", "1000", "10000",
               "--n", "3", "--min-history", "60") == 0
    capsys.readouterr()
    assert log.trial_count() == before


def test_the_sweep_leaves_a_note_saying_what_it_evaluated(env, tmp_path, capsys):
    """It is still a measurement someone made. Not counting it as a trial is
    not the same as pretending it never happened."""
    assert run(env, "data", "ingest") == 0
    capsys.readouterr()
    assert run(env, "accounts", "--equities", "1000", "10000",
               "--n", "3", "--min-history", "60") == 0
    capsys.readouterr()

    notes = TrialLog(paths(tmp_path / "lake").trial_log).records(kind="note")
    assert notes, "the sweep recorded nothing"
    payload = notes[-1].payload
    assert payload["equities"] == [1000.0, 10000.0]
    assert "no variant selected" in payload["text"]


# ---------------------------------------------------------------- the output


def test_the_sweep_reports_every_family_at_every_size(env, capsys):
    assert run(env, "data", "ingest") == 0
    capsys.readouterr()
    assert run(env, "accounts", "--equities", "1000", "100000",
               "--n", "3", "--min-history", "60") == 0
    out = capsys.readouterr().out
    assert "$1,000" in out and "$100,000" in out
    assert "What moved" in out
    assert "not verdicts" in out


def test_the_change_column_is_the_point_of_the_table():
    """Two blocks the reader has to diff by eye is not an answer."""
    from qr.cli import _account_deltas

    frame = pd.DataFrame(
        [
            {"equity": 1_000.0, "hypothesis": "h", "net/gross": 0.13, "gate2": "FAIL"},
            {"equity": 100_000.0, "hypothesis": "h", "net/gross": 0.91, "gate2": "PASS"},
        ]
    )
    row = _account_deltas(frame, [1_000.0, 100_000.0]).iloc[0]
    assert row["change"] == pytest.approx(0.78)
    assert row["gate 2"] == "FAIL -> PASS"
