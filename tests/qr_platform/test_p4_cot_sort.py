"""`scripts/p4_cot_sort.py`: the next-four-week funding and the non-overlapping sort."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("cs", Path(__file__).resolve().parents[2] / "scripts" / "p4_cot_sort.py")
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)


def test_next_funding_sums_the_28_days_from_each_release_and_annualises():
    index = pd.date_range("2024-01-01", periods=100, freq="D", tz="UTC")
    funding = pd.Series(0.0001, index=index)
    stamps = pd.DatetimeIndex([pd.Timestamp("2024-01-06", tz="UTC"), pd.Timestamp("2024-03-20", tz="UTC")])
    out = cs.next_funding(funding, stamps)
    assert out[0] == pytest.approx(0.0001 * 28 * 365 / 28 * 100) and np.isnan(out[1])   # the second window runs past the data


def test_the_sort_finds_a_planted_difference_on_non_overlapping_weeks():
    stamps = pd.date_range("2024-01-06", periods=104, freq="7D", tz="UTC")
    pct = np.where(np.arange(104) % 8 < 2, 95.0, 50.0)              # two crowded weeks in every eight
    weekly = pd.DataFrame({"available": stamps, "cot_pct_26": pct, "cot_pct_52": pct})
    days = pd.date_range("2024-01-01", periods=104 * 7 + 60, freq="D", tz="UTC")
    crowded_days = pd.Series(False, index=days)
    for a, c in zip(stamps, pct >= 90):
        if c:
            crowded_days[(days >= a) & (days < a + pd.Timedelta(days=28))] = True
    funding = pd.Series(np.where(crowded_days, 0.00005, 0.0003), index=days)   # the crowd earns less
    tab = cs.sort_table(weekly, funding, "2024-01-01", "2026-12-31", windows=(26,), grid_p=(90,))
    phase0 = tab[tab["phase"] == 0].iloc[0]
    assert phase0["weeks"] == 26 and phase0["crowded"] > 0 and phase0["diff_pct"] < 0 and phase0["t"] < -2
    assert set(tab["phase"]) == {0, 1, 2, 3}
