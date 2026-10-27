"""Exchange inflows as a selling signal (`docs/prereg/p4_exchange_inflow_v1.md`): the Coin Metrics loader and
the `inflow-um` instrument.

**The data.** Coin Metrics' community files (`mirror/coinmetrics/<asset>.csv`, one row a UTC day):
`FlowInExNtv` and `FlowOutExNtv` are coins moved onto and off the exchange addresses the vendor labels, from
April 2011 for bitcoin. The labelling is revised over time and the history is computed with today's labels —
the look-ahead the memo states before the run. `refresh_coinmetrics` fetches the files again (no key) and
keeps the previous copy beside them.

**When a row is known.** Day d's metrics are published the next day; the memo takes them as usable from
12:00 UTC on d + 1. On daily bars the first bar whose close follows that is d + 1 itself (its close is
24:00 UTC), so the signal of day d sits on the bar of d + 1 and a target set there fills at d + 1's close.

**The feature.** `net_d = FlowInExNtv − FlowOutExNtv`, standardised against the ninety days before d (the
day itself excluded; at least sixty of them), placed on bar d + 1 as `cm_netflow_z`.

**The instrument** is the BTCUSDT USDⓈ-M perpetual's daily bars (`futures/um`) with the venue's daily funding
sum (`futures-um`, the long pays a positive rate) and that one feature.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

MARKET = "inflow-um"
SOURCE = "binance"
PERP_MARKET = "futures/um"
FUNDING_MARKET = "futures-um"
BTC_ONLY = ("BTCUSDT",)
CM_FILES = {"BTCUSDT": "btc.csv", "ETHUSDT": "eth.csv"}
CM_URL = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/{asset}.csv"
WINDOW = 90
MIN_DAYS = 60
LAG_DAYS = 1
GRID_K = (1.0, 1.5, 2.0)
FEATURE = "cm_netflow_z"


def load_coinmetrics(path: Path) -> pd.DataFrame:
    """`time`, `FlowInExNtv`, `FlowOutExNtv` as a UTC-midnight-indexed frame; rows without both flows dropped."""
    frame = pd.read_csv(path, usecols=["time", "FlowInExNtv", "FlowOutExNtv"])
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.dropna(subset=["FlowInExNtv", "FlowOutExNtv"]).set_index("time").sort_index()
    return frame.astype(float)


def netflow_z(flows: pd.DataFrame, window: int = WINDOW, min_days: int = MIN_DAYS) -> pd.DataFrame:
    """Net inflow and its z against the trailing window (the day itself excluded)."""
    net = (flows["FlowInExNtv"] - flows["FlowOutExNtv"]).astype(float)
    prior = net.shift(1)
    mean = prior.rolling(window, min_periods=min_days).mean()
    sd = prior.rolling(window, min_periods=min_days).std()
    z = (net - mean) / sd.where(sd > 0)
    return pd.DataFrame({"net": net, "mean": mean, "sd": sd, "z": z})


def inflow_features(flows: pd.DataFrame, index: pd.DatetimeIndex, window: int = WINDOW, min_days: int = MIN_DAYS, lag_days: int = LAG_DAYS) -> pd.DataFrame:
    """`cm_netflow_z` on `index`: day d's z on the bar of d + `lag_days`, NaN elsewhere."""
    z = netflow_z(flows, window, min_days)["z"]
    z.index = pd.DatetimeIndex(z.index) + pd.Timedelta(days=lag_days)
    out = pd.DataFrame({FEATURE: z.reindex(pd.DatetimeIndex(index))})
    out.index = pd.DatetimeIndex(index)
    return out


def refresh_coinmetrics(mirror_dir: Path, assets: Iterable[str] = ("btc", "eth"), now: datetime | None = None, timeout: int = 120) -> dict:
    """Fetch each community file again; the previous copy is kept as `<asset>_<pulled_at>.csv`.

    A new file is accepted only if it parses, carries the two flow columns and runs at least as far as the old
    one — a short or malformed answer never replaces a good mirror.
    """
    import urllib.request

    mirror_dir = Path(mirror_dir)
    mirror_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    previous = (mirror_dir / "pulled_at.txt").read_text().strip() if (mirror_dir / "pulled_at.txt").exists() else "unknown"
    out = {}
    for asset in assets:
        target = mirror_dir / f"{asset}.csv"
        tmp = mirror_dir / f".{asset}_{stamp}.download"
        req = urllib.request.Request(CM_URL.format(asset=asset), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            tmp.write_bytes(r.read())
        new = load_coinmetrics(tmp)
        old_last = load_coinmetrics(target).index.max() if target.exists() else None
        if old_last is not None and new.index.max() < old_last:
            tmp.unlink()
            raise ValueError(f"{asset}: the fetched file ends {new.index.max().date()}, before the mirror's {old_last.date()}; kept the mirror")
        if target.exists():
            shutil.copy2(target, mirror_dir / f"{asset}_{previous}.csv")
        tmp.replace(target)
        out[asset] = {"last": str(new.index.max().date()), "rows_with_flows": int(len(new)), "previous_last": None if old_last is None else str(old_last.date())}
    (mirror_dir / "pulled_at.txt").write_text(stamp + "\n")
    return out


def build_inflow_lake(
    lake, mirror_dir: Path, symbols: Iterable[str] | None = None, window: int = WINDOW, min_days: int = MIN_DAYS,
    count_start=None, count_end=None,
) -> pd.DataFrame:
    """Write the instrument per symbol and return counts — signal days per threshold, no price read against them."""
    rows = []
    for symbol in list(symbols) if symbols else list(BTC_ONLY):
        flows = load_coinmetrics(Path(mirror_dir) / CM_FILES[symbol])
        bars = lake.read_klines(symbol, "1d", market=PERP_MARKET)
        keep = [c for c in ("open", "high", "low", "close", "volume", "quote_volume", "trades") if c in bars.columns]
        frame = bars[keep].copy()
        try:
            funding = lake.read_klines(symbol, "1d", market=FUNDING_MARKET)["funding_rate"]
        except FileNotFoundError:
            funding = pd.Series(dtype=float)
        frame["funding_rate"] = funding.reindex(frame.index)
        feats = inflow_features(flows, frame.index, window, min_days)
        frame[FEATURE] = feats[FEATURE].to_numpy()
        frame.index.name = "open_time"
        lake.write_klines(symbol, frame, "1d", market=MARKET)
        row = {"symbol": symbol, "bars": len(frame), "start": frame.index[0], "end": frame.index[-1],
               "funding_bars": int(frame["funding_rate"].notna().sum()),
               "flow_days": int(len(flows)), "flow_first": flows.index.min().date(), "flow_last": flows.index.max().date()}
        views = {"all": frame}
        if count_start is not None or count_end is not None:
            inside = frame
            if count_start is not None:
                inside = inside[inside.index >= pd.Timestamp(count_start, tz="UTC")]
            if count_end is not None:
                inside = inside[inside.index <= pd.Timestamp(count_end, tz="UTC")]
            views["window"] = inside
        for label, part in views.items():
            z = part[FEATURE]
            row[f"{label}_z_bars"] = int(z.notna().sum())
            for k in GRID_K:
                row[f"{label}_z_ge_{k}"] = int((z >= k).sum())
                row[f"{label}_z_le_minus_{k}"] = int((z <= -k).sum())
        rows.append(row)
    return pd.DataFrame(rows)
