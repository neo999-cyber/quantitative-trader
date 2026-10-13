"""The surface recorder (`scripts/record_surface.py`): compaction and file layout on fixtures, no network."""
import gzip
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("record_surface", Path(__file__).resolve().parents[2] / "scripts" / "record_surface.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


def test_deribit_rows_keep_the_study_fields_only():
    payload = {"result": [{"instrument_name": "BTC-30OCT26-90000-C", "mark_iv": 55.1, "open_interest": 1200.5, "volume": 3.0, "volume_usd": 100.0,
                           "bid_price": 0.01, "ask_price": 0.012, "mark_price": 0.011, "underlying_price": 85000.0, "underlying_index": "BTC-30OCT26",
                           "interest_rate": 0.0, "creation_timestamp": 1791865141378, "high": 0.02, "low": 0.01, "price_change": -3.1}]}
    rows = rs.compact_deribit(payload)
    assert len(rows) == 1 and rows[0]["instrument_name"] == "BTC-30OCT26-90000-C" and rows[0]["open_interest"] == 1200.5
    assert "high" not in rows[0] and "price_change" not in rows[0]


def test_hyperliquid_contexts_are_joined_to_their_asset_names():
    payload = [{"universe": [{"name": "BTC"}, {"name": "ETH"}]}, [{"funding": "0.0000125", "openInterest": "37459.7"}, {"funding": "0.0000092", "openInterest": "1106988.2"}]]
    rows = rs.compact_hyperliquid(payload)
    assert [r["name"] for r in rows] == ["BTC", "ETH"] and rows[1]["openInterest"] == "1106988.2"
    with pytest.raises(ValueError):
        rs.compact_hyperliquid({"universe": []})


def test_snapshot_lands_in_the_hourly_file(tmp_path):
    from datetime import datetime, timezone

    at = datetime(2026, 10, 13, 8, 20, tzinfo=timezone.utc).timestamp()
    p = rs.write_snapshot(tmp_path, "deribit", {"BTC": [{"instrument_name": "x"}]}, at=at)
    assert p == tmp_path / "deribit" / "2026-10-13" / "08.json.gz"
    with gzip.open(p, "rt") as fh:
        d = json.load(fh)
    assert d["venue"] == "deribit" and d["recorded_at"] == at and d["body"]["BTC"][0]["instrument_name"] == "x"


def test_main_skips_a_failing_venue_and_records_the_other(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "snapshot_deribit", lambda: (_ for _ in ()).throw(OSError("down")))
    monkeypatch.setattr(rs, "snapshot_hyperliquid", lambda: [{"name": "BTC", "funding": "0.0"}])
    assert rs.main(["--out", str(tmp_path)]) == 1
    assert not (tmp_path / "deribit").exists() and len(list((tmp_path / "hyperliquid").glob("*/*.json.gz"))) == 1


def test_get_retries_a_503_then_succeeds(monkeypatch):
    import urllib.error

    calls = {"n": 0}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"result": []}'

    def fake_urlopen(req, timeout=60):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)
        return _Resp()

    monkeypatch.setattr(rs.urllib.request, "urlopen", fake_urlopen)
    slept = []
    assert rs._get("https://example.invalid/x", sleep=slept.append) == b'{"result": []}'
    assert calls["n"] == 3 and slept == [15.0, 30.0]
    calls["n"] = 0
    with pytest.raises(urllib.error.HTTPError):
        rs._get("https://example.invalid/x", retries=2, sleep=slept.append)
