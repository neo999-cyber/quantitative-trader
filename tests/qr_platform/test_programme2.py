"""Programme 2, week 1 (`docs/19_PROGRAMME_2.md` §10): the cash comparator for
gate 5, the perpetual cost model with funding as gross, and the FRED loader.

Synthetic data throughout; no network. The claims are the wiring and the sign
conventions, which are the things a self-flattering bug hides in.
"""
import numpy as np
import pandas as pd
import pytest

from qr.config import paths
from qr.data.fred import load_risk_free, parse_fred_csv, write_risk_free
from qr.data.lake import Lake
from qr.data.panel import Panel
from qr.execution.costs import (
    BINANCE_PERP_REGULAR,
    HYPERLIQUID_PERP_BASE,
    CostModel,
)
from qr.research.runner import funding_pnl, run_backtest
from qr.research.sweep import run_sweep
from qr.strategies.library import TSMOM, BuyAndHold
from qr.validate.gates import BENCHMARKS, GateContext, benchmark_series, gate_5_selection
from qr.validate.selftest import edge_world, noise_world
from qr.validate.spa import cash_benchmark


# ------------------------------------------------------------ cash benchmark


def test_cash_benchmark_compounds_the_annual_rate_per_bar():
    index = pd.date_range("2024-01-01", periods=365, freq="D", tz="UTC")
    cash = cash_benchmark(index, 365.0, 0.05)
    assert cash.name == "cash"
    assert float((1 + cash).prod()) == pytest.approx(1.05, rel=1e-9)
    assert cash.attrs["backfilled_bars"] == 0


def test_cash_benchmark_carries_a_dated_series_forward_and_says_what_it_backfilled():
    index = pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC")
    # published on the 4th and the 8th only; naive dates, as a CSV would give
    rates = pd.Series([0.04, 0.08], index=pd.to_datetime(["2024-01-04", "2024-01-08"]))
    cash = cash_benchmark(index, 365.0, rates)
    annual = (1 + cash) ** 365 - 1
    assert annual.iloc[3] == pytest.approx(0.04) and annual.iloc[6] == pytest.approx(0.04)
    assert annual.iloc[7] == pytest.approx(0.08) and annual.iloc[9] == pytest.approx(0.08)
    # before the first observation the first value is assumed, and counted
    assert annual.iloc[0] == pytest.approx(0.04)
    assert cash.attrs["backfilled_bars"] == 3


def test_cash_benchmark_with_no_rate_is_zero():
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    assert cash_benchmark(index, 365.0, None).abs().sum() == 0.0


# ----------------------------------------------------------------- gate 5


def _ctx(panel, benchmark="buyhold", **kwargs) -> GateContext:
    free = CostModel(fee_bps=0.0, half_spread_bps=0.0)
    grid = TSMOM.grid(lookback=[40, 60, 80])
    sweep = run_sweep(panel, grid, free)
    best = sweep.best()
    return GateContext(
        hypothesis_id="p2",
        panel=panel,
        strategy=next(s for s in grid if s.name == best),
        costs=free,
        result=sweep.results[best],
        sweep=sweep,
        benchmark=benchmark,
        spa_reps=100,
        **kwargs,
    )


@pytest.fixture(scope="module")
def edge():
    return edge_world(n_symbols=4, years=3, seed=1)


def test_the_default_benchmark_is_still_buy_and_hold(edge):
    ctx = _ctx(edge)
    assert ctx.benchmark == "buyhold"
    assert benchmark_series(ctx).name == "buy_and_hold"
    result = gate_5_selection(ctx)
    assert result.stats["benchmark"] == "buyhold"
    assert "vs buy-and-hold" in result.detail


def test_gate_five_can_be_pre_registered_against_cash(edge):
    ctx = _ctx(edge, benchmark="cash", risk_free=0.04)
    series = benchmark_series(ctx)
    assert series.name == "cash"
    assert float((1 + series).prod()) == pytest.approx(1.04 ** (len(series) / 365), rel=1e-6)
    result = gate_5_selection(ctx)
    assert result.stats["benchmark"] == "cash"
    assert "vs cash" in result.detail
    assert "spa_p_consistent" in result.stats


def test_an_unknown_benchmark_is_refused_not_defaulted(edge):
    ctx = _ctx(edge, benchmark="spy")
    with pytest.raises(ValueError, match="unknown benchmark"):
        benchmark_series(ctx)
    assert BENCHMARKS == ("buyhold", "cash")


def test_a_flat_strategy_cannot_beat_cash():
    """The control for the new comparator: a book that earns nothing fails
    against a positive risk-free rate, however many variants were tried."""
    panel = noise_world(n_symbols=4, years=3, seed=3, vol=0.0)  # every return is zero
    ctx = _ctx(panel, benchmark="cash", risk_free=0.05)
    assert float(benchmark_series(ctx).sum()) > 0  # the comparator earns something
    result = gate_5_selection(ctx)
    # every variant is constant, so SPA refuses to test nothing; gate 5 records
    # the refusal rather than passing a book that never traded
    assert "spa_error" in result.stats
    assert result.verdict != "PASS"


# ------------------------------------------------------------- perp costs


def test_binance_perp_regular_user_schedule_and_bnb_discount():
    assert (BINANCE_PERP_REGULAR.maker_bps, BINANCE_PERP_REGULAR.taker_bps) == (2.0, 5.0)
    plain = CostModel.binance_perp(bnb_discount=False)
    bnb = CostModel.binance_perp(bnb_discount=True)
    assert plain.fee_bps == 5.0 and bnb.fee_bps == pytest.approx(4.5)
    assert plain.name == "binance_perp_regular_taker" and bnb.name == "binance_perp_regular_bnb_taker"
    assert bnb.funding is True and bnb.verified_on == "unverified"
    maker = CostModel.binance_perp(use_maker=True)
    assert maker.fee_bps == pytest.approx(1.8) and maker.linear_bps == pytest.approx(1.8)


def test_hyperliquid_base_tier_is_verified_against_its_docs():
    assert (HYPERLIQUID_PERP_BASE.maker_bps, HYPERLIQUID_PERP_BASE.taker_bps) == (1.5, 4.5)
    model = CostModel.hyperliquid_perp()
    assert model.fee_bps == 4.5 and model.linear_bps == pytest.approx(5.5)
    assert model.funding is True and model.verified_on == "2026-09-15"
    assert model.describe()["settles_funding"] is True


def test_spot_models_settle_no_funding():
    assert CostModel.trial().funding is False
    assert CostModel.etf_trial().funding is False
    assert CostModel.trial().describe()["settles_funding"] is False


def test_perp_trading_costs_are_still_a_fraction_of_spot():
    turnover = pd.DataFrame({"BTCUSDT": [1.0]})
    spot = CostModel.trial().charge(turnover).iloc[0]
    perp = CostModel.binance_perp(half_spread_bps=2.0).charge(turnover).iloc[0]
    assert perp < spot


# ------------------------------------------------------ funding as gross


def test_funding_pnl_sign_convention_longs_pay_positive_funding():
    index = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    held = pd.DataFrame({"A": [1.0, -1.0, 0.5]}, index=index)
    rate = pd.DataFrame({"A": [0.001, 0.001, -0.002]}, index=index)
    pnl = funding_pnl(held, rate)
    assert pnl.tolist() == pytest.approx([-0.001, 0.001, 0.001])
    assert pnl.name == "carry"


def test_funding_pnl_settles_nothing_where_no_rate_was_published():
    index = pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC")
    held = pd.DataFrame({"A": [1.0, 1.0]}, index=index)
    rate = pd.DataFrame({"A": [np.nan, 0.001]}, index=index)
    assert funding_pnl(held, rate).tolist() == pytest.approx([0.0, -0.001])


def _perp_panel(rate: float = 0.001) -> Panel:
    base = noise_world(n_symbols=2, years=1, seed=5)
    fields = dict(base.fields)
    fields["funding_rate"] = pd.DataFrame(rate, index=base.index, columns=base.symbols)
    return Panel(fields, base.interval)


def test_a_perp_venue_puts_funding_into_gross_and_a_spot_venue_does_not():
    panel = _perp_panel(0.001)
    free_spot = CostModel(fee_bps=0.0, half_spread_bps=0.0)
    free_perp = CostModel(fee_bps=0.0, half_spread_bps=0.0, funding=True)
    spot = run_backtest(panel, BuyAndHold(), free_spot)
    perp = run_backtest(panel, BuyAndHold(), free_perp)
    assert spot.carry is None
    assert perp.carry is not None
    # a long book paying 10 bps a day of funding
    held_days = perp.held.abs().sum(axis=1) > 0
    assert perp.carry[held_days].round(12).eq(-0.001).all()
    assert np.allclose(perp.gross - spot.gross, perp.carry)
    # and it is gross, not a cost: the cost drag is identical on both venues
    assert np.allclose(perp.costs, spot.costs)


# ------------------------------------------------------------------ FRED


FRED_TEXT = """observation_date,DTB3
2026-09-07,.
2026-09-08,3.95
2026-09-09,
2026-09-10,3.97
"""


def test_fred_csv_parses_to_a_decimal_rate_and_drops_unpublished_days():
    rates = parse_fred_csv(FRED_TEXT)
    assert rates.tolist() == pytest.approx([0.0395, 0.0397])
    assert rates.index.tz is not None
    assert [d.date().isoformat() for d in rates.index] == ["2026-09-08", "2026-09-10"]


def test_fred_csv_refuses_a_value_that_is_neither_a_number_nor_missing():
    with pytest.raises(ValueError, match="non-numeric"):
        # ("n/a" would not do: pandas reads it as missing, which is fine)
        parse_fred_csv("observation_date,DTB3\n2026-09-08,abc\n")


def test_fred_csv_refuses_the_wrong_series():
    with pytest.raises(ValueError, match="expected columns"):
        parse_fred_csv(FRED_TEXT, series="DGS10")


def test_risk_free_round_trips_through_the_lake_and_feeds_the_benchmark(tmp_path):
    lake = Lake(paths(tmp_path / "lake"))
    assert load_risk_free(lake) is None
    write_risk_free(lake, parse_fred_csv(FRED_TEXT))
    stored = load_risk_free(lake)
    assert stored.tolist() == pytest.approx([0.0395, 0.0397])
    index = pd.date_range("2026-09-08", periods=4, freq="D", tz="UTC")
    cash = cash_benchmark(index, 365.0, stored)
    annual = (1 + cash) ** 365 - 1
    assert annual.iloc[1] == pytest.approx(0.0395) and annual.iloc[3] == pytest.approx(0.0397)
    assert lake.manifest_hash()  # the pull is part of what a report is computed on
