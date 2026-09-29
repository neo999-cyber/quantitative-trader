"""E1's instrument: the overnight return of a Nasdaq-listed name, with the
closing-cross imbalance as its decision-time feature (`docs/prereg/p2_auction_imbalance_v1.md`).

The synthetic price `P` of a name moves only from one session's close to
the next session's open: `P_t / P_{t-1} = open_t / close_{t-1}`. A book set
at the close of `t-1` and held over bar `t` therefore earns exactly the
overnight return the family claims, and none of the intraday move. Bars are
sessions; `open_time` is the session date at 00:00 UTC.

A night whose open is more than 40% away from the previous close is a
corporate action (a 10:1 split), not a return, and its bar is left empty; the
bar after it has no previous price to return from and is empty too. Roughly
a dozen such nights exist in the 31 names over 2018–2026, and inventing a
split ratio for them is not something this loader does.

Features from `qr.data.imbalance.closing_snapshots`, at bar `t-1` (the
decision bar): `imb_HHMM` = signed imbalance / paired (negative is a sell
imbalance), `paired_usd_HHMM`, `imb_age_HHMM`; a snapshot older than
`max_age_seconds` at its cutoff is not a feature. `closing_snapshots` only
stamps a message received at or before the cutoff, so the point-in-time
assertion is met by construction.
"""
from __future__ import annotations

import pandas as pd

MARKET = "auction-xnas"
SOURCE = "databento"
SPLIT_THRESHOLD = 0.40
SNAPSHOTS = ("15:50", "15:55", "15:58")

#: QQQ and the 30 Nasdaq-listed stocks that were Nasdaq-100 members
#: throughout 2018–2026 (the E1 pre-registration's `nasdaq31`).
NASDAQ31 = (
    "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "PEP", "CSCO", "ADBE", "INTU", "QCOM", "TXN", "ISRG", "AMGN", "CMCSA",
    "INTC", "BKNG", "AMAT", "MU", "LRCX", "ADI", "GILD", "SBUX", "MDLZ",
)


#: A raw ticker is not an instrument. `META` was the Roundhill Metaverse ETF
#: until Facebook took the symbol on 9 June 2022 (read off the panel: a
#: $12 close followed by a $196 open), so the name's history starts there.
SYMBOL_START = {"META": "2022-06-09"}


def auction_frame(bars: pd.DataFrame, snapshots: pd.DataFrame, max_age_seconds: float = 10.0) -> pd.DataFrame:
    """One name's overnight-return bars with the decision-time imbalance features."""
    bars = bars.sort_index()
    overnight = bars["open"] / bars["close"].shift(1) - 1.0
    split_night = (overnight.abs() > SPLIT_THRESHOLD).fillna(False)
    growth = (1.0 + overnight.fillna(0.0)).where(~split_night, 1.0)
    price = float(bars["close"].iloc[0]) * growth.cumprod()
    price = price.where(~split_night)
    out = pd.DataFrame(
        {
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            # the day's Nasdaq dollar volume, and base volume in the
            # instrument's own price space so quote == volume x price holds
            # (the QA identity the carry unit failed at gate 1 on 15 Sep)
            "quote_volume": bars["volume"].astype(float) * bars["close"].astype(float),
            "volume": (bars["volume"].astype(float) * bars["close"].astype(float)) / price,
            "session_open": bars["open"].astype(float),
            "session_close": bars["close"].astype(float),
            "split_night": split_night.astype(float),
        },
        index=bars.index,
    )
    for snap in SNAPSHOTS:
        tag = snap.replace(":", "")
        out[f"imb_{tag}"] = float("nan")
        out[f"paired_usd_{tag}"] = float("nan")
        out[f"imb_age_{tag}"] = float("nan")
    if snapshots is not None and len(snapshots):
        fresh = snapshots[snapshots["age_seconds"] <= max_age_seconds]
        for snap, group in fresh.groupby("snapshot"):
            tag = snap.replace(":", "")
            stamps = pd.DatetimeIndex(pd.to_datetime(group["session"])).tz_localize("UTC")
            group = group.set_index(stamps)
            group = group[~group.index.duplicated(keep="last")]
            aligned = group.reindex(out.index)
            out[f"imb_{tag}"] = aligned["imbalance_ratio"].astype(float)
            out[f"paired_usd_{tag}"] = (aligned["paired_qty"] * aligned["ref_price"]).astype(float)
            out[f"imb_age_{tag}"] = aligned["age_seconds"].astype(float)
    out.index.name = "open_time"
    return out


def build_auction_lake(lake, daily_bars: dict[str, pd.DataFrame], snapshots: pd.DataFrame) -> pd.DataFrame:
    """Write every name's auction frame under `auction-xnas`; returns a summary."""
    rows = []
    for symbol, bars in daily_bars.items():
        if symbol in SYMBOL_START:
            bars = bars[bars.index >= pd.Timestamp(SYMBOL_START[symbol], tz="UTC")]
        snaps = snapshots[snapshots["symbol"] == symbol]
        frame = auction_frame(bars, snaps)
        lake.write_klines(symbol, frame, "1d", source=SOURCE, market=MARKET)
        rows.append(
            {
                "symbol": symbol,
                "sessions": len(frame),
                "start": frame.index[0],
                "end": frame.index[-1],
                "split_nights": int(frame["split_night"].sum()),
                "snapshots_1555": int(frame["imb_1555"].notna().sum()),
                "mean_imb_1555": round(float(frame["imb_1555"].mean()), 4),
            }
        )
    return pd.DataFrame(rows)
