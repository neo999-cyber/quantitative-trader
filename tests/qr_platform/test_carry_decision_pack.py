"""`scripts/carry_decision_pack.py` on a synthetic lake: the yearly table, the per-symbol stats, the capital views, the page."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("pack", Path(__file__).resolve().parents[2] / "scripts" / "carry_decision_pack.py")
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


@pytest.fixture
def lake(tmp_path):
    idx = pd.date_range("2024-01-01", "2025-12-31", freq="D", tz="UTC")
    for sym, daily in (("BTCUSDT", 0.0003), ("ETHUSDT", 0.0002), ("SOLUSDT", -0.0001)):
        d = tmp_path / "raw" / "binance" / "carry-um" / "klines" / "interval=1d" / f"symbol={sym}"
        d.mkdir(parents=True)
        rate = pd.Series(daily, index=idx)
        if sym == "BTCUSDT":
            rate[idx.year == 2025] = 0.0001           # a thinner second year
        pd.DataFrame({"open_time": idx, "close": 1.0, pack.COL: rate.to_numpy()}).to_parquet(d / "data.parquet")
    r = tmp_path / "reference"
    r.mkdir()
    rf = pd.DataFrame({"date": idx, "rate": np.where(idx.year == 2024, 0.05, 0.04), "series": "DTB3"})
    rf.to_parquet(r / "risk_free_dtb3.parquet")
    return tmp_path


def test_yearly_table_annualises_and_subtracts_the_bill(lake):
    out = pack.build(lake)
    tab = out["yearly"]
    assert tab.loc[2024, "BTCUSDT"] == pytest.approx(0.0003 * 365 * 100, abs=0.05)   # 10.95
    assert tab.loc[2025, "BTCUSDT"] == pytest.approx(0.0001 * 365 * 100, abs=0.05)   # 3.65
    assert tab.loc[2024, "T-bill"] == pytest.approx(5.0) and tab.loc[2025, "T-bill"] == pytest.approx(4.0)
    assert tab.loc[2025, "BTCUSDT − T-bill"] == pytest.approx(3.65 - 4.0, abs=0.06)   # the table is rounded to one decimal
    assert tab.loc[2024, "SOLUSDT"] < 0


def test_symbol_stats_count_negative_months_and_the_worst_window(lake):
    s = pack.symbol_stats(pack.load_funding(lake, "SOLUSDT"))
    assert s["negative_months"] == s["months"] == 24 and s["share_days_funding_le_0"] == 1.0
    assert s["worst_90d_pct"] == pytest.approx(-0.0001 * 90 * 100, abs=0.01) and s["last_365d_pct"] == pytest.approx(-3.65, abs=0.06)
    b = pack.symbol_stats(pack.load_funding(lake, "BTCUSDT"))
    assert b["negative_months"] == 0 and b["last_365d_pct"] == pytest.approx(3.65, abs=0.06)


def test_capital_views_halve_at_1x_and_charge_one_round_trip():
    v = pack.capital_views(10.0)
    assert v["net_of_one_round_trip_pct"] == pytest.approx(10.0 - 0.215, abs=0.006)   # rounded to two decimals
    assert v["on_capital_at_1x_pct"] == pytest.approx((10.0 - 0.215) / 2, abs=0.006) and v["on_capital_at_2_5x_pct"] == pytest.approx((10.0 - 0.215) / 1.4, abs=0.006)


def test_main_writes_the_page_and_the_json(lake, tmp_path, capsys):
    out = tmp_path / "out"
    assert pack.main(["--lake", str(lake), "--date", "2026-01-01", "--out", str(out)]) == 0
    md = (out / "funding_history_2026-01-01.md").read_text()
    assert "| 2024 |" in md and "| BTCUSDT |" in md and "on capital at 1×" in md
    assert (out / "funding_history_2026-01-01.json").exists() and "T-bill" in capsys.readouterr().out
