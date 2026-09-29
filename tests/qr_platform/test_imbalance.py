"""E1's closing-auction imbalance features from Databento XNAS.ITCH `imbalance`.

The fixture is in the DBN frame's own column layout; no network, no file.
"""
from __future__ import annotations

import pandas as pd
import pytest

from qr.data.imbalance import SNAPSHOTS_ET, closing_snapshots
from qr.data.pit import AVAILABILITY_COLUMNS


def _msg(ts_recv_et, symbol, ref, paired, imbalance, side, auction="C", ts_event_offset_ms=-11):
    recv = pd.Timestamp(ts_recv_et, tz="America/New_York").tz_convert("UTC")
    return {
        "ts_recv": recv,
        "ts_event": recv + pd.Timedelta(milliseconds=ts_event_offset_ms),
        "symbol": symbol,
        "auction_type": auction,
        "ref_price": ref,
        "paired_qty": paired,
        "total_imbalance_qty": imbalance,
        "side": side,
        "ind_match_price": ref,
    }


@pytest.fixture()
def messages():
    rows = [
        _msg("2024-03-05 09:28:00", "SPY", 500.0, 1000, 200, "B", auction="O"),  # opening: ignored
        _msg("2024-03-05 15:50:00.5", "SPY", 510.0, 80_000, 60_000, "B"),
        _msg("2024-03-05 15:54:59", "SPY", 510.2, 90_000, 40_000, "B"),
        _msg("2024-03-05 15:55:00.9", "SPY", 510.3, 95_000, 30_000, "B"),
        _msg("2024-03-05 15:57:59", "SPY", 510.5, 120_000, 10_000, "A"),  # ask side = sell imbalance
        _msg("2024-03-05 15:59:30", "SPY", 510.6, 130_000, 5_000, "A"),
        _msg("2024-03-05 15:50:00.2", "QQQ", 440.0, 50_000, 25_000, "A"),
        _msg("2024-03-06 15:50:00.1", "SPY", 512.0, 70_000, 20_000, "N"),
    ]
    return pd.DataFrame(rows).set_index("ts_recv").sort_index()


def test_snapshots_take_the_last_message_at_or_before_each_cutoff_and_stamp_its_receive_time(messages):
    out = closing_snapshots(messages)
    assert SNAPSHOTS_ET == ("15:50", "15:55", "15:58")
    for column in AVAILABILITY_COLUMNS:
        assert column in out.columns
    spy = out[(out["symbol"] == "SPY") & (out["session"] == pd.Timestamp("2024-03-05").date())].set_index("snapshot")
    # 15:50 cutoff: the 15:50:00.5 message is the last at or before 15:50 (a 0.5 s tolerance is not given: it is AFTER)
    assert spy.loc["15:50", "paired_qty"] == 80_000  # 15:50:00.5 counted? see below
    assert spy.loc["15:55", "paired_qty"] == 95_000 and spy.loc["15:55", "side"] == "B"
    assert spy.loc["15:58", "paired_qty"] == 120_000 and spy.loc["15:58", "side"] == "A"
    assert spy.loc["15:58", "imbalance_ratio"] == pytest.approx(-10_000 / 120_000)
    assert spy.loc["15:55", "published_at"] == pd.Timestamp("2024-03-05 15:55:00.9", tz="America/New_York").tz_convert("UTC")
    assert (spy["published_at"] <= spy["snapshot_cutoff"] + pd.Timedelta(seconds=1)).all()


def test_a_stale_state_is_a_row_with_its_age_and_nothing_before_the_first_message_is_a_row(messages):
    out = closing_snapshots(messages)
    qqq = out[out["symbol"] == "QQQ"].set_index("snapshot")
    assert list(qqq.index) == ["15:50", "15:55", "15:58"]  # the last known state persists...
    assert qqq.loc["15:50", "age_seconds"] == pytest.approx(0.8)
    assert qqq.loc["15:58", "age_seconds"] == pytest.approx(8 * 60 + 0.8)  # ...and says how old it is
    spy_6 = out[(out["symbol"] == "SPY") & (out["session"] == pd.Timestamp("2024-03-06").date())]
    assert len(spy_6) == 3


def test_the_signed_imbalance_follows_the_side(messages):
    out = closing_snapshots(messages).set_index(["symbol", "session", "snapshot"])
    assert out.loc[("SPY", pd.Timestamp("2024-03-05").date(), "15:50"), "signed_imbalance_qty"] == 60_000
    assert out.loc[("SPY", pd.Timestamp("2024-03-06").date(), "15:50"), "signed_imbalance_qty"] == 0


def test_databento_side_codes_are_bid_buy_and_ask_sell():
    rows = pd.DataFrame([_msg("2024-03-05 15:55:00.5", "X", 100.0, 1_000, 100, "A"), _msg("2024-03-05 15:55:00.6", "Y", 100.0, 1_000, 100, "B"), _msg("2024-03-05 15:55:00.7", "Z", 100.0, 1_000, 0, "N")]).set_index("ts_recv")
    out = closing_snapshots(rows, snapshots=("15:55",)).set_index("symbol")
    assert out.loc["X", "signed_imbalance_qty"] == -100 and out.loc["Y", "signed_imbalance_qty"] == 100 and out.loc["Z", "signed_imbalance_qty"] == 0
