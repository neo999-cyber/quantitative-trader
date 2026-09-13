import json

import pytest

from qr.cli import main
from qr.config import paths
from qr.validate.trial_log import TrialLog


@pytest.fixture()
def env(tmp_path, mirror):
    """A lake root plus a populated bucket mirror, as CLI arguments."""
    return ["--root", str(tmp_path / "lake"), "--mirror", str(mirror.root)]


def run(env, *args):
    return main(env + list(args))


def test_doctor_reports_paths_and_versions(env, capsys):
    assert run(env, "doctor") == 0
    out = capsys.readouterr().out
    assert "lake root" in out and "manifest hash" in out and "pandas" in out


def test_ingest_then_qa_then_universe(env, capsys):
    assert run(env, "data", "ingest") == 0
    ingest_out = capsys.readouterr().out
    assert "BTCUSDT" in ingest_out and "manifest hash:" in ingest_out

    assert run(env, "data", "qa") == 0
    assert "Data QA" in capsys.readouterr().out

    assert run(env, "data", "universe", "--n", "3", "--min-history", "60") == 0
    universe_out = capsys.readouterr().out
    assert "as of" in universe_out and "BTCUSDT" in universe_out


def test_ingest_is_idempotent(env, capsys):
    run(env, "data", "ingest")
    first = capsys.readouterr().out
    run(env, "data", "ingest")
    second = capsys.readouterr().out
    assert first.split("manifest hash:")[1] == second.split("manifest hash:")[1]


def test_qa_fails_loudly_on_a_broken_symbol(env, tmp_path, capsys):
    run(env, "data", "ingest")
    capsys.readouterr()
    from qr.data.lake import Lake

    lake = Lake(paths(tmp_path / "lake"))
    broken = lake.read_klines("BTCUSDT")
    broken.iloc[5, broken.columns.get_loc("high")] = 0.01
    lake.write_klines("BTCUSDT", broken)

    assert run(env, "data", "qa", "--symbols", "BTCUSDT") == 1
    assert "FAIL" in capsys.readouterr().err


def test_backtest_runs_and_can_record_a_trial(env, tmp_path, capsys):
    run(env, "data", "ingest")
    capsys.readouterr()
    assert (
        run(
            env,
            "backtest",
            "--family", "tsmom",
            "--param", "lookback=30",
            "--n", "3",
            "--min-history", "60",
            "--crosscheck",
            "--leakage",
            "--log",
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "sharpe" in out
    assert "second engine agrees: True" in out
    assert "leakage probe" in out

    log = TrialLog(paths(tmp_path / "lake").trial_log)
    assert log.verify() == 1
    record = log.records(kind="run")[0]
    assert record.payload["family"] == "tsmom"
    assert record.payload["params"]["lookback"] == 30
    assert len(record.payload["manifest_hash"]) == 64


def test_trial_verify_and_show(env, tmp_path, capsys):
    log = TrialLog(paths(tmp_path / "lake").ensure().trial_log)
    log.prereg("h1", "mechanism: trends persist")
    log.run("h1", "tsmom", {"lookback": 90}, "u", {"sharpe": 1.1}, variants=12)

    assert run(env, "trial", "verify") == 0
    assert "12 trials counted" in capsys.readouterr().out

    assert run(env, "trial", "show") == 0
    assert "tsmom" in capsys.readouterr().out


def test_trial_verify_detects_tampering(env, tmp_path, capsys):
    path = paths(tmp_path / "lake").ensure().trial_log
    log = TrialLog(path)
    log.run("h1", "tsmom", {"lookback": 90}, "u", {"sharpe": 0.1})
    lines = path.read_text().splitlines()
    doctored = json.loads(lines[0])
    doctored["payload"]["metrics"]["sharpe"] = 3.0
    path.write_text(json.dumps(doctored, sort_keys=True, separators=(",", ":")) + "\n")

    assert run(env, "trial", "verify") == 2
    assert "CORRUPT" in capsys.readouterr().err


def test_fng_show_reads_a_cached_file(env, tmp_path, capsys):
    reference = paths(tmp_path / "lake").ensure().reference
    (reference / "fear_greed.json").write_bytes(
        json.dumps({"data": [{"value": "55", "value_classification": "Greed", "timestamp": "1735689600"}]}).encode()
    )
    assert run(env, "fng", "show") == 0
    assert "55" in capsys.readouterr().out


def test_backtest_params_accept_json_values(env, capsys):
    run(env, "data", "ingest")
    capsys.readouterr()
    assert run(env, "backtest", "--family", "tsmom", "--param", "vol_target=null", "--n", "3", "--min-history", "60") == 0
    assert "ann_vol" in capsys.readouterr().out


def test_backtest_defaults_to_the_verified_trial_cost_model():
    from qr.cli import _costs, build_parser

    described = _costs(build_parser().parse_args(["backtest"])).describe()
    assert described["linear_bps_per_side"] == 9.5
    assert described["fees_verified_on"] == "2026-09-11"


def test_no_bnb_falls_back_to_the_unverified_schedule():
    from qr.cli import _costs, build_parser

    described = _costs(build_parser().parse_args(["backtest", "--no-bnb"])).describe()
    assert described["linear_bps_per_side"] == 12.0
    assert described["fees_verified_on"] == "unverified"


def test_prereg_then_gates_then_report(env, tmp_path, capsys):
    """The whole workflow: register the prediction, run it, get a report."""
    run(env, "data", "ingest")
    capsys.readouterr()

    assert run(env, "trial", "prereg", "tsmom_v1", "--text", "trends persist; long-only; top 3") == 0
    assert "registered" in capsys.readouterr().out

    run(env, "gates", "--family", "tsmom", "--grid", "lookback=[20,40]", "--n", "3",
        "--min-history", "60", "--permutations", "5", "--all-gates", "--hypothesis", "tsmom_v1")
    out = capsys.readouterr().out
    assert "pre-registration | PASS" in out.replace("| pre-registration | PASS", "pre-registration | PASS")
    assert "wrote" in out

    report = tmp_path / "lake" / "reports" / "tsmom_v1.md"
    assert report.exists()
    assert "# Hypothesis Report" in report.read_text()

    log = TrialLog(paths(tmp_path / "lake").trial_log)
    assert log.verify() > 0
    assert log.trial_count("tsmom_v1") == 2


def test_gates_without_a_preregistration_fails_at_gate_zero(env, tmp_path, capsys):
    run(env, "data", "ingest")
    capsys.readouterr()
    code = run(env, "gates", "--family", "tsmom", "--grid", "lookback=[20,40]", "--n", "3",
               "--min-history", "60", "--permutations", "5", "--hypothesis", "unregistered")
    out = capsys.readouterr().out
    assert code == 1
    assert "exploratory, not a test" in out


def test_registering_after_the_fact_warns_loudly(env, tmp_path, capsys):
    log = TrialLog(paths(tmp_path / "lake").ensure().trial_log)
    log.run("late", "tsmom", {"lookback": 30}, "u")
    assert run(env, "trial", "prereg", "late", "--text", "a prediction made after the fact") == 0
    assert "does not make this a test" in capsys.readouterr().err


def test_an_empty_preregistration_is_refused(env, capsys):
    assert run(env, "trial", "prereg", "h", "--text", "   ") == 2
    assert "needs a mechanism" in capsys.readouterr().err


def test_a_note_justifies_a_warning(env, tmp_path, capsys):
    assert run(env, "trial", "note", "h", "gate 3: short sample by design") == 0
    log = TrialLog(paths(tmp_path / "lake").trial_log)
    assert "gate 3" in log.records(kind="note")[0].payload["text"]


def test_selftest_runs_from_the_cli_and_passes(env, capsys):
    assert run(env, "selftest", "--variants", "40", "--permutations", "10") == 0
    assert "self-test OK" in capsys.readouterr().out


def test_the_trial_log_records_the_cost_model_that_was_used(env, tmp_path, capsys):
    run(env, "data", "ingest")
    capsys.readouterr()
    run(env, "backtest", "--family", "tsmom", "--param", "lookback=30", "--n", "3", "--min-history", "60", "--log")
    capsys.readouterr()

    record = TrialLog(paths(tmp_path / "lake").trial_log).records(kind="run")[0]
    assert record.payload["costs"]["fees_verified_on"] == "2026-09-11"
    assert record.payload["costs"]["linear_bps_per_side"] == 9.5


class TestDataPull:
    """`qr data pull` against a LocalBucket standing in for the live one.

    Worth testing offline: the pull is the one command that cannot be tried in
    the sandbox, and it is also the one that costs an hour of someone's evening
    when it is wrong.
    """

    @pytest.fixture()
    def offline(self, monkeypatch, mirror):
        """Make `qr data pull` read the fixture mirror instead of the internet."""
        import qr.cli as cli

        monkeypatch.setattr(cli, "HttpBucket", lambda **kwargs: mirror)
        return mirror

    def pull(self, env, offline, tmp_path, *args):
        target = ["--mirror", str(tmp_path / "pulled")]
        return main(env[:2] + target + ["data", "pull", *args])

    def test_a_dry_run_counts_without_fetching(self, env, offline, tmp_path, capsys):
        assert self.pull(env, offline, tmp_path, "--dry-run") == 0
        out = capsys.readouterr()
        assert "dry run: would fetch" in out.out
        assert not (tmp_path / "pulled").exists()

    def test_the_quote_filter_keeps_only_matching_pairs(self, env, offline, tmp_path, capsys):
        self.pull(env, offline, tmp_path, "--dry-run", "--quote", "NOPE")
        assert "no symbols matched" in capsys.readouterr().err

        self.pull(env, offline, tmp_path, "--dry-run", "--quote", "USDT")
        assert "0 files" not in capsys.readouterr().err

    def test_checksums_can_be_skipped_and_halve_the_request_count(self, env, offline, tmp_path, capsys):
        self.pull(env, offline, tmp_path, "--dry-run")
        with_sums = int(capsys.readouterr().err.split(" files")[0].split("\n")[-1].replace(",", ""))
        self.pull(env, offline, tmp_path, "--dry-run", "--no-checksums")
        without = int(capsys.readouterr().err.split(" files")[0].split("\n")[-1].replace(",", ""))
        assert without * 2 == with_sums

    def test_a_pull_writes_the_bucket_layout_and_is_resumable(self, env, offline, tmp_path, capsys):
        assert self.pull(env, offline, tmp_path, "--workers", "4") == 0
        first = capsys.readouterr().out
        assert "pulled" in first and "0 failed" in first

        written = list((tmp_path / "pulled").rglob("*.zip"))
        assert written
        assert "data/spot/monthly/klines" in str(written[0])

        # Re-running skips everything already present rather than refetching.
        assert self.pull(env, offline, tmp_path, "--workers", "4") == 0
        assert "pulled 0 files" in capsys.readouterr().out

    def test_a_pulled_mirror_ingests(self, env, offline, tmp_path, capsys):
        self.pull(env, offline, tmp_path, "--workers", "4")
        capsys.readouterr()
        code = main(env[:2] + ["--mirror", str(tmp_path / "pulled"), "data", "ingest"])
        assert code == 0
        assert "manifest hash:" in capsys.readouterr().out

    def test_limit_is_documented_as_alphabetical(self):
        """It is not a volume ranking, and the help must not imply otherwise."""
        from qr.cli import build_parser

        action = next(
            a for a in build_parser()._subparsers._actions if getattr(a, "dest", "") == "command"
        )
        help_text = action.choices["data"]._subparsers._actions[1].choices["pull"].format_help()
        assert "ALPHABETICAL" in help_text


def test_a_wrapped_connection_failure_reports_the_cause_not_the_wrapper():
    """`requests` buries the reason four exceptions deep.

    The ETF pull printed `HTTPSConnectionPool(...): Max retries exceeded` for all
    twelve tickers, which is the same string whether the name did not resolve,
    the handshake was refused, or a proxy dropped it. The pull table truncated it
    at sixty characters, so even the wrapper's own tail was lost.
    """
    from qr.cli import _root_cause

    try:
        try:
            try:
                raise OSError(-2, "Name or service not known")
            except OSError as inner:
                raise ConnectionError("failed to establish a new connection") from inner
        except ConnectionError as middle:
            raise RuntimeError("Max retries exceeded with url: /tiingo/daily") from middle
    except RuntimeError as outer:
        cause = _root_cause(outer)

    assert "Name or service not known" in cause
    assert "Max retries" not in cause


def test_root_cause_of_a_bare_exception_is_itself():
    from qr.cli import _root_cause

    assert _root_cause(ValueError("nothing underneath")) == "ValueError: nothing underneath"


def test_account_size_sweeps_without_touching_the_trial_log(env, tmp_path, capsys):
    """Step 0's command: a sensitivity that must not be charged as a search."""
    run(env, "data", "ingest")
    capsys.readouterr()
    log = TrialLog(paths(tmp_path / "lake").ensure().trial_log)
    log.run("reversal_v1", "reversal", {}, "u", {"sharpe": 0.3}, variants=54)
    before = log.trial_count()

    assert (
        run(
            env,
            "account-size",
            "--asset", "crypto",
            "--only", "reversal_v1",
            "--sizes", "1000", "100000",
            "--n", "3",
            "--min-history", "30",
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "not a verdict" in out
    assert "size-independent" in out
    assert "PASS" not in out.split("## Readings")[-1]

    after = TrialLog(paths(tmp_path / "lake").trial_log)
    assert after.trial_count() == before
    assert after.verify() == 1


def test_sandbox_declare_show_and_check(env, tmp_path, capsys):
    assert run(env, "sandbox", "show") == 2
    assert "no sandbox declared" in capsys.readouterr().err

    assert run(env, "sandbox", "declare", "--market", "binance/spot", "--note", "stage 1") == 0
    assert "declared as record" in capsys.readouterr().out

    assert run(env, "sandbox", "declare", "--market", "binance/spot") == 2
    assert "already has a sandbox" in capsys.readouterr().err

    assert run(env, "sandbox", "check", "--market", "binance/spot", "BTCUSDT", "ETHUSDT") == 0
    out = capsys.readouterr().out
    assert "BTCUSDT" in out and ("discovery" in out or "validation" in out)

    assert run(env, "sandbox", "show") == 0
    assert "binance/spot" in capsys.readouterr().out
    assert TrialLog(paths(tmp_path / "lake").trial_log).verify() == 1


def test_policy_declare_then_show(env, tmp_path, capsys):
    assert run(env, "policy", "show") == 2
    assert "no research policy declared" in capsys.readouterr().err

    assert run(env, "policy", "declare", "--note", "the stage 4 budget") == 0
    assert "counting candidates from seq" in capsys.readouterr().out

    assert run(env, "policy", "declare") == 2
    assert "already in force" in capsys.readouterr().err

    assert run(env, "policy", "show") == 0
    out = capsys.readouterr().out
    assert "candidates_remaining" in out and "stopping_rule_reached" in out
    assert TrialLog(paths(tmp_path / "lake").trial_log).verify() == 1


def test_autopilot_refuses_to_start_without_its_pre_commitments(env, capsys):
    assert run(env, "autopilot", "--no-promote") == 2
    assert "no research policy" in capsys.readouterr().err

    run(env, "policy", "declare")
    capsys.readouterr()
    assert run(env, "autopilot", "--no-promote") == 2
    assert "no discovery sandbox" in capsys.readouterr().err


def test_autopilot_runs_a_night_and_records_every_exit(env, tmp_path, capsys, monkeypatch):
    from qr.research import mechanism as mech

    run(env, "data", "ingest")
    run(env, "policy", "declare")
    run(env, "sandbox", "declare", "--market", "binance/spot", "--symbol-fraction", "0.5")
    capsys.readouterr()

    def fake(brief, model=None, **kw):
        killed = "December" in brief
        return mech.MechanismMemo(
            candidate_id="killed_v1" if killed else "month_end_v1",
            title="a stub",
            forced_trader="a fund with a mandate",
            persistence="momentum works" if killed else "the mandate is audited every month",
            other_side="market makers",
            what_breaks_it="continuous rebalancing",
            crude_version=mech.CrudeVersion(
                "calendar_event", {"event": "month_end", "before": 2}, "positive"
            ),
            required_features=("close", "calendar"),
        )

    monkeypatch.setattr(mech, "propose", fake)
    assert (
        run(
            env,
            "autopilot",
            "--no-promote",
            "--brief", "month end rebalancing",
            "--brief", "December tax-loss selling",
            "--n", "3",
            "--min-history", "30",
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "The night" in out
    assert "killed" in out

    log = TrialLog(paths(tmp_path / "lake").trial_log)
    assert log.verify() > 0
    memos = log.records(kind="memo")
    assert {m.hypothesis_id for m in memos} == {"month_end_v1", "killed_v1"}
    assert not log.records(kind="prereg"), "--no-promote must register nothing"


def test_the_seed_briefs_match_the_market_they_are_sent_to():
    """The first live night self-killed three crypto briefs for the same reason.

    Balanced-fund rebalancing, quarter-end window dressing and wash-sale
    tax-loss selling all name payers who trade equities and bonds. Aiming them
    at a Binance spot universe spends a memo to learn something that was
    knowable when the brief list was written.
    """
    from qr.cli import BRIEFS_BY_ASSET

    crypto = " ".join(BRIEFS_BY_ASSET["crypto"]).lower()
    etf = " ".join(BRIEFS_BY_ASSET["etf"]).lower()

    for tradfi in ("balanced fund", "target-date", "wash-sale", "pension"):
        assert tradfi not in crypto, f"{tradfi!r} names a payer that does not trade crypto"
    for native in ("funding", "liquidation", "unlock"):
        assert native in crypto

    assert "balanced funds" in etf
    assert "wash-sale" in etf
    for native in ("perpetual", "token unlock"):
        assert native not in etf

    assert BRIEFS_BY_ASSET["etf-ls"] is BRIEFS_BY_ASSET["etf"]


def test_autopilot_prices_each_asset_at_the_account_its_trial_uses(tmp_path, monkeypatch):
    """The ETF side asked the per-order-floor question in the wrong account.

    `CostModel.etf_trial()` was passed without an account size, so the kill
    test fell through to `run_backtest`'s $10,000 default while the ETF trial
    itself is priced at $1,000 — testing whether an edge survives a floor in an
    account ten times too large to feel it.
    """
    import argparse

    from qr import cli
    from qr.execution.costs import ETF_TRIAL_EQUITY, LONG_SHORT_TRIAL_EQUITY
    from qr.research import autopilot
    from qr.research.policy import ResearchPolicy, declare
    from qr.data.sandbox import SandboxSpec, declare as declare_sandbox

    root = tmp_path / "lake"
    log = TrialLog(paths(root).ensure().trial_log)
    declare(log, ResearchPolicy())
    declare_sandbox(log, SandboxSpec(market="binance/spot"))
    declare_sandbox(log, SandboxSpec(market="tiingo/etf", mode="period", period_end="2018-12-31"))

    panel = pytest.importorskip("qr.validate.selftest").noise_world(n_symbols=6, years=2, seed=1)
    monkeypatch.setattr(cli, "_asset_panel", lambda args, asset: (None, panel, None, "u"))
    monkeypatch.setattr(cli, "_progress", lambda line: None)

    seen = {}
    monkeypatch.setattr(
        "qr.research.autopilot.run_night",
        lambda briefs, log, policy, sandbox, panel, **kw: seen.update(kw) or autopilot.Night(),
    )

    def run_asset(asset):
        seen.clear()
        args = argparse.Namespace(
            root=root, asset=asset, brief=["x"], briefs_file=None, limit=None,
            model="claude-opus-5", equity=None, permutations=5, no_promote=True,
            interval="1d", start=None, end=None, n=30, lookback=90, min_history=60,
            no_restrict_universe=False,
        )
        assert cli.cmd_autopilot(args) == 0
        return seen

    crypto = run_asset("crypto")
    assert crypto["equity"] is None, "a Binance taker pays the same bps at any size"
    assert crypto["costs"].per_share_usd == 0.0

    etf = run_asset("etf")
    assert etf["equity"] == ETF_TRIAL_EQUITY
    assert etf["costs"].min_commission_usd > 0

    long_short = run_asset("etf-ls")
    assert long_short["equity"] == LONG_SHORT_TRIAL_EQUITY
    assert long_short["costs"].borrow_bps_per_year > 0
