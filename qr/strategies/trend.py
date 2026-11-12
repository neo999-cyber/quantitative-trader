"""Trend with a momentum reset (`trend_reset`): the technical rule from the owner's input of 12 November 2026.

The rule as spoken in the clip the owner sent ("He Managed $4 Billion — Here's How To Use AI to Trade", Titans of
Tomorrow): trade a name only while it is above its 200-day moving average and that average points up; enter when its
rate of change "has reset close to zero after being higher" — a consolidation inside an uptrend; ride the trend for
about three months; five names at a time. The clip gives no numbers for any of it and claims no result.

Made exact here (a memo freezes the values before any run):

- **trend**: close above SMA(`MA`), and SMA(`MA`) above its own level `SLOPE` bars ago;
- **rate of change** over `roc` bars, in units of the name's own volatility over that span (the daily log-return
  standard deviation over `VOL` bars × √roc), so one threshold fits a quiet name and a wild one — the first tweak;
- **was higher**: the scaled rate of change reached `was_high` on some bar among the `2 × roc` before today;
- **has reset**: its absolute value today is at most `near_zero`;
- **entry** at the close of a bar where all three hold and the name is not already held; at most `SLOTS` positions of
  1/`SLOTS` of the book each, the rest in cash; when more names qualify than there are free slots, the strongest prior
  run first;
- **exit** after `hold` bars, or at the first close at or below the moving average; a name that still qualifies on its
  exit bar is held on.

Controls (`control`), the questions a pass would have to survive:

- `"trend"` enters on the trend filter alone — does waiting for the reset add anything to the filter?
- `"mirror"` enters when the scaled rate of change is at or above `was_high` *today* — strength, not the reset;
- `"placebo"` draws, for each name, as many entry bars as the rule opened positions in it, at random among that
  name's trend bars (a fixed seed) — the same exposure to the trend, the timing removed. A bar drawn while the name
  is already held opens nothing, so the placebo holds at most as many positions as the rule. The draw uses the whole
  sample, so the placebo is a control and never a candidate.

Weights are for bar *t*, held over bar *t+1*, from information at or before the close of bar *t* (`Strategy`'s rule);
the placebo aside, truncating the panel after any bar leaves every earlier weight unchanged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy

MA = 200                # the moving average the rule is spoken on
SLOPE = 21              # a rising average: the average against its own level this many bars ago
VOL = 252               # bars behind the volatility that scales the rate of change
SLOTS = 5               # five names at a time, as in the clip
SEED = 20261112         # the placebo's draw
CONTROLS = ("none", "trend", "mirror", "placebo")


def trend_filter(close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(in an uptrend, above the average): above a rising SMA(`MA`), and merely above it."""
    sma = close.rolling(MA, min_periods=MA).mean()
    above = close > sma
    return above & (sma > sma.shift(SLOPE)), above


def scaled_roc(close: pd.DataFrame, n: int) -> pd.DataFrame:
    """The log change over `n` bars in units of the name's own volatility over `n` bars."""
    sigma = np.log(close).diff().rolling(VOL, min_periods=VOL).std() * np.sqrt(n)
    return np.log(close / close.shift(n)) / sigma.where(sigma > 0)


def book(entry: np.ndarray, strength: np.ndarray, keep: np.ndarray, hold: int, slots: int = SLOTS) -> tuple[np.ndarray, np.ndarray]:
    """The positions a stream of entry signals turns into: (weights, opened), both bars × names.

    Each bar, in this order: a held name ages by one bar and is closed if it has been held `hold` bars or `keep` is false
    for it; then free slots are filled from the names with `entry` true and no position, the largest `strength` first
    (ties by column order). A name closed on a bar may be reopened on that same bar. Every open position weighs 1/slots.
    """
    bars, names = entry.shape
    weights = np.zeros((bars, names))
    opened = np.zeros((bars, names), dtype=bool)
    age = np.full(names, -1)                                   # -1: no position; otherwise bars since it was opened
    rank = np.where(np.isfinite(strength), strength, -np.inf)
    for t in range(bars):
        held = age >= 0
        age[held] += 1
        age[held & ((age >= hold) | ~keep[t])] = -1
        free = slots - int((age >= 0).sum())
        if free > 0:
            candidates = np.flatnonzero(entry[t] & (age < 0))
            if len(candidates):
                for j in candidates[np.argsort(-rank[t, candidates], kind="stable")][:free]:
                    age[j] = 0
                    opened[t, j] = True
        weights[t, age >= 0] = 1.0 / slots
    return weights, opened


class TrendReset(Strategy):
    """Long a name in an uptrend when its momentum has reset; see the module docstring for the rule and its controls."""

    family = "trend_reset"

    def __init__(self, roc: int = 63, was_high: float = 1.0, near_zero: float = 0.25, hold: int = 63, control: str = "none") -> None:
        if control not in CONTROLS:
            raise ValueError(f"unknown control {control!r}; expected one of {CONTROLS}")
        super().__init__(roc=roc, was_high=was_high, near_zero=near_zero, hold=hold, control=control)

    def _inputs(self, panel: Panel, universe: pd.DataFrame | None) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """(entry, strength, keep, trend) as arrays: the rule's own entry signal before any control replaces it."""
        p = self.params
        close = panel.close
        allowed = panel.tradable()
        if universe is not None:
            allowed = allowed & universe.reindex_like(allowed).fillna(False)
        trend, above = trend_filter(close)
        z = scaled_roc(close, p["roc"])
        prior = z.shift(1).rolling(2 * p["roc"], min_periods=1).max()      # the best reading before today
        trend = (trend & allowed).fillna(False)
        if p["control"] == "trend":
            entry = trend
        elif p["control"] == "mirror":
            entry = trend & (z >= p["was_high"])
        else:
            entry = trend & (prior >= p["was_high"]) & (z.abs() <= p["near_zero"])
        keep = (above & allowed).fillna(False)
        return entry.fillna(False).to_numpy(), prior.to_numpy(), keep.to_numpy(), trend.to_numpy()

    def positions(self, panel: Panel, universe: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        """(weights, opened): the book, and the bars on which each position was opened (what a count reads)."""
        entry, strength, keep, trend = self._inputs(panel, universe)
        hold = int(self.params["hold"])
        weights, opened = book(entry, strength, keep, hold)
        if self.params["control"] == "placebo":
            rng = np.random.default_rng(SEED)
            drawn = np.zeros_like(entry)
            for j in range(entry.shape[1]):
                eligible = np.flatnonzero(trend[:, j])
                take = min(int(opened[:, j].sum()), len(eligible))
                if take:
                    drawn[rng.choice(eligible, size=take, replace=False), j] = True
            weights, opened = book(drawn, rng.random(entry.shape), keep, hold)
        frame = lambda a: pd.DataFrame(a, index=panel.index, columns=panel.symbols)   # noqa: E731
        return frame(weights), frame(opened)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        weights, _ = self.positions(panel, universe)
        return self.schedule(self.mask_to_universe(weights, panel, universe), panel)
