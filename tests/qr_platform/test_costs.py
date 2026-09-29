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
    """The law itself, with the spread-netting switched off."""
    model = CostModel(impact_coef=1.0, net_impact_against_spread=False)
    small = model.impact_bps(np.array([[1_000.0]]), np.array([[1_000_000.0]]), np.array([[0.04]]))
    big = model.impact_bps(np.array([[4_000.0]]), np.array([[1_000_000.0]]), np.array([[0.04]]))
    assert big[0, 0] == pytest.approx(2 * small[0, 0])
    assert small[0, 0] == pytest.approx(0.04 * np.sqrt(1e-3) / BPS)


def test_impact_is_charged_net_of_the_spread_the_linear_term_already_took():
    """`docs/07_ENGINE_FIXES.md` §2: charging both double-counts."""
    model = CostModel(impact_coef=1.0)
    raw = CostModel(impact_coef=1.0, net_impact_against_spread=False)
    args = (np.array([[1_000.0]]), np.array([[1_000_000.0]]), np.array([[0.04]]))
    assert model.impact_bps(*args)[0, 0] == pytest.approx(
        raw.impact_bps(*args)[0, 0] - model.half_spread_bps
    )


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
    impact_bps = 0.04 * np.sqrt(5e5 / 1e8) / BPS - model.half_spread_bps
    assert with_impact > linear
    assert with_impact == pytest.approx(linear + 0.5 * impact_bps * BPS)


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


# ------------------------------------------------------- what the cost is made of


def _one_day(turn=0.1, price=300.0, n=12):
    index = pd.date_range("2024-01-02", periods=n, freq="D", tz="UTC")
    return (
        pd.DataFrame(turn, index=index, columns=["SPY"]),
        pd.DataFrame(price, index=index, columns=["SPY"]),
        index,
    )


def test_the_components_sum_to_the_charge():
    """`charge` is `components`, summed — anything else is two cost models."""
    turnover, prices, index = _one_day()
    shorts = pd.Series(0.5, index=index)
    for model in (CostModel.trial(), CostModel.etf_trial(), CostModel.etf_long_short()):
        parts = model.components(turnover, 10_000.0, prices=prices, short_exposure=shorts)
        total = model.charge(turnover, 10_000.0, prices=prices, short_exposure=shorts)
        assert np.allclose(parts.sum(axis=1), total)


def test_a_proportional_venue_splits_its_rate_into_fee_and_spread():
    turnover, _, _ = _one_day()
    model = CostModel.trial()
    parts = model.components(turnover)
    assert parts["commission"].sum() > 0 and parts["spread"].sum() > 0
    assert parts["borrow"].sum() == 0.0 and parts["impact"].sum() == 0.0
    assert np.isclose(
        parts[["commission", "spread"]].sum().sum(), float(model.charge(turnover).sum())
    )


def test_gate_two_names_the_cost_when_one_dominates():
    """"Costs eat 62%" is a dead end; naming the culprit is a direction."""
    from qr.validate.gates import _dominant_cost

    assert "per-order commission" in _dominant_cost({"commission": 0.96, "borrow": 0.04})
    assert "borrow fee" in _dominant_cost({"borrow": 0.70, "commission": 0.30})
    # A three-way split names nothing rather than picking a winner out of noise.
    assert _dominant_cost({"commission": 0.4, "spread": 0.35, "borrow": 0.25}) == ""
    assert _dominant_cost({}) == ""


def test_a_backtest_carries_the_split_it_was_charged():
    from qr.research.runner import run_backtest
    from qr.strategies.library import BuyAndHold
    from qr.validate.gates import _cost_attribution
    from qr.validate.selftest import noise_world

    panel = noise_world(n_symbols=6, years=3, seed=7)
    result = run_backtest(panel, BuyAndHold(), CostModel.trial())
    assert np.allclose(result.cost_parts.sum(axis=1), result.costs)
    shares = _cost_attribution(result)
    assert np.isclose(sum(shares.values()), 1.0)
