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


# ------------------------------------------------------------------ the volatility block (11 November 2026)
import math
import statistics
from datetime import date, timedelta

import pytest

NOW = datetime(2026, 11, 11, 6, 40, tzinfo=timezone.utc)
_H = {"last_line": "ok", "wrong": False, "pm_mb_yesterday": "1", "reconnects_24h": 0, "surface_files_yesterday": 24, "disk_free": "1G"}
_C = {"ibit_today": True, "etha_today": True, "table_rows": 0, "equities_flows_age_h": 1.0, "yield_today": True, "latest_yield_file": "x"}


def _sessions(n, end=date(2026, 11, 10)):
    """The last `n` weekdays up to `end`, oldest first."""
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


def _fixture_market():
    """VIX flat at 15 with two jumps near the end; bitcoin's close moves −1% of each VIX point on session days and is flat at weekends."""
    days = _sessions(300)
    vix = [15.0] * 300
    vix[-5], vix[-4], vix[-2], vix[-1] = 18.0, 15.0, 15.5, 20.0          # +3.0, −3.0, (flat), +0.5, +4.5: two jumps of more than 2 points
    vx = list(zip(days, vix))
    closes, px, prev = [], 100.0, vix[0]
    by_day = dict(vx)
    d = days[0]
    while d <= days[-1]:
        if d in by_day:
            px *= math.exp(-0.01 * (by_day[d] - prev))
            prev = by_day[d]
        closes.append((d, px))
        d += timedelta(days=1)
    dvol = [(days[-1] - timedelta(days=399 - k), 40.0) for k in range(400)]
    dvol[-1] = (dvol[-1][0], 50.0)
    dvol[-31] = (dvol[-31][0], 45.0)
    return closes, dvol, vx


def test_volatility_measures_priced_against_actual_and_the_link_to_vix():
    closes, dvol, vx = _fixture_market()
    v = ds.volatility(NOW, closes=lambda s, now: closes, dvol=lambda c, now: dvol, vix=lambda now: vx)
    btc = v["assets"]["BTC"]
    px = [c for _, c in closes]
    rets = [math.log(b / a) for a, b in zip(px, px[1:])]
    assert btc["implied"] == 50.0 and btc["implied_month_ago"] == 45.0 and btc["implied_pctile"] == 100
    assert btc["realised"][7] == pytest.approx(statistics.stdev(rets[-7:]) * math.sqrt(365) * 100)
    assert btc["realised"][30] == pytest.approx(statistics.stdev(rets[-30:]) * math.sqrt(365) * 100)
    assert btc["realised_week_pctile"] == 100                                 # the last week holds the largest move
    assert btc["ret_pct"][30] == pytest.approx((px[-1] / px[-31] - 1) * 100) and btc["as_of"] == "2026-11-10"
    s = v["stocks"]
    assert (s["vix"], s["as_of"], s["vix_month_ago"], s["high_30"], s["high_30_date"]) == (20.0, "2026-11-10", 15.0, 20.0, "2026-11-10")
    assert s["median_252"] == 15.0 and s["pctile_252"] == 100 and s["jump_days_30"] == 2
    assert v["link"][20] == pytest.approx(-1.0) and v["link"][250] == pytest.approx(-1.0)
    assert ds._ann_vol([0.01, -0.01, 0.01, -0.01]) == pytest.approx(22.06, abs=0.01)   # sqrt(4e-4 / 3) × sqrt(365) × 100


def test_volatility_pairs_bitcoin_with_vix_sessions_across_a_weekend(monkeypatch):
    monkeypatch.setattr(ds, "LINK_WINDOWS", (3,))
    thu = date(2026, 11, 5)
    closes = [(thu + timedelta(days=k), c) for k, c in enumerate([100.0, 110.0, 120.0, 90.0, 99.0, 108.9])]   # Thu … Tue, the weekend included
    vx = [(thu, 15.0), (thu + timedelta(days=1), 16.0), (thu + timedelta(days=4), 18.0), (thu + timedelta(days=5), 17.0)]
    v = ds.volatility(NOW, closes=lambda s, now: closes, dvol=lambda c, now: [(thu, 40.0)], vix=lambda now: vx)
    r = [math.log(110 / 100), math.log(99 / 110), math.log(108.9 / 99)]       # Thu→Fri, Fri→Mon over the weekend, Mon→Tue
    assert v["link"][3] == pytest.approx(statistics.correlation(r, [1.0, 2.0, -1.0]))
    assert v["stocks"]["jump_days_30"] == 0 and v["stocks"]["vix_month_ago"] is None      # a short series pairs neighbours, not a day with itself
    assert v["assets"]["BTC"]["realised"] == {} and v["assets"]["BTC"]["implied_month_ago"] is None


def test_volatility_block_renders_and_a_failed_source_leaves_the_rest(tmp_path):
    closes, dvol, vx = _fixture_market()
    v = ds.volatility(NOW, closes=lambda s, now: closes, dvol=lambda c, now: dvol, vix=lambda now: vx)
    # with the funding lines present, as on the box: the page's funding loops must not swallow the block (they once did,
    # by reusing its variable name — caught by the dry run on the box on 11 November, not by a test with empty funding)
    f = {"BTCUSDT": {"rate_8h": 1e-4, "annualised_pct": 10.95}, "ETHUSDT": {"error": "URLError"}}
    t = {"BTCUSDT": {365: {"days": 365.0, "n": 1095, "gross_pct": 3.4, "on_capital_1x_pct": 1.6}}, "ETHUSDT": {30: {"days": 30.0, "n": 90, "gross_pct": 4.2, "on_capital_1x_pct": 2.0}}}
    page = ds.render(_H, ds.recording_progress(tmp_path / "none.jsonl"), _C, {"dtb3": 4.12, "dtb3_date": "x"}, f, NOW, t, v)
    assert "BTCUSDT funding realised" in page and "against the bill (4.12%)" in page
    assert "## Volatility — priced by options for the next 30 days against actual" in page
    assert "- BTC: priced **50%** (100th percentile; 45% a month ago). Actual **" in page and "Priced minus actual: " in page
    assert "- Stocks: VIX **20.0** on 10 Nov (100th percentile, median 15.0; 15.0 a month ago); 30-session high 20.0 on 10 Nov, 2 jumps of more than 2 points." in page
    assert "**−1.00** over 20 sessions, −1.00 over 250" in page and "Size, never direction." in page
    assert page.index("## Volatility") < page.index("## Notes") and "Open decisions" in page

    def closes_or_fail(symbol, now):
        if symbol == "ETHUSDT":
            raise TimeoutError
        return closes
    broken = ds.volatility(NOW, closes=closes_or_fail, dvol=lambda c, now: dvol, vix=lambda now: 1 / 0)
    assert broken["assets"]["ETH"]["price_error"] == "TimeoutError" and broken["stocks"] == {"error": "ZeroDivisionError"} and broken["link"] == {}
    page = ds.render(_H, ds.recording_progress(tmp_path / "none.jsonl"), _C, {}, {}, NOW, {}, broken)
    assert "- ETH: priced **50%** (100th percentile; 45% a month ago). Actual: unavailable (TimeoutError)." in page
    assert "- Stocks: VIX unavailable (ZeroDivisionError)." in page and "Bitcoin against stock fear" not in page
    assert "- BTC: priced **50%**" in page and "## Notes" in page
    # no block when nothing was read (the --no-net path), and the older call still renders
    assert "## Volatility" not in ds.render(_H, ds.recording_progress(tmp_path / "none.jsonl"), _C, {}, {}, NOW, {})


def test_the_push_is_the_fullest_form_ntfy_shows_as_text(tmp_path):
    closes, dvol, vx = _fixture_market()
    v = ds.volatility(NOW, closes=lambda s, now: closes, dvol=lambda c, now: dvol, vix=lambda now: vx)
    t = {"BTCUSDT": {365: {"days": 365.0, "n": 1095, "gross_pct": 3.4, "on_capital_1x_pct": 1.6}}}
    at = lambda short: ds.render(_H, ds.recording_progress(tmp_path / "none.jsonl"), _C, {"dtb3": 4.12}, {"BTCUSDT": {"rate_8h": 1e-4, "annualised_pct": 10.95}}, NOW, t, v, short)
    full, no_reading, cut = at(0), at(1), at(2)
    assert "Reading it" in full and "Open decisions" in full
    assert "Reading it" not in no_reading and "Open decisions" in no_reading and "- BTC: priced" in no_reading
    assert "Reading it" not in cut and "Open decisions" not in cut and "The full notes are in `latest.md`" in cut and "- BTC: priced" in cut
    assert len(full.encode()) > len(no_reading.encode()) > len(cut.encode())
    assert ds.push_body(at, limit=len(full.encode())) == full
    assert ds.push_body(at, limit=len(full.encode()) - 1) == no_reading
    assert ds.push_body(at, limit=len(no_reading.encode()) - 1) == cut
    assert ds.push_body(lambda short: "−" * 1400) == "−" * 1400               # 4,200 bytes in 1,400 characters: over the limit at every step, the last form goes
    assert ds.PUSH_LIMIT < 4096


def test_ordinals_and_the_no_net_page(tmp_path):
    assert [ds._ord(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 100, 101, 111, None)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "100th", "101st", "111th", "n/a"]
    out = tmp_path / "desk"
    assert ds.main(["--no-net", "--out", str(out), "--health-log", str(tmp_path / "h.log"), "--pm", str(tmp_path / "pm"),
                    "--surface", str(tmp_path / "s"), "--flows", str(tmp_path / "f"), "--yield-dir", str(tmp_path / "y")]) == 0
    page = (out / "latest.md").read_text()
    assert "## Recorders" in page and "## Volatility" not in page and "**30 Nov**" in page
