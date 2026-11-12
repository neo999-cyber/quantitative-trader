"""The `trend_reset` family's instruments (`docs/prereg/p6_trend_reset_v1.md`).

Two markets, the same columns:

- **`trend-xnas`** (source `databento`): one bar per regular session for each of the 31 Nasdaq names, built from the
  lake's own minute bars (`xnas`, 1m). The open is the first regular minute's open; the close is the closing auction's
  print — the open of the minute stamped at the close, 16:00 New York and 13:00 on an early close — or, when that
  minute is missing, the last regular minute's close. Adjusted for splits, not for dividends. The lake's own daily
  bars for these names run 04:00–19:59 and are not session bars (`docs/20`, 1 November 2026), which is why these are
  built from minutes.
- **`trend-etf`** (source `tiingo`): the twelve ETFs' daily bars as the lake holds them, adjusted for splits and
  dividends, with the share volume restated in the adjusted price space so that dollars over shares is the bar's price.

**Splits.** A session that opens more than `SPLIT_GAP` below the previous close (or the same distance above it, a
reverse split) is a corporate action, not a return. Its ratio is read as the nearest of `SPLIT_RATIOS` within
`SPLIT_TOLERANCE`; every earlier price is divided by it and every earlier share volume multiplied. A night that fits
no ratio is left as it is and reported as unexplained, never guessed.

**Features.** The rule's inputs (`qr.strategies.trend.features`) are computed on each name's full history and stored
on the bar at whose close they are known, so a panel cut at any date arrives warmed up: the engine's gates run the
rule on sub-panels, and a rule that needs 252 bars before its first signal would otherwise spend a one-year holdout
warming up.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qr.data.auction import NASDAQ31, SYMBOL_START
from qr.strategies.trend import ROCS, features

XNAS_MARKET, XNAS_SOURCE = "trend-xnas", "databento"
ETF_MARKET, ETF_SOURCE = "trend-etf", "tiingo"
NY = "America/New_York"
ETF12 = ("DBC", "EEM", "EFA", "GLD", "HYG", "IEF", "IWM", "LQD", "QQQ", "SPY", "TLT", "VNQ")
SPLIT_GAP = 0.40
SPLIT_RATIOS = (2, 3, 4, 5, 7, 8, 10, 15, 20, 25, 50)
SPLIT_TOLERANCE = 0.10

#: Sessions that closed at 13:00 New York (the exchange's published schedule, 2018–2026).
EARLY_CLOSES = frozenset(
    pd.Timestamp(d).date()
    for d in (
        "2018-07-03", "2018-11-23", "2018-12-24", "2019-07-03", "2019-11-29", "2019-12-24", "2020-11-27", "2020-12-24",
        "2021-11-26", "2022-11-25", "2023-07-03", "2023-11-24", "2024-07-03", "2024-11-29", "2024-12-24",
        "2025-07-03", "2025-11-28", "2025-12-24", "2026-11-27", "2026-12-24",
    )
)


def session_bars(minutes: pd.DataFrame) -> pd.DataFrame:
    """One bar per regular session from minute bars stamped with the start of their minute (UTC)."""
    minutes = minutes.sort_index()                                         # every mask below is positional: order first
    stamps = pd.DatetimeIndex(minutes.index)
    if stamps.tz is None:
        stamps = stamps.tz_localize("UTC")
    local = stamps.tz_convert(NY)
    frame = pd.DataFrame(
        {
            "open": minutes["open"].to_numpy(dtype=float),
            "high": minutes["high"].to_numpy(dtype=float),
            "low": minutes["low"].to_numpy(dtype=float),
            "close": minutes["close"].to_numpy(dtype=float),
            "volume": minutes["volume"].to_numpy(dtype=float),
        }
    )
    frame["day"] = local.tz_localize(None).normalize()
    minute = (local.hour * 60 + local.minute).to_numpy()
    early = np.isin(frame["day"].dt.date.to_numpy(), list(EARLY_CLOSES))
    close_at = np.where(early, 13 * 60, 16 * 60)
    frame["dollars"] = frame["volume"] * frame["close"]
    inside = frame[(minute >= 9 * 60 + 30) & (minute < close_at)]
    at_close = frame[minute == close_at]
    body = inside.groupby("day").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), last=("close", "last"),
        volume=("volume", "sum"), dollars=("dollars", "sum"), minutes=("close", "size"),
    )
    cross = at_close.groupby("day").agg(cross=("open", "first"), cross_volume=("volume", "first"))
    out = body.join(cross)
    close = out["cross"].fillna(out["last"])
    cross_volume = out["cross_volume"].fillna(0.0)
    bars = pd.DataFrame(
        {
            "open": out["open"],
            "high": np.maximum(out["high"], close),
            "low": np.minimum(out["low"], close),
            "close": close,
            "volume": out["volume"] + cross_volume,
            "quote_volume": out["dollars"] + cross_volume * close,
            "early_close": np.isin(out.index.date, list(EARLY_CLOSES)).astype(float),
            "has_cross": out["cross"].notna().astype(float),
            "cross_share": cross_volume / (out["volume"] + cross_volume).where((out["volume"] + cross_volume) > 0),
            "minutes": out["minutes"].astype(float),
        }
    )
    bars.index = pd.DatetimeIndex(bars.index).tz_localize("UTC")
    bars.index.name = "open_time"
    return bars


def split_adjust(bars: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Back-adjust prices and share volume for the splits the opens reveal; returns the bars and the events found."""
    bars = bars.sort_index()
    gap = bars["open"] / bars["close"].shift(1)
    factor = pd.Series(1.0, index=bars.index)
    events: list[dict] = []
    for stamp, g in gap[(gap < 1.0 - SPLIT_GAP) | (gap > 1.0 / (1.0 - SPLIT_GAP))].items():
        size = 1.0 / g if g < 1.0 else g
        ratio = min(SPLIT_RATIOS, key=lambda k: abs(size / k - 1.0))
        explained = abs(size / ratio - 1.0) <= SPLIT_TOLERANCE
        events.append({"date": stamp.date().isoformat(), "ratio": (ratio if g < 1.0 else -ratio) if explained else 0, "gap": round(float(g), 4)})
        if explained:
            factor[bars.index < stamp] *= (1.0 / ratio) if g < 1.0 else float(ratio)
    out = bars.copy()
    out["close_unadjusted"] = bars["close"]
    for col in ("open", "high", "low", "close"):
        out[col] = bars[col] * factor
    out["volume"] = bars["volume"] / factor
    out["split_factor"] = factor
    return out, events


def with_features(bars: pd.DataFrame) -> pd.DataFrame:
    """The bars with the rule's inputs, computed on this name's own history."""
    out = bars.copy()
    for name, frame in features(bars[["close"]], ROCS).items():
        out[name] = frame["close"]
    return out


def build_trend_xnas(lake, symbols=None) -> pd.DataFrame:
    """Write every name's session bars and features under `trend-xnas`; returns a summary of counts."""
    rows = []
    for symbol in symbols or NASDAQ31:
        minutes = lake.read_klines(symbol, "1m", source=XNAS_SOURCE, market="xnas")
        if symbol in SYMBOL_START:
            minutes = minutes[minutes.index >= pd.Timestamp(SYMBOL_START[symbol], tz="UTC")]
        if minutes.empty:
            rows.append({"symbol": symbol, "sessions": 0})
            continue
        bars, events = split_adjust(session_bars(minutes))
        frame = with_features(bars)
        lake.write_klines(symbol, frame, "1d", source=XNAS_SOURCE, market=XNAS_MARKET)
        ready = frame["zroc_63"].first_valid_index()
        normal = frame[frame["early_close"] == 0.0]
        rows.append(
            {
                "symbol": symbol,
                "sessions": len(frame),
                "start": frame.index[0].date().isoformat(),
                "end": frame.index[-1].date().isoformat(),
                "splits": " ".join(f"{e['ratio']}:1@{e['date']}" for e in events if e["ratio"]) or "-",
                "unexplained": sum(1 for e in events if not e["ratio"]),
                "early": int(frame["early_close"].sum()),
                "no_cross": int((frame["has_cross"] == 0.0).sum()),
                "short_days": int((normal["minutes"] < 300).sum()),
                "cross_share_med": round(float(frame["cross_share"].median()), 3),
                "features_from": ready.date().isoformat() if ready is not None else "-",
                "trend_bars": int((frame["trend_ok"] > 0.5).sum()),
            }
        )
    return pd.DataFrame(rows)


def build_trend_etf(lake, symbols=None) -> pd.DataFrame:
    """Write the twelve ETFs' bars with the rule's inputs under `trend-etf`; returns a summary of counts."""
    rows = []
    for symbol in symbols or ETF12:
        bars = lake.read_klines(symbol, "1d", source=ETF_SOURCE, market="etf")
        if bars.empty:
            rows.append({"symbol": symbol, "sessions": 0})
            continue
        keep = [c for c in ("open", "high", "low", "close", "volume", "quote_volume", "close_unadjusted") if c in bars.columns]
        frame = bars[keep].sort_index().copy()
        # Dollars over shares must be a price on the bar, or `Panel.tradable` refuses it. The ETF ingest states the
        # share count in the adjusted price space since 12 November 2026 (`qr/data/tiingo.py`, `docs/20`), so on a lake
        # ingested since then this restates the same numbers; it stays so that a lake ingested before then — adjusted
        # prices beside shares as traded, every dividend payer masked — still builds a consistent instrument.
        if "quote_volume" in frame.columns:
            frame["volume"] = frame["quote_volume"] / frame["close"]
        frame = with_features(frame)
        lake.write_klines(symbol, frame, "1d", source=ETF_SOURCE, market=ETF_MARKET)
        ready = frame["zroc_63"].first_valid_index()
        rows.append(
            {
                "symbol": symbol,
                "sessions": len(frame),
                "start": frame.index[0].date().isoformat(),
                "end": frame.index[-1].date().isoformat(),
                "features_from": ready.date().isoformat() if ready is not None else "-",
                "trend_bars": int((frame["trend_ok"] > 0.5).sum()),
            }
        )
    return pd.DataFrame(rows)
