"""The ETF-flow instrument (qr/data/etfflow.py) and the flow-pressure family (qr/strategies/etfflow.py)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qr.config import paths
from qr.data.etfflow import BTC_ONLY, MARKET, PERP_MARKET, build_etfflow_lake, decision_bars, entry_days, flow_features, flow_z
from qr.data.lake import Lake
from qr.data.panel import Panel
from qr.data.qa import trading_sessions
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.etfflow import HOLD_BARS, EtfFlowPressure

UTC = "UTC"


def test_the_scale_excludes_the_row_and_waits_for_enough_history():
    dates = pd.bdate_range("2024-01-02", periods=30)
    flow = pd.Series(100.0, index=dates)
    flow.iloc[10] = -300.0
    flow.iloc[25] = 0.0
    z = flow_z(flow, window=5, min_rows=3)
    assert z["z"].iloc[:3].isna().all()                              # fewer than three rows before them
    assert z["z"].iloc[3] == pytest.approx(1.0)
    assert z["z"].iloc[10] == pytest.approx(-3.0)                    # its own size is not in its denominator
    assert z["scale"].iloc[11] == pytest.approx((100.0 * 4 + 300.0) / 5)
    assert z["z"].iloc[25] == 0.0                                    # a flat day is zero, never a trade


def test_entry_days_follow_the_new_york_calendar():
    # Wed; the Thursday before Good Friday 2024; the Wednesday before 4 July; a Friday
    days = pd.DatetimeIndex(["2024-03-27", "2024-03-28", "2024-07-03", "2024-07-05"])
    t2 = entry_days(days, "t2")
    assert list(t2.strftime("%Y-%m-%d")) == ["2024-03-28", "2024-04-01", "2024-07-05", "2024-07-08"]
    assert entry_days(days, "t1").equals(days)
    with pytest.raises(ValueError):
        entry_days(days, "t0")


def test_the_decision_bar_closes_at_nine_new_york_in_both_halves_of_the_year():
    bars = decision_bars(pd.DatetimeIndex(["2024-07-08", "2024-01-08"]))
    assert bars[0] == pd.Timestamp("2024-07-08 12:00", tz=UTC)   # summer: 09:00 New York is 13:00 UTC
    assert bars[1] == pd.Timestamp("2024-01-08 13:00", tz=UTC)   # winter: 14:00 UTC


def _flows(start="2024-06-03", n=90, seed=1):
    dates = pd.bdate_range(start, periods=n)
    dates = dates[dates.isin(trading_sessions(dates[0], dates[-1]).tz_localize(None))]   # the issuer has no row on a holiday
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"date": dates, "flow_usd": rng.normal(0.0, 100e6, len(dates))})


def test_features_land_on_the_decision_bar_of_the_right_day_and_nowhere_else():
    flows = _flows()
    index = pd.date_range("2024-06-01", "2024-11-01", freq="h", tz=UTC)
    f = flow_features(flows, index, window=10, min_rows=5)
    z = flow_z(flows.set_index("date")["flow_usd"], 10, 5)
    friday = pd.Timestamp("2024-07-05")
    assert f.loc[pd.Timestamp("2024-07-05 12:00", tz=UTC), "etf_flow_z_t1"] == pytest.approx(z.loc[friday, "z"])
    assert f.loc[pd.Timestamp("2024-07-08 12:00", tz=UTC), "etf_flow_z_t2"] == pytest.approx(z.loc[friday, "z"])   # Monday
    assert f.loc[pd.Timestamp("2024-07-05 12:00", tz=UTC), "etf_flow_z_t2"] == pytest.approx(z.loc[pd.Timestamp("2024-07-03"), "z"])   # 4 July closed
    assert f.loc["2024-07-08", "etf_flow_z_t2"].notna().sum() == 1
    assert f["etf_flow_z_t2"].notna().sum() == z["z"].notna().sum() == f["etf_flow_z_t1"].notna().sum()
    assert f.attrs["unplaced_t2"] == 0 and f.attrs["collisions_t2"] == 0


def _panel(index, z_t2=None, z_t1=None, funding=None, price=None):
    n = len(index)
    px = np.full(n, 100.0) if price is None else np.asarray(price, dtype=float)
    frame = pd.DataFrame({"open": px, "high": px * 1.001, "low": px * 0.999, "close": px, "volume": 10.0, "quote_volume": 10.0 * px}, index=index)
    frame["etf_flow_z_t2"] = np.nan if z_t2 is None else z_t2
    frame["etf_flow_z_t1"] = np.nan if z_t1 is None else z_t1
    if funding is not None:
        frame["funding_rate"] = funding
    frame.index.name = "open_time"
    return Panel.from_frames({"BTCUSDT": frame}, interval="1h")


def test_the_session_hold_is_seven_bars_from_the_decision_and_the_day_hold_twenty_four():
    index = pd.date_range("2024-07-08", periods=24 * 5, freq="h", tz=UTC)
    z = pd.Series(np.nan, index=index)
    z[pd.Timestamp("2024-07-08 12:00", tz=UTC)] = 1.4     # long
    z[pd.Timestamp("2024-07-09 12:00", tz=UTC)] = -0.8    # under k = 1: nothing
    z[pd.Timestamp("2024-07-10 12:00", tz=UTC)] = -2.0    # short
    z[pd.Timestamp("2024-07-11 12:00", tz=UTC)] = 0.0     # a flat day
    panel = _panel(index, z_t2=z.to_numpy())
    w = EtfFlowPressure(k=1.0, hold="session").target_weights(panel)["BTCUSDT"]
    day8, day10 = w.loc["2024-07-08"], w.loc["2024-07-10"]
    assert day8[day8 != 0].index.hour.tolist() == list(range(12, 19)) and (day8[day8 != 0] == 1.0).all()
    assert (w.loc["2024-07-09"] == 0.0).all() and (w.loc["2024-07-11"] == 0.0).all()
    assert int((day10 != 0).sum()) == 7 and (day10[day10 != 0] == -1.0).all()
    w24 = EtfFlowPressure(k=1.0, hold="24h").target_weights(panel)["BTCUSDT"]
    assert w24[pd.Timestamp("2024-07-08 12:00", tz=UTC):pd.Timestamp("2024-07-09 11:00", tz=UTC)].eq(1.0).all()
    assert w24[pd.Timestamp("2024-07-09 12:00", tz=UTC)] == 0.0
    assert int((w24 != 0).sum()) == 2 * HOLD_BARS["24h"]
    # the diagnostic arm reads its own column, which here is empty
    assert (EtfFlowPressure(k=1.0, timing="t1").target_weights(panel) == 0.0).all().all()


def test_the_controls_mirror_shuffle_within_month_and_buy_every_eligible_day():
    index = pd.date_range("2024-07-01", "2024-09-30 23:00", freq="h", tz=UTC)
    days = pd.bdate_range("2024-07-01", "2024-09-27")
    bars = pd.DatetimeIndex([pd.Timestamp(f"{d.date()} 12:00", tz=UTC) for d in days])
    z = pd.Series(np.nan, index=index)
    z[bars] = np.random.default_rng(3).normal(0.0, 1.5, len(bars))
    panel = _panel(index, z_t2=z.to_numpy())
    base = EtfFlowPressure(k=1.0).target_weights(panel)["BTCUSDT"]
    assert EtfFlowPressure(k=1.0, control="mirror").target_weights(panel)["BTCUSDT"].equals(-base)
    always = EtfFlowPressure(k=1.0, control="always_long").target_weights(panel)["BTCUSDT"]
    assert int((always != 0).sum()) == 7 * len(bars) and (always[always != 0] == 1.0).all()
    placebo = EtfFlowPressure(k=1.0, control="placebo").target_weights(panel)["BTCUSDT"]
    by_month = lambda s: pd.Series(s[bars].to_numpy(), index=bars).groupby(bars.month).agg(["sum", lambda x: (x != 0).sum()])
    pd.testing.assert_frame_equal(by_month(base), by_month(placebo))   # the same flows in each month, on other days
    assert not placebo.equals(base)
    assert EtfFlowPressure(k=1.0, control="placebo").target_weights(panel)["BTCUSDT"].equals(placebo)   # seeded


def test_a_session_trade_runs_through_the_ledger_and_pays_the_four_oclock_settlement():
    index = pd.date_range("2024-07-08", periods=48, freq="h", tz=UTC)
    price = np.full(48, 100.0)
    price[13:] = 101.0                       # the move lands on the first bar held
    z = np.full(48, np.nan)
    z[12] = 2.0                              # the decision bar closes at 13:00 UTC = 09:00 New York
    funding = np.zeros(48)
    funding[15] = 0.0001                     # the 16:00 UTC settlement, paid by the book held over the 15:00 bar
    panel = _panel(index, z_t2=z, funding=funding, price=price)
    free = CostModel(fee_bps=0.0, half_spread_bps=0.0, funding=True, name="free_perp")
    res = run_backtest(panel, EtfFlowPressure(k=1.0, hold="session"), free, engine="ledger")
    held = res.held["BTCUSDT"]
    assert held.iloc[13:20].round(6).eq(1.0).all() and held.iloc[12] == 0.0 and held.iloc[20] == 0.0
    assert res.gross.iloc[13] == pytest.approx(0.01, abs=1e-6)
    assert res.carry is not None and res.carry.iloc[15] == pytest.approx(-0.0001, rel=1e-3)   # the whole NAV is in the position
    assert res.carry.drop(res.carry.index[15]).abs().sum() == 0.0
    measured = CostModel.maker_measured(day_type="weekday")
    haircut = run_backtest(panel, EtfFlowPressure(k=1.0, hold="session"), measured, engine="ledger")
    assert haircut.held["BTCUSDT"].iloc[14] == pytest.approx(measured.fill_rate, rel=1e-3)   # the measured fill rate scales the book
    assert haircut.net.sum() < res.net.sum()


class _Bucket:
    def __init__(self, settlements):
        self.settlements = settlements

    def load_funding(self, symbol):
        return self.settlements


def test_the_build_writes_the_instrument_and_the_lake_loads_it_with_its_funding_intact(tmp_path):
    lake = Lake(paths(tmp_path / "lake").ensure())
    index = pd.date_range("2024-06-01", "2024-10-31 23:00", freq="h", tz=UTC)
    index.name = "open_time"
    px = 100.0 + np.cumsum(np.random.default_rng(0).normal(0, 0.1, len(index)))
    bars = pd.DataFrame({"open": px, "high": px * 1.001, "low": px * 0.999, "close": px, "volume": 10.0, "quote_volume": 10.0 * px, "trades": 5}, index=index)
    lake.write_klines("BTCUSDT", bars, "1h", market=PERP_MARKET)
    flows = _flows()
    lake.write_reference("etf_flows_ishares_daily", flows.assign(ticker="IBIT", nav=50.0, shares_outstanding=1.0, shares_change=0.0, snapshot="test"), source="test")
    stamps = pd.date_range("2024-06-01 08:00", "2024-11-01", freq="8h", tz=UTC)
    settlements = pd.DataFrame({"funding_rate": 0.0001}, index=stamps)
    summary = build_etfflow_lake(lake, _Bucket(settlements), window=10, min_rows=5, count_start="2024-08-01", count_end="2024-09-30")
    row = summary.iloc[0]
    assert row["symbol"] == "BTCUSDT" and row["settlements"] > 0 and row["unplaced_t2"] == 0
    assert row["all_t2_decision_bars"] == row["all_t1_decision_bars"] > row["window_t2_decision_bars"] > 0
    assert row["all_t2_abs_z_ge_0.5"] >= row["all_t2_abs_z_ge_1.0"] >= row["all_t2_abs_z_ge_1.5"]
    panel = lake.load_panel(interval="1h", market=MARKET)
    assert panel.symbols == list(BTC_ONLY) and {"etf_flow_z_t2", "etf_flow_z_t1", "funding_rate"} <= set(panel.fields)
    # the venue's sign: the rate is stored as published, a long pays a positive rate, and the settlement sits on the
    # bar that closes at the settlement time (the 07:00 bar for 08:00)
    rate = panel["funding_rate"]["BTCUSDT"]
    assert rate[pd.Timestamp("2024-07-08 07:00", tz=UTC)] == pytest.approx(0.0001) and rate[pd.Timestamp("2024-07-08 08:00", tz=UTC)] == 0.0
    assert panel["etf_flow_z_t2"]["BTCUSDT"].notna().sum() == row["all_t2_decision_bars"]


def test_the_family_and_its_cost_model_are_reachable_from_the_cli():
    from types import SimpleNamespace

    from qr.cli import BASKETS, FAMILIES, _build_grid, _costs, _family_class

    assert FAMILIES["etf_flow_pressure"] == "EtfFlowPressure" and _family_class("etf_flow_pressure") is EtfFlowPressure
    assert BASKETS["btc"] == "qr.data.etfflow:BTC_ONLY"
    model = _costs(SimpleNamespace(costs="maker", tier="VIP 0", bnb=True, spread=2.0))
    assert model.use_maker and model.funding and 0.9 < model.fill_rate < 1.0 and model.fill_rate_by_dow is None
    grid = _build_grid(EtfFlowPressure, ["k=[0.5,1.0,1.5]", 'hold=["session","24h"]'], ["timing=t2"])
    assert len(grid) == 6 and {s.params["timing"] for s in grid} == {"t2"}
