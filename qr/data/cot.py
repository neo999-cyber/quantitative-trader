"""CME positioning as a timer for the carry holding (`docs/prereg/p4_cot_crowding_v1.md`): the Traders in
Financial Futures parser and the `carrycot-um` instrument.

**The data.** The CFTC's yearly `fut_fin_txt_<year>.zip` (mirror `mirror/cftc/`), one comma-separated row per
market and report Tuesday: open interest and the leveraged-fund long and short positions, among others.
`BITCOIN - CHICAGO MERCANTILE EXCHANGE` runs from 10 April 2018, `ETHER CASH SETTLED - CHICAGO MERCANTILE
EXCHANGE` from early 2021. Read as released: the files carry no revisions.

**When a row is known.** Tuesday's positions are published on Friday at 15:30 New York, so the row is usable
from 00:00 UTC on Saturday (report date + 4 days). In a week with a US federal holiday on the Tuesday through
Friday the CFTC releases on the following Monday instead, so such a row is usable from 00:00 UTC on the
Tuesday after (report date + 7 days): the memo's Saturday rule in ordinary weeks, a conservative three days
later in holiday weeks (`release_time`).

**The feature.** `crowd = (lev_short − lev_long) / open_interest`, and its percentile within the trailing 26
and 52 reports (the current one included, so the first 26 or 52 weeks of a market define none). On the daily
carry-unit bars each day carries the latest row known by the bar's open (`merge_asof`), so a Saturday bar's
decision reads Friday's release and a target set on it fills at Saturday's close.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

MARKET = "carrycot-um"
SOURCE = "binance"
CARRY_MARKET = "carry-um"
BTC_ONLY = ("BTCUSDT",)
ETH_ONLY = ("ETHUSDT",)
TFF_MARKETS = {
    "BTCUSDT": "BITCOIN - CHICAGO MERCANTILE EXCHANGE",
    "ETHUSDT": "ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE",
}
WINDOWS = (26, 52)
#: the registered thresholds, counted by the build so the sample minimum is known before any run
GRID_P = (80, 90, 95)
FEATURES = ("cot_crowd",) + tuple(f"cot_pct_{w}" for w in WINDOWS)
_COLUMNS = {
    "Market_and_Exchange_Names": "market",
    "Report_Date_as_YYYY-MM-DD": "report_date",
    "Open_Interest_All": "open_interest",
    "Lev_Money_Positions_Long_All": "lev_long",
    "Lev_Money_Positions_Short_All": "lev_short",
}


def parse_tff(text: str) -> pd.DataFrame:
    """One TFF text file -> market, report_date, open_interest, lev_long, lev_short (the rest dropped)."""
    frame = pd.read_csv(io.StringIO(text), skipinitialspace=True, dtype=str)
    frame.columns = [c.strip() for c in frame.columns]
    missing = [c for c in _COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"TFF file lacks {missing}; columns start {list(frame.columns)[:6]}")
    out = frame[list(_COLUMNS)].rename(columns=_COLUMNS)
    out["market"] = out["market"].str.strip()
    out["report_date"] = pd.to_datetime(out["report_date"].str.strip(), errors="coerce")
    for col in ("open_interest", "lev_long", "lev_short"):
        out[col] = pd.to_numeric(out[col].str.strip(), errors="coerce")
    out = out.dropna(subset=["report_date", "open_interest"])
    return out.sort_values(["market", "report_date"]).reset_index(drop=True)


def read_tff_zips(mirror_dir: Path) -> pd.DataFrame:
    """Every `fut_fin_txt_*.zip` under `mirror_dir`, parsed and de-duplicated on (market, report_date)."""
    frames = []
    for path in sorted(Path(mirror_dir).glob("fut_fin_txt_*.zip")):
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
            if not names:
                raise ValueError(f"{path.name} holds no .txt member: {zf.namelist()}")
            frames.append(parse_tff(zf.read(names[0]).decode("utf-8", "replace")))
    if not frames:
        raise FileNotFoundError(f"no fut_fin_txt_*.zip under {mirror_dir}")
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(["market", "report_date"], keep="last").sort_values(["market", "report_date"]).reset_index(drop=True)


def release_time(report_dates: Iterable) -> pd.DatetimeIndex:
    """When each report's row is usable: Saturday 00:00 UTC after an ordinary week, the Tuesday after a holiday week."""
    from pandas.tseries.holiday import USFederalHolidayCalendar

    dates = pd.DatetimeIndex(pd.to_datetime(list(report_dates))).normalize()
    if len(dates) == 0:
        return pd.DatetimeIndex([], tz="UTC")
    holidays = USFederalHolidayCalendar().holidays(start=dates.min() - pd.Timedelta(days=7), end=dates.max() + pd.Timedelta(days=14))
    out = []
    for d in dates:
        week = pd.date_range(d, d + pd.Timedelta(days=3), freq="D")   # the report Tuesday through its Friday
        delayed = bool(week.isin(holidays).any())
        out.append((d + pd.Timedelta(days=7 if delayed else 4)).tz_localize("UTC"))
    return pd.DatetimeIndex(out)


def crowd_features(weekly: pd.DataFrame, windows: Iterable[int] = WINDOWS) -> pd.DataFrame:
    """One market's reports -> crowd ratio, its trailing percentiles and the availability stamp."""
    w = weekly.sort_values("report_date").reset_index(drop=True).copy()
    w["cot_crowd"] = (w["lev_short"] - w["lev_long"]) / w["open_interest"].where(w["open_interest"] > 0)
    for n in windows:
        w[f"cot_pct_{n}"] = w["cot_crowd"].rolling(int(n)).apply(lambda x: float((x <= x[-1]).mean() * 100.0), raw=True)
    w["available"] = release_time(w["report_date"])
    return w


def daily_features(weekly_feats: pd.DataFrame, index: pd.DatetimeIndex, windows: Iterable[int] = WINDOWS) -> pd.DataFrame:
    """The latest row known by each bar's open, on `index`; NaN before the first release."""
    cols = ["cot_crowd"] + [f"cot_pct_{n}" for n in windows]
    right = weekly_feats[["available"] + cols].sort_values("available")
    left = pd.DataFrame({"open_time": pd.DatetimeIndex(index)})
    merged = pd.merge_asof(left, right, left_on="open_time", right_on="available", direction="backward")
    out = merged[cols]
    out.index = pd.DatetimeIndex(index)
    return out


def build_carrycot_lake(
    lake, mirror_dir: Path, symbols: Iterable[str] | None = None, interval: str = "1d",
    count_start=None, count_end=None,
) -> pd.DataFrame:
    """Write the instrument per symbol and return counts — crowded weeks per threshold and window, no funding read against them."""
    tff = read_tff_zips(mirror_dir)
    rows = []
    for symbol in list(symbols) if symbols else list(BTC_ONLY):
        name = TFF_MARKETS[symbol]
        weekly = tff[tff["market"] == name]
        if weekly.empty:
            raise ValueError(f"no {name!r} rows in the TFF files; markets seen: {sorted(tff['market'].unique())[:12]}")
        feats = crowd_features(weekly)
        bars = lake.read_klines(symbol, interval, market=CARRY_MARKET)
        frame = bars.copy()
        daily = daily_features(feats, frame.index)
        for col in daily.columns:
            frame[col] = daily[col].to_numpy()
        frame.index.name = "open_time"
        lake.write_klines(symbol, frame, interval, market=MARKET)
        row = {"symbol": symbol, "market": name, "bars": len(frame), "start": frame.index[0], "end": frame.index[-1],
               "reports": int(len(feats)), "first_report": feats["report_date"].min().date(), "last_report": feats["report_date"].max().date(),
               "delayed_releases": int(((feats["available"] - feats["report_date"].dt.tz_localize("UTC")).dt.days == 7).sum()),
               "bars_with_feature": int(frame["cot_crowd"].notna().sum())}
        views = {"all": feats}
        if count_start is not None or count_end is not None:
            inside = feats
            if count_start is not None:
                inside = inside[inside["available"] >= pd.Timestamp(count_start, tz="UTC")]
            if count_end is not None:
                inside = inside[inside["available"] <= pd.Timestamp(count_end, tz="UTC")]
            views["window"] = inside
        for label, part in views.items():
            row[f"{label}_weeks"] = int(len(part))
            for n in WINDOWS:
                for p in GRID_P:
                    row[f"{label}_crowded_w{n}_p{p}"] = int((part[f"cot_pct_{n}"] >= p).sum())
        rows.append(row)
    return pd.DataFrame(rows)
