"""Pull Bybit USDT-perp daily klines for every symbol whose funding is mirrored (C2). Laptop only.

    export QR_ROOT=~/qr/lake
    .venv/bin/python scripts/bybit_klines_pull.py
"""
from pathlib import Path

from qr.config import paths
from qr.data.bybit import pull_klines

root = paths(None).root
funding = sorted(p.stem for p in (root / "mirror" / "bybit" / "funding").glob("*.parquet"))
table = pull_klines(root / "mirror" / "bybit" / "klines_1d", symbols=funding)
print(table.to_string())
print(f"{len(funding)} symbols; {table['bars'].notna().sum() if 'bars' in table else 0} pulled")
