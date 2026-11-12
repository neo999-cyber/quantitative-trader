"""`momentum_breakout` (`qr/strategies/breakout.py`): Qullamaggie's setup made exact; synthetic prices only.

The book is checked on hand-sized arrays (stop, partial, break-even, trail, slots, drift, leaving the universe);
then the signal on a planted breakout, the controls, the look-ahead rule by truncation and the registry.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.strategies import breakout as bo
from qr.strategies.breakout import MomentumBreakout, simulate


def _sim(close, low=None, member=None, entry=None, stop=None, strength=None, trail=None, slots=4, partial=5):
    close = np.asarray(close, dtype=float).reshape(len(close), -1)
    shape = close.shape
    low = close * 0.99 if low is None else np.asarray(low, dtype=float).reshape(shape)
    member = np.ones(shape, dtype=bool) if member is None else np.asarray(member, dtype=bool).reshape(shape)
    entry = np.zeros(shape, dtype=bool) if entry is None else np.asarray(entry, dtype=bool).reshape(shape)
    stop = low if stop is None else np.asarray(stop, dtype=float).reshape(shape)
    strength = np.zeros(shape) if strength is None else np.asarray(strength, dtype=float).reshape(shape)
    trail = np.full(shape, np.nan) if trail is None else np.asarray(trail, dtype=float).reshape(shape)
    return simulate(close, low, member, entry, stop, strength, trail, slots=slots, partial=partial)


def test_stop_before_the_partial_closes_the_whole_position():
    close = [100, 101, 99, 98.9, 100]
    entry = [1, 0, 0, 0, 0]
    w, opened = _sim(close, stop=[99.0] * 5, entry=entry)
    assert opened[:, 0].tolist() == [True, False, False, False, False]
    assert w[0, 0] == pytest.approx(0.25) and w[1, 0] > 0 and w[2, 0] > 0          # 99 is not below 99
    assert w[3, 0] == 0.0 and w[4, 0] == 0.0                                          # 98.9 is


def test_partial_halves_moves_the_stop_to_entry_then_trails():
    close = [100, 103, 105, 106, 107, 108, 110, 109, 99.5]
    trail = [np.nan] * 7 + [109.5, 90]
    w, _ = _sim(close, stop=[95.0] * 9, entry=[1] + [0] * 8, trail=trail)
    units = 0.25 / 100
    eq5 = 0.75 + units * 108
    assert w[4, 0] == pytest.approx(units * 107 / (0.75 + units * 107))
    assert w[5, 0] == pytest.approx(0.5 * units * 108 / eq5)                          # half sold on the fifth close
    assert w[6, 0] > 0 and w[7, 0] == 0.0                                             # 109 < the 109.5 trail
    w2, _ = _sim(close, stop=[95.0] * 9, entry=[1] + [0] * 8)                         # no trail: break-even stop at 100
    assert w2[7, 0] > 0 and w2[8, 0] == 0.0


def test_slots_take_the_strongest_and_a_freed_slot_is_refilled():
    close = np.full((4, 3), 100.0)
    entry = np.zeros((4, 3), dtype=bool); entry[0] = True; entry[1:, 2] = True
    strength = np.tile([1.0, 3.0, 2.0], (4, 1))
    stop = np.full((4, 3), 90.0); stop[0, 1] = 101.0                                   # name 1 is stopped on bar 1
    w, opened = _sim(close, entry=entry, strength=strength, stop=stop, slots=2)
    assert opened[0].tolist() == [False, True, True]
    assert w[1, 1] == 0.0 and opened[1, 2] == False and opened[1, 0] == False         # name 0 never signalled again
    w, opened = _sim(close, entry=np.vstack([entry[:1], np.ones((3, 3), dtype=bool)]), strength=strength, stop=stop, slots=2)
    assert opened[1, 1] and not opened[1, 0]                                          # the freed slot goes to the strongest, the name just stopped


def test_weights_drift_with_price_and_a_name_leaving_the_universe_is_sold():
    close = np.array([[100.0, 100.0], [200.0, 100.0], [200.0, 100.0]])
    entry = np.zeros((3, 2), dtype=bool); entry[0] = True
    w, _ = _sim(close, entry=entry, slots=2, stop=np.full((3, 2), 1.0))
    assert w[0].tolist() == pytest.approx([0.5, 0.5]) and w[1].tolist() == pytest.approx([2 / 3, 1 / 3])
    member = np.ones((3, 2), dtype=bool); member[2, 0] = False
    w, _ = _sim(close, entry=entry, slots=2, stop=np.full((3, 2), 1.0), member=member)
    assert w[2, 0] == 0.0 and w[2, 1] == pytest.approx(0.5 / 1.5)                      # A sold at 200: cash 1.0, B worth 0.5


def _market(n=420, seed=3):
    """BTCUSDT rising; LEAD: a big move, a tight base, then a breakout on volume at bar BO; 20 noisy names."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC")
    names = ["BTCUSDT", "LEAD"] + [f"N{k:02d}USDT" for k in range(20)]
    lr = rng.normal(0.0, 0.03, (n, len(names)))
    lr[:, 0] = 0.003 + rng.normal(0, 0.005, n)
    lr[:, 1] = rng.normal(0.0, 0.004, n)
    lr[200:260, 1] = 0.02                                       # the big move
    lr[260:275, 1] = rng.normal(0.0, 0.002, 15)                  # a tight base
    close = pd.DataFrame(100 * np.exp(np.cumsum(lr, axis=0)), index=idx, columns=names)
    high, low = close * 1.035, close * 0.965
    vol = pd.DataFrame(1e7, index=idx, columns=names)
    BO = 275
    close.iloc[BO, 1] = close.iloc[BO - 1, 1] * 1.06            # up 6% on the day, under its 7% average range
    high.iloc[BO, 1] = close.iloc[BO, 1] * 1.002
    low.iloc[BO, 1] = close.iloc[BO - 1, 1] * 0.97
    vol.iloc[BO, 1] = 5e7
    f = {"close": close, "high": high, "low": low, "volume": vol / close, "quote_volume": vol}
    return Panel(f, "1d"), BO


def test_the_planted_breakout_is_found_and_the_controls_differ():
    panel, BO = _market()
    rule = MomentumBreakout(base=5, tight=2.5, trail=10)
    f = bo.inputs(panel, None, 5, 2.5)
    assert bool(f["signal"]["LEAD"].iloc[BO])
    assert not f["signal"]["LEAD"].iloc[BO - 1]
    adr = (panel["high"]["LEAD"] / panel["low"]["LEAD"] - 1).rolling(20).mean().iloc[BO - 1]
    assert f["stop"]["LEAD"].iloc[BO] == pytest.approx(max(panel["low"]["LEAD"].iloc[BO], panel.close["LEAD"].iloc[BO] * (1 - adr)))
    assert f["stop"]["LEAD"].iloc[BO] > panel["low"]["LEAD"].iloc[BO]                 # a 9% day range: the stop is capped at one range
    w, opened = rule.positions(panel)
    assert bool(opened["LEAD"].iloc[BO]) and w["LEAD"].iloc[BO] > 0
    _, late = MomentumBreakout(control="late").positions(panel)
    assert bool(late["LEAD"].iloc[BO + 1]) and not late["LEAD"].iloc[BO]
    _, lead = MomentumBreakout(control="leaders").positions(panel)
    assert lead.to_numpy().sum() >= opened.to_numpy().sum()
    p1, o1 = MomentumBreakout(control="placebo").positions(panel)
    p2, o2 = MomentumBreakout(control="placebo").positions(panel)
    assert p1.equals(p2) and o1.equals(o2)
    for c in panel.symbols:
        assert o1[c].sum() <= opened[c].sum()
    assert not (o1 & ~f["eligible"]).any().any()
    with pytest.raises(ValueError):
        MomentumBreakout(control="x")
    with pytest.raises(ValueError):
        bo.inputs(Panel({k: v.drop(columns="BTCUSDT") for k, v in panel.fields.items()}, "1d"), None, 5, 2.5)


@pytest.mark.parametrize("control", ["none", "leaders", "late", "nofilter"])
def test_no_weight_reads_a_later_bar(control):
    panel, BO = _market()
    s = MomentumBreakout(base=5, tight=2.5, trail=10, control=control)
    full = s.target_weights(panel)
    for cut in (BO, BO + 3, 380):
        short = s.target_weights(Panel({k: v.iloc[:cut] for k, v in panel.fields.items()}, "1d"))
        pd.testing.assert_frame_equal(short, full.iloc[:cut])


def test_registry_and_grid():
    from qr.cli import FAMILIES, _family_class
    assert FAMILIES["momentum_breakout"] == "MomentumBreakout" and _family_class("momentum_breakout") is MomentumBreakout
    assert len(MomentumBreakout.grid(base=[5, 10], tight=[2.5, 4.0], trail=[10, 20])) == 8
