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
