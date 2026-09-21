"""Pull SEC fails-to-deliver (2010 ->) and FINRA Reg SHO daily short volume (2010 ->) into the mirror.

    export QR_ROOT=~/qr/lake
    .venv/bin/python scripts/short_data_pull.py
"""
import pandas as pd
from pathlib import Path

from qr.config import paths
from qr.data.short_data import ftd_periods, pull_ftd, pull_regsho

root = Path(paths().root) / "mirror"
ftd = pull_ftd(root / "sec" / "ftd", ftd_periods("2010-01"))
print("ftd:", len(ftd), "files fetched;", int(ftd["note"].notna().sum()) if "note" in ftd else 0, "errors", flush=True)
days = pd.bdate_range("2010-01-04", pd.Timestamp.now().normalize())
sho = pull_regsho(root / "finra" / "regsho", days)
print("regsho:", len(sho), "files fetched;", int(sho["note"].notna().sum()) if "note" in sho else 0, "errors", flush=True)
