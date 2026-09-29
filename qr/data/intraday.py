"""E2's instrument: two bars a session, the day so far and the last half hour
(`docs/prereg/p2_late_day_momentum_v1.md`).

Bar A opens at 09:30 ET and closes at the decision time (15:30 by default):
its `ret_to_decision` is the session's move so far, the signal. Bar B opens
at the decision time and closes at 16:00: its return is what a position set
at the decision earns, and the runner's one-bar shift makes a target set on
bar A the book held over bar B. A target of zero on bar B keeps nothing
overnight. The synthetic price is continuous through both bars, so the
runner's returns, turnover and costs read as they do for any panel; the
overnight move (16:00 to next 09:30) is dropped, because the family never
holds it and a bar that spans it would credit or charge a return the rule
does not take.

Minute bars are Nasdaq's (`XNAS.ITCH ohlcv-1m`, market `xnas` in the lake);
the price at the decision is the close of the last minute bar at or before
it, the close is the last regular-hours minute's close, the open the first
regular-hours minute's open. Early-close sessions (13:00) have no 15:30 and
yield no bars.
"""
from __future__ import annotations

import pandas as pd

MARKET = "intraday-xnas"
SOURCE = "databento"
NY = "America/New_York"
QQQ_ONLY = ("QQQ",)


def session_split_frames(minutes: pd.DataFrame, decision: str = "15:30") -> pd.DataFrame:
    local = minutes.copy()
    stamps = pd.DatetimeIndex(local.index)
    if stamps.tz is None:
        stamps = stamps.tz_localize("UTC")
    local.index = stamps.tz_convert(NY)
    hh, mm = (int(x) for x in decision.split(":"))
    regular = local.between_time("09:30", "16:00")
    rows = []
    for day, bars in regular.groupby(regular.index.date):
        bars = bars.sort_index()
        # Databento stamps a minute bar with the *start* of its interval, so
        # the bar stamped 15:30 closes at 15:31 and is not known at a 15:30
        # decision: only bars stamped before the decision are complete by it
        # (review 22, §1.6; until 17 September 2026 the 15:30 bar was read).
        at_decision = bars[bars.index.time < pd.Timestamp(f"{day} {decision}").time()]
        after = bars[bars.index.time >= pd.Timestamp(f"{day} {decision}").time()]
        if at_decision.empty or after.empty:
            continue  # an early close, or a day with no bars around the decision
        if bars.index[-1].time() < pd.Timestamp("15:45").time():
            continue
        open_px = float(bars["open"].iloc[0])
        px_dec = float(at_decision["close"].iloc[-1])
        # The session's closing print is the auction at 16:00:00, which is the
        # first trade of the bar stamped 16:00; that bar's close (15:59-16:01
        # prints after the auction) is not a regular-session fill.
        last = bars.iloc[-1]
        close_px = float(last["open"]) if last.name.time() == pd.Timestamp("16:00").time() else float(last["close"])
        vol_a = float(at_decision["volume"].sum()); vol_b = float(after["volume"].sum())
        rows.append((pd.Timestamp(f"{day} 09:30", tz=NY), open_px, px_dec, vol_a, px_dec / open_px - 1.0, 0.0))
        rows.append((pd.Timestamp(f"{day} {decision}", tz=NY), px_dec, close_px, vol_b, float("nan"), 1.0))
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows, columns=["stamp", "seg_open", "seg_close", "seg_volume", "ret_to_decision", "is_late"]).set_index("stamp")
    frame.index = frame.index.tz_convert("UTC")
    frame.index.name = "open_time"
    # a continuous synthetic price: each bar's return is its segment's move,
    # the overnight gap between a close and the next open is dropped
    seg_ret = frame["seg_close"] / frame["seg_open"] - 1.0
    price = float(frame["seg_open"].iloc[0]) * (1.0 + seg_ret).cumprod()
    out = pd.DataFrame(
        {
            "open": price / (1.0 + seg_ret),
            "high": pd.concat([price, price / (1.0 + seg_ret)], axis=1).max(axis=1),
            "low": pd.concat([price, price / (1.0 + seg_ret)], axis=1).min(axis=1),
            "close": price,
            "quote_volume": frame["seg_volume"] * frame["seg_close"],
            "volume": frame["seg_volume"] * frame["seg_close"] / price,
            "session_open": frame["seg_open"].where(frame["is_late"] == 0.0),
            "ret_to_decision": frame["ret_to_decision"],
            "is_late": frame["is_late"],
        },
        index=frame.index,
    )
    return out


def build_intraday_lake(lake, symbols, decision: str = "15:30") -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        minutes = lake.read_klines(symbol, "1m", source=SOURCE, market="xnas")
        frame = session_split_frames(minutes, decision)
        if frame.empty:
            rows.append({"symbol": symbol, "bars": 0, "note": "no sessions"})
            continue
        lake.write_klines(symbol, frame, "1d", source=SOURCE, market=MARKET)
        late = frame[frame["is_late"] == 1.0]["close"].pct_change()
        rows.append({"symbol": symbol, "bars": len(frame), "sessions": int(frame["is_late"].sum()), "start": frame.index[0], "end": frame.index[-1],
                     "mean_late_bps": round(float((frame["close"].pct_change()[frame["is_late"] == 1.0]).mean() * 1e4), 2)})
    return pd.DataFrame(rows)
