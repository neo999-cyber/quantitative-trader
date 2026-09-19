"""Ingest Databento XNAS.ITCH ohlcv bars from the mirror into the lake.

    export QR_ROOT=~/qr/lake
    .venv/bin/python scripts/databento_bars_ingest.py ohlcv-1m   # -> market xnas, interval 1m
    .venv/bin/python scripts/databento_bars_ingest.py ohlcv-1d   # -> market xnas, interval 1d

Raw Nasdaq bars, unadjusted, one series per raw ticker; `quote_volume` is
volume x close. `META` starts on 2022-06-09 for the reason in
`qr/data/auction.py`. Bars keep their own timestamps (UTC).
"""
import sys
from pathlib import Path

import databento as db
import pandas as pd

from qr.config import paths
from qr.data.auction import SYMBOL_START
from qr.data.lake import Lake

schema = sys.argv[1]
interval = {"ohlcv-1m": "1m", "ohlcv-1d": "1d"}[schema]
root = Path(paths().root) / "mirror" / "databento" / "XNAS.ITCH" / schema
files = sorted(root.rglob("*.dbn.zst"))
if not files:
    sys.exit(f"no files under {root}")
lake = Lake()
frames = []
for f in files:
    frames.append(db.DBNStore.from_file(f).to_df()[["symbol", "open", "high", "low", "close", "volume"]])
    print(f.name, flush=True)
bars = pd.concat(frames).sort_index()
for symbol, one in bars.groupby("symbol"):
    one = one.drop(columns="symbol")
    one.index = pd.DatetimeIndex(one.index).tz_convert("UTC")
    if interval == "1d":
        one.index = one.index.normalize()
    one = one[~one.index.duplicated(keep="last")]
    if symbol in SYMBOL_START:
        one = one[one.index >= pd.Timestamp(SYMBOL_START[symbol], tz="UTC")]
    one["quote_volume"] = one["volume"].astype(float) * one["close"].astype(float)
    one.index.name = "open_time"
    lake.write_klines(symbol, one, interval, source="databento", market="xnas")
    print(f"{symbol}: {len(one)} bars {one.index[0]} -> {one.index[-1]}", flush=True)
print("manifest", lake.manifest_hash())
