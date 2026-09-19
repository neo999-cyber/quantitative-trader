"""Results of QuantConnect backtests, brought home as data (`docs/20` §6, §10 item 8).

The free tier has no API, so a run's result leaves the browser as a JSON file
saved from the owner's logged-in session: the backtest record (`/api/v2/backtests/read`)
and the `Strategy Equity` chart (`/api/v2/backtests/chart/read`). The chart is
LEAN's equity sampled through the day; `daily_equity` keeps each session's
last sample, so the series the gates see is close-to-close on exchange days
and nothing else. Provenance: the backtest id, the project id and the time
the file was fetched, all in the JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

NY = "America/New_York"


def load_result(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def daily_equity(result: dict) -> pd.Series:
    """Session-end equity, indexed by session date (UTC midnight), from the chart's OHLC samples."""
    values = result["equity_chart"]["chart"]["series"]["Equity"]["values"]
    frame = pd.DataFrame(values, columns=["ts", "open", "high", "low", "close"])
    stamps = pd.to_datetime(frame["ts"], unit="s", utc=True).dt.tz_convert(NY)
    frame["session"] = stamps.dt.normalize()
    # a sample at 00:00 New York belongs to the session that just closed
    at_midnight = (stamps.dt.hour == 0) & (stamps.dt.minute == 0)
    frame.loc[at_midnight, "session"] = frame.loc[at_midnight, "session"] - pd.Timedelta(days=1)
    frame = frame[frame["session"].dt.dayofweek < 5]
    last = frame.groupby("session")["close"].last()
    last.index = pd.DatetimeIndex(last.index).tz_convert("UTC")
    last.index.name = "open_time"
    return last.astype(float).rename("equity")


def statistics(result: dict) -> dict:
    bt = result["backtest"]["backtest"]
    return dict(bt.get("statistics") or {})


def parameters(result: dict) -> dict:
    bt = result["backtest"]["backtest"]
    return {p.get("name"): p.get("value") for p in bt.get("parameterSet", []) if isinstance(p, dict)}
