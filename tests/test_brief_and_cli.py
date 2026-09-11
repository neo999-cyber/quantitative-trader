import json
from pathlib import Path

from centaur.brief import EveningBrief, candidate_template
from centaur.cli import main
from centaur.config import AccountConfig
from centaur.screens.pattern_matcher import SetupSpec, scan_universe, pooled_stats
from centaur.screens.options_flow import FlowFlag
from conftest import make_ohlcv, inject_setup

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _hits():
    hist = {"HIT": inject_setup(make_ohlcv(400, seed=21, vol=0.004), at=399),
            "QUIET": make_ohlcv(400, seed=22, vol=0.004)}
    return hist, scan_universe(hist, SetupSpec())


def test_brief_markdown_and_save(tmp_path, risk_on):
    hist, hits = _hits()
    flow = [FlowFlag("HIT", "2026-09-18", 100.0, 4000, 1000, 4.0, 8, 2500, 30, "")]
    brief = EveningBrief(date="2026-09-10", regime=risk_on, spec=SetupSpec(), hits=hits,
                         pooled=pooled_stats(hist), flow=flow, universe_size=2, journal_feedback="## Trade journal feedback")
    md = brief.markdown()
    assert "**HIT**" in md and "sentiment_flow: call volume 4.0x" in md and "Trade journal feedback" in md
    md_path, js_path = brief.save(tmp_path)
    data = json.loads(js_path.read_text())
    assert data["hits"][0]["ticker"] == "HIT" and data["regime"]["regime"] == "RISK_ON"
    assert md_path.read_text().startswith("# Evening Brief - 2026-09-10")


def test_candidate_template_is_1_to_3_by_construction(cfg):
    _, hits = _hits()
    c = candidate_template(hits[0], cfg, resistance=[hits[0].close * 1.1, hits[0].close * 0.9], atr_value=2.0)
    assert c.ticker == "HIT" and c.stop < c.entry < c.target
    assert abs(c.reward_risk - cfg.min_reward_risk) < 0.05
    assert all(r > c.entry for r in c.resistance_levels)
    assert c.signals and c.signals[0].source == "pattern_matcher"


def test_cli_gauntlet_examples(capsys):
    rc = main(["--equity", "10000", "gauntlet", str(EXAMPLES / "candidate_aapl.json"),
               "--regime", str(EXAMPLES / "regime_risk_on.json"), "--offline"])
    out = capsys.readouterr().out
    assert rc == 0 and "VERDICT: TAKE" in out and "20 shares" in out

    rc = main(["--equity", "10000", "gauntlet", str(EXAMPLES / "candidate_fails_resistance.json"),
               "--regime", str(EXAMPLES / "regime_risk_on.json"), "--offline"])
    out = capsys.readouterr().out
    assert rc == 2 and "VERDICT: ABORT" in out and "resistance at 158.00" in out

    rc = main(["--equity", "10000", "gauntlet", str(EXAMPLES / "candidate_aapl.json"),
               "--regime", str(EXAMPLES / "regime_risk_off.json"), "--offline", "--json"])
    report = json.loads(capsys.readouterr().out)
    assert rc == 2 and report["verdict"] == "ABORT"
    assert [r["rule"] for r in report["results"] if not r["passed"]] == ["R3"]


def test_cli_size_and_journal(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["--equity", "10000", "size", "--entry", "150", "--stop", "145", "--target", "157"]) == 0
    out = capsys.readouterr().out
    assert "20 shares" in out and "below 1:3" in out

    main(["journal", "open", "AAPL", "--entry", "150", "--stop", "145", "--target", "165", "--shares", "20", "--why", "test"])
    entry_id = capsys.readouterr().out.split()[1].rstrip(":")
    main(["journal", "close", entry_id, "--exit-price", "145", "--reason", "stop", "--lessons", "stop respected"])
    assert "-1.00R" in capsys.readouterr().out
    main(["journal", "stats"])
    assert json.loads(capsys.readouterr().out)["closed_trades"] == 1


def test_cli_evening_synthetic_writes_brief(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["evening", "--synthetic", "--tickers", "AAA", "BBB", "CCC", "--skip-flow", "--years", "3"])
    out = capsys.readouterr().out
    assert rc == 0 and "# Evening Brief" in out
    assert list(Path("briefs").glob("*.md"))
    assert main(["morning"]) == 0
