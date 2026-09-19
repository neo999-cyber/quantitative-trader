"""The one mechanism family that OHLCV can already test: the calendar.

Every other idea on `docs/10_NEXT.md`'s list — funding, liquidations, index
inclusion, unlocks — names a payer this project cannot see, because the data
is not in the lake (`qr/research/features.py` says which dataset each one
waits on). The calendar is different. The forced trader is real and nameable,
the date is knowable in advance, and nothing beyond a timestamp is required:

* **Month and quarter end.** A balanced fund whose mandate is 60/40 must sell
  what rose and buy what fell, on a schedule written into its prospectus, in
  size, regardless of price. It is not choosing to trade.
* **Turn of the month.** Salary, pension contributions and coupon
  reinvestment arrive on a date nobody picks.
* **December.** Tax-loss selling is a deadline, and the deadline is the whole
  mechanism: the seller would rather not, and sells anyway.

`CalendarEvent` is deliberately the crudest thing that can express those: hold
the universe, equal-weighted, in a window of bars around a recurring date, flat
otherwise. It is a *kill test*, not a strategy. If a mechanism is real it should
show up in the crudest possible version before anyone spends a grid on it — and
if it only appears after tuning, that is the finding.

What it is not: this family says nothing about **which** names to hold, so it
cannot express "the funds must buy the winners". That is a cross-sectional
question and `CrossSectionalMomentum` already answers it, having failed. The
claim here is about *timing* — that returns in a window around a forced-trading
date differ from returns outside it — and the mechanism either puts them there
or it does not.
"""
from __future__ import annotations

import pandas as pd

from qr.data.panel import Panel
from qr.strategies.base import Strategy

#: Recurring dates a forced trader is known to act on. Each maps to a function
#: from an index to the bars that *are* the event, before any window is applied.
EVENTS = ("month_end", "month_start", "quarter_end", "year_end", "weekday")


def event_bars(index: pd.DatetimeIndex, event: str, weekday: int = 0) -> pd.Series:
    """The bars on which the event itself falls.

    Computed from the index alone, which is the property that makes this family
    testable at all: no lookahead is possible, because a calendar is known in
    advance by construction. The one thing to be careful of is that "month end"
    means *the last bar this index has in that month*, not the 31st — crypto
    trades on the 31st and equities may not, and a rule that asks for a date
    the market was shut on simply never fires.
    """
    if event not in EVENTS:
        raise ValueError(f"unknown event {event!r}; expected one of {EVENTS}")
    series = pd.Series(index, index=index)
    if event == "weekday":
        return pd.Series(index.weekday == weekday, index=index)
    # Periods carry no timezone, and converting a tz-aware index to one warns
    # about dropping it. The offset is irrelevant to "which month is this bar
    # in" for a UTC index, so it is dropped deliberately and quietly here
    # rather than noisily by pandas on every call.
    naive = index.tz_localize(None) if index.tz is not None else index
    freq = {"month_end": "M", "month_start": "M", "quarter_end": "Q", "year_end": "Y"}[event]
    keys = naive.to_period(freq)
    how = "min" if event == "month_start" else "max"
    last = series.groupby(keys).transform(how)
    return pd.Series(series.to_numpy() == last.to_numpy(), index=index)


def window_mask(events: pd.Series, before: int = 0, after: int = 0) -> pd.Series:
    """Widen event bars into a window of `before` bars up to and `after` after.

    A forced trade is anticipated and then absorbed, so the interesting bars
    are rarely the event bar alone. `before=3, after=0` is "the three bars into
    month end"; `before=0, after=3` is "the three bars out of it". Keeping them
    separate parameters rather than one symmetric width matters, because the
    two make opposite claims about who is early.
    """
    if before < 0 or after < 0:
        raise ValueError("before and after are bar counts and cannot be negative")
    flags = events.to_numpy(dtype=bool)
    out = flags.copy()
    for shift in range(1, before + 1):
        out[:-shift] |= flags[shift:]
    for shift in range(1, after + 1):
        out[shift:] |= flags[:-shift]
    return pd.Series(out, index=events.index)


class CalendarEvent(Strategy):
    """Equal-weight the universe inside a calendar window; flat outside it.

    `side` is +1 to be long in the window and -1 to be short it. Both are worth
    running: the claim "forced buying lifts prices into month end" and the
    claim "forced selling depresses them" are different mechanisms with
    different payers, and the sign is the thing the memo has to commit to in
    advance rather than read off afterwards.
    """

    family = "calendar_event"

    def __init__(
        self,
        event: str = "month_end",
        before: int = 3,
        after: int = 0,
        side: int = 1,
        weekday: int = 0,
        gross: float = 1.0,
    ) -> None:
        if side not in (1, -1):
            raise ValueError(f"side must be +1 or -1; got {side}")
        # Validate the event name here rather than at the first backtest: a
        # grid of 40 variants that dies on the 39th has already cost 38 runs.
        event_bars(pd.DatetimeIndex([pd.Timestamp("2020-01-01", tz="UTC")]), event, weekday)
        super().__init__(
            event=event, before=before, after=after, side=side, weekday=weekday, gross=gross
        )

    def in_window(self, index: pd.DatetimeIndex) -> pd.Series:
        events = event_bars(index, self.params["event"], self.params["weekday"])
        return window_mask(events, self.params["before"], self.params["after"])

    def target_weights(self, panel: Panel, universe: pd.DataFrame | None = None) -> pd.DataFrame:
        live = panel.tradable()
        if universe is not None:
            live = live & universe.reindex_like(live).fillna(False).astype(bool)

        held = live.astype(float)
        inside = self.in_window(panel.index).to_numpy()
        held = held.mul(inside.astype(float), axis=0)

        weights = self.normalise(held, gross=float(self.params["gross"]))
        return weights * float(self.params["side"])
