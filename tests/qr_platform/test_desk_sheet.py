"""The desk sheet (`scripts/desk_sheet.py`): structural counts and the ladder from fixtures; no network."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("desk_sheet", Path(__file__).resolve().parents[2] / "scripts" / "desk_sheet.py")
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)


def _cat_line(at, markets):
    return json.dumps({"at": at, "min_horizon_days": 1, "markets": markets}) + "\n"


def test_recording_progress_counts_daily_ladders_and_settled_clusters(tmp_path):
    cat = tmp_path / "catalogue.jsonl"
    daily = lambda tok, asset, day: {"yes_token": tok, "question": f"Will the price of {asset} be above $1 on October {day}?", "start": f"2026-10-{day-7:02d}T16:00:15Z", "end": f"2026-10-{day:02d}T16:00:00Z"}
    monthly = {"yes_token": "m1", "question": "Will Bitcoin reach $150,000 in October?", "start": "2026-10-01T05:00:00Z", "end": "2026-11-01T04:00:00Z"}
    before = _cat_line(ds.V3_START.timestamp() - 3600, [monthly])                                     # before the switch: ignored
    after = _cat_line(ds.V3_START.timestamp() + 3600, [monthly, daily("a", "Bitcoin", 14), daily("b", "Ethereum", 14), daily("c", "Bitcoin", 20)])
    later = _cat_line(ds.V3_START.timestamp() + 7200, [monthly, daily("a", "Bitcoin", 14), daily("d", "Solana", 20)])
    cat.write_text(before + after + later)
    p = ds.recording_progress(cat, now=datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
    assert p["catalogue_lines_since_switch"] == 2 and p["latest_markets"] == 3 and p["latest_daily_markets"] == 2
    assert p["daily_markets_seen"] == 4 and p["clusters_total"] == 4            # (BTC,14) (ETH,14) (BTC,20) (SOL,20)
    assert p["clusters_settled"] == 2                                            # the 14 October ladders settled at 16:00 UTC that day
    assert ds.recording_progress(tmp_path / "missing.jsonl")["clusters_total"] == 0


def test_ladder_reads_the_latest_snapshot_by_tvl(tmp_path):
    y = tmp_path / "yields"
    y.mkdir()
    rec = {"recorded_at": "2026-10-15T06:10:10+00:00", "dtb3": 3.95, "pools": [
        {"project": "maple", "chain": "Ethereum", "symbol": "USDC", "tvlUsd": 2.8e9, "apy": 5.29, "apyMean30d": 5.15, "stablecoin": True},
        {"project": "aave-v3", "chain": "Ethereum", "symbol": "USDT", "tvlUsd": 3.2e8, "apy": 3.37, "apyMean30d": 3.86, "stablecoin": True},
        {"project": "lido", "chain": "Ethereum", "symbol": "STETH", "tvlUsd": 9e9, "apy": 2.9, "apyMean30d": 2.9, "stablecoin": False}]}
    (y / "2026-10-14.jsonl").write_text(json.dumps({"recorded_at": "old", "pools": []}) + "\n")
    (y / "2026-10-15.jsonl").write_text(json.dumps(rec) + "\n")
    l = ds.ladder(tmp_path)
    assert [x["name"] for x in l["pools"]] == ["maple USDC (Ethereum)", "aave-v3 USDT (Ethereum)"] and l["dtb3"] == 3.95
    page = ds.render({"last_line": "ok", "wrong": False, "pm_mb_yesterday": "120", "reconnects_24h": 1, "surface_files_yesterday": 24, "disk_free": "24G"},
                     ds.recording_progress(tmp_path / "none.jsonl"), {"ibit_today": True, "etha_today": False, "table_rows": 3, "equities_flows_age_h": 2.0, "yield_today": True, "latest_yield_file": "x"},
                     l, {"BTCUSDT": {"rate_8h": 0.0001, "annualised_pct": 10.95}}, datetime(2026, 10, 15, 6, 40, tzinfo=timezone.utc))
    assert "# Desk sheet — 2026-10-15 06:40 UTC" in page and "maple USDC" in page and "10.95%/yr" in page and "ETHA **no**" in page


def test_ladder_reads_a_tbill_record_with_its_source(tmp_path):
    y = tmp_path / "yields"
    y.mkdir()
    (y / "2026-10-15.jsonl").write_text(json.dumps({"recorded_at": "x", "pools": [], "tbill": {"date": "2026-10-14", "dtb3": 4.10, "source": "treasury_13w_bank_discount"}}) + "\n")
    l = ds.ladder(tmp_path)
    assert l["dtb3"] == 4.10 and l["dtb3_date"] == "2026-10-14 treasury_13w_bank_discount"


def test_funding_trailing_annualises_the_days_held_and_renders_against_the_bill(tmp_path):
    now = datetime(2026, 10, 28, 6, 40, tzinfo=timezone.utc)
    eight_h = 8 * 3600 * 1000

    def fetch(symbol, start_ms):                                              # 400 days of 8-hourly settlements at 0.0001, newest first is fine
        n = 400 * 3 if symbol == "BTCUSDT" else 30                            # ETH: a listing only ten days old
        return [{"fundingTime": int(now.timestamp() * 1000) - (k + 1) * eight_h, "fundingRate": "0.00010000"} for k in range(n)]

    t = ds.funding_trailing(now=now, fetch=fetch)
    btc = t["BTCUSDT"]
    assert set(btc) == {30, 90, 365} and all(btc[w]["n"] == 3 * w for w in btc)
    assert all(btc[w]["gross_pct"] == 10.95 for w in btc)                     # 0.0001 × 3 × 365
    assert btc[365]["on_capital_1x_pct"] == round((10.95 - 0.214) / 2, 2)      # one round trip a year, half the capital earns nothing
    eth = t["ETHUSDT"]
    assert eth[365]["days"] == 10.0 and eth[365]["gross_pct"] == 10.95 and eth[30]["days"] == 10.0
    assert ds.funding_trailing(symbols=("X",), now=now, fetch=lambda s, m: 1 / 0)["X"] == {"error": "ZeroDivisionError"}
    y = tmp_path / "yields"
    y.mkdir()
    (y / "2026-10-28.jsonl").write_text(json.dumps({"recorded_at": "x", "pools": [], "dtb3": 3.6}) + "\n")
    page = ds.render({"last_line": "ok", "wrong": False, "pm_mb_yesterday": "1", "reconnects_24h": 0, "surface_files_yesterday": 24, "disk_free": "1G"},
                     ds.recording_progress(tmp_path / "none.jsonl"), {"ibit_today": True, "etha_today": True, "table_rows": 0, "equities_flows_age_h": 1.0, "yield_today": True, "latest_yield_file": "x"},
                     ds.ladder(tmp_path), {}, now, {"BTCUSDT": {365: {"days": 365.0, "n": 1095, "gross_pct": 3.4, "on_capital_1x_pct": 1.6}}, "ETHUSDT": {"error": "URLError"}})
    assert "BTCUSDT funding realised, annualised (gross / at 1× on the capital it ties up): 365 d 3.4% / 1.6%" in page
    assert "against the bill (3.6%), last 365 days, in points: BTC −2.0" in page and "ETHUSDT funding realised: URLError" in page
