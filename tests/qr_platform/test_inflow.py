"""The Coin Metrics loader, the inflow instrument (qr/data/inflow.py) and the fade family (qr/strategies/inflow.py)."""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from qr.config import paths
from qr.data.inflow import FEATURE, FUNDING_MARKET, MARKET, PERP_MARKET, build_inflow_lake, inflow_features, load_coinmetrics, netflow_z, refresh_coinmetrics
from qr.data.lake import Lake
from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.inflow import ExchangeInflowFade, _one_at_a_time

UTC = "UTC"


def _flows(n=400, start="2021-01-01", seed=0):
    idx = pd.date_range(start, periods=n, freq="D", tz=UTC)
    rng = np.random.default_rng(seed)
    inflow = rng.normal(1000.0, 100.0, n)
    out = rng.normal(1000.0, 100.0, n)
    return pd.DataFrame({"FlowInExNtv": inflow, "FlowOutExNtv": out}, index=idx)


def _csv_text(frame):
    f = frame.copy()
    f.insert(0, "time", f.index.strftime("%Y-%m-%d"))
    f["AdrActCnt"] = 1
    return f.reset_index(drop=True)[["time", "AdrActCnt", "FlowInExNtv", "FlowOutExNtv"]].to_csv(index=False)


def test_the_z_reads_only_the_days_before_and_waits_for_sixty_of_them():
    flows = _flows()
    flows.iloc[200, 0] += 5000.0   # a big inflow day
    z = netflow_z(flows, window=90, min_days=60)
    assert z["z"].iloc[:60].isna().all() and z["z"].iloc[60:].notna().all()
    prior = (flows["FlowInExNtv"] - flows["FlowOutExNtv"]).iloc[110:200]
    assert z["mean"].iloc[200] == pytest.approx(prior.mean()) and z["sd"].iloc[200] == pytest.approx(prior.std())
    assert z["z"].iloc[200] > 10
    assert z["mean"].iloc[201] > z["mean"].iloc[200]   # the spike enters the next day's window, not its own


def test_the_feature_sits_on_the_bar_after_the_day_it_measures():
    flows = _flows()
    index = pd.date_range("2021-01-01", periods=420, freq="D", tz=UTC)
    f = inflow_features(flows, index)
    z = netflow_z(flows)["z"]
    d = pd.Timestamp("2021-10-01", tz=UTC)
    assert f.loc[d + pd.Timedelta(days=1), FEATURE] == pytest.approx(z.loc[d])
    assert f[FEATURE].notna().sum() == z.notna().sum()


def test_one_at_a_time_skips_a_signal_inside_an_open_hold():
    fire = np.zeros(20, dtype=bool)
    fire[[3, 4, 5, 12]] = True
    t = _one_at_a_time(fire, 3)
    assert t[3:6].tolist() == [1.0, 1.0, 1.0] and t[6] == 0.0 and t[12:15].tolist() == [1.0] * 3 and t.sum() == 6


def _panel(index, z, price=None, funding=None):
    px = np.full(len(index), 100.0) if price is None else np.asarray(price, dtype=float)
    frame = pd.DataFrame({"open": px, "high": px * 1.001, "low": px * 0.999, "close": px, "volume": 10.0, "quote_volume": 10.0 * px}, index=index)
    frame[FEATURE] = z
    if funding is not None:
        frame["funding_rate"] = funding
    frame.index.name = "open_time"
    return Panel.from_frames({"BTCUSDT": frame})


def test_the_fade_shorts_for_h_bars_and_the_controls_do_what_they_say():
    index = pd.date_range("2024-01-01", periods=400, freq="D", tz=UTC)
    z = np.zeros(400)
    z[[10, 11, 50, 300]] = 2.0
    z[[100, 101]] = -2.0
    panel = _panel(index, z)
    w = ExchangeInflowFade(k=1.5, h=3).target_weights(panel)["BTCUSDT"]
    assert (w.iloc[10:13] == -1.0).all() and w.iloc[13] == 0.0 and (w.iloc[50:53] == -1.0).all() and int((w != 0).sum()) == 9
    long = ExchangeInflowFade(k=1.5, h=2, control="mirror").target_weights(panel)["BTCUSDT"]
    assert (long.iloc[100:102] == 1.0).all() and int((long != 0).sum()) == 2
    placebo = ExchangeInflowFade(k=1.5, h=3, control="placebo").target_weights(panel)["BTCUSDT"]
    assert (placebo.iloc[190:193] == -1.0).all() and placebo.iloc[10] == 0.0    # the signal of day 10 lands 180 days later
    random = ExchangeInflowFade(k=1.5, h=3, control="random").target_weights(panel)["BTCUSDT"]
    assert int((random != 0).sum()) <= 12 and (random[random != 0] == -1.0).all()
    assert ExchangeInflowFade(k=1.5, h=3, control="random").target_weights(panel)["BTCUSDT"].equals(random)


def test_a_short_runs_through_the_ledger_and_receives_the_funding():
    index = pd.date_range("2024-01-01", periods=30, freq="D", tz=UTC)
    price = np.full(30, 100.0)
    price[11:] = 99.0                        # the drop lands on the first bar held
    z = np.zeros(30)
    z[10] = 2.0
    funding = np.zeros(30)
    funding[12] = 0.0005                     # longs pay 5 bps on the second bar held: the short receives it
    panel = _panel(index, z, price, funding)
    free = CostModel(fee_bps=0.0, half_spread_bps=0.0, funding=True, name="free_perp")
    res = run_backtest(panel, ExchangeInflowFade(k=1.5, h=3), free, engine="ledger")
    held = res.held["BTCUSDT"]
    assert held.iloc[11:14].round(6).eq(-1.0).all() and held.iloc[10] == 0.0 and held.iloc[14] == 0.0
    assert res.gross.iloc[11] == pytest.approx(0.01, abs=1e-6)
    assert res.carry is not None and res.carry.iloc[12] == pytest.approx(0.0005, rel=1e-3) and res.carry.drop(res.carry.index[12]).abs().sum() == 0.0


def test_the_build_writes_the_instrument_and_the_lake_loads_it(tmp_path):
    lake = Lake(paths(tmp_path / "lake").ensure())
    index = pd.date_range("2021-01-01", periods=420, freq="D", tz=UTC)
    index.name = "open_time"
    px = 100.0 + np.cumsum(np.random.default_rng(1).normal(0, 1, len(index)))
    lake.write_klines("BTCUSDT", pd.DataFrame({"open": px, "high": px * 1.01, "low": px * 0.99, "close": px, "volume": 10.0, "quote_volume": 10.0 * px, "trades": 5}, index=index), "1d", market=PERP_MARKET)
    lake.write_klines("BTCUSDT", pd.DataFrame({"funding_rate": 0.0003, "open_interest": 1.0, "open_interest_usd": 1.0}, index=index), "1d", market=FUNDING_MARKET)
    cm = tmp_path / "coinmetrics"
    cm.mkdir()
    (cm / "btc.csv").write_text(_csv_text(_flows()))
    summary = build_inflow_lake(lake, cm, count_start="2021-06-01", count_end="2021-12-31")
    row = summary.iloc[0]
    assert row["flow_days"] == 400 and row["funding_bars"] == 420 and row["all_z_bars"] == 340
    assert row["all_z_ge_1.0"] >= row["all_z_ge_1.5"] >= row["all_z_ge_2.0"] and row["window_z_bars"] < row["all_z_bars"]
    panel = lake.load_panel(interval="1d", market=MARKET)
    assert {FEATURE, "funding_rate"} <= set(panel.fields) and panel["funding_rate"].iloc[5, 0] == pytest.approx(0.0003)


def test_the_refresh_keeps_the_old_copy_and_refuses_a_shorter_file(tmp_path, monkeypatch):
    import urllib.request

    cm = tmp_path / "coinmetrics"
    cm.mkdir()
    old = _flows(n=100)
    (cm / "btc.csv").write_text(_csv_text(old))
    (cm / "pulled_at.txt").write_text("2026-10-13\n")

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    payload = {"new": _csv_text(_flows(n=130)).encode(), "short": _csv_text(_flows(n=50)).encode()}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _Resp(payload["new"]))
    out = refresh_coinmetrics(cm, assets=("btc",), now=pd.Timestamp("2026-10-27").to_pydatetime())
    assert out["btc"]["rows_with_flows"] == 130 and (cm / "btc_2026-10-13.csv").exists() and (cm / "pulled_at.txt").read_text().strip() == "2026-10-27"
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _Resp(payload["short"]))
    with pytest.raises(ValueError, match="before the mirror"):
        refresh_coinmetrics(cm, assets=("btc",))
    assert len(load_coinmetrics(cm / "btc.csv")) == 130


def test_the_family_and_its_cost_model_are_reachable_from_the_cli():
    from types import SimpleNamespace

    from qr.cli import FAMILIES, _build_grid, _costs, _family_class

    assert FAMILIES["exchange_inflow_fade"] == "ExchangeInflowFade" and _family_class("exchange_inflow_fade") is ExchangeInflowFade
    model = _costs(SimpleNamespace(costs="maker_dow", tier="VIP 0", bnb=True, spread=2.0))
    assert model.use_maker and model.funding and model.fill_rate_by_dow is not None
    assert len(_build_grid(ExchangeInflowFade, ["k=[1.0,1.5,2.0]", "h=[1,3,7]"], None)) == 9
