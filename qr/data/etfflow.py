"""The ETF-flow instrument (`docs/prereg/p4_etf_flow_pressure_v1.md`): Programme 4's first panel.

One symbol, the BTCUSDT USDⓈ-M perpetual on hourly bars — the instrument stage 1 measured its maker fill
and fee on (`docs/33`) — with the venue's funding on the bar it is paid for (`qr.data.funding.bar_funding`)
and the issuer's daily creation/redemption flow standardised and placed on **the one bar a rule may act on
it**. Nothing in here reads a flow against a price: the build is a join and a count.

**What the issuer's row means, and when it is known.** iShares' workbook (`reference/etf_flows_ishares_daily`,
`qr.data.etf_flows.build_crypto_etf_flows`) dates a creation by the NAV date on which the shares were issued,
one business day after the day the authorised participant placed the order and the desk bought the coin:
the aggregators' "flow of 12 October" is the issuer's row of 13 October (`docs/31` §18; the record day of 7
November 2024 sits on the 8th in the series). Call the trade date T and the issuer's row date D = T + 1
session. The row is published after D's close and the box reads it at 06:00 UTC the next morning, so the
flow of T is known to us on the morning of the session after D — **T + 2 sessions, the primary arm**
(`etf_flow_z_t2`). An aggregator publishes the flow of T on the evening of T; that path exists live from
15 October 2026 and has no history, so the **T + 1 arm** (`etf_flow_z_t1`, the row acted on during D
itself) is a diagnostic of the mechanism's speed, not a candidate for money.

**Placement.** The standardised flow of row D sits on the bar whose *close* is 09:00 New York time on the
entry session (12:00 UTC open time in summer, 13:00 in winter), so the runner's one-bar shift makes the
order fill at 09:00 — before the cash open — and the position is held over the session. Every other bar
carries NaN. Entry sessions follow the New York exchange calendar (`qr.data.qa.trading_sessions`), which is
public years ahead: the row of a Friday enters on Monday, the row before Good Friday on the Monday after.

**Standardisation.** `z_D = flow_D / mean(|flow|)` over the sixty rows *before* D (the row itself
excluded), defined once twenty rows exist. A flat day is z = 0, never a trade.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

MARKET = "etfflow-um"
SOURCE = "binance"
PERP_MARKET = "futures/um"
BTC_ONLY = ("BTCUSDT",)
TICKER = "IBIT"
REFERENCE = "etf_flows_ishares_daily"
WINDOW = 60
MIN_ROWS = 20
NY = "America/New_York"
ENTRY_LOCAL = "09:00"
TIMINGS = ("t2", "t1")
FEATURES = tuple(f"etf_flow_z_{t}" for t in TIMINGS)
#: the registered thresholds, counted by the build so the sample minimum is known before any run
GRID_K = (0.5, 1.0, 1.5)


def _naive_days(dates: Iterable) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    return idx.normalize()


def flow_z(flow: pd.Series, window: int = WINDOW, min_rows: int = MIN_ROWS) -> pd.DataFrame:
    """`flow` indexed by the issuer's NAV date, one row a session: the flow, its scale and `z`.

    The scale is the mean absolute flow of the `window` rows before the row — the row itself is not in its
    own denominator — and needs `min_rows` of them; earlier rows have no `z`. A zero scale (a fund that has
    not traded yet) gives no `z` either.
    """
    s = flow.dropna().astype(float)
    s.index = _naive_days(s.index)
    s = s.sort_index()
    scale = s.abs().shift(1).rolling(window, min_periods=min_rows).mean()
    z = s / scale.where(scale > 0)
    return pd.DataFrame({"flow_usd": s, "scale": scale, "z": z})


def entry_days(nav_dates: Iterable, timing: str) -> pd.DatetimeIndex:
    """The session a rule may first act on the row dated D.

    `t1`: D itself (the aggregator's evening-of-T publication, assumed; the diagnostic arm). `t2`: the first
    New York session on or after D + 1 calendar day (the issuer's row, read by the box at 06:00 UTC the next
    morning; the primary arm).
    """
    days = _naive_days(nav_dates)
    if timing == "t1":
        return days
    if timing != "t2":
        raise ValueError(f"timing is 't2' (the issuer's row, primary) or 't1' (the diagnostic arm), not {timing!r}")
    if len(days) == 0:
        return days
    from qr.data.qa import trading_sessions

    sessions = trading_sessions(days.min(), days.max() + pd.Timedelta(days=10)).tz_localize(None)
    pos = sessions.searchsorted(days + pd.Timedelta(days=1), side="left")
    return pd.DatetimeIndex(sessions[pos])


def decision_bars(entry: Iterable, interval: str = "1h", local_time: str = ENTRY_LOCAL) -> pd.DatetimeIndex:
    """The bar whose close is `local_time` New York on each entry day: the bar a target is set on."""
    step = pd.Timedelta(interval)
    stamps = [pd.Timestamp(f"{d.date()} {local_time}", tz=NY).tz_convert("UTC") - step for d in _naive_days(entry)]
    return pd.DatetimeIndex(stamps, tz="UTC") if stamps else pd.DatetimeIndex([], tz="UTC")


def flow_features(
    flows: pd.DataFrame, index: pd.DatetimeIndex, interval: str = "1h", window: int = WINDOW, min_rows: int = MIN_ROWS
) -> pd.DataFrame:
    """`etf_flow_z_t2` / `etf_flow_z_t1` on `index`: each row's `z` on its decision bar, NaN elsewhere.

    `flows` has `date` and `flow_usd` for one fund. A row whose decision bar is not in `index` (no bar that
    hour) is dropped and counted in `attrs["unplaced_<timing>"]`; two rows landing on one bar (an issuer
    row on a day the calendar calls closed) keep the later row and count in `attrs["collisions_<timing>"]`.
    """
    z = flow_z(flows.set_index("date")["flow_usd"], window, min_rows)
    out = pd.DataFrame(index=index)
    for timing in TIMINGS:
        days = entry_days(z.index, timing)
        bars = decision_bars(days, interval)
        col = pd.Series(np.nan, index=index, dtype=float)
        placed = np.asarray(bars.isin(index))
        values = z["z"].to_numpy()
        seen = pd.Index(bars[placed])
        out.attrs[f"collisions_{timing}"] = int(seen.duplicated().sum())
        out.attrs[f"unplaced_{timing}"] = int((~placed).sum())
        for bar, value in zip(bars[placed], values[placed]):
            col.loc[bar] = value
        out[f"etf_flow_z_{timing}"] = col
    return out


def build_etfflow_lake(
    lake,
    funding_bucket,
    symbols: Iterable[str] | None = None,
    interval: str = "1h",
    ticker: str = TICKER,
    window: int = WINDOW,
    min_rows: int = MIN_ROWS,
    reference: str = REFERENCE,
    count_start=None,
    count_end=None,
) -> pd.DataFrame:
    """Write the instrument for each symbol and return a summary of counts — no price is read against a flow.

    The summary carries, per timing, the decision bars with a `z` and how many clear each registered
    threshold, over the whole series and (when `count_start`/`count_end` are given) inside the registered
    in-sample window: the memo's sample minimum is checked here, before the engine runs.
    """
    from qr.data.funding import bar_funding

    path = lake.paths.reference / f"{reference}.parquet"
    flows = pd.read_parquet(path)
    flows = flows[flows["ticker"] == ticker][["date", "flow_usd"]].dropna()
    if flows.empty:
        raise ValueError(f"no {ticker} rows in {path}")
    rows = []
    for symbol in list(symbols) if symbols else list(BTC_ONLY):
        bars = lake.read_klines(symbol, interval, market=PERP_MARKET)
        keep = [c for c in ("open", "high", "low", "close", "volume", "quote_volume", "trades") if c in bars.columns]
        frame = bars[keep].copy()
        settlements = funding_bucket.load_funding(symbol)
        funding = bar_funding(settlements, interval) if len(settlements) else pd.Series(dtype=float)
        frame["funding_rate"] = funding.reindex(frame.index)
        feats = flow_features(flows, frame.index, interval, window, min_rows)
        for col in feats.columns:
            frame[col] = feats[col]
        frame.index.name = "open_time"
        lake.write_klines(symbol, frame, interval, market=MARKET)
        row = {
            "symbol": symbol, "bars": len(frame), "start": frame.index[0], "end": frame.index[-1],
            "funding_bars": int(frame["funding_rate"].notna().sum()),
            "settlements": int((frame["funding_rate"].fillna(0.0) != 0.0).sum()),
            "flow_rows": int(len(flows)), "flow_first": flows["date"].min(), "flow_last": flows["date"].max(),
        }
        windows = {"all": frame}
        if count_start is not None or count_end is not None:
            inside = frame
            if count_start is not None:
                inside = inside[inside.index >= pd.Timestamp(count_start, tz="UTC")]
            if count_end is not None:
                inside = inside[inside.index <= pd.Timestamp(count_end, tz="UTC")]
            windows["window"] = inside
        for name, part in windows.items():
            for timing in TIMINGS:
                z = part[f"etf_flow_z_{timing}"]
                row[f"{name}_{timing}_decision_bars"] = int(z.notna().sum())
                for k in GRID_K:
                    row[f"{name}_{timing}_abs_z_ge_{k}"] = int((z.abs() >= k).sum())
        row.update(feats.attrs)
        rows.append(row)
    return pd.DataFrame(rows)
