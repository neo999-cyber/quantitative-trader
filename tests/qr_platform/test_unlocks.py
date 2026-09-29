"""The unlock calendar (qr/data/unlocks.py) and the unlock fade (qr/strategies/unlocks.py)."""
import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.data.unlocks import circulating_supply, cliff_events, unlock_features
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.unlocks import UnlockFade


def _payload():
    """A DefiLlama-shaped schedule: 1,000 tokens circulating from day 0, a 5% insider
    cliff on 2024-03-01, a 0.2% investor cliff on 2024-02-10, a 3% ecosystem cliff on 2024-03-15."""
    days = pd.date_range("2024-01-01", "2024-04-30", freq="D", tz="UTC")
    stamps = (days.astype("int64") // 10**9).tolist()
    unlocked = [{"timestamp": t, "unlocked": 1000.0} for t in stamps]
    return {
        "categories": {"insiders": ["Team"], "privateSale": ["Investors"], "ecosystem": ["Ecosystem"]},
        "documentedData": {"data": [{"label": "Team", "data": unlocked}]},
        "metadata": {
            "events": [
                {"timestamp": int(pd.Timestamp("2024-03-01", tz="UTC").timestamp()), "category": "insiders", "unlockType": "cliff", "noOfTokens": [50.0]},
                {"timestamp": int(pd.Timestamp("2024-02-10", tz="UTC").timestamp()), "category": "privateSale", "unlockType": "cliff", "noOfTokens": [2.0]},
                {"timestamp": int(pd.Timestamp("2024-03-15", tz="UTC").timestamp()), "category": "ecosystem", "unlockType": "cliff", "noOfTokens": [30.0]},
                {"timestamp": int(pd.Timestamp("2024-02-01", tz="UTC").timestamp()), "category": "staking", "unlockType": "linear", "noOfTokens": [0, 1]},
            ]
        },
    }


def test_features_read_only_cliffs_after_the_bar_and_size_them_against_supply():
    payload = _payload()
    events = cliff_events(payload)
    assert list(events["category"]) == ["privateSale", "insiders", "ecosystem"]  # linear events are not cliffs
    supply = circulating_supply(payload)
    index = pd.date_range("2024-01-15", "2024-03-20", freq="D", tz="UTC")
    f = unlock_features(events, supply, index, horizon_days=30, min_pct=0.01)
    at = lambda d: f.loc[pd.Timestamp(d, tz="UTC")]
    # 31 January: the 10 Feb investor cliff (0.2%) and the 1 Mar insider cliff (5%) are both within 30 days
    assert at("2024-01-31")["unlock_pct_30d"] == pytest.approx(0.052)
    assert at("2024-01-30")["unlock_pct_30d"] == pytest.approx(0.002)  # 1 Mar is 31 days out
    # the next *big* cliff is the insider one: 30 days away on 31 January, 0.2% cliff ignored
    assert at("2024-01-31")["days_to_cliff"] == 30 and at("2024-01-31")["cliff_pct_next"] == pytest.approx(0.05)
    assert at("2024-03-01")["days_to_cliff"] != 0  # the bar of the cliff no longer sees it (it is not after the bar)
    assert np.isnan(at("2024-03-02")["days_to_cliff"])  # nothing big left
    assert at("2024-02-20")["unlock_pct_eco_30d"] == pytest.approx(0.03)
    assert at("2024-02-20")["unlock_pct_30d"] == pytest.approx(0.05)


def _panel_with_calendar(n_symbols=4, cliff_day="2024-03-01", cliff_pct=0.05):
    idx = pd.date_range("2024-01-01", "2024-04-30", freq="D", tz="UTC")
    idx.name = "open_time"
    frames = {}
    for i in range(n_symbols):
        c = np.full(len(idx), 100.0 + i)
        frame = pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c, "volume": 1e4, "quote_volume": 1e6}, index=idx)
        payload = _payload()
        if i > 0:  # only symbol 0 has the big cliff
            payload["metadata"]["events"] = payload["metadata"]["events"][2:]
        f = unlock_features(cliff_events(payload), circulating_supply(payload), idx)
        for col in ("unlock_pct_30d", "unlock_pct_eco_30d", "days_to_cliff", "cliff_pct_next"):
            frame[col] = f[col]
        frames[f"S{i}"] = frame
    return Panel.from_frames(frames)


def test_the_fade_is_short_from_lead_days_before_the_cliff_to_post_days_after():
    panel = _panel_with_calendar()
    w = UnlockFade(lead=30, post=14, min_pct=0.01, n_max=5).target_weights(panel)
    held = w["S0"] != 0
    first, last = held[held].index[0], held[held].index[-1]
    assert first == pd.Timestamp("2024-01-31", tz="UTC")
    assert last == pd.Timestamp("2024-03-15", tz="UTC")  # cliff 1 Mar, released after 14 bars
    assert (w.loc[held, "S0"] == -1.0).all()
    assert (w[["S1", "S2", "S3"]] == 0).all().all()
    long = UnlockFade(side="long").target_weights(panel)
    assert (long.loc[held, "S0"] == 1.0).all()
    eco = UnlockFade(category="eco", min_pct=0.01).target_weights(panel)
    # every symbol carries the 3% ecosystem cliff on 15 Mar: four names, equal weight
    assert (eco.loc["2024-02-20":"2024-03-14"] == -0.25).all().all()
    assert (eco.loc["2024-03-15":] == 0.0).all().all()


def test_the_fade_runs_through_the_ledger_with_funding_received_on_the_short():
    panel = _panel_with_calendar()
    fields = dict(panel.fields)
    rate = pd.DataFrame(0.0, index=panel.index, columns=panel.symbols)
    rate.loc["2024-02-01":"2024-03-15", "S0"] = 0.001  # longs pay 10 bps a day; the short receives it
    fields["funding_rate"] = rate
    panel = Panel(fields, "1d")
    res = run_backtest(panel, UnlockFade(), CostModel.binance_perp(), engine="ledger")
    assert res.carry is not None and res.carry.sum() > 0
    assert res.stats()["carry_share_of_gross"] == pytest.approx(1.0)  # flat prices: the whole gross is funding
