"""The counts-only stages of `scripts/p3a_dryrun_counts.py`: the stream pass and the daily-ladder (v3) coverage."""
from __future__ import annotations

import gzip
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("dryrun", Path(__file__).resolve().parents[2] / "scripts" / "p3a_dryrun_counts.py")
dryrun = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dryrun)


def _ts(s: str) -> float:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()


def _write(rec: Path, venue: str, lines: list[tuple[float, dict]]) -> None:
    for t, msg in lines:
        d = datetime.fromtimestamp(t, tz=timezone.utc)
        f = rec / venue / d.strftime("%Y-%m-%d") / f"{d:%H}.jsonl.gz"
        f.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(f, "at", encoding="utf-8") as fh:
            fh.write(json.dumps({"venue": venue, "recorded_at": t, "raw": json.dumps(msg)}) + "\n")


def _trade(tok: str) -> dict:
    return {"market": "0x", "asset_id": tok, "price": "0.5", "size": "1", "side": "BUY", "timestamp": "0", "event_type": "last_trade_price"}


def _quote(tok: str) -> dict:
    return {"market": "0x", "price_changes": [{"asset_id": tok, "price": "0.5", "size": "1", "side": "BUY", "best_bid": "0.5", "best_ask": "0.52"}],
            "timestamp": "0", "event_type": "price_change"}


def test_stream_counts_skips_day_folders_outside_the_window_and_counts_prints_per_token(tmp_path):
    rec = tmp_path
    _write(rec, "polymarket", [(_ts("2026-10-12T23:00"), _trade("222"))])                       # the day before the window: folder not opened
    _write(rec, "polymarket", [(_ts("2026-10-13T05:00"), _quote("111")), (_ts("2026-10-13T06:00"), _trade("111")), (_ts("2026-10-13T07:00"), _trade("111"))])
    _write(rec, "deribit", [(_ts("2026-10-13T05:00"), {"jsonrpc": "2.0", "method": "subscription", "params": {"channel": "deribit_price_index.btc_usd", "data": {}}})])
    out = dryrun.stream_counts(rec, _ts("2026-10-13T00:00"), _ts("2026-10-14T00:00"))
    assert out["files"]["polymarket"]["n"] == 3 and out["files"]["polymarket"]["days"] == ["2026-10-13"]
    assert out["messages"]["polymarket"]["by_type"] == {"price_change": 1, "last_trade_price": 2}
    assert out["token_ids"]["trade_prints_by_token"] == {"111": 2} and out["token_ids"]["with_any_quote"] == ["111"]
    assert out["tokens"]["with_trade_print"] == 1 and out["messages"]["deribit"]["total"] == 1


def _catalogue(rec: Path, markets: list[dict]) -> None:
    (rec / "polymarket").mkdir(parents=True, exist_ok=True)
    (rec / "polymarket" / "catalogue.jsonl").write_text(json.dumps({"at": _ts("2026-10-13T04:53"), "min_horizon_days": 1, "markets": markets}) + "\n")


def _m(mid, q, end, start, tok):
    return {"market_id": mid, "question": q, "end": end, "start": start, "yes_token": tok, "no_token": tok + "n"}


@pytest.fixture
def daily_fixture(tmp_path):
    rec = tmp_path / "rec"
    _catalogue(rec, [
        _m("b20", "Will the price of Bitcoin be above $110,000 on October 20?", "2026-10-20T16:00:00Z", "2026-10-13T16:00:15Z", "111"),   # 5 prints
        _m("e20", "Will the price of Ethereum be above $4,000 on October 20?", "2026-10-20T16:00:00Z", "2026-10-13T16:00:15Z", "222"),    # quoted, no print
        _m("s29", "Will the price of Solana be above $200 on October 29?", "2026-10-29T16:00:00Z", "2026-10-22T16:00:15Z", "333"),        # nothing yet
        _m("m", "Will Bitcoin reach $150,000 in October?", "2026-11-01T04:00:00Z", "2026-10-01T05:00:00Z", "777"),                       # monthly: not v3's
        {"market_id": "nostart", "question": "Will the price of Bitcoin be above $100,000 on October 21?", "end": "2026-10-21T16:00:00Z", "yes_token": "444", "no_token": "444n"},
        _m("long", "Will the price of Bitcoin be above $100,000 on October 22?", "2026-10-22T16:00:00Z", "2026-10-13T06:00:00Z", "555"),   # 9.4 days: over the life cap
    ])
    counts = {"token_ids": {"with_any_quote": ["111", "222", "777", "555"], "with_trade_print": ["111", "777", "555"],
                            "trade_prints_by_token": {"111": 5, "777": 9, "555": 3}}}
    return rec, counts


def test_daily_ladder_coverage_selects_like_the_engine_and_clusters_by_settlement_date(daily_fixture):
    rec, counts = daily_fixture
    cov = dryrun.daily_ladder_coverage(rec, counts, "2026-10-25T06:00:00+00:00")
    assert cov["markets"]["n"] == 3 and cov["markets"]["by_asset"] == {"BTC": 1, "ETH": 1, "SOL": 1}
    assert cov["markets"]["with_any_quote"] == 2 and cov["markets"]["with_trade_print"] == 1 and cov["markets"]["trade_prints_total"] == 5
    assert cov["markets"]["life_days"]["median"] == 7.0
    assert cov["clusters"]["all"] == {"clusters": 3, "with_any_quote": 2, "with_trade_print": 1, "by_asset_with_trade_print": {"BTC": 1}}
    assert cov["clusters"]["settled_by_until"]["clusters"] == 2 and cov["clusters"]["settled_by_until"]["with_trade_print"] == 1
    assert cov["clusters"]["settling_in_v3_window"]["clusters"] == 3            # 29 October settles before the window's end
    assert cov["clusters"]["memo_minimum_with_a_fill"] == 30
    assert cov["by_settlement_date"]["2026-10-20"]["BTC"] == {"markets": 1, "with_trade_print": 1, "prints": 5}
    assert cov["by_settlement_date"]["2026-10-20"]["ETH"]["prints"] == 0 and "2026-11-01" not in cov["by_settlement_date"]
    assert cov["days_recorded"] == pytest.approx(12.0, abs=0.1)


def test_daily_ladder_coverage_without_per_token_counts_falls_back_to_membership(daily_fixture):
    rec, counts = daily_fixture
    del counts["token_ids"]["trade_prints_by_token"]
    cov = dryrun.daily_ladder_coverage(rec, counts, "2026-10-25T06:00:00+00:00")
    assert cov["markets"]["with_trade_print"] == 1 and cov["markets"]["trade_prints_total"] == 1


def test_surface_presence_counts_the_missing_hours(tmp_path):
    for h in ("03", "04", "06"):
        f = tmp_path / "deribit" / "2026-10-24" / f"{h}.json.gz"
        f.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(f, "wt") as fh:
            fh.write("{}")
    (tmp_path / "deribit" / "2026-10-24" / "junk.txt").write_text("x")
    out = dryrun.surface_presence(tmp_path, "2026-10-24T06:30:00+00:00")
    assert set(out) == {"deribit"}
    assert out["deribit"]["files"] == 3 and out["deribit"]["expected_hours_to_until"] == 4
    assert out["deribit"]["missing_hours"] == 1 and out["deribit"]["missing"] == ["2026-10-24T05"]
    assert dryrun.surface_presence(tmp_path / "nowhere", "2026-10-24T06:30:00+00:00") == {}


def test_daily_stage_from_the_command_line_writes_the_combined_json(daily_fixture, tmp_path, capsys):
    rec, counts = daily_fixture
    (tmp_path / "counts.json").write_text(json.dumps({"files": {}, **counts}))
    out = tmp_path / "daily.json"
    assert dryrun.main(["--daily", "--rec", str(rec), "--counts", str(tmp_path / "counts.json"), "--surface", str(tmp_path / "surface"),
                        "--until", "2026-10-25T06:00:00+00:00", "--out", str(out)]) == 0
    written = json.loads(out.read_text())
    assert "token_ids" not in written and written["daily"]["clusters"]["all"]["clusters"] == 3 and written["daily"]["surface"] == {}
    assert '"memo_minimum_with_a_fill": 30' in capsys.readouterr().out
