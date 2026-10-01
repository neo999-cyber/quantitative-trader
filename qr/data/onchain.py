"""Bitcoin on-chain basics from blockchain.com's public charts (Programme 3, P3-C input).

    https://api.blockchain.info/charts/<name>?timespan=all&format=json&sampled=false

Free, no key, daily since 2009: `hash-rate`, `n-unique-addresses`,
`n-transactions`. Mirrored under `mirror/blockchain_info/` and written to
the lake as `reference/onchain_btc` (one column per chart). These are
final once a day has closed; a point-in-time feature lags them one day.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://api.blockchain.info/charts/{name}?timespan=all&format=json&sampled=false"
CHARTS = ("hash-rate", "n-unique-addresses", "n-transactions")
REFERENCE_NAME = "onchain_btc"


def fetch(name: str) -> list[dict]:
    with urllib.request.urlopen(urllib.request.Request(URL.format(name=name), headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
        return json.loads(r.read())["values"]


def to_frame(series: dict[str, list[dict]]) -> pd.DataFrame:
    frames = []
    for name, values in series.items():
        s = pd.Series([float(v["y"]) for v in values], index=pd.to_datetime([int(v["x"]) for v in values], unit="s", utc=True).normalize(), name=name.replace("-", "_"))
        frames.append(s[~s.index.duplicated(keep="last")])
    df = pd.concat(frames, axis=1).sort_index()
    df.index.name = "date"
    return df.reset_index()


def build(lake, mirror: Path, stamp: str) -> pd.DataFrame:
    out = mirror / "blockchain_info"
    out.mkdir(parents=True, exist_ok=True)
    series = {}
    for name in CHARTS:
        values = fetch(name)
        (out / f"{name}_{stamp}.json").write_text(json.dumps(values))
        series[name] = values
        time.sleep(0.5)
    df = to_frame(series)
    lake.write_reference(REFERENCE_NAME, df, source="blockchain_info")
    return df
