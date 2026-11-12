"""`trend_reset` (`qr/strategies/trend.py`): the rule from the owner's input of 12 November 2026, on synthetic prices only.

The book is checked on hand-sized arrays; the signals against a slow reference written here with plain loops; then the
controls, the look-ahead rule and the universe mask. No real series is read.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.strategies import trend as tr
from qr.strategies.trend import TrendReset, book

BASE, RUN, ROC, HOLD = 400, 21, 21, 10


# ------------------------------------------------------------------ the book, by hand
def _b(rows):
    return np.array(rows, dtype=bool)


def test_book_holds_for_the_holding_period_and_reopens_on_the_exit_bar():
    entry = _b([[0], [0], [1], [0], [0], [0], [0]])
    keep = np.ones((7, 1), dtype=bool)
    w, opened = book(entry, np.zeros((7, 1)), keep, hold=3)
    assert w[:, 0].tolist() == [0, 0, 0.2, 0.2, 0.2, 0, 0] and opened[:, 0].tolist() == [0, 0, 1, 0, 0, 0, 0]
    always = np.ones((7, 1), dtype=bool)
    w, opened = book(always, np.zeros((7, 1)), keep, hold=2)                 # still qualifying on its exit bar: held on
    assert w[:, 0].tolist() == [0.2] * 7 and opened[:, 0].tolist() == [1, 0, 1, 0, 1, 0, 1]


def test_book_closes_when_the_name_falls_out_and_fills_the_strongest_first():
    entry = _b([[0], [1], [0], [0], [0], [0]])
    keep = _b([[1], [1], [1], [0], [1], [1]])
    w, _ = book(entry, np.zeros((6, 1)), keep, hold=10)
    assert w[:, 0].tolist() == [0, 0.2, 0.2, 0, 0, 0]                        # closed at the first bar it is not kept
    entry = np.zeros((3, 7), dtype=bool); entry[0] = True
    strength = np.tile(np.array([1.0, 5.0, 3.0, np.nan, 4.0, 2.0, 6.0]), (3, 1))
    w, opened = book(entry, strength, np.ones((3, 7), dtype=bool), hold=2)
    assert opened[0].tolist() == [False, True, True, False, True, True, True]                # 6, 5, 4, 3, 2 — not 1, not the NaN
    assert w[0].sum() == pytest.approx(1.0) and w[2].sum() == 0.0


def test_book_gives_a_freed_slot_to_the_name_that_was_waiting():
    entry = _b([[1, 1], [0, 1], [0, 1], [0, 1], [0, 1], [0, 1]])
    strength = np.tile(np.array([2.0, 1.0]), (6, 1))
    w, opened = book(entry, strength, np.ones((6, 2), dtype=bool), hold=2, slots=1)
    assert w[:, 0].tolist() == [1, 1, 0, 0, 0, 0] and w[:, 1].tolist() == [0, 0, 1, 1, 1, 1]
    assert opened[:, 1].tolist() == [0, 0, 1, 0, 1, 0]


# ------------------------------------------------------------------ a synthetic market
def _closes():
    """UP: a quiet rise, a three-week run, then a flat stretch (the reset). DOWN: a quiet fall. CHOP: a seeded walk."""
    n = 900
    alt = np.array([0.002 if k % 2 else -0.002 for k in range(n)])
    up = np.zeros(n)
    up[1:BASE] = 0.001 + alt[1:BASE]
    up[BASE:BASE + RUN] = 0.02
    up[BASE + RUN:] = alt[BASE + RUN:]
    down = np.zeros(n); down[1:] = -0.001 + alt[1:]
    chop = np.zeros(n); chop[1:] = np.random.default_rng(7).normal(0.0004, 0.02, n - 1)
    idx = pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({"UP": 100 * np.exp(np.cumsum(up)), "DOWN": 100 * np.exp(np.cumsum(down)), "CHOP": 100 * np.exp(np.cumsum(chop))}, index=idx)


@pytest.fixture(scope="module")
def panel():
    return Panel({"close": _closes()}, "1d")


def _reference(close: np.ndarray, roc: int, was_high: float, near_zero: float):
    """The rule's entry signal, its strength and the keep mask for one name, with loops and no rolling windows."""
    n = len(close)
    lr = np.full(n, np.nan); lr[1:] = np.log(close[1:] / close[:-1])
    sma = np.full(n, np.nan)
    for t in range(tr.MA - 1, n):
        sma[t] = close[t - tr.MA + 1:t + 1].mean()
    z = np.full(n, np.nan)
    for t in range(tr.VOL, n):
        sigma = np.std(lr[t - tr.VOL + 1:t + 1], ddof=1) * math.sqrt(roc)
        z[t] = math.log(close[t] / close[t - roc]) / sigma
    entry, strength, keep = np.zeros(n, dtype=bool), np.full(n, np.nan), np.zeros(n, dtype=bool)
    for t in range(n):
        keep[t] = not math.isnan(sma[t]) and close[t] > sma[t]
        rising = t - tr.SLOPE >= 0 and not math.isnan(sma[t - tr.SLOPE]) and sma[t] > sma[t - tr.SLOPE]
        window = z[max(0, t - 2 * roc):t]
        prior = np.nanmax(window) if np.isfinite(window).any() else np.nan
        strength[t] = prior
        entry[t] = bool(keep[t] and rising and not math.isnan(prior) and prior >= was_high and not math.isnan(z[t]) and abs(z[t]) <= near_zero)
    return entry, strength, keep


def test_the_rule_matches_a_slow_reference_and_enters_at_the_reset(panel):
    s = TrendReset(roc=ROC, was_high=1.0, near_zero=0.25, hold=HOLD)
    weights, opened = s.positions(panel)
    cols = [_reference(panel.close[c].to_numpy(), ROC, 1.0, 0.25) for c in panel.symbols]
    ref_w, ref_opened = book(np.column_stack([c[0] for c in cols]), np.column_stack([c[1] for c in cols]), np.column_stack([c[2] for c in cols]), HOLD)
    assert np.array_equal(opened.to_numpy(), ref_opened) and np.allclose(weights.to_numpy(), ref_w)
    up = opened["UP"].to_numpy().nonzero()[0]
    first = BASE + RUN + ROC - 1                                             # the first bar whose 21-bar window lies wholly in the flat stretch
    assert up[0] == first and weights["UP"].iloc[:first].sum() == 0.0        # nothing during the rise or the run: the rate of change is high, not reset
    assert weights["UP"].iloc[first] == pytest.approx(0.2)
    assert np.all(np.diff(up) == HOLD)                                       # held on, ten bars at a time, while it still qualifies
    last_high = BASE + RUN + 19 - 1                                          # the last bar the scaled rate of change is still above 1
    assert up[-1] <= last_high + 2 * ROC < up[-1] + HOLD                     # and not reopened once the earlier high is 42 bars stale
    assert weights["UP"].iloc[up[-1] + HOLD:].sum() == 0.0
    assert weights["DOWN"].sum() == 0.0                                      # never above a rising average
    assert s.target_weights(panel).equals(weights)


def test_controls_ask_their_own_questions(panel):
    rule_w, rule_open = TrendReset(roc=ROC, hold=HOLD).positions(panel)
    _, trend_open = TrendReset(roc=ROC, hold=HOLD, control="trend").positions(panel)
    assert trend_open["UP"].to_numpy().nonzero()[0][0] == tr.MA - 1 + tr.SLOPE     # the first bar the filter can be read
    _, mirror_open = TrendReset(roc=ROC, hold=HOLD, control="mirror").positions(panel)
    first_mirror = mirror_open["UP"].to_numpy().nonzero()[0][0]
    assert first_mirror == tr.VOL and first_mirror < rule_open["UP"].to_numpy().nonzero()[0][0]   # strength, as soon as the volatility exists
    assert mirror_open["DOWN"].sum() == 0 and trend_open["DOWN"].sum() == 0
    placebo = TrendReset(roc=ROC, hold=HOLD, control="placebo")
    pw, popen = placebo.positions(panel)
    pw2, popen2 = placebo.positions(panel)
    assert pw.equals(pw2) and popen.equals(popen2)                           # a fixed seed
    in_trend, _ = tr.trend_filter(panel.close)
    assert not (popen & ~in_trend).any().any()                               # only on trend bars
    for c in panel.symbols:
        assert popen[c].sum() <= rule_open[c].sum()
    assert 0 < popen["UP"].sum() and not popen["UP"].equals(rule_open["UP"]) and popen["DOWN"].sum() == 0
    with pytest.raises(ValueError):
        TrendReset(control="nonsense")


@pytest.mark.parametrize("control", ["none", "trend", "mirror"])
def test_no_weight_reads_a_later_bar(panel, control):
    s = TrendReset(roc=ROC, hold=HOLD, control=control)
    full = s.target_weights(panel)
    for cut in (430, 445, 600):
        short = s.target_weights(Panel({"close": panel.close.iloc[:cut]}, "1d"))
        assert short.equals(full.iloc[:cut])


def test_the_universe_mask_and_the_registry(panel):
    universe = pd.DataFrame(True, index=panel.index, columns=panel.symbols)
    universe["UP"] = False
    w = TrendReset(roc=ROC, hold=HOLD).target_weights(panel, universe)
    assert w["UP"].sum() == 0.0
    from qr.cli import FAMILIES, _family_class
    assert FAMILIES["trend_reset"] == "TrendReset" and _family_class("trend_reset") is TrendReset
    assert TrendReset.grid(roc=[21, 63], was_high=[1.0, 1.5], near_zero=[0.25, 0.5]).__len__() == 8
