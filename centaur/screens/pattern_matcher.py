"""Prompt #1 - The Historical Pattern Matcher.

    "Scan the S&P 500 for stocks that have dropped 3 consecutive days on
     above-average volume, but have an RSI below 30. Then tell me the
     historical 5-day forward return of this exact setup over the last
     10 years."

`flag_setup` marks every bar in a price history where the setup fired,
`backtest_setup` measures what happened `horizon` days later each time, and
`scan_universe` finds the tickers where the setup is firing *today* and
attaches each one's own historical statistics.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Iterable

import numpy as np
import pandas as pd

from ..indicators import rsi, consecutive_down_days, relative_volume, avg_dollar_volume

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SetupSpec:
    down_days: int = 3            # consecutive lower closes
    volume_multiple: float = 1.0  # each down day's volume must exceed this x the 20d average
    volume_window: int = 20
    rsi_period: int = 14
    rsi_max: float = 30.0
    horizon: int = 5              # forward-return horizon in trading days

    def describe(self) -> str:
        return (
            f"{self.down_days} consecutive down days, each on > {self.volume_multiple:.1f}x "
            f"the {self.volume_window}-day average volume, RSI({self.rsi_period}) < {self.rsi_max:g}; "
            f"{self.horizon}-day forward return"
        )


@dataclass
class SetupStats:
    occurrences: int
    win_rate: float          # fraction of occurrences with positive forward return
    mean_return: float
    median_return: float
    std_return: float
    best: float
    worst: float
    baseline_mean: float     # mean `horizon`-day return of *all* bars, for comparison
    edge: float              # mean_return - baseline_mean
    t_stat: float            # crude significance of the edge
    last_occurrence: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        if self.occurrences == 0:
            return "no historical occurrences"
        return (
            f"n={self.occurrences}, win rate {self.win_rate:.0%}, mean {self.mean_return:+.2%}, "
            f"median {self.median_return:+.2%}, baseline {self.baseline_mean:+.2%}, "
            f"edge {self.edge:+.2%} (t={self.t_stat:.1f})"
        )


@dataclass
class ScanHit:
    ticker: str
    date: str
    close: float
    rsi: float
    consecutive_down: int
    relative_volume: float
    drawdown_pct: float           # move over the down streak
    avg_dollar_volume: float
    stats: SetupStats
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stats"] = self.stats.to_dict()
        return d


def flag_setup(df: pd.DataFrame, spec: SetupSpec = SetupSpec()) -> pd.Series:
    """Boolean Series: True on bars where the setup is complete."""
    close, volume = df["Close"], df["Volume"]
    down = close.diff() < 0
    vol_ok = relative_volume(volume, spec.volume_window) > spec.volume_multiple
    both = (down & vol_ok).astype(int)
    streak_ok = both.rolling(spec.down_days).sum() == spec.down_days
    rsi_ok = rsi(close, spec.rsi_period) < spec.rsi_max
    out = (streak_ok & rsi_ok).fillna(False)
    return out.astype(bool).rename("setup")


def forward_returns(close: pd.Series, horizon: int) -> pd.Series:
    return (close.shift(-horizon) / close - 1.0).rename(f"fwd_{horizon}d")


def backtest_setup(df: pd.DataFrame, spec: SetupSpec = SetupSpec(), min_bars: int = 60) -> SetupStats:
    """Forward-return statistics of every historical occurrence of the setup.

    Occurrences whose forward window has not completed yet (the last
    `horizon` bars) are excluded so today's signal never contaminates its
    own statistics.
    """
    empty = SetupStats(0, float("nan"), float("nan"), float("nan"), float("nan"),
                       float("nan"), float("nan"), float("nan"), float("nan"), float("nan"))
    if len(df) < min_bars:
        return empty
    signal = flag_setup(df, spec)
    fwd = forward_returns(df["Close"], spec.horizon)
    fired = fwd[signal & fwd.notna()]
    baseline = float(fwd.dropna().mean()) if fwd.notna().any() else float("nan")
    if fired.empty:
        empty.baseline_mean = baseline
        return empty
    n = int(len(fired))
    mean = float(fired.mean())
    std = float(fired.std(ddof=1)) if n > 1 else float("nan")
    t_stat = float((mean - baseline) / (std / np.sqrt(n))) if n > 1 and std > 0 else float("nan")
    return SetupStats(
        occurrences=n,
        win_rate=float((fired > 0).mean()),
        mean_return=mean,
        median_return=float(fired.median()),
        std_return=std,
        best=float(fired.max()),
        worst=float(fired.min()),
        baseline_mean=baseline,
        edge=mean - baseline,
        t_stat=t_stat,
        last_occurrence=str(fired.index[-1].date()),
    )


def scan_universe(
    histories: dict[str, pd.DataFrame],
    spec: SetupSpec = SetupSpec(),
    min_avg_dollar_volume: float = 0.0,
) -> list[ScanHit]:
    """Find tickers where the setup fired on the most recent bar."""
    hits: list[ScanHit] = []
    for ticker, df in histories.items():
        if df is None or len(df) < 60:
            continue
        try:
            signal = flag_setup(df, spec)
            if not bool(signal.iloc[-1]):
                continue
            adv = avg_dollar_volume(df).iloc[-1]
            if min_avg_dollar_volume and (np.isnan(adv) or adv < min_avg_dollar_volume):
                continue
            streak = int(consecutive_down_days(df["Close"]).iloc[-1])
            start_px = float(df["Close"].iloc[-1 - streak])
            last_px = float(df["Close"].iloc[-1])
            stats = backtest_setup(df, spec)
            hit = ScanHit(
                ticker=ticker,
                date=str(df.index[-1].date()),
                close=last_px,
                rsi=float(rsi(df["Close"], spec.rsi_period).iloc[-1]),
                consecutive_down=streak,
                relative_volume=float(relative_volume(df["Volume"], spec.volume_window).iloc[-1]),
                drawdown_pct=last_px / start_px - 1.0,
                avg_dollar_volume=float(adv),
                stats=stats,
            )
            hit.signals.append(
                f"technical: {streak}-day capitulation on {hit.relative_volume:.1f}x volume, RSI {hit.rsi:.0f}"
            )
            if stats.occurrences >= 10 and stats.edge > 0 and stats.win_rate >= 0.55:
                hit.signals.append(
                    f"statistical: setup has {stats.win_rate:.0%} win rate over {stats.occurrences} occurrences"
                )
            hits.append(hit)
        except Exception as exc:  # keep scanning the rest of the universe
            log.warning("scan failed for %s: %s", ticker, exc)
    # Best expectancy first; unknown stats last.
    hits.sort(key=lambda h: (-(h.stats.edge if h.stats.occurrences else -9), -h.stats.occurrences))
    return hits


def pooled_stats(histories: dict[str, pd.DataFrame], spec: SetupSpec = SetupSpec()) -> SetupStats:
    """Pool every occurrence across the whole universe into one distribution.

    Answers "what is the historical 5-day forward return of this exact setup"
    for the index as a whole rather than one name at a time.
    """
    fired_all: list[pd.Series] = []
    base_all: list[pd.Series] = []
    for df in histories.values():
        if df is None or len(df) < 60:
            continue
        sig = flag_setup(df, spec)
        fwd = forward_returns(df["Close"], spec.horizon)
        fired_all.append(fwd[sig & fwd.notna()])
        base_all.append(fwd.dropna())
    fired = pd.concat(fired_all) if fired_all else pd.Series(dtype=float)
    base = pd.concat(base_all) if base_all else pd.Series(dtype=float)
    if fired.empty:
        return SetupStats(0, *([float("nan")] * 9))
    n = len(fired)
    mean, std = float(fired.mean()), float(fired.std(ddof=1))
    baseline = float(base.mean())
    return SetupStats(
        occurrences=int(n),
        win_rate=float((fired > 0).mean()),
        mean_return=mean,
        median_return=float(fired.median()),
        std_return=std,
        best=float(fired.max()),
        worst=float(fired.min()),
        baseline_mean=baseline,
        edge=mean - baseline,
        t_stat=float((mean - baseline) / (std / np.sqrt(n))) if std > 0 else float("nan"),
        last_occurrence=str(fired.index.max().date()),
    )
