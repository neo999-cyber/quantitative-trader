"""E7's public short-side data: SEC fails-to-deliver and FINRA Reg SHO daily short volume.

Both are free and point-in-time by publication:

* **SEC fails-to-deliver** (`cnsfails{YYYYMM}{a|b}.zip`, twice a month, from
  2004): settlement date, CUSIP, symbol, fails quantity, price. The SEC
  publishes the first half of a month about two weeks after it ends and the
  second half about a month after; the file's HTTP `Last-Modified` is
  recorded as `published_at` when the server gives it (it is what was
  observed), and `first_observed_at` is the time of the pull.
* **FINRA Reg SHO daily short volume** (`CNMSshvol{YYYYMMDD}.txt`), the
  consolidated file for every day since 2009: date, symbol, short volume,
  short-exempt volume, total volume, markets. Published the same evening;
  `published_at` is stated as 18:00 ET of the trade date, the conservative
  reading, and the pull's `first_observed_at` is recorded beside it.

A signal at time t may read a row only if `published_at <= t`; the loader
does not enforce that — `qr.data.pit.asof_view` does.
"""
from __future__ import annotations

import hashlib
import io
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd

USER_AGENT = "quantitative-trader research (neo999@gmail.com)"
FTD_URL = "https://www.sec.gov/files/data/fails-deliver-data/cnsfails{period}.zip"
REGSHO_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{day}.txt"
NY = "America/New_York"


def _get(url: str, timeout: int = 120) -> tuple[bytes, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Last-Modified")


def parse_ftd(payload: bytes) -> pd.DataFrame:
    """One `cnsfails` zip -> rows with settlement_date, cusip, symbol, fails, price."""
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        raw = zf.read(zf.namelist()[0])
    text = raw.decode("latin-1")
    # A few descriptions carry a literal "|" (one line in 52,725 of the
    # 2017-07a file); the row's first five fields are still positional, so
    # split by hand and keep the first six columns rather than drop the row.
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header = [c.strip().lower() for c in lines[0].split("|")]
    body = [ln.split("|", len(header) - 1)[: len(header)] for ln in lines[1:]]
    body = [row + [""] * (len(header) - len(row)) for row in body]
    frame = pd.DataFrame(body, columns=header, dtype=str)
    frame = frame.rename(columns={"settlement date": "settlement_date", "quantity (fails)": "fails"})
    frame = frame[frame["settlement_date"].str.match(r"^\d{8}$")]
    out = pd.DataFrame(
        {
            "settlement_date": pd.to_datetime(frame["settlement_date"], format="%Y%m%d"),
            "cusip": frame["cusip"].str.strip(),
            "symbol": frame["symbol"].str.strip(),
            "fails": pd.to_numeric(frame["fails"], errors="coerce"),
            "price": pd.to_numeric(frame["price"], errors="coerce"),
        }
    )
    return out.dropna(subset=["fails"]).reset_index(drop=True)


def parse_regsho(payload: bytes) -> pd.DataFrame:
    text = payload.decode("latin-1")
    frame = pd.read_csv(io.StringIO(text), sep="|", dtype=str, keep_default_na=False)
    frame = frame[frame["Date"].str.match(r"^\d{8}$")]
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["Date"], format="%Y%m%d"),
            "symbol": frame["Symbol"].str.strip(),
            "short_volume": pd.to_numeric(frame["ShortVolume"], errors="coerce"),
            "short_exempt_volume": pd.to_numeric(frame["ShortExemptVolume"], errors="coerce"),
            "total_volume": pd.to_numeric(frame["TotalVolume"], errors="coerce"),
        }
    )
    out["short_ratio"] = out["short_volume"] / out["total_volume"].where(out["total_volume"] > 0)
    return out.reset_index(drop=True)


def ftd_periods(start: str = "2010-01", end: str | None = None) -> list[str]:
    stop = pd.Timestamp(end) if end else pd.Timestamp.now(tz="UTC").tz_localize(None)
    months = pd.period_range(start, stop.strftime("%Y-%m"), freq="M")
    return [f"{m.strftime('%Y%m')}{half}" for m in months for half in ("a", "b")]


def pull_ftd(mirror: Path, periods: list[str], pause: float = 0.2) -> pd.DataFrame:
    mirror.mkdir(parents=True, exist_ok=True)
    rows = []
    for period in periods:
        target = mirror / f"cnsfails{period}.zip"
        meta = target.with_suffix(".json")
        if target.exists():
            continue
        try:
            payload, last_modified = _get(FTD_URL.format(period=period))
        except Exception as exc:  # noqa: BLE001
            rows.append({"period": period, "note": str(exc)[:80]})
            continue
        target.write_bytes(payload)
        published = parsedate_to_datetime(last_modified).astimezone(timezone.utc).isoformat() if last_modified else None
        meta.write_text(pd.Series({"period": period, "published_at": published, "first_observed_at": datetime.now(timezone.utc).isoformat(), "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}).to_json())
        rows.append({"period": period, "bytes": len(payload), "published_at": published})
        time.sleep(pause)
    return pd.DataFrame(rows)


def pull_regsho(mirror: Path, days: pd.DatetimeIndex, pause: float = 0.05) -> pd.DataFrame:
    mirror.mkdir(parents=True, exist_ok=True)
    rows = []
    for day in days:
        stamp = day.strftime("%Y%m%d")
        target = mirror / f"CNMSshvol{stamp}.txt"
        if target.exists():
            continue
        try:
            payload, _ = _get(REGSHO_URL.format(day=stamp), timeout=60)
        except Exception as exc:  # noqa: BLE001
            rows.append({"day": stamp, "note": str(exc)[:60]})
            continue
        target.write_bytes(payload)
        rows.append({"day": stamp, "bytes": len(payload)})
        time.sleep(pause)
    return pd.DataFrame(rows)


def load_ftd(mirror: Path) -> pd.DataFrame:
    frames = []
    for zip_path in sorted(Path(mirror).glob("cnsfails*.zip")):
        meta_path = zip_path.with_suffix(".json")
        meta = pd.read_json(meta_path, typ="series") if meta_path.exists() else pd.Series()
        frame = parse_ftd(zip_path.read_bytes())
        frame["published_at"] = pd.to_datetime(meta.get("published_at"), utc=True) if meta.get("published_at") else pd.NaT
        frame["first_observed_at"] = pd.to_datetime(meta.get("first_observed_at"), utc=True) if meta.get("first_observed_at") else pd.NaT
        frame["source_hash"] = meta.get("sha256", "")
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(out):
        out["event_time"] = out["settlement_date"].dt.tz_localize(NY) + pd.Timedelta(hours=16)
        out["ingested_at"] = pd.Timestamp.now(tz="UTC")
    return out


def load_regsho(mirror: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(Path(mirror).glob("CNMSshvol*.txt")):
        frame = parse_regsho(path.read_bytes())
        frame["source_hash"] = hashlib.sha256(path.read_bytes()).hexdigest()
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(out):
        out["event_time"] = out["date"].dt.tz_localize(NY) + pd.Timedelta(hours=16)
        out["published_at"] = out["date"].dt.tz_localize(NY) + pd.Timedelta(hours=18)
        out["first_observed_at"] = pd.Timestamp.now(tz="UTC")
        out["ingested_at"] = pd.Timestamp.now(tz="UTC")
    return out


# ------------------------------------------------------- FINRA short interest

FINRA_SI_URL = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{day}.csv"


def si_settlement_days(start: str = "2020-01-01", end: str | None = None) -> list[str]:
    """FINRA's twice-monthly settlement dates: the 15th and the last day of each
    month, moved back to the previous business day when they fall on a weekend."""
    stop = pd.Timestamp(end) if end else pd.Timestamp.now().normalize()
    out = []
    for m in pd.period_range(start, stop.strftime("%Y-%m"), freq="M"):
        for d in (pd.Timestamp(m.start_time.year, m.month, 15), m.end_time.normalize()):
            while d.weekday() >= 5:
                d -= pd.Timedelta(days=1)
            if pd.Timestamp(start) <= d <= stop:
                out.append(d.strftime("%Y%m%d"))
    return out


def parse_finra_si(payload: bytes) -> pd.DataFrame:
    text = payload.decode("latin-1")
    frame = pd.read_csv(io.StringIO(text), sep="|", dtype=str, keep_default_na=False)
    out = pd.DataFrame(
        {
            "settlement_date": pd.to_datetime(frame["settlementDate"], errors="coerce"),
            "symbol": frame["symbolCode"].str.strip(),
            "market": frame["marketClassCode"].str.strip(),
            "short_interest": pd.to_numeric(frame["currentShortPositionQuantity"], errors="coerce"),
            "previous_short_interest": pd.to_numeric(frame["previousShortPositionQuantity"], errors="coerce"),
            "adv": pd.to_numeric(frame["averageDailyVolumeQuantity"], errors="coerce"),
            "days_to_cover": pd.to_numeric(frame["daysToCoverQuantity"], errors="coerce"),
            "revision": frame["revisionFlag"].str.strip(),
        }
    )
    return out.dropna(subset=["settlement_date"]).reset_index(drop=True)


def pull_finra_si(mirror: Path, days: list[str], pause: float = 0.2) -> pd.DataFrame:
    mirror.mkdir(parents=True, exist_ok=True)
    rows = []
    for stamp in days:
        target = mirror / f"shrt{stamp}.csv"
        if target.exists():
            continue
        try:
            payload, last_modified = _get(FINRA_SI_URL.format(day=stamp), timeout=60)
        except Exception as exc:  # noqa: BLE001
            rows.append({"day": stamp, "note": str(exc)[:60]})
            continue
        target.write_bytes(payload)
        published = parsedate_to_datetime(last_modified).astimezone(timezone.utc).isoformat() if last_modified else None
        target.with_suffix(".json").write_text(pd.Series({"day": stamp, "published_at": published, "first_observed_at": datetime.now(timezone.utc).isoformat(), "sha256": hashlib.sha256(payload).hexdigest()}).to_json())
        rows.append({"day": stamp, "bytes": len(payload), "published_at": published})
        time.sleep(pause)
    return pd.DataFrame(rows)


def load_finra_si(mirror: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(Path(mirror).glob("shrt*.csv")):
        meta_path = path.with_suffix(".json")
        meta = pd.read_json(meta_path, typ="series") if meta_path.exists() else pd.Series()
        frame = parse_finra_si(path.read_bytes())
        frame["published_at"] = pd.to_datetime(meta.get("published_at"), utc=True) if meta.get("published_at") else pd.NaT
        frame["first_observed_at"] = pd.to_datetime(meta.get("first_observed_at"), utc=True) if meta.get("first_observed_at") else pd.NaT
        frame["source_hash"] = meta.get("sha256", "")
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(out):
        out["event_time"] = out["settlement_date"].dt.tz_localize(NY) + pd.Timedelta(hours=16)
        out["ingested_at"] = pd.Timestamp.now(tz="UTC")
    return out
