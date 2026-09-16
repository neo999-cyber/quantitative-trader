"""E1's closing-auction imbalance features (Databento `XNAS.ITCH`, schema `imbalance`).

Nasdaq disseminates the closing-cross imbalance from 15:50 ET every five
seconds (every second in the last minutes). The signal E1 pre-registers
reads it at fixed clock times so that a live decision and the backtest see
the same thing: for each snapshot cutoff the **last message received at or
before the cutoff** (a one-second grace for dissemination latency), stamped
with that message's receive time as `published_at` and its age at the
cutoff as `age_seconds`. A symbol with nothing received by the cutoff has
no row for it; a stale state is a row with a large age, for the
pre-registration to cap.

Source file: `mirror/databento/XNAS.ITCH/imbalance/*.dbn.zst`, read with the
`databento` package; the sidecar `.json` records the request, the SHA-256,
the bytes and the time it was observed. Bought once on 16 September 2026
for $6.27 of the account's credit (SPY, QQQ, IWM, DIA, 2018-05-01 to
2026-09-01).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from qr.data.pit import AVAILABILITY_COLUMNS  # noqa: F401  (the columns this frame carries)

SNAPSHOTS_ET = ("15:50", "15:55", "15:58")
GRACE = pd.Timedelta(seconds=1)
NY = "America/New_York"


def closing_snapshots(messages: pd.DataFrame, snapshots: tuple[str, ...] = SNAPSHOTS_ET) -> pd.DataFrame:
    """One row per symbol, session and snapshot: the auction as last published by the cutoff."""
    frame = messages[messages["auction_type"].eq("C")].copy()
    if frame.empty:
        return pd.DataFrame()
    recv = pd.DatetimeIndex(frame.index)
    if recv.tz is None:
        recv = recv.tz_localize("UTC")
    local = recv.tz_convert(NY)
    frame["_recv"] = recv
    frame["session"] = local.date
    rows = []
    for symbol, by_symbol in frame.groupby("symbol", sort=False):
        for session, day in by_symbol.groupby("session", sort=False):
            day = day.sort_values("_recv")
            for snap in snapshots:
                hh, mm = snap.split(":")
                cutoff = pd.Timestamp(session, tz=NY).replace(hour=int(hh), minute=int(mm)) + GRACE
                before = day[day["_recv"] <= cutoff.tz_convert("UTC")]
                if before.empty:
                    continue
                last = before.iloc[-1]
                paired = float(last["paired_qty"])
                total = float(last["total_imbalance_qty"])
                # Databento's `side`: 'B' = bid (buy) imbalance, 'A' = ask (sell)
                # imbalance, 'N' = none. The first version mapped 'S' for sell,
                # which the feed never sends, so every sell imbalance read as
                # zero and the E1 family never fired (16 September 2026).
                sign = {"B": 1.0, "A": -1.0}.get(str(last["side"]), 0.0)
                rows.append(
                    {
                        "symbol": symbol,
                        "session": session,
                        "snapshot": snap,
                        "snapshot_cutoff": cutoff.tz_convert("UTC"),
                        "ref_price": float(last["ref_price"]),
                        "ind_match_price": float(last.get("ind_match_price", float("nan"))),
                        "paired_qty": paired,
                        "total_imbalance_qty": total,
                        "side": str(last["side"]),
                        "signed_imbalance_qty": sign * total,
                        "imbalance_ratio": (sign * total / paired) if paired > 0 else float("nan"),
                        "event_time": pd.Timestamp(last["ts_event"]).tz_convert("UTC") if pd.Timestamp(last["ts_event"]).tzinfo else pd.Timestamp(last["ts_event"]).tz_localize("UTC"),
                        "published_at": pd.Timestamp(last["_recv"]).tz_convert("UTC"),
                        # how stale the last message was at the cutoff; Nasdaq
                        # publishes every five seconds, so a large age means
                        # the feed, not the auction, was quiet
                        "age_seconds": float((cutoff.tz_convert("UTC") - pd.Timestamp(last["_recv"]).tz_convert("UTC")).total_seconds()),
                    }
                )
    out = pd.DataFrame(rows)
    out["first_observed_at"] = pd.Timestamp(messages.attrs.get("first_observed_at", pd.Timestamp.now(tz="UTC")))
    out["ingested_at"] = pd.Timestamp.now(tz="UTC")
    out["source_hash"] = messages.attrs.get("source_hash", "")
    return out


def load_dbn(path: str | Path) -> pd.DataFrame:
    """Read a DBN file into the frame `closing_snapshots` expects, with provenance in `attrs`."""
    import databento as db

    path = Path(path)
    frame = db.DBNStore.from_file(path).to_df()
    sidecar = path.with_suffix(".json")
    meta = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    frame.attrs["source_hash"] = meta.get("sha256") or hashlib.sha256(path.read_bytes()).hexdigest()
    frame.attrs["first_observed_at"] = meta.get("first_observed_at", "")
    return frame
