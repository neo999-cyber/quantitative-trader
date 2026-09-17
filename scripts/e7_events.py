"""E7 event file for QuantConnect (docs/prereg/p2_short_squeeze_v1.md): per FINRA
settlement date, the top-10 days-to-cover names among rising-FTD names, the
low-cover mirror and a random draw, each stamped with the date after which
both source files were public. Reads no price series.

    export QR_ROOT=~/qr/lake
    .venv/bin/python scripts/e7_events.py
"""
import base64
import hashlib
import json
import glob
import random
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from qr.data.short_data import load_finra_si, load_ftd

root = Path.home() / "qr/lake/mirror"
si = load_finra_si(root / "finra/shortinterest")
ftd = load_ftd(root / "sec/ftd")
si["settlement_date"] = pd.to_datetime(si.settlement_date)
si = si[si.settlement_date >= "2019-01-01"]

# ---- availability, the conservative rule of the pre-registration
si_meta = pd.DataFrame([json.load(open(f)) for f in sorted(glob.glob(str(root / "finra/shortinterest/*.json")))])
si_meta["day"] = pd.to_datetime(si_meta.day)
si_meta["observed"] = pd.to_datetime(si_meta.published_at, utc=True).dt.tz_localize(None)
si_meta["rule"] = si_meta.day + pd.Timedelta(days=20)
# a stamp is credible when it sits 0-60 days after settlement; FINRA's whole
# 2019-2023 archive carries a 2023-07-27 regeneration stamp, which is not a
# publication date (amendment, docs/prereg/p2_short_squeeze_v1_amendment.md)
si_ok = (si_meta.observed > si_meta.day) & (si_meta.observed <= si_meta.day + pd.Timedelta(days=60))
si_meta["avail"] = np.where(si_ok, si_meta[["observed", "rule"]].max(axis=1), si_meta["rule"])
si_avail = dict(zip(si_meta.day, si_meta.avail))

ftd_meta = pd.DataFrame([json.load(open(f)) for f in sorted(glob.glob(str(root / "sec/ftd/*.json")))])
ftd_meta["observed"] = pd.to_datetime(ftd_meta.published_at, utc=True).dt.tz_localize(None)


def half_end(p):
    y, mo, h = int(p[:4]), int(p[4:6]), p[6]
    return pd.Timestamp(y, mo, 15) if h == "a" else pd.Timestamp(y, mo, 1) + pd.offsets.MonthEnd(0)


ftd_meta["end"] = ftd_meta.period.map(half_end)
ftd_meta["rule"] = ftd_meta["end"] + pd.Timedelta(days=20)
credible = (ftd_meta.observed > ftd_meta["end"]) & (ftd_meta.observed <= ftd_meta["end"] + pd.Timedelta(days=60))
ftd_meta["avail"] = np.where(credible, ftd_meta[["observed", "rule"]].max(axis=1), ftd_meta["rule"])
ftd_avail = dict(zip(ftd_meta.period, pd.to_datetime(ftd_meta.avail)))

# ---- rising fails per half
f = ftd.copy()
f["period"] = f.settlement_date.dt.strftime("%Y%m") + np.where(f.settlement_date.dt.day <= 15, "a", "b")
f["value"] = f.fails * f.price
agg = f.groupby(["period", "symbol"]).agg(fails_value=("value", "sum"), price=("price", "last")).reset_index()
periods = sorted(agg.period.unique())
prev = {p: periods[i - 1] for i, p in enumerate(periods) if i > 0}
agg["prev_period"] = agg.period.map(prev)
agg = agg.merge(
    agg[["period", "symbol", "fails_value"]].rename(columns={"period": "prev_period", "fails_value": "prev_value"}),
    on=["prev_period", "symbol"], how="left",
)
agg["prev_value"] = agg.prev_value.fillna(0.0)
agg["rising"] = (agg.fails_value >= 2 * agg.prev_value) & (agg.fails_value >= 5e5)

s = si[si.adv >= 1e6].copy()
s["period"] = s.settlement_date.dt.strftime("%Y%m") + np.where(s.settlement_date.dt.day <= 15, "a", "b")
j = s.merge(agg[["period", "symbol", "rising", "price"]], on=["period", "symbol"], how="inner")
q = j[j.rising & (j.price >= 5)].copy()

rng = random.Random(7)
rows = []
for date, g in q.groupby("settlement_date"):
    period = g.period.iloc[0]
    if date not in si_avail or period not in ftd_avail:
        continue
    avail = max(si_avail[date], ftd_avail[period])
    g = g.sort_values("days_to_cover", ascending=False)
    top = list(g.symbol.head(10))
    bottom = list(g.sort_values("days_to_cover", ascending=True).symbol.head(10))
    pool = list(g.symbol)
    rnd = rng.sample(pool, min(10, len(pool)))
    for mode, names in (("top", top), ("bottom", bottom), ("random", rnd)):
        for rank, sym in enumerate(names, 1):
            rows.append((avail.strftime("%Y-%m-%d"), sym, mode, rank, date.strftime("%Y-%m-%d")))

out = pd.DataFrame(rows, columns=["avail_date", "symbol", "mode", "rank", "settlement_date"])
csv = out.to_csv(index=False)
digest = hashlib.sha256(csv.encode()).hexdigest()
Path("qc/e7_events.b64").write_text(base64.b64encode(zlib.compress(csv.encode(), 9)).decode())
print(out.groupby("mode").size().to_dict(), "dates", out.settlement_date.nunique(), "sha256", digest[:16])
print("availability lag (days) from settlement:", (pd.to_datetime(out.avail_date) - pd.to_datetime(out.settlement_date)).dt.days.describe()[["min", "50%", "max"]].to_dict())
print(out.head(3).to_string())
