"""QA checks on raw bars. The gate-1 (data integrity) evidence starts here.

Every check returns a `CheckResult` with a verdict and the offending rows, so
a failure is a list of timestamps to go and look at rather than a boolean. The
checks are deliberately blunt about the failure modes that have actually ruined
crypto backtests:

* bars whose spacing does not match the interval (the millisecond/microsecond
  switch, or a mixed-cadence concatenation);
* OHLC that cannot be a bar (`high` below `close`), which means a parse error;
* gaps inside a pair's listing window, which a forward-fill would paper over;
* zero-volume bars, which are untradable but price-bearing, and are the usual
  source of a beautiful backtest that cannot be executed;
* `quote_volume` inconsistent with `volume x price`, which means the columns
  are in the wrong order.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from qr.report import table

#: Exchange closures that no holiday rule produces: funerals, an attack, a
#: storm. Each one is a day the NYSE was shut with the calendar saying
#: otherwise, and without them every equity series in the lake carries a
#: permanent "missing bar" that is not missing.
NYSE_SPECIAL_CLOSURES = (
    "1994-04-27",  # Nixon's funeral
    "2001-09-11",  # the attacks; the market stayed shut for four sessions
    "2001-09-12",
    "2001-09-13",
    "2001-09-14",
    "2004-06-11",  # Reagan's funeral
    "2007-01-02",  # Ford's funeral
    "2012-10-29",  # Hurricane Sandy
    "2012-10-30",
    "2018-12-05",  # George H. W. Bush's funeral
    "2025-01-09",  # Carter's funeral
)

#: Which calendar a market keeps. Crypto never closes, so a missing daily bar
#: is a missing bar. An exchange is shut on weekends and about nine holidays a
#: year, and measuring it against a continuous calendar produces thousands of
#: "gaps" per symbol — a check that fires on every instrument forever teaches
#: the reader to ignore it, which is worse than not having it.
#: "sessions2" is a two-bars-a-session instrument (qr/data/intraday.py): the
#: spacing and gap checks assume one cadence and do not apply; every other
#: check does.
CALENDARS = ("continuous", "xnys", "sessions2")


def _nyse_holidays(start, end) -> pd.DatetimeIndex:
    from pandas.tseries.holiday import AbstractHolidayCalendar, GoodFriday, USFederalHolidayCalendar

    class _NYSE(AbstractHolidayCalendar):
        # Columbus Day and Veterans Day are federal holidays on which the stock
        # exchange trades; Good Friday is the reverse.
        rules = [
            rule
            for rule in USFederalHolidayCalendar.rules
            if rule.name not in {"Columbus Day", "Veterans Day"}
        ] + [GoodFriday]

    holidays = _NYSE().holidays(start=start, end=end)
    return pd.DatetimeIndex(holidays)


def trading_sessions(start, end) -> pd.DatetimeIndex:
    """The days the New York exchanges were open, inclusive, as UTC midnights.

    Rule-derived rather than listed, except for the unforeseeable closures
    above. Two rules disagree with the federal calendar before the dates their
    pandas definitions start (MLK Day before 1998, Juneteenth in 2021) — both
    err towards expecting a closure on a day that traded, which can only drop a
    session from the expectation, never invent a missing one.
    """
    start = pd.Timestamp(start).tz_localize(None).normalize()
    end = pd.Timestamp(end).tz_localize(None).normalize()
    days = pd.bdate_range(start, end)
    closed = _nyse_holidays(start, end).union(
        pd.DatetimeIndex([pd.Timestamp(d) for d in NYSE_SPECIAL_CLOSURES])
    )
    return pd.DatetimeIndex(days.difference(closed)).tz_localize("UTC")


INTERVAL_DELTA = {
    "1d": pd.Timedelta(days=1),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1w": pd.Timedelta(weeks=1),
    "1m": pd.Timedelta(minutes=1),
}


@dataclass
class CheckResult:
    name: str
    verdict: str  # PASS | WARN | FAIL
    detail: str
    offenders: pd.Index = field(default_factory=lambda: pd.DatetimeIndex([], tz="UTC"))

    @property
    def count(self) -> int:
        return len(self.offenders)

    def excluding(self, bars: pd.Index) -> "CheckResult":
        """The same check with `bars` taken out of its offenders.

        A check that had offenders and has none left passes: every bar it
        objected to has already been kept away from the strategy. A check that
        never had offenders is returned untouched, which matters because the
        index-level checks (`timezone_utc`, `non_empty`) fail with an empty
        offender list and must not be talked out of it by this.
        """
        if self.count == 0:
            return self
        remaining = self.offenders.difference(pd.Index(bars))
        if len(remaining) == len(self.offenders):
            return self
        verdict = "PASS" if len(remaining) == 0 else self.verdict
        detail = self.detail
        if len(remaining) < self.count:
            detail = f"{detail} ({self.count - len(remaining)} on bars already excluded)"
        return CheckResult(self.name, verdict, detail, remaining)


@dataclass
class QAReport:
    symbol: str
    interval: str
    rows: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    checks: list[CheckResult]

    @property
    def verdict(self) -> str:
        verdicts = {c.verdict for c in self.checks}
        return "FAIL" if "FAIL" in verdicts else ("WARN" if "WARN" in verdicts else "PASS")

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.verdict == "FAIL"]

    def excluding(self, bars: pd.Index) -> "QAReport":
        """This report re-scored over the bars a strategy could actually consume.

        `Panel.tradable()` already drops bars whose values cannot be true — the
        negative-volume BTTUSDT prints, the AUDUSDT bar whose high sits below
        its own close — so a strategy is never allowed to read them. Gate 1 was
        nonetheless failing symbols for exactly those bars, which is the
        platform blaming a strategy for data it had already withheld from it.

        Passing the excluded timestamps here removes them from every check's
        offender list. Note what it does *not* remove: `calendar_gaps` reports
        timestamps that are absent from the frame altogether, so they are not
        in the excluded set and the warning survives — which is right, because
        a hole in a listing window is a fact about the data whether or not
        anyone traded through it.
        """
        return QAReport(
            self.symbol,
            self.interval,
            self.rows,
            self.start,
            self.end,
            [c.excluding(bars) for c in self.checks],
        )

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "symbol": self.symbol,
                    "check": c.name,
                    "verdict": c.verdict,
                    "offending_bars": c.count,
                    "detail": c.detail,
                }
                for c in self.checks
            ]
        )

    def to_markdown(self) -> str:
        head = (
            f"### {self.symbol} ({self.interval}) — **{self.verdict}**\n\n"
            f"{self.rows} bars, {self.start} → {self.end}\n\n"
            "| check | verdict | bars | detail |\n|---|---|---|---|\n"
        )
        body = "".join(
            f"| {c.name} | {c.verdict} | {c.count} | {c.detail} |\n" for c in self.checks
        )
        return head + body


def check_klines(
    frame: pd.DataFrame,
    symbol: str = "?",
    interval: str = "1d",
    max_abs_return: float = 0.8,
    quote_volume_tolerance: float = 0.05,
    calendar: str = "continuous",
) -> QAReport:
    """Run every check over one symbol's bars.

    `calendar` says what "no bar today" means: nothing, for a market that never
    closes, or a missing session for one that keeps exchange hours.
    """
    if calendar not in CALENDARS:
        raise ValueError(f"unknown calendar {calendar!r}; expected one of {CALENDARS}")
    checks: list[CheckResult] = []
    empty = pd.DatetimeIndex([], tz="UTC")

    def add(name: str, bad: pd.Series | pd.Index | None, detail: str, verdict_if_bad: str = "FAIL") -> None:
        idx = empty if bad is None else (bad[bad].index if isinstance(bad, pd.Series) else bad)
        checks.append(
            CheckResult(name, "PASS" if len(idx) == 0 else verdict_if_bad, detail, idx)
        )

    if frame.empty:
        checks.append(CheckResult("non_empty", "FAIL", "no bars at all"))
        return QAReport(symbol, interval, 0, None, None, checks)

    index = pd.DatetimeIndex(frame.index)

    # -- index ----------------------------------------------------------
    checks.append(
        CheckResult(
            "timezone_utc",
            "PASS" if str(getattr(index, "tz", None)) == "UTC" else "FAIL",
            f"index tz is {getattr(index, 'tz', None)}",
        )
    )
    add("monotonic_index", None if index.is_monotonic_increasing else index[:1], "bars are out of order")
    add("unique_index", index[index.duplicated()], "duplicate bar timestamps")

    # -- spacing and gaps -------------------------------------------------
    step = INTERVAL_DELTA.get(interval)
    if step is not None and len(index) > 1 and calendar != "sessions2":
        deltas = pd.Series(index[1:] - index[:-1], index=index[1:])
        add(
            "bar_spacing",
            deltas[deltas % step != pd.Timedelta(0)].index,
            f"bar spacing is not a multiple of {interval} (timestamp unit or cadence mix)",
        )
        if calendar == "xnys" and interval == "1d":
            expected = trading_sessions(index[0], index[-1])
            detail = "exchange sessions with no bar — do not forward-fill these"
        else:
            expected = pd.date_range(index[0], index[-1], freq=step, tz="UTC")
            detail = "bars missing inside the listing window — do not forward-fill these"
        missing = expected.difference(index)
        checks.append(
            CheckResult(
                "calendar_gaps",
                "PASS" if len(missing) == 0 else "WARN",
                detail,
                missing,
            )
        )

    # -- OHLC sanity ------------------------------------------------------
    o, h, l, c = (frame[x] for x in ("open", "high", "low", "close"))
    add("positive_prices", (frame[["open", "high", "low", "close"]] <= 0).any(axis=1), "non-positive price")
    add("high_is_highest", (h < pd.concat([o, c, l], axis=1).max(axis=1)), "high below open/close/low")
    add("low_is_lowest", (l > pd.concat([o, c, h], axis=1).min(axis=1)), "low above open/close/high")
    add("prices_finite", ~np.isfinite(frame[["open", "high", "low", "close"]]).all(axis=1), "NaN or inf price")

    # -- volume -----------------------------------------------------------
    if "volume" in frame:
        add("volume_non_negative", frame["volume"] < 0, "negative volume")
        add(
            "zero_volume_bars",
            frame["volume"] <= 0,
            "bars with no trading — priced but not tradable",
            verdict_if_bad="WARN",
        )
    if "taker_buy_base" in frame and "volume" in frame:
        add(
            "taker_buy_within_volume",
            frame["taker_buy_base"] > frame["volume"] * (1 + 1e-9),
            "taker buy volume exceeds total volume (columns misaligned)",
        )
    if "quote_volume" in frame and "volume" in frame:
        traded = frame["volume"] > 0
        vwap = frame["quote_volume"].where(traded) / frame["volume"].where(traded)
        # The two sides must be in the same price space. A dividend-adjusted
        # frame carries an adjusted range and a `quote_volume` built from the
        # price that actually changed hands, so comparing them directly fails
        # every bar before the most recent distribution — which is what an
        # adjusted ETF series looks like: eleven of twelve funds "corrupt", and
        # the one that pays nothing clean. The factor puts the implied VWAP
        # back into the frame's own space before the comparison.
        low, high = l, h
        if "close_unadjusted" in frame:
            factor = (frame["close"] / frame["close_unadjusted"]).replace([np.inf, -np.inf], np.nan)
            vwap = vwap * factor.where(factor > 0)
        outside = traded & ((vwap < low * (1 - quote_volume_tolerance)) | (vwap > high * (1 + quote_volume_tolerance)))
        add(
            "quote_volume_consistent",
            outside,
            "implied VWAP outside the bar's range (columns misaligned or wrong units)",
        )

    # -- returns ----------------------------------------------------------
    returns = c.pct_change(fill_method=None)
    add(
        "extreme_returns",
        returns.abs() > max_abs_return,
        f"|return| above {max_abs_return:.0%} — real in crypto, but worth an eye",
        verdict_if_bad="WARN",
    )
    add(
        "frozen_price",
        (returns == 0).rolling(10).sum() >= 10,
        "10 consecutive unchanged closes — a stalled feed or a dead pair",
        verdict_if_bad="WARN",
    )

    return QAReport(symbol, interval, len(frame), index[0], index[-1], checks)


def check_panel(frames: dict[str, pd.DataFrame], interval: str = "1d", **kwargs) -> list[QAReport]:
    return [check_klines(f, symbol=s, interval=interval, **kwargs) for s, f in sorted(frames.items())]


def summarise(reports: list[QAReport]) -> pd.DataFrame:
    """One row per symbol: the worst verdict and what drove it."""
    rows = []
    for rep in reports:
        worst = [c.name for c in rep.checks if c.verdict == rep.verdict and rep.verdict != "PASS"]
        rows.append(
            {
                "symbol": rep.symbol,
                "bars": rep.rows,
                "start": rep.start,
                "end": rep.end,
                "verdict": rep.verdict,
                "driven_by": ", ".join(worst),
            }
        )
    return pd.DataFrame(rows)


def report_markdown(reports: list[QAReport], title: str = "Data QA report") -> str:
    summary = summarise(reports)
    counts = summary["verdict"].value_counts().to_dict()
    head = (
        f"# {title}\n\n"
        f"{len(reports)} symbols — "
        + ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
        + "\n\n"
        + table(summary)
        + "\n"
    )
    detail = "\n".join(r.to_markdown() for r in reports if r.verdict != "PASS")
    return head + ("## Symbols needing a look\n\n" + detail if detail else "Every symbol passed.\n")
