"""Small Markdown helpers, so reports do not pull in a table dependency."""
from __future__ import annotations

import pandas as pd


def fmt(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, float):
        return f"{value:,.4g}"
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M" if value.tz is None else "%Y-%m-%d %H:%M %Z")
    return str(value)


def table(frame: pd.DataFrame, index: bool = False) -> str:
    """A GitHub-flavoured Markdown table."""
    body = frame.reset_index() if index else frame
    if body.empty:
        return "_(none)_\n"
    header = "| " + " | ".join(str(c) for c in body.columns) + " |\n"
    rule = "|" + "|".join("---" for _ in body.columns) + "|\n"
    rows = "".join(
        "| " + " | ".join(fmt(v) for v in row) + " |\n" for row in body.itertuples(index=False)
    )
    return header + rule + rows
