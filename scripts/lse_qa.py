#!/usr/bin/env python
"""Stage-0 quality pass over the London Strategic Edge data API (docs/research/11 §5).

Run once, uncounted: it is a data check, not a backtest, and it reads no strategy.

  A. the key's plan and limits; the included markets' time zones and `derived` flags;
  B. BTCUSDT one-minute candles, 13-30 October 2026, against Binance's own daily 1m zips
     (data.binance.vision, SHA-256 checked, mirrored under $QR_ROOT/mirror/binance/...);
  C. BTCUSDT 1h (August 2026) and 1d (2024-01-01 to 2026-08-31) against the lake's spot klines;
  D. AAPL one-minute candles (August 2026) against Databento XNAS 1m in the lake, every minute
     and the regular session only, with the time-zone reading checked by shifting;
  E. AAPL daily (2024-01-01 to 2026-08-31) against Databento's daily bar, the regular-session
     bar built from Databento minutes, and the closing-auction price;
  F. the IBIT and ETHA options chains and a week of their flow tape: what is populated;
  G. the reference collections, the insider series for NVDA and AAPL (duplicate rows),
     AAPL's split factors;
  H. the paid tier's answer to one day of ES orders.

The key is read from ~/.qr/secrets.env as LSE_API_KEY through qr.secrets and never printed.
One call a second, about 30 calls and 80k rows in all, inside the free plan's limits.
Raw pulls are kept under $QR_ROOT/mirror/lse/qa_<date>/ for provenance; the report goes to
reports/lse_qa/lse_qa_<date>.md and .json in the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qr import secrets  # noqa: E402

BASE = "https://download.londonstrategicedge.com"
BUCKET = "https://data.binance.vision/data/spot/daily/klines"
QR_ROOT = Path(os.environ.get("QR_ROOT", Path.home() / "qr" / "lake"))
UA = "qr-lse-qa/0.1 (research quality pass)"


# ── the thin client ──────────────────────────────────────────────────────────

class LSE:
    """GET under /v3 with the key in the header; one call a second; 202 jobs polled."""

    def __init__(self, key: str, pace: float = 1.05, log=None):
        self._key = key
        self.pace = pace
        self._last = 0.0
        self.calls = 0
        self.log = log or (lambda s: None)

    def _request(self, path: str, params: dict | None = None, timeout: float = 180.0):
        q = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = f"{BASE}{path}" + (f"?{q}" if q else "")
        wait = self.pace - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(4):
            req = urllib.request.Request(url, headers={"X-API-Key": self._key, "User-Agent": UA,
                                                       "Accept": "application/json, text/csv, */*"})
            self._last = time.monotonic()
            self.calls += 1
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.status, dict(r.headers), r.read()
            except urllib.error.HTTPError as e:
                body = e.read()
                if e.code == 429 and attempt < 3:
                    retry = float(e.headers.get("Retry-After") or 5)
                    time.sleep(min(retry, 120) + 0.5)
                    continue
                if e.code in (500, 502, 503, 504) and attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                return e.code, dict(e.headers), body
        raise RuntimeError(f"{path}: no answer after retries")

    def json(self, path: str, **params):
        status, _, body = self._request(path, params)
        try:
            data = json.loads(body.decode("utf-8"))
        except ValueError:
            data = {"_raw": body[:500].decode("utf-8", "replace")}
        if status != 200:
            data = {"_status": status, **(data if isinstance(data, dict) else {"_body": data})}
        return data

    def csv(self, path: str, **params) -> pd.DataFrame:
        params = {**params, "format": "csv"}
        status, headers, body = self._request(path, params, timeout=600.0)
        if status == 202:
            job = json.loads(body.decode("utf-8"))
            job_id = job["job_id"]
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                info = self.json(f"/v3/jobs/{job_id}")
                if info.get("status") == "ready":
                    break
                if info.get("status") in ("failed", "expired"):
                    raise RuntimeError(f"export {info.get('status')}: {info.get('error')}")
                time.sleep(3)
            else:
                raise RuntimeError("export job did not finish in ten minutes")
            dl = info.get("download_url") or f"/v3/jobs/{job_id}/file"
            status, headers, body = self._request(dl, None, timeout=600.0)
            if len(body) != int(info["bytes"]) or hashlib.sha256(body).hexdigest() != info["checksum"].lower():
                raise RuntimeError("downloaded rows failed their size or SHA-256 check")
        if status != 200:
            raise RuntimeError(f"{path} {params}: HTTP {status}: {body[:300]!r}")
        if not body.strip():
            return pd.DataFrame()
        return pd.read_csv(io.BytesIO(body), na_values=["\\N"])


# ── references ───────────────────────────────────────────────────────────────

def binance_daily_1m(symbol: str, days: list[date], log) -> pd.DataFrame:
    """Binance's own daily 1m kline zips, SHA-256 checked, mirrored in the bucket's layout."""
    mirror = QR_ROOT / "mirror" / "binance" / "data" / "spot" / "daily" / "klines" / symbol / "1m"
    mirror.mkdir(parents=True, exist_ok=True)
    frames = []
    for day in days:
        name = f"{symbol}-1m-{day:%Y-%m-%d}.zip"
        zp = mirror / name
        if not zp.exists():
            url = f"{BUCKET}/{symbol}/1m/{name}"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
                data = r.read()
            with urllib.request.urlopen(urllib.request.Request(url + ".CHECKSUM", headers={"User-Agent": UA}), timeout=60) as r:
                chk = r.read().decode("utf-8").split()[0].lower()
            if hashlib.sha256(data).hexdigest() != chk:
                raise RuntimeError(f"{name}: checksum mismatch against the bucket's CHECKSUM file")
            zp.write_bytes(data)
            (mirror / (name + ".CHECKSUM")).write_text(f"{chk}  {name}\n")
            log(f"  mirrored {name} ({len(data)} bytes, sha256 ok)")
        with zipfile.ZipFile(zp) as z:
            raw = z.read(z.namelist()[0])
        df = pd.read_csv(io.BytesIO(raw), header=None, dtype=str)
        if not str(df.iloc[0, 0]).strip().lstrip("-").isdigit():
            df = df.iloc[1:].reset_index(drop=True)
        df = df.iloc[:, :12]
        df.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
                      "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
        df = df.astype({c: float for c in df.columns})
        unit = "us" if df["open_time"].max() > 1e14 else "ms"
        df["time"] = pd.to_datetime(df["open_time"].astype("int64"), unit=unit, utc=True)
        frames.append(df[["time", "open", "high", "low", "close", "volume", "quote_volume", "trades"]])
    out = pd.concat(frames).set_index("time").sort_index()
    return out[~out.index.duplicated()]


def lake_parquet(rel: str) -> pd.DataFrame:
    df = pd.read_parquet(QR_ROOT / rel)
    df["time"] = pd.to_datetime(df["open_time"], utc=True)
    return df.set_index("time").sort_index()


def lse_candles(df: pd.DataFrame) -> pd.DataFrame:
    """An export's candles indexed by UTC bar time."""
    if df.empty:
        return df
    out = df.copy()
    out["time"] = pd.to_datetime(out["time"], utc=True)
    return out.set_index("time").sort_index()


# ── the comparison ───────────────────────────────────────────────────────────

def compare(lse: pd.DataFrame, ref: pd.DataFrame, expected_n: int | None = None) -> dict:
    common = lse.index.intersection(ref.index)
    res = {"n_lse": int(len(lse)), "n_ref": int(len(ref)), "n_common": int(len(common)),
           "missing_in_lse": int(len(ref.index.difference(lse.index))),
           "extra_in_lse": int(len(lse.index.difference(ref.index)))}
    if expected_n is not None:
        res["expected_n"] = expected_n
    if len(common) == 0:
        return res
    a, b = lse.loc[common], ref.loc[common]
    for c in ("open", "high", "low", "close"):
        if c in a and c in b:
            d = ((a[c] - b[c]).abs() / b[c].abs() * 1e4).astype(float)
            res[c] = {"exact": round(float((d == 0).mean()), 4), "within_1bp": round(float((d <= 1).mean()), 4),
                      "within_5bp": round(float((d <= 5).mean()), 4), "median_bps": round(float(d.median()), 3),
                      "p99_bps": round(float(d.quantile(0.99)), 2), "max_bps": round(float(d.max()), 2)}
    if "volume" in a and "volume" in b:
        r = (a["volume"] / b["volume"].replace(0, np.nan)).dropna()
        if len(r):
            res["volume_ratio"] = {"median": float(r.median()), "p10": float(r.quantile(0.1)), "p90": float(r.quantile(0.9))}
    if "trades" in a and "trades" in b:
        res["trades_exact"] = round(float((a["trades"].astype(float) == b["trades"].astype(float)).mean()), 4)
    miss = ref.index.difference(lse.index)
    res["missing_sample"] = [str(t) for t in miss[:6]]
    extra = lse.index.difference(ref.index)
    res["extra_sample"] = [str(t) for t in extra[:6]]
    return res


def best_shift(lse: pd.DataFrame, ref: pd.DataFrame, hours=(0, -4, 4, -5, 5)) -> dict:
    """Which reading of the stamp lines the closes up: shift the LSE index by whole hours."""
    out = {}
    for h in hours:
        shifted = lse.copy()
        shifted.index = shifted.index + pd.Timedelta(hours=h)
        common = shifted.index.intersection(ref.index)
        if len(common) == 0:
            out[str(h)] = {"n_common": 0}
            continue
        d = (shifted.loc[common, "close"] - ref.loc[common, "close"]).abs() / ref.loc[common, "close"] * 1e4
        out[str(h)] = {"n_common": int(len(common)), "close_exact": round(float((d == 0).mean()), 4),
                       "close_median_bps": round(float(d.median()), 3)}
    return out


# ── the checks ───────────────────────────────────────────────────────────────

def check_a(api: LSE, log) -> dict:
    usage = api.json("/v3/usage")
    markets = api.json("/v3/markets")
    allowed = {k: usage.get(k) for k in ("plan", "product", "calls_per_minute", "rate_mbit", "connections", "rows", "weekly", "withheld")}
    rows = []
    for m in markets.get("markets", []):
        rows.append({k: m.get(k) for k in ("folder", "label", "allowed", "derived", "pairs", "time_zone", "levels", "required_plan")}
                    | {"capabilities": m.get("capabilities")})
    log(f"  plan {allowed.get('plan')}, {allowed.get('calls_per_minute')} calls/min, markets {len(rows)}")
    return {"usage": allowed, "markets": rows, "manifest_built_at": markets.get("manifest_built_at")}


def check_b(api: LSE, start: date, end: date, keep: Path, log) -> dict:
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    ref = binance_daily_1m("BTCUSDT", days, log)
    raw = api.csv("/v3/export", market="crypto", symbol="BTCUSDT", timeframe="1m", adjusted="1", data="candles",
                  **{"from": start.isoformat(), "to": end.isoformat()})
    raw.to_csv(keep / f"BTCUSDT_1m_{start}_{end}.csv", index=False)
    lse = lse_candles(raw)
    res = {"columns": list(raw.columns), "window": [start.isoformat(), end.isoformat()]}
    res["against_binance_zips"] = compare(lse, ref, expected_n=len(days) * 1440)
    # the volume scale: Binance volume is in BTC; a fixed integer scale would show as a constant ratio
    common = lse.index.intersection(ref.index)
    if len(common):
        r = (lse.loc[common, "volume"] / ref.loc[common, "volume"].replace(0, np.nan)).dropna()
        res["volume_scale_guess"] = {"median_ratio": float(r.median()),
                                     "share_ratio_equal_1e8_within_1pct": round(float(((r / 1e8 - 1).abs() < 0.01).mean()), 4),
                                     "share_ratio_equal_1_within_1pct": round(float(((r - 1).abs() < 0.01).mean()), 4)}
        if "quote_volume" in ref:
            rq = (lse.loc[common, "volume"] / ref.loc[common, "quote_volume"].replace(0, np.nan)).dropna()
            res["volume_scale_guess"]["median_ratio_to_quote_volume"] = float(rq.median())
        # a sample of Binance's own tape never exceeds Binance's extremes and never counts more trades
        a, b = lse.loc[common], ref.loc[common]
        rt = (a["trades"] / b["trades"].replace(0, np.nan)).dropna()
        rv = ((a["volume"] / 1e8) / b["volume"].replace(0, np.nan)).dropna()
        res["sample_of_binance_test"] = {
            "trades_ratio_median": round(float(rt.median()), 3), "trades_ratio_p10": round(float(rt.quantile(0.1)), 3),
            "trades_ratio_p90": round(float(rt.quantile(0.9)), 3),
            "share_trades_at_or_below_binance": round(float((a["trades"] <= b["trades"]).mean()), 4),
            "volume_over_1e8_ratio_median": round(float(rv.median()), 3),
            "share_volume_over_1e8_at_or_below_binance": round(float(((a["volume"] / 1e8) <= b["volume"]).mean()), 4),
            "corr_volume": round(float(np.corrcoef(a["volume"], b["volume"])[0, 1]), 3),
            "corr_trades": round(float(np.corrcoef(a["trades"], b["trades"])[0, 1]), 3),
            "share_high_above_binance_high": round(float((a["high"] > b["high"] + 1e-9).mean()), 4),
            "share_low_below_binance_low": round(float((a["low"] < b["low"] - 1e-9).mean()), 4),
        }
    log(f"  B: {res['against_binance_zips'].get('n_common')} common minutes of {len(days) * 1440}")
    return res


def check_c(api: LSE, keep: Path, log) -> dict:
    out = {}
    ref_h = lake_parquet("raw/binance/spot/klines/interval=1h/symbol=BTCUSDT/data.parquet")
    ref_h = ref_h[(ref_h.index >= "2026-08-01") & (ref_h.index < "2026-09-01")]
    raw = api.csv("/v3/export", market="crypto", symbol="BTCUSDT", timeframe="1h", adjusted="1", data="candles",
                  **{"from": "2026-08-01", "to": "2026-08-31"})
    raw.to_csv(keep / "BTCUSDT_1h_2026-08.csv", index=False)
    out["1h_aug_2026_vs_lake"] = compare(lse_candles(raw), ref_h, expected_n=31 * 24)
    ref_d = lake_parquet("raw/binance/spot/klines/interval=1d/symbol=BTCUSDT/data.parquet")
    ref_d = ref_d[(ref_d.index >= "2024-01-01") & (ref_d.index < "2026-09-01")]
    raw = api.csv("/v3/export", market="crypto", symbol="BTCUSDT", timeframe="1d", adjusted="1", data="candles",
                  **{"from": "2024-01-01", "to": "2026-08-31"})
    raw.to_csv(keep / "BTCUSDT_1d_2024-01_2026-08.csv", index=False)
    lse_d = lse_candles(raw)
    stamps = lse_d.index
    out["1d_stamp_hours_utc"] = {str(k): int(v) for k, v in pd.Series(stamps.hour).value_counts().sort_index().items()}
    lse_d.index = lse_d.index.normalize()
    ref_d.index = ref_d.index.normalize()
    out["1d_2024_2026-08_vs_lake"] = compare(lse_d, ref_d, expected_n=len(ref_d))
    log(f"  C: 1h common {out['1h_aug_2026_vs_lake'].get('n_common')}, 1d common {out['1d_2024_2026-08_vs_lake'].get('n_common')}")
    return out


def rth_mask(idx: pd.DatetimeIndex) -> np.ndarray:
    et = idx.tz_convert("America/New_York")
    minutes = np.asarray(et.hour) * 60 + np.asarray(et.minute)
    return (minutes >= 9 * 60 + 30) & (minutes < 16 * 60) & (np.asarray(et.weekday) < 5)


def check_d(api: LSE, keep: Path, log) -> dict:
    ref = lake_parquet("raw/databento/xnas/klines/interval=1m/symbol=AAPL/data.parquet")
    ref = ref[(ref.index >= "2026-08-01") & (ref.index < "2026-09-01")]
    raw = api.csv("/v3/export", market="us_stocks", symbol="AAPL", timeframe="1m", adjusted="1", data="candles",
                  **{"from": "2026-08-01", "to": "2026-08-31"})
    raw.to_csv(keep / "AAPL_1m_2026-08.csv", index=False)
    lse = lse_candles(raw)
    out = {"columns": list(raw.columns), "n_lse": int(len(lse)), "n_databento": int(len(ref))}
    out["stamp_reading"] = best_shift(lse, ref)
    out["all_minutes_utc_reading"] = compare(lse, ref)
    lse_r, ref_r = lse[rth_mask(lse.index)], ref[rth_mask(ref.index)]
    out["regular_session_only"] = compare(lse_r, ref_r)
    et = lse.index.tz_convert("America/New_York")
    out["lse_minutes_by_et_hour"] = {str(k): int(v) for k, v in pd.Series(et.hour).value_counts().sort_index().items()}
    log(f"  D: RTH common {out['regular_session_only'].get('n_common')}, close exact {out['regular_session_only'].get('close', {}).get('exact')}")
    return out


def check_e(api: LSE, keep: Path, log) -> dict:
    raw = api.csv("/v3/export", market="us_stocks", symbol="AAPL", timeframe="1d", adjusted="1", data="candles",
                  **{"from": "2024-01-01", "to": "2026-08-31"})
    raw.to_csv(keep / "AAPL_1d_2024-01_2026-08.csv", index=False)
    lse = lse_candles(raw)
    out = {"n_lse": int(len(lse))}
    out["stamp_hours_utc"] = {str(k): int(v) for k, v in pd.Series(lse.index.hour).value_counts().sort_index().items()}
    lse_day = lse.copy()
    lse_day.index = lse_day.index.normalize()
    # (i) Databento's daily bar
    db_d = lake_parquet("raw/databento/xnas/klines/interval=1d/symbol=AAPL/data.parquet")
    db_d = db_d[(db_d.index >= "2024-01-01") & (db_d.index < "2026-09-01")]
    db_d.index = db_d.index.normalize()
    out["vs_databento_1d"] = compare(lse_day, db_d, expected_n=len(db_d))
    # (ii) the regular session built from Databento minutes
    m = lake_parquet("raw/databento/xnas/klines/interval=1m/symbol=AAPL/data.parquet")
    m = m[(m.index >= "2024-01-01") & (m.index < "2026-09-01")]
    m = m[rth_mask(m.index)]
    day = m.index.tz_convert("America/New_York").normalize().tz_localize(None)
    g = m.groupby(day)
    rth = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "volume": g["volume"].sum()})
    rth.index = pd.DatetimeIndex(rth.index).tz_localize("UTC")
    out["vs_regular_session_from_minutes"] = compare(lse_day, rth, expected_n=len(rth))
    # what the lake's Databento daily bar is: its open and close against the day's minutes
    m_all = lake_parquet("raw/databento/xnas/klines/interval=1m/symbol=AAPL/data.parquet")
    m_all = m_all[(m_all.index >= "2024-01-01") & (m_all.index < "2026-09-01")]
    et_all = m_all.index.tz_convert("America/New_York")
    day_all = pd.DatetimeIndex(et_all.normalize().tz_localize(None))
    hm = np.asarray(et_all.hour) * 100 + np.asarray(et_all.minute)
    last_bar = pd.DataFrame({"close": m_all["close"].groupby(day_all).last()})
    first_bar = pd.DataFrame({"open": m_all["open"].groupby(day_all).first()})
    cross = pd.DataFrame({"close": m_all[hm == 1600]["open"].groupby(day_all[hm == 1600]).first()})
    for frame in (last_bar, first_bar, cross):
        frame.index = pd.DatetimeIndex(frame.index).tz_localize("UTC")
    dbd = db_d.copy()
    out["lake_databento_1d_is"] = {
        "close_equals_last_minute_of_day": compare(dbd[["close"]], last_bar)["close"]["exact"],
        "open_equals_first_minute_of_day": compare(dbd[["open"]], first_bar)["open"]["exact"],
        "close_equals_1600_cross_minute": compare(dbd[["close"]], cross)["close"]["exact"],
    }
    # (iii) LSE close against the extended day's last minute, (iv) against the 16:00 ET minute's open (the closing cross)
    out["close_vs_last_minute_of_day"] = compare(lse_day[["close"]], last_bar, expected_n=len(last_bar))
    out["close_vs_1600_cross_minute"] = compare(lse_day[["close"]], cross, expected_n=len(cross))
    log(f"  E: vs 1d close exact {out['vs_databento_1d'].get('close', {}).get('exact')}, vs 16:00 cross within 1 bp {out['close_vs_1600_cross_minute'].get('close', {}).get('within_1bp')}")
    return out


def check_f(api: LSE, keep: Path, log) -> dict:
    out = {}
    today = date.today()
    for und in ("IBIT", "ETHA"):
        rows, offset, meta = [], 0, {}
        while True:
            page = api.json("/v3/options/chain", underlying=und, limit=1000, offset=offset)
            if "_status" in page:
                meta = {"error": page}
                break
            meta = {k: page.get(k) for k in ("contracts", "greeks_as_of", "underlying_price", "underlying_at")}
            rows.extend(page.get("rows", []))
            if page.get("returned", 0) < 1000 or len(rows) >= int(page.get("contracts", 0)):
                break
            offset += 1000
        df = pd.DataFrame(rows)
        if len(df):
            df.to_csv(keep / f"chain_{und}.csv", index=False)
        r = dict(meta)
        r["rows_fetched"] = int(len(df))
        if len(df):
            r["columns"] = list(df.columns)
            r["has_open_interest_column"] = any("interest" in c or c == "oi" for c in df.columns)
            r["with_iv"] = int(df["iv"].notna().sum()) if "iv" in df else None
            r["with_delta"] = int(df["delta"].notna().sum()) if "delta" in df else None
            r["with_last_price"] = int(df["last_price"].notna().sum()) if "last_price" in df else None
            r["expiries"] = int(df["expiry"].nunique()) if "expiry" in df else None
            r["volume_today_total"] = float(df["volume_today"].fillna(0).sum()) if "volume_today" in df else None
            if "last_trade_at" in df:
                lt = pd.to_datetime(df["last_trade_at"], errors="coerce", utc=True)
                r["traded_in_last_7_days"] = int((lt >= pd.Timestamp(today - timedelta(days=7), tz="UTC")).sum())
                r["newest_last_trade"] = str(lt.max())
            if "iv" in df and df["iv"].notna().any():
                near = df[df["iv"].notna()].sort_values(["dte"])
                r["iv_sample_nearest"] = near[["expiry", "strike", "contract_type", "iv", "delta"]].head(4).to_dict("records")
        out[f"chain_{und}"] = r
        flow = api.json("/v3/options/flow", underlying=und, limit=1000, order="desc",
                        **{"from": (today - timedelta(days=7)).isoformat(), "to": today.isoformat()})
        if "_status" in flow:
            out[f"flow_{und}"] = {"error": flow}
        else:
            fr = pd.DataFrame(flow.get("rows", []))
            if len(fr):
                fr.to_csv(keep / f"flow_{und}.csv", index=False)
            fo = {k: flow.get(k) for k in flow if k not in ("rows",)}
            fo["rows_returned"] = int(len(fr))
            if len(fr):
                fo["columns"] = list(fr.columns)
                for c in ("premium", "size", "volume"):
                    if c in fr:
                        fo[f"{c}_total"] = float(pd.to_numeric(fr[c], errors="coerce").fillna(0).sum())
                tcol = next((c for c in ("time", "ts", "traded_at", "printed_at") if c in fr), None)
                if tcol:
                    t = pd.to_datetime(fr[tcol], errors="coerce", utc=True)
                    fo["first_print"], fo["last_print"] = str(t.min()), str(t.max())
            out[f"flow_{und}"] = fo
        log(f"  F: {und} chain {r.get('rows_fetched')} rows, with iv {r.get('with_iv')}, flow rows {out[f'flow_{und}'].get('rows_returned')}")
    return out


def check_g(api: LSE, keep: Path, log) -> dict:
    out = {}
    cat = api.json("/v3/reference", limit=100)
    datasets = cat.get("datasets", [])
    out["datasets"] = [{k: d.get(k) for k in ("dataset", "category", "rows", "series", "first", "last", "columns", "time_column", "as_of")}
                       for d in datasets]
    insider = next((d["dataset"] for d in datasets if "insider" in str(d.get("dataset", ""))), None)
    out["insider_dataset"] = insider
    if insider:
        for sym in ("NVDA", "AAPL"):
            series = api.json("/v3/reference", dataset=insider, q=sym, limit=5)
            names = [s.get("symbol") for s in series.get("series", [])]
            use = sym if sym in names else (names[0] if names else sym)
            try:
                df = api.csv("/v3/reference/export", dataset=insider, symbol=use, **{"from": "2026-01-01", "to": "2026-10-31"})
            except RuntimeError as e:
                out[f"insider_{sym}"] = {"error": str(e)[:300], "series_seen": names}
                continue
            if len(df):
                df.to_csv(keep / f"insider_{sym}_2026.csv", index=False)
            r = {"series_symbol": use, "series_seen": names, "rows": int(len(df)), "columns": list(df.columns)}
            if len(df):
                r["exact_duplicate_rows"] = int(df.duplicated().sum())
                key_cols = [c for c in df.columns if any(k in c.lower() for k in ("date", "filed", "owner", "insider", "name", "shares", "price", "type", "code"))]
                r["duplicate_on_key_columns"] = int(df.duplicated(subset=key_cols).sum()) if key_cols else None
                r["key_columns_used"] = key_cols
                for c in df.columns:
                    if "date" in c.lower() or "filed" in c.lower():
                        r[f"{c}_range"] = [str(df[c].min()), str(df[c].max())]
            out[f"insider_{sym}"] = r
    factors = api.json("/v3/factors", market="us_stocks", symbol="AAPL")
    if "_status" in factors:
        out["factors_AAPL"] = {"error": factors}
    else:
        splits = factors.get("splits") or []
        divs = factors.get("dividends") or []
        out["factors_AAPL"] = {"keys": list(factors.keys()), "splits": splits[:10] if isinstance(splits, list) else splits,
                               "n_dividends": len(divs) if isinstance(divs, list) else None,
                               "dividend_sample": divs[:3] if isinstance(divs, list) else None}
    log(f"  G: {len(datasets)} datasets, insider dataset {insider}")
    return out


def check_h(api: LSE, log) -> dict:
    est = api.json("/v3/estimate", market="cme", symbol="ES", timeframe="tick", adjusted="0", data="orders",
                   **{"from": "2026-10-20", "to": "2026-10-20"})
    r = {k: est.get(k) for k in ("rows", "estimated_bytes", "message", "mode", "basis")}
    dl = est.get("download") or {}
    r["download"] = {k: dl.get(k) for k in ("code", "message", "status")}
    r["required_plan"] = {k: (dl.get("required_plan") or {}).get(k) for k in ("market", "tier", "name")}
    log(f"  H: ES orders → {r['download'].get('code')} ({r['required_plan'].get('tier')})")
    return r


# ── the report ───────────────────────────────────────────────────────────────

def fmt_cmp(c: dict) -> str:
    if not c or "n_common" not in c:
        return "no comparison"
    parts = [f"LSE {c['n_lse']}, reference {c['n_ref']}, common {c['n_common']}, missing in LSE {c['missing_in_lse']}, extra in LSE {c['extra_in_lse']}"]
    if "expected_n" in c:
        parts[0] += f", expected {c['expected_n']}"
    for col in ("open", "high", "low", "close"):
        if col in c:
            s = c[col]
            parts.append(f"{col}: exact {s['exact']:.1%}, within 1 bp {s['within_1bp']:.1%}, median {s['median_bps']} bps, p99 {s['p99_bps']} bps, max {s['max_bps']} bps")
    if "volume_ratio" in c:
        v = c["volume_ratio"]
        parts.append(f"volume ratio LSE/reference: median {v['median']:.4g} (p10 {v['p10']:.4g}, p90 {v['p90']:.4g})")
    if "trades_exact" in c:
        parts.append(f"trade counts equal: {c['trades_exact']:.1%}")
    if c.get("missing_sample"):
        parts.append(f"missing sample: {', '.join(c['missing_sample'][:4])}")
    return "; ".join(parts)


def write_report(res: dict, out_md: Path, out_json: Path, run_date: str) -> None:
    out_json.write_text(json.dumps(res, indent=1, default=str))
    L = [f"# London Strategic Edge — stage-0 quality pass, {run_date}", "",
         "Uncounted data check (`scripts/lse_qa.py`), not a backtest. Key read from `~/.qr/secrets.env`; nothing here holds it.",
         f"API calls made: {res['_meta']['calls']}; raw pulls kept under `{res['_meta']['keep']}`.", ""]
    a = res.get("A", {})
    u = a.get("usage", {})
    L += ["## A. Plan, limits, markets", "",
          f"Plan `{u.get('plan')}` ({u.get('product')}): {u.get('calls_per_minute')} calls a minute, {u.get('rate_mbit')} Mbit/s, "
          f"{u.get('connections')} download at a time; rows {u.get('rows', {}).get('per_day')} a day and {u.get('rows', {}).get('per_export')} an export; "
          f"weekly allowance {round((u.get('weekly') or {}).get('allowance_bytes', 0) / 2**30, 1)} GiB; withheld: {u.get('withheld')}.", "",
          "| market | allowed | derived | pairs | time zone | candles | tick | trades | book | orders | plan |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in a.get("markets", []):
        cap = m.get("capabilities") or {}
        rp = m.get("required_plan") or {}
        L.append(f"| {m.get('folder')} | {m.get('allowed')} | {m.get('derived')} | {m.get('pairs')} | {m.get('time_zone')} | {cap.get('candles')} | {cap.get('tick')} | {cap.get('trades')} | {cap.get('book')} | {cap.get('orders')} | {rp.get('tier') or '—'} |")
    b = res.get("B", {})
    L += ["", "## B. BTCUSDT one-minute candles, 13–30 October 2026, against Binance's own daily 1m zips", "",
          f"Columns delivered: {b.get('columns')}.", "", fmt_cmp(b.get("against_binance_zips", {})), ""]
    if "volume_scale_guess" in b:
        v = b["volume_scale_guess"]
        L.append(f"Volume scale: median LSE/Binance base-volume ratio {v['median_ratio']:.6g}; share of minutes where the ratio is 1e8 within 1% {v['share_ratio_equal_1e8_within_1pct']:.1%}, where it is 1 within 1% {v['share_ratio_equal_1_within_1pct']:.1%}; median ratio to Binance quote volume {v.get('median_ratio_to_quote_volume', float('nan')):.6g}.")
    if "sample_of_binance_test" in b:
        t = b["sample_of_binance_test"]
        L += ["", f"Is it Binance's tape? Trade counts LSE/Binance median {t['trades_ratio_median']} (p10 {t['trades_ratio_p10']}, p90 {t['trades_ratio_p90']}), at or below Binance's in {t['share_trades_at_or_below_binance']:.1%} of minutes; volume read as 1e-8 units is {t['volume_over_1e8_ratio_median']} of Binance's (at or below in {t['share_volume_over_1e8_at_or_below_binance']:.1%}); correlations volume {t['corr_volume']}, trades {t['corr_trades']}. "
              f"But the LSE high exceeds Binance's high in {t['share_high_above_binance_high']:.1%} of minutes and the LSE low undercuts Binance's low in {t['share_low_below_binance_low']:.1%}: a sample of Binance's own tape could not do that, so the bars are not Binance's bars."]
    c = res.get("C", {})
    L += ["", "## C. BTCUSDT 1h (August 2026) and 1d (2024-01-01 → 2026-08-31) against the lake's spot klines", "",
          "1h: " + fmt_cmp(c.get("1h_aug_2026_vs_lake", {})), "",
          f"1d stamps by UTC hour: {c.get('1d_stamp_hours_utc')}", "",
          "1d (dates aligned): " + fmt_cmp(c.get("1d_2024_2026-08_vs_lake", {})), ""]
    d = res.get("D", {})
    L += ["## D. AAPL one-minute candles, August 2026, against Databento XNAS 1m", "",
          f"Columns delivered: {d.get('columns')}. LSE rows {d.get('n_lse')}, Databento rows {d.get('n_databento')}.", "",
          f"Stamp reading (shift the LSE stamp by whole hours; the right reading has the most exact closes): {d.get('stamp_reading')}", "",
          "All minutes, stamps read as UTC: " + fmt_cmp(d.get("all_minutes_utc_reading", {})), "",
          "Regular session only (09:30–16:00 ET): " + fmt_cmp(d.get("regular_session_only", {})), "",
          f"LSE minutes by ET hour: {d.get('lse_minutes_by_et_hour')}", ""]
    e = res.get("E", {})
    L += ["## E. AAPL daily, 2024-01-01 → 2026-08-31", "",
          f"LSE rows {e.get('n_lse')}; daily stamps by UTC hour: {e.get('stamp_hours_utc')}", "",
          "Against Databento's daily bar: " + fmt_cmp(e.get("vs_databento_1d", {})), "",
          "Against the regular session built from Databento minutes: " + fmt_cmp(e.get("vs_regular_session_from_minutes", {})), "",
          f"What the lake's Databento daily bar is (share exact): {e.get('lake_databento_1d_is')} — the 04:00–19:59 ET extended day, not the session.", "",
          "Close against the extended day's last minute (19:59 ET): " + fmt_cmp(e.get("close_vs_last_minute_of_day", {})), "",
          "Close against the 16:00 ET minute's open (the closing cross): " + fmt_cmp(e.get("close_vs_1600_cross_minute", {})), ""]
    f = res.get("F", {})
    L += ["## F. Options: IBIT and ETHA chains, a week of flow", ""]
    for und in ("IBIT", "ETHA"):
        ch, fl = f.get(f"chain_{und}", {}), f.get(f"flow_{und}", {})
        L.append(f"- **{und} chain**: contracts {ch.get('contracts')}, fetched {ch.get('rows_fetched')}, expiries {ch.get('expiries')}, with IV {ch.get('with_iv')}, with delta {ch.get('with_delta')}, with a last price {ch.get('with_last_price')}, traded in the last 7 days {ch.get('traded_in_last_7_days')}, volume today {ch.get('volume_today_total')}; greeks_as_of {ch.get('greeks_as_of')}; underlying {ch.get('underlying_price')} at {ch.get('underlying_at')}; open-interest column present: {ch.get('has_open_interest_column')}; newest last trade {ch.get('newest_last_trade')}.")
        if ch.get("iv_sample_nearest"):
            L.append(f"  IV sample (nearest expiries): {ch['iv_sample_nearest']}")
        if ch.get("columns"):
            L.append(f"  columns: {ch['columns']}")
        page_fields = {k: v for k, v in fl.items() if k not in ("columns", "rows_returned", "premium_total", "first_print", "last_print")}
        L.append(f"- **{und} flow, last 7 days (one page of 1000)**: rows {fl.get('rows_returned')}, premium total {fl.get('premium_total')}, first print {fl.get('first_print')}, last print {fl.get('last_print')}; page fields {page_fields}")
        if fl.get("columns"):
            L.append(f"  columns: {fl['columns']}")
    g = res.get("G", {})
    L += ["", "## G. Reference collections, insider filings, split factors", "",
          "| dataset | category | rows | series | first | last | columns |", "|---|---|---|---|---|---|---|"]
    for ds in g.get("datasets", []):
        L.append(f"| {ds.get('dataset')} | {ds.get('category')} | {ds.get('rows')} | {ds.get('series')} | {ds.get('first')} | {ds.get('last')} | {', '.join(ds.get('columns') or [])} |")
    L.append("")
    for sym in ("NVDA", "AAPL"):
        r = g.get(f"insider_{sym}", {})
        L.append(f"- **Insider series {sym}** (dataset `{g.get('insider_dataset')}`, 2026-01-01 → 2026-10-31): {r}")
    L.append(f"- **AAPL factors**: {g.get('factors_AAPL')}")
    h = res.get("H", {})
    L += ["", "## H. The paid tier's answer to one day of ES Level 3 orders", "", f"{h}", ""]
    out_md.write_text("\n".join(L) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--btc-start", default="2026-10-13")
    p.add_argument("--btc-end", default="2026-10-30")
    p.add_argument("--out", default=str(ROOT / "reports" / "lse_qa"))
    p.add_argument("--only", default="ABCDEFGH", help="which checks to run, letters")
    a = p.parse_args()
    key = secrets.require("LSE_API_KEY")
    run_date = date.today().isoformat()
    keep = QR_ROOT / "mirror" / "lse" / f"qa_{run_date}"
    keep.mkdir(parents=True, exist_ok=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = lambda s: print(s, flush=True)  # noqa: E731
    api = LSE(key, log=log)
    res: dict = {"_meta": {"run_date": run_date, "keep": str(keep), "qr_root": str(QR_ROOT)}}
    prior = out / f"lse_qa_{run_date}.json"
    if prior.exists() and a.only != "ABCDEFGH":  # a partial re-run keeps the other checks' results
        earlier = json.loads(prior.read_text())
        res = {**earlier, **res}
        res["_meta"]["prior_calls"] = int((earlier.get("_meta") or {}).get("calls") or 0)
    steps = {"A": lambda: check_a(api, log), "B": lambda: check_b(api, date.fromisoformat(a.btc_start), date.fromisoformat(a.btc_end), keep, log),
             "C": lambda: check_c(api, keep, log), "D": lambda: check_d(api, keep, log), "E": lambda: check_e(api, keep, log),
             "F": lambda: check_f(api, keep, log), "G": lambda: check_g(api, keep, log), "H": lambda: check_h(api, log)}
    for letter in a.only:
        log(f"[{letter}] {datetime.now(timezone.utc):%H:%M:%S} UTC")
        try:
            res[letter] = steps[letter]()
        except Exception as exc:  # keep going; the report records the failure
            res[letter] = {"error": f"{type(exc).__name__}: {str(exc)[:400]}"}
            log(f"  {letter} failed: {type(exc).__name__}: {str(exc)[:200]}")
    res["_meta"]["calls"] = api.calls + int(res["_meta"].get("prior_calls") or 0)
    write_report(res, out / f"lse_qa_{run_date}.md", out / f"lse_qa_{run_date}.json", run_date)
    log(f"wrote {out / f'lse_qa_{run_date}.md'} ({api.calls} API calls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
