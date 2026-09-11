"""Strategy library. Two entries so far; the rest land on Day 4.

Every strategy here obeys the interface contract: the weights returned for bar
*t* use only bars up to and including *t*, and the runner applies the shift.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy, VolTarget


class BuyAndHold(Strategy):
    """Equal weight across the universe. The baseline gate 5 tests against.

    Not a strawman: in crypto this is a hard benchmark over most samples, and a
    strategy that cannot beat it after costs has nothing to offer.
    """

    family = "buy_and_hold"

    def __init__(self, gross: float = 1.0) -> None:
        super().__init__(gross=gross)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        ones = pd.DataFrame(1.0, index=panel.index, columns=panel.symbols)
        return self.normalise(self.mask_to_universe(ones, panel, universe), self.params["gross"])


class TSMOM(Strategy):
    """Time-series momentum: hold what has gone up over `lookback` bars.

    The oldest and most replicated systematic effect there is, and the one most
    likely to survive costs at a daily horizon. Long-only because the trial
    models Binance **spot**: there is nothing to short.

    `skip` drops the most recent bars from the lookback window — the 12-1
    convention from the equity literature, which avoids the short-term reversal
    that sits on top of the momentum signal.
    """

    family = "tsmom"

    def __init__(
        self,
        lookback: int = 90,
        skip: int = 0,
        vol_target: float | None = 0.20,
        vol_lookback: int = 30,
        max_leverage: float = 1.0,
    ) -> None:
        super().__init__(
            lookback=lookback,
            skip=skip,
            vol_target=vol_target,
            vol_lookback=vol_lookback,
            max_leverage=max_leverage,
        )

    def signal(self, panel: Panel) -> pd.DataFrame:
        lookback, skip = self.params["lookback"], self.params["skip"]
        close = panel.close
        recent = close.shift(skip)
        past = close.shift(lookback + skip)
        return (recent / past - 1.0)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        momentum = self.signal(panel)
        raw = (momentum > 0).astype(float).where(momentum.notna(), 0.0)
        weights = self.normalise(self.mask_to_universe(raw, panel, universe))
        target = self.params["vol_target"]
        if target:
            weights = VolTarget(
                annual_target=target,
                lookback=self.params["vol_lookback"],
                max_leverage=self.params["max_leverage"],
            ).scale(weights, panel)
        return weights.fillna(0.0)


class RandomEntry(Strategy):
    """A deterministic-seed random book with the same turnover profile.

    Gate 6 needs a "would a coin toss have done this" baseline, and gate 5's SPA
    test needs a benchmark set. Seeded so a report is reproducible.
    """

    family = "random_entry"

    def __init__(self, n_held: int = 5, hold: int = 20, seed: int = 0) -> None:
        super().__init__(n_held=n_held, hold=hold, seed=seed)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        rng = np.random.default_rng(self.params["seed"])
        hold, n_held = self.params["hold"], self.params["n_held"]
        allowed = panel.tradable()
        if universe is not None:
            allowed = allowed & universe.reindex_like(allowed).fillna(False)

        # Choose only on rebalance bars and assign whole blocks of rows at once.
        # Gate 6 runs this hundreds of times per hypothesis, and a per-bar loop
        # made the random-entry baseline 200x slower than the strategy it is
        # meant to be a cheap null for.
        mask = allowed.to_numpy()
        raw = np.zeros(mask.shape)
        for start in range(0, len(mask), hold):
            candidates = np.flatnonzero(mask[start])
            take = min(n_held, len(candidates))
            if take:
                chosen = rng.choice(candidates, size=take, replace=False)
                raw[start : start + hold, chosen] = 1.0
        # A name that stops trading mid-block simply drops out and the book
        # renormalises, which is what the real strategies do too.
        raw *= mask
        frame = pd.DataFrame(raw, index=panel.index, columns=panel.symbols)
        return self.normalise(self.mask_to_universe(frame, panel, universe))


# --------------------------------------------------------------- cross-section


def _rebalance_mask(index: pd.DatetimeIndex, every: int) -> np.ndarray:
    """True on the bars a weekly-ish strategy is allowed to trade.

    Holding a selection between rebalances is not cosmetic: rebalancing a
    ranked book every bar multiplies turnover by the rebalance period, and at
    19 bps a round trip that is the difference between an edge and a fee.
    """
    flags = np.zeros(len(index), dtype=bool)
    flags[::every] = True
    return flags


def _hold_between_rebalances(selection: pd.DataFrame, every: int) -> pd.DataFrame:
    """Carry each rebalance bar's selection forward until the next one."""
    if every <= 1:
        return selection
    mask = _rebalance_mask(selection.index, every)
    held = selection.where(pd.Series(mask, index=selection.index), other=np.nan)
    return held.ffill().fillna(0.0)


class CrossSectionalMomentum(Strategy):
    """Buy the winners relative to their peers — the 12-1 convention.

    Ranks the universe on the return from `lookback + skip` bars ago to `skip`
    bars ago and holds the top `n_long` equally weighted. Long-only, because
    the trial models Binance **spot**: the short leg of the academic factor is
    not available, and half a factor is a different strategy with a different
    expected return.

    `skip` is the point of the convention. The most recent month of a momentum
    window carries short-term *reversal*, which works against the signal, so
    the standard 12-1 formulation measures 12 months ending one month ago. At
    daily bars in crypto the natural scale is shorter, but the structure is the
    same and `skip` is a parameter rather than an assumption.
    """

    family = "xsmom"

    def __init__(
        self,
        lookback: int = 180,
        skip: int = 21,
        n_long: int = 5,
        rebalance: int = 7,
        vol_target: float | None = 0.20,
        vol_lookback: int = 30,
        max_leverage: float = 1.0,
    ) -> None:
        super().__init__(
            lookback=lookback,
            skip=skip,
            n_long=n_long,
            rebalance=rebalance,
            vol_target=vol_target,
            vol_lookback=vol_lookback,
            max_leverage=max_leverage,
        )

    def signal(self, panel: Panel) -> pd.DataFrame:
        close = panel.close
        skip, lookback = self.params["skip"], self.params["lookback"]
        return close.shift(skip) / close.shift(skip + lookback) - 1.0

    def _rank_and_select(self, score: pd.DataFrame, panel: Panel, universe, ascending: bool) -> pd.DataFrame:
        eligible = panel.tradable()
        if universe is not None:
            eligible = eligible & universe.reindex_like(eligible).fillna(False)
        ranked = score.where(eligible & score.notna()).rank(axis=1, ascending=ascending, method="first")
        picked = (ranked <= self.params["n_long"]).astype(float)
        return _hold_between_rebalances(picked, self.params["rebalance"])

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        picked = self._rank_and_select(self.signal(panel), panel, universe, ascending=False)
        weights = self.normalise(self.mask_to_universe(picked, panel, universe))
        target = self.params["vol_target"]
        if target:
            weights = VolTarget(
                annual_target=target,
                lookback=self.params["vol_lookback"],
                max_leverage=self.params["max_leverage"],
            ).scale(weights, panel)
        return weights.fillna(0.0)


class ShortTermReversal(CrossSectionalMomentum):
    """Buy last week's biggest losers.

    The mirror image of the momentum family and the reason `skip` exists in it.
    The mechanism claimed is liquidity provision: a coin that fell hard in a
    week did so partly because sellers needed out, and someone is paid for
    taking the other side.

    This is the family most likely to be destroyed by costs — it rebalances
    into and out of the most volatile names in the universe every week — which
    is exactly why gate 2 runs before anything else gets excited.
    """

    family = "reversal"

    def __init__(
        self,
        lookback: int = 7,
        n_long: int = 5,
        rebalance: int = 7,
        vol_target: float | None = 0.20,
        vol_lookback: int = 30,
        max_leverage: float = 1.0,
    ) -> None:
        Strategy.__init__(
            self,
            lookback=lookback,
            n_long=n_long,
            rebalance=rebalance,
            vol_target=vol_target,
            vol_lookback=vol_lookback,
            max_leverage=max_leverage,
        )

    def signal(self, panel: Panel) -> pd.DataFrame:
        return panel.close / panel.close.shift(self.params["lookback"]) - 1.0

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        # ascending=True: rank 1 is the worst performer, which is what we buy.
        picked = self._rank_and_select(self.signal(panel), panel, universe, ascending=True)
        weights = self.normalise(self.mask_to_universe(picked, panel, universe))
        target = self.params["vol_target"]
        if target:
            weights = VolTarget(
                annual_target=target,
                lookback=self.params["vol_lookback"],
                max_leverage=self.params["max_leverage"],
            ).scale(weights, panel)
        return weights.fillna(0.0)


# ------------------------------------------------------------------ the control


def wilder_rsi(close: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Wilder's RSI, computed across a whole panel at once.

    Seeded exactly as `centaur.indicators.rsi` does it — a simple mean of the
    first `period` changes, then recursive smoothing at alpha = 1/period — and
    the test suite checks the two agree column by column. Two implementations
    of the same definition that disagree would mean the control strategy is not
    the setup it claims to be, which would make the whole comparison worthless.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    def _wilder(frame: pd.DataFrame) -> pd.DataFrame:
        if len(frame) <= period:
            return pd.DataFrame(np.nan, index=frame.index, columns=frame.columns)
        seeded = frame.copy()
        seed = frame.iloc[1 : period + 1].mean()  # row 0 is the NaN from diff()
        seeded.iloc[: period + 1] = np.nan
        seeded.iloc[period] = seed
        return seeded.ewm(alpha=1.0 / period, adjust=False, ignore_na=True).mean()

    avg_gain, avg_loss = _wilder(gain), _wilder(loss)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(avg_loss != 0.0, 100.0)  # no losses at all -> RSI 100
    return out.where(avg_gain.notna() & avg_loss.notna())


def relative_volume(volume: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Today's volume over the average of the *previous* `window` bars.

    The shift matters: dividing by a window that includes today leaks today's
    volume into its own baseline and makes the ratio impossible to exceed by
    much, which would quietly weaken the filter rather than break it.
    """
    baseline = volume.shift(1).rolling(window, min_periods=window).mean()
    return volume / baseline


class RSIReversal(Strategy):
    """The existing Centaur setup, run as a systematic strategy. **The control.**

    Three consecutive down closes, each on above-average volume, with RSI below
    `rsi_max` — then hold for `hold` bars. This is `centaur/screens/
    pattern_matcher.py`'s `SetupSpec`, ported unchanged, and it is in the trial
    to fail.

    That is not a prediction about this particular setup. It is the point of
    having a control at all: a validation engine that passes everything it is
    shown is worthless, and the only way to know it can say no is to hand it
    something that should get a no. The setup was chosen by eye on US equities,
    has never been costed, never been swept, and never met a multiple-testing
    correction. If it passes nine gates on crypto spot, the surprise is
    informative and the first thing to check is the engine.

    Six parameters, which is over gate 8's limit of five — also deliberate, and
    also true of the original.
    """

    family = "rsi_reversal"

    def __init__(
        self,
        down_days: int = 3,
        volume_multiple: float = 1.0,
        volume_window: int = 20,
        rsi_period: int = 14,
        rsi_max: float = 30.0,
        hold: int = 5,
    ) -> None:
        super().__init__(
            down_days=down_days,
            volume_multiple=volume_multiple,
            volume_window=volume_window,
            rsi_period=rsi_period,
            rsi_max=rsi_max,
            hold=hold,
        )

    def setup(self, panel: Panel) -> pd.DataFrame:
        """True on bars where the setup is complete. Mirrors `flag_setup`."""
        close = panel.close
        volume = panel.get("volume")
        if volume is None:
            raise ValueError("the RSI setup needs a volume field")
        down = close.diff() < 0
        volume_ok = relative_volume(volume, self.params["volume_window"]) > self.params["volume_multiple"]
        both = (down & volume_ok).astype(float)
        streak = both.rolling(self.params["down_days"]).sum() == self.params["down_days"]
        rsi_ok = wilder_rsi(close, self.params["rsi_period"]) < self.params["rsi_max"]
        return (streak & rsi_ok).fillna(False)

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        fired = self.setup(panel)
        hold = self.params["hold"]
        # A position opened on a signal bar stays on for `hold` bars; overlapping
        # signals do not double the size, they just extend the holding.
        held = fired.rolling(hold, min_periods=1).max().fillna(0.0).astype(float)
        return self.normalise(self.mask_to_universe(held, panel, universe))
