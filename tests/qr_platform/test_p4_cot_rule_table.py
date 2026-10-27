"""`scripts/p4_cot_rule_table.py`: the per-variant stats against the holding."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("rt", Path(__file__).resolve().parents[2] / "scripts" / "p4_cot_rule_table.py")
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)


def test_the_stats_read_the_yield_the_time_in_and_the_years():
    index = pd.date_range("2023-01-01", "2024-12-31", freq="D", tz="UTC")
    holding = pd.Series(0.0004, index=index)                    # 14.6% a year, every day
    timer = holding.copy()
    timer[index.year == 2024] = 0.0                              # out for all of 2024
    st = rt.variant_stats(timer)
    assert st["days_in_share"] == pytest.approx(365 / 731, abs=1e-3) and st["years"]["2023"] == pytest.approx(14.6, abs=0.01) and st["years"]["2024"] == 0.0
    tab = rt.sweep_table(pd.DataFrame({"carry_crowding_timer_x": timer}), reference=holding)
    row = tab.iloc[0]
    assert row["variant"] == "x" and row["vs_holding_ann_pct"] < 0 and row["years_ahead_of_holding"] == 0
    assert "2023:+14.6" in row["years"]
