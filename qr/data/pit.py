"""Point-in-time views of published data (`docs/20_PROGRAMME_2.md` §10, item 10).

Every alternative-data loader carries `event_time`, `published_at`,
`first_observed_at`, `ingested_at` and `source_hash`. A signal computed at
time `t` may read a row only if `published_at <= t`, and if a row was later
amended it reads the version that was public at `t`, not the corrected one.
"""
from __future__ import annotations

import pandas as pd

AVAILABILITY_COLUMNS = ("event_time", "published_at", "first_observed_at", "ingested_at", "source_hash")


def asof_view(frame: pd.DataFrame, asof: pd.Timestamp, key: str | list[str], published: str = "published_at") -> pd.DataFrame:
    """Rows as they stood at `asof`: published by then, latest version per `key`.

    An amendment published after `asof` is invisible, so a backtest sees the
    same numbers the signal saw on the day; one published before replaces the
    original. Rows with no `published_at` are never visible.
    """
    if published not in frame.columns:
        raise ValueError(f"a point-in-time view needs a {published!r} column")
    stamps = pd.to_datetime(frame[published])
    asof = pd.Timestamp(asof)
    if stamps.dt.tz is None and asof.tzinfo is not None:
        asof = asof.tz_convert("UTC").tz_localize(None)
    elif stamps.dt.tz is not None and asof.tzinfo is None:
        asof = asof.tz_localize(stamps.dt.tz)
    visible = frame[stamps.notna() & (stamps <= asof)]
    if visible.empty:
        return visible
    ordered = visible.assign(_published=pd.to_datetime(visible[published])).sort_values("_published", kind="stable")
    keys = [key] if isinstance(key, str) else list(key)
    return ordered.drop_duplicates(subset=keys, keep="last").drop(columns="_published")
