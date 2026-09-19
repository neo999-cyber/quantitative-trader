"""The cross-venue unit (`qr/data/xvenue.py`, C2): two perps on the same coin, one venue each way."""
import numpy as np
import pandas as pd
import pytest

from qr.data.xvenue import xvenue_frames
from qr.execution.costs import CostModel


def _bars(index, close, quote_volume=1e6):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": quote_volume / close, "quote_volume": quote_volume},
        index=index,
    )


@pytest.fixture()
def legs():
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    index.name = "open_time"
    binance = _bars(index, [100.0, 100, 101, 101, 101], quote_volume=5e6)
    bybit = _bars(index, [100.0, 100.2, 101, 100.9, 100.9], quote_volume=2e6)
    f_binance = pd.Series([0.0010] * 5, index=index)  # longs pay 10 bps a day on Binance
    f_bybit = pd.Series([0.0002] * 5, index=index)  # 2 bps on Bybit
    return binance, bybit, f_binance, f_bybit


def test_long_bybit_short_binance_collects_the_spread_and_the_other_side_pays_it(legs):
    unit = xvenue_frames(*legs, side="BYBN")
    # long Bybit pays 2 bps, short Binance receives 10 bps: the unit is paid 8 bps
    assert unit["funding_rate"].iloc[0] == pytest.approx(-0.0008)
    assert unit["perp_funding_rate"].iloc[0] == pytest.approx(0.0008)
    mirror = xvenue_frames(*legs, side="BNBY")
    assert mirror["funding_rate"].iloc[0] == pytest.approx(0.0008)
    assert mirror["perp_funding_rate"].iloc[0] == pytest.approx(-0.0008)


def test_the_unit_price_is_the_long_leg_over_the_short_leg(legs):
    unit = xvenue_frames(*legs, side="BNBY")
    assert unit["close"].iloc[1] == pytest.approx(100 / 100.2)
    r = unit["close"].pct_change().iloc[2]
    assert r == pytest.approx((101 / 100) / (101 / 100.2) - 1)
    assert unit["quote_volume"].iloc[0] == 2e6  # the thinner leg
    # quote volume == volume x price, so the unit passes gate 1's identity
    assert np.allclose(unit["quote_volume"], unit["volume"] * unit["close"])


def test_the_two_sides_are_exact_mirrors_in_funding(legs):
    a = xvenue_frames(*legs, side="BNBY")
    b = xvenue_frames(*legs, side="BYBN")
    assert np.allclose(a["perp_funding_rate"], -b["perp_funding_rate"])
    assert np.allclose(a["close"] * b["close"], 1.0)


def test_the_cross_venue_cost_model_adds_both_taker_legs():
    unit = CostModel.carry_pair(CostModel.binance_perp(), CostModel.bybit_perp())
    assert unit.fee_bps == pytest.approx(CostModel.binance_perp().fee_bps + 5.5)
    assert unit.half_spread_bps == pytest.approx(1.0 + 1.5)
    assert unit.funding
