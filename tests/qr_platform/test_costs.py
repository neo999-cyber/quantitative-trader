import numpy as np
import pandas as pd
import pytest

from qr.execution.costs import BPS, BinanceSpotFees, CostModel


def test_vip0_is_ten_basis_points_per_side():
    fees = BinanceSpotFees.for_tier("VIP0")
    assert (fees.maker_bps, fees.taker_bps) == (10.0, 10.0)


def test_bnb_discount_is_twenty_five_percent():
    plain = BinanceSpotFees.for_tier("VIP1")
    bnb = BinanceSpotFees.for_tier("VIP1", bnb_discount=True)
    assert bnb.taker_bps == pytest.approx(plain.taker_bps * 0.75)


def test_unknown_tier_is_rejected():
    with pytest.raises(ValueError, match="unknown Binance spot tier"):
        BinanceSpotFees.for_tier("VIP99")


def test_linear_cost_is_fee_plus_half_spread():
    model = CostModel.binance_spot()
    assert model.linear_bps == pytest.approx(12.0)
    turnover = pd.DataFrame({"BTCUSDT": [1.0, 0.0], "ETHUSDT": [0.5, 0.25]})
    cost = model.charge(turnover)
    assert cost.iloc[0] == pytest.approx(1.5 * 12.0 * BPS)
    assert cost.iloc[1] == pytest.approx(0.25 * 12.0 * BPS)


def test_stressing_doubles_every_component():
    model = CostModel.binance_spot()
    assert model.stressed(2).linear_bps == pytest.approx(2 * model.linear_bps)
    turnover = pd.DataFrame({"BTCUSDT": [1.0]})
    assert model.stressed(2).charge(turnover).iloc[0] == pytest.approx(2 * model.charge(turnover).iloc[0])


def test_impact_follows_the_square_root_of_participation():
    model = CostModel(impact_coef=1.0)
    small = model.impact_bps(np.array([[1_000.0]]), np.array([[1_000_000.0]]), np.array([[0.04]]))
    big = model.impact_bps(np.array([[4_000.0]]), np.array([[1_000_000.0]]), np.array([[0.04]]))
    assert big[0, 0] == pytest.approx(2 * small[0, 0])
    assert small[0, 0] == pytest.approx(0.04 * np.sqrt(1e-3) / BPS)


def test_impact_is_zero_where_there_is_no_volume():
    model = CostModel()
    out = model.impact_bps(np.array([[1_000.0]]), np.array([[0.0]]), np.array([[0.04]]))
    assert out[0, 0] == 0.0


def test_impact_adds_to_the_linear_charge():
    model = CostModel.binance_spot()
    turnover = pd.DataFrame({"BTCUSDT": [0.5]})
    adv = pd.DataFrame({"BTCUSDT": [1e8]})
    vol = pd.DataFrame({"BTCUSDT": [0.04]})
    linear = model.charge(turnover).iloc[0]
    with_impact = model.charge(turnover, equity=1e6, adv_notional=adv, volatility=vol).iloc[0]
    assert with_impact > linear
    assert with_impact == pytest.approx(linear + 0.5 * 0.04 * np.sqrt(5e5 / 1e8))


def test_the_trial_model_is_vip0_with_the_bnb_discount():
    model = CostModel.trial()
    assert model.fee_bps == pytest.approx(7.5)
    assert model.linear_bps == pytest.approx(9.5)
    assert model.name == "binance_spot_vip0_bnb_taker"


def test_the_trial_model_carries_its_verification_date():
    described = CostModel.trial().describe()
    assert described["fees_verified_on"] == "2026-09-11"
    assert CostModel.binance_spot().describe()["fees_verified_on"] == "unverified"


def test_gate_two_stress_is_double_the_round_trip():
    model = CostModel.trial()
    assert 2 * model.stressed(2.0).linear_bps == pytest.approx(38.0)
