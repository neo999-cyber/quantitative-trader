"""The CFTC TFF parser, the carry-timer instrument (qr/data/cot.py) and the family (qr/strategies/cot.py)."""
from __future__ import annotations

import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from qr.config import paths
from qr.data.carry import CARRY_MARKET, carry_frames
from qr.data.cot import MARKET, build_carrycot_lake, crowd_features, daily_features, parse_tff, read_tff_zips, release_time
from qr.data.lake import Lake
from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.cot import CarryCrowdingTimer, block_shuffle

UTC = "UTC"
HEADER = '"Market_and_Exchange_Names","As_of_Date_In_Form_YYMMDD","Report_Date_as_YYYY-MM-DD","CFTC_Contract_Market_Code","Open_Interest_All","Dealer_Positions_Long_All","Lev_Money_Positions_Long_All","Lev_Money_Positions_Short_All","Pct_of_Open_Interest_All"'


def _tff_text(rows):
    lines = [HEADER]
    for market, date, oi, lo, sh in rows:
        yymmdd = pd.Timestamp(date).strftime("%y%m%d")
        lines.append(f'"{market}",{yymmdd},{date},133741,   {oi},    7064,    {lo},   {sh},  100.0')
    return "\n".join(lines) + "\n"


def test_the_parser_keeps_the_five_columns_and_strips_the_padding():
    text = _tff_text([("BITCOIN - CHICAGO MERCANTILE EXCHANGE", "2025-12-30", 20166, 2115, 13026), ("ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE", "2025-12-30", 100, 10, 50)])
    f = parse_tff(text)
    assert list(f.columns) == ["market", "report_date", "open_interest", "lev_long", "lev_short"]
    row = f.set_index("market").loc["BITCOIN - CHICAGO MERCANTILE EXCHANGE"]
    assert row["open_interest"] == 20166 and row["lev_long"] == 2115 and row["lev_short"] == 13026
    assert row["report_date"] == pd.Timestamp("2025-12-30")
    with pytest.raises(ValueError, match="lacks"):
        parse_tff("a,b,c\n1,2,3\n")


def test_release_is_saturday_in_an_ordinary_week_and_the_tuesday_after_in_a_holiday_week():
    stamps = release_time(["2024-02-20", "2024-07-02", "2024-11-26", "2024-12-24", "2024-09-03"])
    assert stamps[0] == pd.Timestamp("2024-02-24", tz=UTC)   # ordinary: Saturday
    assert stamps[1] == pd.Timestamp("2024-07-09", tz=UTC)   # 4 July on the Thursday
    assert stamps[2] == pd.Timestamp("2024-12-03", tz=UTC)   # Thanksgiving
    assert stamps[3] == pd.Timestamp("2024-12-31", tz=UTC)   # Christmas on the Wednesday
    assert stamps[4] == pd.Timestamp("2024-09-07", tz=UTC)   # Labor Day was the Monday before the report: no delay


def _weekly(n=60, start="2023-01-03"):
    dates = pd.date_range(start, periods=n, freq="7D")
    crowd_short = np.linspace(1000, 4000, n)              # the short grows every week
    return pd.DataFrame({"market": "X", "report_date": dates, "open_interest": 10000.0, "lev_long": 500.0, "lev_short": crowd_short})


def test_the_percentile_counts_the_trailing_reports_including_the_current_one():
    f = crowd_features(_weekly())
    assert f["cot_crowd"].iloc[0] == pytest.approx((1000 - 500) / 10000)
    assert f["cot_pct_26"].iloc[:25].isna().all() and f["cot_pct_26"].iloc[25] == 100.0   # a rising series: always the top
    assert f["cot_pct_52"].iloc[:51].isna().all() and f["cot_pct_52"].iloc[-1] == 100.0
    assert (f["available"] - f["report_date"].dt.tz_localize(UTC)).dt.days.isin([4, 7]).all()


def test_daily_bars_carry_the_latest_release_known_by_their_open():
    f = crowd_features(_weekly(n=30))
    index = pd.date_range("2023-06-01", "2023-07-31", freq="D", tz=UTC)
    d = daily_features(f, index)
    # the report of Tuesday 2023-06-27 is released Friday 30 June, usable from Saturday 1 July
    row = f.set_index("report_date").loc["2023-06-27"]
    assert d.loc[pd.Timestamp("2023-07-01", tz=UTC), "cot_crowd"] == pytest.approx(row["cot_crowd"])
    prev = f.set_index("report_date").loc["2023-06-20"]
    assert d.loc[pd.Timestamp("2023-06-30", tz=UTC), "cot_crowd"] == pytest.approx(prev["cot_crowd"])   # Friday still reads last week's


def _bars(index, px):
    return pd.DataFrame({"open": px, "high": px * 1.001, "low": px * 0.999, "close": px, "volume": 1e3, "quote_volume": 1e3 * px, "trades": 10}, index=index)


def _carry_panel(index, pct52, funding=1e-4):
    px = np.full(len(index), 100.0)
    unit = carry_frames(_bars(index, px), _bars(index, px * 1.001), pd.DataFrame({"funding_rate": np.full(len(index), funding)}, index=index))
    unit["cot_crowd"] = 0.1
    unit["cot_pct_52"] = pct52
    unit["cot_pct_26"] = pct52
    unit.index.name = "open_time"
    return Panel.from_frames({"BTCUSDT": unit})


def test_the_timer_is_out_while_crowded_and_the_controls_do_what_they_say():
    index = pd.date_range("2024-01-01", periods=365, freq="D", tz=UTC)
    pct = np.full(365, 50.0)
    pct[100:200] = 95.0
    panel = _carry_panel(index, pct)
    w = CarryCrowdingTimer(p=90, window=52).target_weights(panel)["BTCUSDT"]
    assert (w.iloc[:100] == 1.0).all() and (w.iloc[100:200] == 0.0).all() and (w.iloc[200:] == 1.0).all()
    assert (CarryCrowdingTimer(p=96, window=52).target_weights(panel)["BTCUSDT"] == 1.0).all()   # never crowded at this p
    assert (CarryCrowdingTimer(control="always_in").target_weights(panel)["BTCUSDT"] == 1.0).all()
    mirror = CarryCrowdingTimer(p=90, window=52, control="mirror").target_weights(panel)["BTCUSDT"]
    assert mirror.equals(1.0 - w)
    placebo = CarryCrowdingTimer(p=90, window=52, control="placebo").target_weights(panel)["BTCUSDT"]
    assert int((placebo == 0.0).sum()) == 100 and not placebo.equals(w)
    assert CarryCrowdingTimer(p=90, window=52, control="placebo").target_weights(panel)["BTCUSDT"].equals(placebo)
    with pytest.raises(ValueError):
        CarryCrowdingTimer(window=13)


def test_block_shuffle_moves_whole_blocks():
    flags = pd.DataFrame({"a": [True] * 10 + [False] * 20}, index=range(30))
    out = block_shuffle(flags, 10, seed=1)
    assert out["a"].sum() == 10
    blocks = [out["a"].iloc[i:i + 10].all() or (~out["a"].iloc[i:i + 10]).all() for i in (0, 10, 20)]
    assert all(blocks)


def test_the_timer_runs_through_the_ledger_and_collects_funding_only_while_in():
    index = pd.date_range("2024-01-01", periods=120, freq="D", tz=UTC)
    pct = np.full(120, 50.0)
    pct[40:80] = 95.0
    panel = _carry_panel(index, pct, funding=1e-3)
    res = run_backtest(panel, CarryCrowdingTimer(p=90, window=52), CostModel.carry_pair(CostModel.trial(half_spread_bps=0.0), CostModel.maker_measured()), engine="ledger")
    held = res.held["BTCUSDT"]
    assert held.iloc[42:80].abs().max() == 0.0 and held.iloc[10] > 0.9 and held.iloc[100] > 0.9
    assert res.carry is not None and res.carry.iloc[10] > 0 and res.carry.iloc[60] == 0.0
    assert int((res.turnover > 0).sum()) >= 3   # in at the start, out at the cliff, back in after it


def test_the_build_writes_the_instrument_and_counts_crowded_weeks(tmp_path):
    lake = Lake(paths(tmp_path / "lake").ensure())
    index = pd.date_range("2023-01-01", "2024-06-30", freq="D", tz=UTC)
    index.name = "open_time"
    px = np.full(len(index), 100.0)
    unit = carry_frames(_bars(index, px), _bars(index, px * 1.001), pd.DataFrame({"funding_rate": 1e-4}, index=index))
    lake.write_klines("BTCUSDT", unit, "1d", market=CARRY_MARKET)
    cftc = tmp_path / "cftc"
    cftc.mkdir()
    weekly = _weekly(n=80, start="2022-11-01")
    rows = [("BITCOIN - CHICAGO MERCANTILE EXCHANGE", d.strftime("%Y-%m-%d"), 10000, 500, int(s)) for d, s in zip(weekly["report_date"], weekly["lev_short"])]
    for year in (2022, 2023, 2024):
        text = _tff_text([r for r in rows if r[1].startswith(str(year))])
        with zipfile.ZipFile(cftc / f"fut_fin_txt_{year}.zip", "w") as zf:
            zf.writestr("FinFutYY.txt", text)
    tff = read_tff_zips(cftc)
    assert len(tff) == 80
    summary = build_carrycot_lake(lake, cftc, count_start="2023-06-01", count_end="2024-06-30")
    row = summary.iloc[0]
    assert row["reports"] == 80 and row["bars_with_feature"] > 0
    assert row["window_weeks"] < row["all_weeks"] == 80
    assert row["all_crowded_w26_p90"] >= row["all_crowded_w26_p95"] and row["all_crowded_w26_p90"] > 0
    panel = lake.load_panel(interval="1d", market=MARKET)
    assert {"cot_crowd", "cot_pct_26", "cot_pct_52", "funding_rate", "perp_funding_rate", "spot_close"} <= set(panel.fields)
    assert panel["funding_rate"].iloc[-1, 0] == pytest.approx(-1e-4)   # the short leg's sign survives the load
    with pytest.raises(FileNotFoundError):
        read_tff_zips(tmp_path / "empty")


def test_the_family_and_its_cost_model_are_reachable_from_the_cli():
    from types import SimpleNamespace

    from qr.cli import BASKETS, FAMILIES, _build_grid, _costs, _family_class

    assert FAMILIES["carry_crowding_timer"] == "CarryCrowdingTimer" and _family_class("carry_crowding_timer") is CarryCrowdingTimer
    assert BASKETS["eth"] == "qr.data.cot:ETH_ONLY"
    model = _costs(SimpleNamespace(costs="carry_maker", tier="VIP 0", bnb=True, spread=2.0))
    assert 2 * (model.fee_bps + model.half_spread_bps) == pytest.approx(21.5, abs=0.1) and model.funding
    assert len(_build_grid(CarryCrowdingTimer, ["p=[80,90,95]", "window=[26,52]"], None)) == 6
