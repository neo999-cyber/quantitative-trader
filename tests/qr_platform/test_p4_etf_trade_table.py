"""`scripts/p4_etf_trade_table.py`: the per-trade sums and the variant-name parser."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("tt", Path(__file__).resolve().parents[2] / "scripts" / "p4_etf_trade_table.py")
tt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tt)


def test_the_variant_name_parses_and_the_trade_sums_follow_the_hold():
    p = tt.parse_variant("etf_flow_pressure_controlnone_gross1_hold24h_k1p5_timingt2")
    assert p == {"control": "none", "hold": "24h", "k": 1.5, "timing": "t2"}
    q = tt.parse_variant("etf_flow_pressure_controlalways_long_gross1_holdsession_k0_timingt2")
    assert q["k"] == 0.0 and q["control"] == "always_long" and q["hold"] == "session"
    net = np.zeros(40)
    net[13:20] = 0.001          # a session trade decided on bar 12: seven bars of 10 bps
    net[31:34] = -0.002
    assert tt.per_trade(net, np.array([12]), 7).tolist() == [np.float64(0.007)] or abs(tt.per_trade(net, np.array([12]), 7)[0] - 0.007) < 1e-12
    assert len(tt.per_trade(net, np.array([12, 36]), 7)) == 1   # the entry cut by the sample's end is dropped


def test_the_sweep_table_counts_sides_and_entries():
    index = pd.date_range("2024-07-01", periods=24 * 6, freq="h", tz="UTC")
    z = pd.Series(np.nan, index=index)
    z.iloc[12], z.iloc[36], z.iloc[60] = 2.0, -2.0, 0.5
    r = pd.DataFrame({"etf_flow_pressure_controlnone_gross1_holdsession_k1_timingt2": 0.0}, index=index)
    r.iloc[13:20, 0] = 0.001
    r.iloc[37:44, 0] = 0.002
    tab = tt.sweep_table(r, {"t2": z, "t1": z}, 365 * 24)
    row = tab.iloc[0]
    assert row["entries"] == 2 and row["long"] == 1 and row["short"] == 1
    assert row["mean_net_bps"] == 105.0 and row["hit_rate"] == 1.0
