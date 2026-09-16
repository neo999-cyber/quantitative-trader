"""C5's pre-registered, mechanical universe read (docs/prereg/p2_oi_reversal_v1.md).

Run by the night chain after the OI metrics are ingested and BEFORE the
hypothesis is registered. Exit 0 only if every criterion below holds; the
criteria were written before any return was looked at, and this script reads
no returns. Prints what it saw so the amendment section can quote it.

    export QR_ROOT=~/qr/lake
    .venv/bin/python scripts/c5_universe_check.py
"""
import sys

import numpy as np
import pandas as pd

from qr.data.lake import Lake
from qr.data.universe import LEVERAGED_SUFFIXES, NOT_CRYPTO_ASSETS, UniverseSpec, membership

lake = Lake()
panel = lake.load_panel(interval="1d", market="futures/um", start="2021-12-01", end="2025-08-31")
oi = panel.get("open_interest")
if oi is None:
    sys.exit("FAIL: the perp panel carries no open_interest")
spec = UniverseSpec(n=150, rank_min=31, lookback=30, min_history=90, name="futures_um_ranks31_150")
m = membership(panel, spec)
members = m.sum(axis=1)
ever = list(m.any()[m.any()].index)
has_oi = oi[m].notna().sum() / m.sum().replace(0, np.nan)
bad_names = [s for s in ever if s in NOT_CRYPTO_ASSETS or s.endswith(LEVERAGED_SUFFIXES) or any(x in s for x in ("USDC", "BUSD", "TUSD", "FDUSD", "EUR", "GBP"))]
print(f"members per bar: median {members.median():.0f}, min {members.min()}, max {members.max()}; ever {len(ever)}")
print(f"share of member-bars with OI, median across names: {has_oi.median():.2f}; names below 0.5: {(has_oi < 0.5).sum()}")
print(f"OI observed from {oi.notna().any(axis=1).idxmax().date()}; sample bars {len(panel.index)}")
print("suspect names:", bad_names)
ok = members.median() >= 100 and has_oi.median() >= 0.8 and not bad_names and (oi.notna().any(axis=1).idxmax() <= pd.Timestamp("2022-03-01", tz="UTC"))
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
