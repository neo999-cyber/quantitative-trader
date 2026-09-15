"""The carry unit (`qr/data/carry.py`) and the funding-carry family (C1).

Synthetic legs with known basis and funding, so every sign is checkable.
"""
import numpy as np
import pandas as pd
import pytest

from qr.config import paths
from qr.data.carry import CARRY_MARKET, PERP_MARKET, SPOT_MARKET, build_carry_lake, carry_frames
from qr.data.funding import MARKET as FUNDING_MARKET
from qr.data.lake import Lake
from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.carry import FundingCarry


def _bars(index, close, quote_volume=1e6):
    return pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1.0,
            "quote_volume": quote_volume,
            "trades": 10,
        },
        index=index,
    )


@pytest.fixture()
def legs():
    index = pd.date_range("2024-01-01", periods=6, freq="D", tz="UTC")
    index.name = "open_time"
    spot = _bars(index, np.array([100.0, 100, 100, 110, 110, 110]), quote_volume=5e6)
    perp = _bars(index, np.array([101.0, 101, 102, 112.2, 112.2, 112.2]), quote_volume=2e6)
    funding = pd.DataFrame({"funding_rate": [0.001] * 6, "open_interest": [1.0] * 6}, index=index)
    return spot, perp, funding


def test_the_unit_price_is_the_spot_over_perp_ratio_and_the_basis_is_carried(legs):
    spot, perp, funding = legs
    unit = carry_frames(spot, perp, funding)
    assert unit["close"].iloc[0] == pytest.approx(100 / 101)
    assert unit["basis"].iloc[0] == pytest.approx(0.01)
    # the unit's return is exactly (1 + r_spot) / (1 + r_perp) - 1
    r = unit["close"].pct_change().iloc[3]
    assert r == pytest.approx((110 / 100) / (112.2 / 102) - 1)
    # liquidity is the thinner leg
    assert unit["quote_volume"].iloc[0] == 2e6


def test_the_units_funding_carries_the_short_legs_sign(legs):
    spot, perp, funding = legs
    unit = carry_frames(spot, perp, funding)
    assert (unit["perp_funding_rate"] == 0.001).all()
    assert (unit["funding_rate"] == -0.001).all()  # a long unit *receives* a positive perp rate


def test_a_missing_funding_series_settles_nothing(legs):
    spot, perp, _ = legs
    unit = carry_frames(spot, perp, None)
    assert unit["funding_rate"].isna().all()


def test_the_index_is_the_intersection_of_both_legs(legs):
    spot, perp, funding = legs
    unit = carry_frames(spot.iloc[:4], perp.iloc[2:], funding)
    assert len(unit) == 2


def _carry_panel(days=400, rate=0.0005, symbols=("AAAUSDT", "BBBUSDT"), basis_drift=0.0) -> Panel:
    index = pd.date_range("2023-01-01", periods=days, freq="D", tz="UTC")
    index.name = "open_time"
    frames = {}
    for i, s in enumerate(symbols):
        spot = _bars(index, np.full(days, 100.0))
        perp_close = 100.0 * (1.0 + basis_drift) ** np.arange(days)
        perp = _bars(index, perp_close)
        funding = pd.DataFrame({"funding_rate": np.full(days, rate * (1 + i))}, index=index)
        frames[s] = carry_frames(spot, perp, funding)
    return Panel.from_frames(frames)


def test_a_held_unit_earns_the_perp_funding_as_gross_on_a_carry_venue():
    panel = _carry_panel(days=60, rate=0.001)
    free = CostModel(fee_bps=0.0, half_spread_bps=0.0, funding=True)
    strat = FundingCarry(lookback=1, entry=0.10, exit=0.03, ceiling=1.0, n_max=2)
    result = run_backtest(panel, strat, free)
    held = result.held.sum(axis=1) > 0
    assert held.sum() > 40
    # two units at 10 and 20 bps a day, equal weight: 15 bps a day of carry, no price move
    assert result.carry[held].round(10).eq(0.0015).all()
    assert np.allclose(result.gross[held], 0.0015)


def test_the_family_opens_above_entry_and_holds_until_below_exit():
    days = 60
    index = pd.date_range("2023-01-01", periods=days, freq="D", tz="UTC")
    index.name = "open_time"
    spot = _bars(index, np.full(days, 100.0))
    perp = _bars(index, np.full(days, 100.0))
    # funding: 0 for 10 days, 30% p.a. for 20 days, 5% p.a. for 20 days, 0 after
    daily = np.concatenate([np.zeros(10), np.full(20, 0.30 / 365), np.full(20, 0.05 / 365), np.zeros(10)])
    funding = pd.DataFrame({"funding_rate": daily}, index=index)
    panel = Panel.from_frames({"AAAUSDT": carry_frames(spot, perp, funding)})
    strat = FundingCarry(lookback=1, entry=0.10, exit=0.03, ceiling=1.0, n_max=1)
    w = strat.target_weights(panel)["AAAUSDT"]
    assert w.iloc[:10].sum() == 0.0  # nothing to collect
    assert (w.iloc[10:30] == 1.0).all()  # opened above entry
    assert (w.iloc[30:50] == 1.0).all()  # 5% is below entry but above exit: kept
    assert w.iloc[50:].sum() == 0.0  # closed below exit


def test_the_crash_filter_refuses_to_open_in_the_top_tail():
    days = 400
    index = pd.date_range("2023-01-01", periods=days, freq="D", tz="UTC")
    index.name = "open_time"
    spot = _bars(index, np.full(days, 100.0))
    perp = _bars(index, np.full(days, 100.0))
    daily = np.full(days, 0.15 / 365)
    daily[-5:] = 2.0 / 365  # a spike into the top tail of the trailing year
    panel = Panel.from_frames({"AAAUSDT": carry_frames(spot, perp, pd.DataFrame({"funding_rate": daily}, index=index))})
    strict = FundingCarry(lookback=1, entry=0.10, exit=0.03, ceiling=0.95, n_max=1)
    loose = FundingCarry(lookback=1, entry=0.10, exit=0.03, ceiling=1.0, n_max=1)
    # both hold through the calm stretch; the spike is *kept* (already open) by both,
    # so test the open decision: force a close first by a day below exit
    daily2 = daily.copy()
    daily2[-6] = 0.0
    panel2 = Panel.from_frames({"AAAUSDT": carry_frames(spot, perp, pd.DataFrame({"funding_rate": daily2}, index=index))})
    assert loose.target_weights(panel2)["AAAUSDT"].iloc[-1] == 1.0
    assert strict.target_weights(panel2)["AAAUSDT"].iloc[-1] == 0.0


def test_parameters_that_cannot_be_a_hypothesis_are_refused():
    with pytest.raises(ValueError, match="exit"):
        FundingCarry(entry=0.05, exit=0.10)
    assert FundingCarry(entry=0.15).params["exit"] == pytest.approx(0.05)  # tied by default
    with pytest.raises(ValueError, match="percentile"):
        FundingCarry(ceiling=1.5)


def test_a_non_carry_panel_is_refused_not_silently_held():
    index = pd.date_range("2023-01-01", periods=10, freq="D", tz="UTC")
    panel = Panel.from_frames({"AAAUSDT": _bars(index, np.full(10, 1.0))})
    with pytest.raises(ValueError, match="carry-unit panel"):
        FundingCarry().target_weights(panel)


def test_carry_pair_costs_are_the_two_legs_added():
    spot = CostModel.trial()
    perp = CostModel.binance_perp()
    unit = CostModel.carry_pair(spot, perp)
    assert unit.fee_bps == pytest.approx(spot.fee_bps + perp.fee_bps)
    assert unit.half_spread_bps == pytest.approx(spot.half_spread_bps + perp.half_spread_bps)
    assert unit.funding is True and unit.verified_on == "unverified"
    with pytest.raises(ValueError, match="per share"):
        CostModel.carry_pair(CostModel.etf_trial(), perp)


def test_build_carry_lake_writes_only_symbols_with_both_legs(tmp_path, legs):
    lake = Lake(paths(tmp_path / "lake"))
    spot, perp, funding = legs
    lake.write_klines("AAAUSDT", spot, "1d", market=SPOT_MARKET)
    lake.write_klines("AAAUSDT", perp, "1d", market=PERP_MARKET)
    lake.write_klines("AAAUSDT", funding, "1d", market=FUNDING_MARKET)
    lake.write_klines("BBBUSDT", spot, "1d", market=SPOT_MARKET)  # no perp
    summary = build_carry_lake(lake, ["AAAUSDT", "BBBUSDT"])
    assert summary.set_index("symbol").loc["AAAUSDT", "days"] == 6
    assert summary.set_index("symbol").loc["BBBUSDT", "note"] == "missing a leg"
    assert lake.symbols("1d", market=CARRY_MARKET) == ["AAAUSDT"]
    panel = lake.load_panel(interval="1d", market=CARRY_MARKET)
    assert "perp_funding_rate" in panel.fields and "basis" in panel.fields
    assert panel["funding_rate"].iloc[0, 0] == pytest.approx(-0.001)


def test_the_universe_volatility_floor_can_read_the_spot_leg():
    """On a carry panel the unit's own close barely moves; the floor must see the coin."""
    from qr.data.universe import UniverseSpec, membership

    days = 200
    index = pd.date_range("2023-01-01", periods=days, freq="D", tz="UTC")
    index.name = "open_time"
    rng = np.random.default_rng(0)
    coin = 100.0 * np.cumprod(1 + rng.normal(0, 0.04, days))  # a volatile coin
    peg = np.full(days, 1.0) + rng.normal(0, 0.0002, days)  # a stablecoin
    frames = {}
    for name, spot_px in (("COINUSDT", coin), ("PEGUSDT", peg)):
        spot = _bars(index, spot_px)
        perp = _bars(index, spot_px * 1.001)
        frames[name] = carry_frames(spot, perp, pd.DataFrame({"funding_rate": np.full(days, 1e-4)}, index=index))
    panel = Panel.from_frames(frames)
    assert "spot_close" in panel.fields
    on_unit = membership(panel, UniverseSpec(n=2, min_history=30, vol_field="close"))
    on_spot = membership(panel, UniverseSpec(n=2, min_history=30, vol_field="spot_close"))
    assert not on_unit.iloc[-1].any()  # the ratio never moves: everything excluded
    assert bool(on_spot.iloc[-1]["COINUSDT"]) and not bool(on_spot.iloc[-1]["PEGUSDT"])


def test_a_unit_whose_open_differs_from_its_close_is_still_a_tradable_bar():
    # Found 2026-09-15: high == low == close made every bar with open != close
    # fail the bracket check in Panel.tradable(), and the universe read empty.
    index = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    index.name = "open_time"
    spot = _bars(index, np.array([100.0, 102, 99, 101]))
    spot["open"] = np.array([99.0, 103, 100, 100])
    perp = _bars(index, np.array([101.0, 102, 100, 101.5]))
    perp["open"] = np.array([101.0, 102, 101, 100])
    frame = carry_frames(spot, perp, None)
    assert (frame["high"] >= frame[["open", "close"]].max(axis=1)).all()
    assert (frame["low"] <= frame[["open", "close"]].min(axis=1)).all()
    panel = Panel.from_frames({"XUSDT": frame})
    assert panel.tradable().all().all()


def test_a_units_volume_is_its_quote_volume_in_its_own_price_space(legs):
    # Found at gate 1 on 2026-09-15: the QA identity quote == volume x price
    # failed every unit because volume was the thinner leg's coin count.
    from qr.data.qa import check_klines

    spot, perp, funding = legs
    frame = carry_frames(spot, perp, funding)
    assert np.allclose(frame["quote_volume"], frame["volume"] * frame["close"])
    assert (frame["quote_volume"] == 2e6).all()  # still the thinner leg
    report = check_klines(frame, "XUSDT", "1d")
    assert not [c.name for c in report.checks if c.verdict == "FAIL"]


def test_a_permuted_carry_panel_keeps_its_funding_with_the_bars(legs):
    # Found at gate 6 on 2026-09-15: permute_panel dropped every field
    # outside OHLC and volume, so the permuted carry panel had no funding
    # and FundingCarry.signal raised inside the permutation test.
    from qr.validate.permutation import permute_panel

    spot, perp, funding = legs
    funding = funding.assign(funding_rate=[0.001, 0.002, 0.003, 0.004, 0.005, 0.006])
    frame = carry_frames(spot, perp, funding)
    panel = Panel.from_frames({"XUSDT": frame}, fields=list(frame.columns))
    shuffled = permute_panel(panel, seed=3)
    for name in ("perp_funding_rate", "funding_rate", "basis", "spot_close"):
        assert name in shuffled.fields
        # the same multiset of settlements, moved with their bars (first bar fixed)
        assert sorted(shuffled[name]["XUSDT"].to_numpy()[1:]) == sorted(panel[name]["XUSDT"].to_numpy()[1:])
    assert (shuffled["funding_rate"] == -shuffled["perp_funding_rate"]).all().all()
    assert not (shuffled["perp_funding_rate"]["XUSDT"].to_numpy()[1:] == panel["perp_funding_rate"]["XUSDT"].to_numpy()[1:]).all()


def test_a_permuted_panel_keeps_cross_symbol_correlation_across_staggered_listings():
    # Found at gate 6 on 2026-09-15 on the carry panel: filtering one global
    # order to each symbol's live bars only aligned symbols with identical
    # windows, so a panel of staggered listings lost its cross-section and
    # the null's book was better diversified than any real one.
    from qr.validate.permutation import _live_order, permute_panel

    rng = np.random.default_rng(0)
    n = 600
    index = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    common = rng.standard_normal(n)
    frames = {}
    for k, (sym, start) in enumerate([("AAA", 0), ("BBB", 150), ("CCC", 300)]):
        r = 0.01 * (0.8 * common + 0.6 * rng.standard_normal(n))
        close = 100 * np.cumprod(1 + r)
        f = pd.DataFrame(
            {"open": close, "high": close, "low": close, "close": close, "volume": 1.0, "quote_volume": 100.0},
            index=index,
        )
        f.iloc[:start] = np.nan
        frames[sym] = f
    panel = Panel.from_frames(frames)
    real = panel.close.pct_change().corr()
    perm = permute_panel(panel, seed=7).close.pct_change().corr()
    # Alignment survives on the bars where both source and destination are
    # live: about three quarters of BBB's window against AAA, half of CCC's.
    # Full preservation would need within-epoch shuffles, which is no null.
    assert perm.loc["AAA", "BBB"] > 0.55 * real.loc["AAA", "BBB"]
    assert perm.loc["AAA", "CCC"] > 0.35 * real.loc["AAA", "CCC"]
    assert perm.loc["BBB", "CCC"] > 0.35 * real.loc["BBB", "CCC"]

    order = rng.permutation(n - 1)
    live = np.arange(150, n - 1)
    out = _live_order(order, live)
    assert sorted(out) == list(live)  # every live bar used once
    agree = order[live] == out
    assert agree.mean() > 0.6  # most destinations take their global source


def test_the_result_reports_the_share_of_gross_that_was_funding(legs):
    # A unit whose price never moves earns only its funding: share = 1.
    spot, perp, funding = legs
    spot["open"] = spot["close"] = 100.0
    perp["open"] = perp["close"] = 101.0
    frame = carry_frames(spot, perp, funding)
    panel = Panel.from_frames({"XUSDT": frame}, fields=list(frame.columns))
    result = run_backtest(panel, FundingCarry(entry=-1.0, exit=-2.0, ceiling=1.0, n_max=40, lookback=1), CostModel.carry_pair())
    assert result.stats()["carry_share_of_gross"] == pytest.approx(1.0)
    spot_only = run_backtest(panel, FundingCarry(entry=-1.0, exit=-2.0, ceiling=1.0, n_max=40, lookback=1), CostModel(fee_bps=0.0, half_spread_bps=0.0))
    assert np.isnan(spot_only.stats()["carry_share_of_gross"])
