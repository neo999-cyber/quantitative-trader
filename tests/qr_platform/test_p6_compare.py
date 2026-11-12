"""`scripts/p6_trend_compare.py`: the rule against its controls, on the median variant of each sweep; synthetic returns only."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("p6_trend_compare", Path(__file__).resolve().parents[2] / "scripts" / "p6_trend_compare.py")
cmp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cmp)

IDX = pd.bdate_range("2019-07-01", periods=1500, tz="UTC")


def _r(mean, sd, seed):
    return pd.Series(np.random.default_rng(seed).normal(mean, sd, len(IDX)), index=IDX)


def test_the_median_variant_is_not_the_best_of_n():
    noise = _r(0.0, 0.01, 1)                                                            # one noise, four drifts: the order is the drifts'
    frame = pd.DataFrame({"a": noise + 0.0010, "b": noise + 0.0006, "c": noise + 0.0002, "d": noise - 0.0002})
    order = sorted(frame.columns, key=lambda c: -cmp.sharpe(frame[c]))
    assert order == ["a", "b", "c", "d"] and cmp.median_variant(frame) == "b"          # rank 2 of 4
    assert cmp.median_variant(frame[["a", "b", "c"]]) == "b" and cmp.median_variant(frame[["c"]]) == "c"
    eight = pd.DataFrame({f"v{k}": noise + 0.001 - 0.0001 * k for k in range(8)})
    assert cmp.median_variant(eight) == "v3"                                            # rank 4 of 8


def test_newey_west_t_is_the_plain_t_without_serial_correlation_and_smaller_with_it():
    d = _r(0.001, 0.01, 7)                                                              # a mean about four standard errors from zero
    plain = d.mean() / (d.std(ddof=0) / math.sqrt(len(d)))
    assert cmp.newey_west_t(d, lags=0) == pytest.approx(plain, rel=1e-9)
    assert cmp.newey_west_t(d) == pytest.approx(plain, rel=0.25)                        # white noise: the lags change little
    smooth = d.rolling(10, min_periods=1).mean()                                        # the same mean, positively autocorrelated
    naive = smooth.mean() / (smooth.std(ddof=0) / math.sqrt(len(smooth)))
    assert 0 < cmp.newey_west_t(smooth) < 0.6 * naive
    assert math.isnan(cmp.newey_west_t(d.iloc[:10]))


def test_compare_finds_a_real_difference_and_not_a_shared_one():
    market = _r(0.0005, 0.012, 21)
    control = market + _r(0.0, 0.004, 22)
    better = market + _r(0.0008, 0.004, 23)                                             # twenty points a year on a 6% tracking error
    same = market + _r(0.0, 0.004, 24)
    hit, miss = cmp.compare(better, control), cmp.compare(same, control)
    assert hit["t"] > cmp.T_BAR and hit["mean_diff_pct_yr"] == pytest.approx(0.0008 * 252 * 100, rel=0.5) and hit["bars"] == len(IDX)
    assert abs(miss["t"]) < cmp.T_BAR and hit["sharpe_diff"] > miss["sharpe_diff"]


def test_the_script_reads_the_sweeps_and_writes_nothing_when_told(tmp_path, capsys):
    reports = tmp_path / "reports"
    reports.mkdir()
    market = _r(0.0005, 0.012, 31)
    pd.DataFrame({f"rule{k}": market + _r(0.0, 0.004, 40 + k) for k in range(8)}).to_parquet(reports / "p6_trend_reset_v1_variant_returns.parquet")
    pd.DataFrame({"trend": market + _r(0.0, 0.004, 50)}).to_parquet(reports / "p6_trend_reset_v1_trend_variant_returns.parquet")
    pd.DataFrame({f"p{k}": market + _r(0.0, 0.004, 60 + k) for k in range(8)}).to_parquet(reports / "p6_trend_reset_v1_placebo_variant_returns.parquet")
    pd.DataFrame({f"m{k}": market + _r(0.0, 0.004, 70 + k) for k in range(4)}).to_parquet(reports / "p6_trend_reset_v1_mirror_variant_returns.parquet")
    assert cmp.main(["--root", str(tmp_path), "--no-write"]) == 0
    out = capsys.readouterr().out
    assert "Not found, so not compared: `p6_trend_reset_v1_etf`, `p6_trend_reset_v1_etf_trend`" in out
    assert "| its trend filter alone | 1500 |" in out and "| its placebo | 1500 |" in out and "| its mirror | 1500 |" in out
    assert "Conditions (2)–(4) of the memo: **not met**" in out                          # eight books of the same market plus noise are not better than a ninth
