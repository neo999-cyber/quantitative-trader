import datetime as dt

import pandas as pd

from centaur.screens.options_flow import OptionActivity, flag_unusual_calls, ChainHistoryFlowProvider

TODAY = dt.date(2026, 9, 10)


def act(**kw):
    base = dict(ticker="XYZ", expiration=TODAY + dt.timedelta(days=7), strike=100.0, kind="call",
                volume=4000.0, avg_volume_30d=1000.0, open_interest=2500.0)
    base.update(kw)
    return OptionActivity(**base)


def test_flags_only_calls_over_threshold_within_dte():
    flags = flag_unusual_calls([
        act(),                                                    # 4x, 7 DTE -> flag
        act(kind="put"),                                          # puts ignored
        act(volume=2500.0),                                       # 2.5x < 3x
        act(expiration=TODAY + dt.timedelta(days=30)),            # too far out
        act(expiration=TODAY - dt.timedelta(days=1)),             # expired
        act(volume=6000.0, strike=110.0),                         # 6x -> flag, sorted first
    ], threshold=3.0, max_dte=14, as_of=TODAY)
    assert [f.ratio for f in flags] == [6.0, 4.0]
    assert "volume > open interest" in flags[0].note


def test_low_baseline_is_annotated():
    f = flag_unusual_calls([act(baseline_days=5)], as_of=TODAY)[0]
    assert "baseline only 5 days" in f.note


class _FakeProvider:
    def __init__(self, chain):
        self.chain = chain

    def option_chain(self, ticker):
        return self.chain


def test_chain_history_provider_builds_baseline(tmp_path):
    exp = pd.Timestamp(TODAY + dt.timedelta(days=5))
    chain = pd.DataFrame({
        "type": ["call", "call", "put"], "expiration": [exp, exp, exp], "strike": [100.0, 105.0, 100.0],
        "volume": [300.0, 100.0, 50.0], "openInterest": [1000.0, 500.0, 900.0],
    })
    fp = ChainHistoryFlowProvider(_FakeProvider(chain), history_path=tmp_path / "h.json")
    # seed 10 prior days of 100 total call volume
    for i in range(1, 11):
        fp.record("XYZ", 100.0, TODAY - dt.timedelta(days=i))
    acts = fp.activity("XYZ", as_of=TODAY)
    assert len(acts) == 2
    assert all(a.baseline_days == 10 for a in acts)
    # today's total (400) is 4x the baseline (100) -> every bucket carries a 4x ratio
    flags = flag_unusual_calls(acts, as_of=TODAY, min_volume=50)
    assert len(flags) == 2 and all(abs(f.ratio - 4.0) < 1e-9 for f in flags)
