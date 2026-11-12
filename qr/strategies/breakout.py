"""Momentum breakout (`momentum_breakout`): Qullamaggie's swing setup, made exact for crypto spot (`p6_breakout_crypto_v1`).

The rule as he teaches it in *Qullamaggie Swing Trading School* (2020; `docs/research/13`, §1): scan for the biggest
gainers over one, three and six months; among them, a stock that has made a big move, then goes sideways on a rising
10-, 20- or 50-day average and gets tight; buy the breakout from the tight range on volume, with the stop at the
breakout day's low and never more than about one average range away; sell a third to a half after three to five days
and move the stop to break-even; trail the rest on the first close below the 10-day average (20-day for slower names);
at most 25% of the account in one name; trade only while the market's 10- and 20-day averages rise with the 10 above
the 20. He says the setup works on crypto and shows it on BTC and ETH.

Made exact here, everything known at the close of bar *t* (a memo freezes the values before any run):

- **universe**: the ranked Binance spot universe the run is given (top `--n` by 30-day quote volume, the 15% volatility
  floor, pegs and leveraged tokens out); a name is sold at the close of the bar it leaves the universe;
- **leader**: in the top `1 − LEADER_PCT` of the universe that day by its 21-, 63- or 126-bar change (any of the three);
- **range**: its average daily range over 20 bars (mean of high/low − 1) is at least `MIN_ADR`;
- **trend**: close above SMA20, SMA20 above SMA50, SMA20 above its own level five bars ago;
- **market**: BTCUSDT's SMA10 above its SMA20, and at least one of the two rising on the bar;
- **base**: over the `base` bars before *t*, highest high less lowest low, in units of the prior close, is at most
  `tight` × the average range × √(`base`/5) — the square root so that a 5- and a 10-bar base are judged alike (a
  base's range grows with its length; on the lake's eligible bars the median 5-bar base spans 2.0 ranges and the
  median 10-bar base 3.0);
- **breakout**: close above that highest high; quote volume at least `VOL_MULT` × its 20-bar average before *t*;
  the day's change no more than the average range ("I don't buy a stock already up more on the day than its
  average range");
- **entry** at the close of *t*, `1/SLOTS` of equity, if a slot is free; several candidates are taken strongest
  first (the best of the three momentum percentiles, then the 126-bar change);
- **stop**: the breakout day's low, but never more than one average range below the entry ("the stop shouldn't be
  further away than the average range"), on a close below it (daily bars cannot honour an intraday stop);
- **partial**: on the `PARTIAL`-th close after entry, half is sold and the stop moves to the entry price;
- **trail**: after the partial, the rest is sold on the first close below SMA(`trail`) or below the entry price.

The book is simulated inside the rule, so the weights it reports are the positions' values as prices move — the
runner trades every bar to its target, and a fixed 1/`SLOTS` target would sell a winner back to size every day.

Controls (`control`), the questions a pass has to survive:

- `"leaders"`: enters on any bar the name is an eligible leader in trend under the market filter — no base, no
  breakout, no volume — with the same exits: does the setup add anything to owning momentum leaders?
- `"placebo"`: for each name, as many entries as the rule made, on bars drawn at random among its eligible bars (a
  fixed seed), stop by the same formula on that bar, same exits: does the choice of day matter? The draw uses the whole sample,
  so it is a control, never a candidate.
- `"late"`: enters one bar after the rule's signal, with the signal bar's stop: does the breakout day matter?
- `"nofilter"`: the rule without the market filter: does the filter carry it?
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy

SLOTS = 4                # at most 25% of the account in a name
PARTIAL = 5              # the close on which half is sold ("after three to five days")
VOL_MULT = 1.5           # breakout volume against its 20-bar average
LEADER_PCT = 0.93        # top 7% of the universe ("rank 93%")
MIN_ADR = 0.05           # "ADR 5–6% for you"
WINDOWS = (21, 63, 126)  # one, three and six months
REGIME = "BTCUSDT"
SEED = 20261112
CONTROLS = ("none", "leaders", "placebo", "late", "nofilter")


def _sma(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.rolling(n, min_periods=n).mean()


def inputs(panel: Panel, universe: pd.DataFrame | None, base: int, tight: float) -> dict[str, pd.DataFrame]:
    """The rule's inputs as frames: `member`, `eligible` (with the market filter), `eligible_nf` (without),
    `signal`, `signal_nf`, `strength`, `sma10`, `sma20`, `stop` (the stop a position opened on the bar takes). Every
    value is known at the close of its own bar."""
    close, high, low = panel.close, panel["high"], panel["low"]
    qv = panel.get("quote_volume")
    if qv is None:
        raise ValueError("momentum_breakout needs a quote_volume field")
    member = panel.tradable()
    if universe is not None:
        member = member & universe.reindex_like(member).fillna(False).astype(bool)
    adr = (high / low - 1.0).rolling(20, min_periods=20).mean()
    sma10, sma20, sma50 = _sma(close, 10), _sma(close, 20), _sma(close, 50)
    trend = (close > sma20) & (sma20 > sma50) & (sma20 > sma20.shift(5))
    pct = []
    for n in WINDOWS:
        change = (close / close.shift(n) - 1.0).where(member)
        pct.append(change.rank(axis=1, pct=True))
    best = pd.concat(pct).groupby(level=0).max().reindex(close.index)
    leader = best >= LEADER_PCT
    if REGIME not in close.columns:
        raise ValueError(f"momentum_breakout reads the market filter from {REGIME}, which this panel does not carry")
    b10, b20 = _sma(close[[REGIME]], 10)[REGIME], _sma(close[[REGIME]], 20)[REGIME]
    regime = ((b10 > b20) & ((b10 > b10.shift(1)) | (b20 > b20.shift(1)))).fillna(False)
    eligible_nf = (member & leader & trend & (adr >= MIN_ADR)).fillna(False)
    eligible = eligible_nf & pd.DataFrame(np.repeat(regime.to_numpy()[:, None], close.shape[1], axis=1), index=close.index, columns=close.columns)
    hh = high.shift(1).rolling(base, min_periods=base).max()
    ll = low.shift(1).rolling(base, min_periods=base).min()
    tight_ok = (hh - ll) / close.shift(1) <= tight * adr.shift(1) * np.sqrt(base / 5.0)
    setup = (
        tight_ok
        & (close > hh)
        & (qv >= VOL_MULT * qv.shift(1).rolling(20, min_periods=20).mean())
        & (close / close.shift(1) - 1.0 <= adr.shift(1))
    ).fillna(False)
    stop = np.maximum(low, close * (1.0 - adr.shift(1)))
    strength = best.fillna(-1.0) * 10.0 + (close / close.shift(126) - 1.0).clip(-1, 9).fillna(-1.0) / 100.0
    return {"member": member.fillna(False), "eligible": eligible, "eligible_nf": eligible_nf, "signal": setup & eligible,
            "signal_nf": setup & eligible_nf, "strength": strength, "sma10": sma10, "sma20": sma20, "stop": stop}


def simulate(close: np.ndarray, low: np.ndarray, member: np.ndarray, entry: np.ndarray, stop_low: np.ndarray,
             strength: np.ndarray, trail_ma: np.ndarray, slots: int = SLOTS, partial: int = PARTIAL) -> tuple[np.ndarray, np.ndarray]:
    """The book an entry stream turns into: (weights, opened), bars × names.

    Each bar, in this order: every held name ages one bar and is closed at this close if it has no price or has left
    the universe, if before the partial its close is below its stop, or if after the partial its close is below the
    entry price or below the trailing average; on the `partial`-th bar half is sold and the stop moves to the entry
    price; then free slots take `1/slots` of equity each from the names with `entry` true and no position, the
    largest `strength` first. A name closed on a bar may be re-entered on that bar. `stop_low[t, j]` is the stop a
    position opened on bar t takes. Weights are the positions' values over equity after the bar's trades.
    """
    bars, names = close.shape
    weights = np.zeros((bars, names))
    opened = np.zeros((bars, names), dtype=bool)
    units = np.zeros(names)
    entry_px = np.zeros(names)
    stop = np.zeros(names)
    age = np.full(names, -1)
    halved = np.zeros(names, dtype=bool)
    last_px = np.full(names, np.nan)
    cash = 1.0
    rank = np.where(np.isfinite(strength), strength, -np.inf)
    for t in range(bars):
        px = close[t]
        priced = np.isfinite(px) & (px > 0)
        last_px = np.where(priced, px, last_px)
        for j in np.flatnonzero(age >= 0):
            age[j] += 1
            p = px[j] if priced[j] else last_px[j]
            if not priced[j] or not member[t, j]:
                out = True
            elif not halved[j]:
                out = p < stop[j]
            else:
                out = p < entry_px[j] or (np.isfinite(trail_ma[t, j]) and p < trail_ma[t, j])
            if out:
                cash += units[j] * p
                units[j], age[j], halved[j] = 0.0, -1, False
            elif not halved[j] and age[j] >= partial:
                cash += 0.5 * units[j] * p
                units[j] *= 0.5
                halved[j] = True
                stop[j] = entry_px[j]
        value = np.where(age >= 0, units * np.where(priced, px, last_px), 0.0)
        equity = cash + value.sum()
        free = slots - int((age >= 0).sum())
        if free > 0:
            cand = np.flatnonzero(entry[t] & (age < 0) & priced & member[t])
            if len(cand):
                for j in cand[np.argsort(-rank[t, cand], kind="stable")][:free]:
                    amount = min(equity / slots, cash)
                    if amount <= 0:
                        break
                    units[j] = amount / px[j]
                    cash -= amount
                    entry_px[j], stop[j], age[j], halved[j] = px[j], stop_low[t, j], 0, False
                    opened[t, j] = True
        value = np.where(age >= 0, units * np.where(priced, px, last_px), 0.0)
        equity = cash + value.sum()
        if equity > 0:
            weights[t] = value / equity
    return weights, opened


class MomentumBreakout(Strategy):
    """Long a momentum leader breaking out of a tight base; see the module docstring for the rule and its controls."""

    family = "momentum_breakout"

    def __init__(self, base: int = 5, tight: float = 2.0, trail: int = 10, control: str = "none") -> None:
        if control not in CONTROLS:
            raise ValueError(f"unknown control {control!r}; expected one of {CONTROLS}")
        if trail not in (10, 20):
            raise ValueError("trail is 10 or 20")
        super().__init__(base=int(base), tight=float(tight), trail=int(trail), control=control)

    def positions(self, panel: Panel, universe: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        """(weights, opened): the drifted book, and the bars on which each position was opened (what a count reads)."""
        p = self.params
        f = inputs(panel, universe, p["base"], p["tight"])
        close, low = panel.close.to_numpy(dtype=float), panel["low"].to_numpy(dtype=float)
        member = f["member"].to_numpy(dtype=bool)
        strength = f["strength"].to_numpy(dtype=float)
        trail_ma = (f["sma10"] if p["trail"] == 10 else f["sma20"]).to_numpy(dtype=float)
        signal = f["signal"].to_numpy(dtype=bool)
        stop_low = f["stop"].to_numpy(dtype=float)
        control = p["control"]
        if control == "nofilter":
            entry = f["signal_nf"].to_numpy(dtype=bool)
        elif control == "leaders":
            entry = f["eligible"].to_numpy(dtype=bool)
        elif control == "late":
            entry = np.zeros_like(signal)
            entry[1:] = signal[:-1]
            stop_low = np.vstack([np.full((1, low.shape[1]), np.nan), stop_low[:-1]])
        else:
            entry = signal
        weights, opened = simulate(close, low, member, entry, stop_low, strength, trail_ma)
        if control == "placebo":
            rng = np.random.default_rng(SEED)
            eligible = f["eligible"].to_numpy(dtype=bool)
            drawn = np.zeros_like(signal)
            for j in range(signal.shape[1]):
                bars = np.flatnonzero(eligible[:, j])
                take = min(int(opened[:, j].sum()), len(bars))
                if take:
                    drawn[rng.choice(bars, size=take, replace=False), j] = True
            weights, opened = simulate(close, low, member, drawn, f["stop"].to_numpy(dtype=float), rng.random(signal.shape), trail_ma)
        frame = lambda a: pd.DataFrame(a, index=panel.index, columns=panel.symbols)  # noqa: E731
        return frame(weights), frame(opened)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        weights, _ = self.positions(panel, universe)
        return self.schedule(self.mask_to_universe(weights, panel, universe), panel)
