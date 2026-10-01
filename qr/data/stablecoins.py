"""Total USD-pegged stablecoin supply, daily, from DefiLlama (Programme 3, P3-C input).

    https://stablecoins.llama.fi/stablecoincharts/all

Free, no key. One row a day since November 2017: `totalCirculatingUSD.peggedUSD`
is the dollar value of every USD-pegged stablecoin in circulation. The pull
is mirrored under `mirror/defillama/stablecoins/` and written to the lake as
`reference/stablecoin_supply`. Point-in-time caveat, stated: DefiLlama
restates history when it adds or fixes a coin's adapter; the series used
by a kill test is the mirrored file of its registration day, not a later
pull.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://stablecoins.llama.fi/stablecoincharts/all"
REFERENCE_NAME = "stablecoin_supply"


def fetch() -> list[dict]:
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        return json.loads(r.read())


def to_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame({"date": pd.to_datetime([int(r["date"]) for r in rows], unit="s", utc=True).normalize(),
                       "supply_usd": [float((r.get("totalCirculatingUSD") or {}).get("peggedUSD") or float("nan")) for r in rows]})
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def build(lake, mirror: Path, stamp: str) -> pd.DataFrame:
    rows = fetch()
    out = mirror / "defillama" / "stablecoins" / f"all_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows))
    df = to_frame(rows)
    lake.write_reference(REFERENCE_NAME, df, source="defillama")
    return df
