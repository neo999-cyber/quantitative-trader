"""The four audit cases still owed from `docs/20_PROGRAMME_2.md` §10 item 11.

Each is a test with a hand-computed expected dollar answer, not a comparison
against the engine's own formula. The other four (a $1,000 whole-share order's
commission, a four-leg carry round trip, funding that reverses sign, a
delisting) were covered by the week-1 tests.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qr.data.carry import carry_frames
from qr.data.funding import daily_funding, parse_funding
from qr.data.panel import Panel
from qr.data.pit import asof_view
from qr.execution.audit import redenomination_bars, unmatched_leg_loss


def _bars(index, close, quote_volume=1e6):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 1.0,
         "quote_volume": quote_volume, "trades": 10},
        index=index,
    )


# ------------------------------------------------ 1. one leg filled, the other not


def test_one_leg_filled_and_the_other_not_is_a_naked_bar_of_the_coin():
    """A $1,000 account opens a 20% carry unit: $200 of spot bought, the perp
    short not filled. Overnight the coin falls 5%. The unit would have made
    about nothing; the account is down 5% of $200 = $10. If the coin rose
    5% the account is up $10 — the point is the size of the exposure, not
    its sign, so both are asserted and the loss is what gate 8 sizes on."""
    assert unmatched_leg_loss(weight=0.20, spot_return=-0.05, equity=1_000.0) == pytest.approx(-10.0)
    assert unmatched_leg_loss(weight=0.20, spot_return=+0.05, equity=1_000.0) == pytest.approx(+10.0)
    # the short leg unfilled while the long leg is on is the same exposure;
    # the perp leg alone (spot unfilled) is the opposite sign
    assert unmatched_leg_loss(weight=0.20, spot_return=-0.05, equity=1_000.0, leg="perp") == pytest.approx(+10.0)


# ------------------------------------------------------ 2. a split on a carry unit


def test_a_redenomination_that_hits_the_two_legs_on_different_days_is_not_a_return():
    """Spot is redenominated 1:1000 on day 3 and the perp on day 5 (this is
    what happened to several 1000x tickers). For days 3 and 4 the ratio
    spot / perp is 1000x what it was, then it comes back. The unit did not
    move: a book holding 20% of a $1,000 account made $0 across those bars,
    not +$199,800 then -$200. The two artefact bars are excluded, so the unit
    is not tradable on them and the book is liquidated at its last real
    close with nothing earned."""
    index = pd.date_range("2024-01-01", periods=8, freq="D", tz="UTC")
    index.name = "open_time"
    spot = _bars(index, [1.0, 1.0, 1.0, 1000.0, 1000.0, 1000.0, 1000.0, 1000.0])
    perp = _bars(index, [1.01, 1.01, 1.01, 1.01, 1.01, 1010.0, 1010.0, 1010.0])
    ratio = spot["close"] / perp["close"]
    artefact = redenomination_bars(ratio)
    assert artefact.tolist() == [False, False, False, True, True, False, False, False]
    frame = carry_frames(spot, perp, None)
    assert frame["close"].isna().tolist() == artefact.tolist()
    panel = Panel.from_frames({"XUSDT": frame})
    tradable = panel.tradable()["XUSDT"]
    assert not tradable.iloc[3] and not tradable.iloc[4]
    # the unit's return over the whole episode is zero
    good = frame["close"].dropna()
    assert float(good.iloc[-1] / good.iloc[0] - 1.0) == pytest.approx(0.0)
    # and a real, persistent basis blow-out (LUNA, 12 May 2022: the perp at 25x
    # spot and never coming back) is NOT masked — that loss was real
    luna = pd.Series([1.0, 1.0, 1.0, 0.04, 0.04, 0.04, 0.04, 0.04], index=index)
    assert not redenomination_bars(luna).any()


# ------------------------------ 3. a Form 4 amendment published after the signal


def test_a_form_4_amendment_published_after_the_signal_does_not_change_it():
    """An officer's purchase of 10,000 shares at $25 ($250,000) is accepted
    by EDGAR on 3 March at 17:10 ET. The signal is computed on 5 March. On
    9 March a Form 4/A corrects it to 1,000 shares ($25,000). The book on
    5 March saw $250,000 and traded on it — that is what happened, and the
    backtest must see the same; the view on 10 March sees $25,000."""
    rows = pd.DataFrame(
        {
            "accession": ["0001-24-000001", "0001-24-000001"],
            "issuer": ["ACME", "ACME"],
            "shares": [10_000.0, 1_000.0],
            "price": [25.0, 25.0],
            "event_time": pd.to_datetime(["2024-03-01", "2024-03-01"]).tz_localize("America/New_York"),
            "published_at": pd.to_datetime(["2024-03-03 17:10", "2024-03-09 09:00"]).tz_localize("America/New_York"),
            "is_amendment": [False, True],
        }
    )
    on_signal = asof_view(rows, pd.Timestamp("2024-03-05 16:00", tz="America/New_York"), key="accession")
    assert len(on_signal) == 1
    assert float(on_signal["shares"].iloc[0] * on_signal["price"].iloc[0]) == pytest.approx(250_000.0)
    later = asof_view(rows, pd.Timestamp("2024-03-10 16:00", tz="America/New_York"), key="accession")
    assert len(later) == 1
    assert float(later["shares"].iloc[0] * later["price"].iloc[0]) == pytest.approx(25_000.0)
    # before publication nothing is visible, whatever the event time says
    assert asof_view(rows, pd.Timestamp("2024-03-02 16:00", tz="America/New_York"), key="accession").empty


# ------------------------------------------------ 4. a funding-interval change


def test_a_funding_interval_change_settles_the_same_daily_total():
    """Day 1 settles three times at 0.01% (8-hour funding); day 2 the venue
    moves the symbol to 4-hour funding and settles six times at 0.005%. A
    $1,000 short perp (a carry unit at full weight) receives 0.03% = $0.30 on
    each day. The daily sum must be $0.30 both days — a mean or a last-value
    would read day 2 as half the income — and the interval must be visible
    so a change is a recorded fact, not a silent one."""
    day1 = [(f"2024-06-01 {h:02d}:00", 8, 0.0001) for h in (0, 8, 16)]
    day2 = [(f"2024-06-02 {h:02d}:00", 4, 0.00005) for h in (0, 4, 8, 12, 16, 20)]
    lines = ["calc_time,funding_interval_hours,last_funding_rate"]
    for stamp, hours, rate in day1 + day2:
        ms = int(pd.Timestamp(stamp, tz="UTC").timestamp() * 1000)
        lines.append(f"{ms},{hours},{rate}")
    frame = parse_funding("\n".join(lines).encode())
    assert frame["funding_interval_hours"].tolist() == [8, 8, 8, 4, 4, 4, 4, 4, 4]
    daily = daily_funding(frame)
    assert daily.tolist() == pytest.approx([0.0003, 0.0003])
    received = daily * 1_000.0  # short perp, full weight, longs pay
    assert received.tolist() == pytest.approx([0.30, 0.30])
