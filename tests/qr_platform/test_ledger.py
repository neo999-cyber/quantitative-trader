"""The position/cash ledger (`qr/research/ledger.py`): acceptance tests from a hand ledger.

Every expected number below was worked by hand before the engine existed
(`docs/26_SESSION_BRIEF_LEDGER.md`), not read off the production formula.
"""
import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.execution.costs import CostModel
from qr.research.ledger import run_ledger
from qr.research.runner import run_backtest
from qr.strategies.base import Strategy
from qr.strategies.library import TSMOM, BuyAndHold, CrossSectionalMomentum
from qr.validate.selftest import edge_world

FREE = CostModel(fee_bps=0.0, half_spread_bps=0.0, name="free")


def _index(n):
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    idx.name = "open_time"
    return idx


def _frame(closes, quote_volume=1e6, **extra):
    idx = _index(len(closes))
    c = np.asarray(closes, dtype=float)
    frame = pd.DataFrame(
        {"open": c, "high": c * 1.001, "low": c * 0.999, "close": c, "volume": quote_volume / c, "quote_volume": quote_volume},
        index=idx,
    )
    for k, v in extra.items():
        frame[k] = np.asarray(v, dtype=float)
    return frame


class _Book(Strategy):
    """Hold the given weights; trade only on the bars `marks` says (held bars)."""

    family = "test"
    round_trip_each_bar = False

    def __init__(self, weights, marks=None):
        super().__init__()
        self._w = weights
        self._marks = marks

    def target_weights(self, panel, universe=None):
        return self._w.copy()

    def trades_on(self, index):
        if self._marks is None:
            return pd.Series(True, index=index)
        return pd.Series(np.asarray(self._marks, dtype=bool), index=index)


class _RoundTrip(_Book):
    round_trip_each_bar = True


# -- state and drift -------------------------------------------------------


def test_half_stock_half_cash_drifts_to_54_545_percent_with_no_trade():
    # $50 stock + $50 cash; stock +20% -> $60 + $50 = $110, weight 60/110
    idx = _index(4)
    panel = Panel.from_frames({"X": _frame([100, 100, 120, 120])})
    w = pd.DataFrame({"X": [0.5] * 4}, index=idx)
    res = run_ledger(panel, _Book(w, marks=[False, True, False, False]), FREE, equity=100.0)
    assert res.nav.loc[idx[1]] == pytest.approx(100.0)
    assert res.nav.loc[idx[2]] == pytest.approx(110.0)
    assert res.cash.loc[idx[2]] == pytest.approx(50.0)
    assert res.quantities.loc[idx[2], "X"] == pytest.approx(0.5)
    assert res.held.loc[idx[3], "X"] == pytest.approx(60.0 / 110.0)  # 54.545%
    assert res.turnover.loc[idx[2]] == 0.0 and res.turnover.loc[idx[3]] == 0.0
    assert res.net.loc[idx[2]] == pytest.approx(0.10)


def test_a_short_has_its_liability_in_the_denominator():
    # -$50 stock + $150 cash; stock +20% -> liability $60, NAV $90, weight -60/90
    idx = _index(4)
    panel = Panel.from_frames({"X": _frame([100, 100, 120, 120])})
    w = pd.DataFrame({"X": [-0.5] * 4}, index=idx)
    res = run_ledger(panel, _Book(w, marks=[False, True, False, False]), FREE, equity=100.0)
    assert res.cash.loc[idx[1]] == pytest.approx(150.0)
    assert res.quantities.loc[idx[1], "X"] == pytest.approx(-0.5)
    assert res.nav.loc[idx[2]] == pytest.approx(90.0)
    assert res.held.loc[idx[3], "X"] == pytest.approx(-60.0 / 90.0)  # -66.667%
    assert res.net.loc[idx[2]] == pytest.approx(-0.10)


def test_a_monthly_book_keeps_its_quantities_between_marks():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2024-01-01", periods=95, freq="D", tz="UTC")
    idx.name = "open_time"
    frames = {}
    for s in ("A", "B"):
        c = 100 * np.cumprod(1 + rng.normal(0, 0.02, len(idx)))
        frames[s] = _frame(c)
    panel = Panel.from_frames(frames)
    res = run_ledger(panel, BuyAndHold(rebalance_on="MS"), CostModel.trial())
    marks = BuyAndHold(rebalance_on="MS").trades_on(idx).to_numpy()
    q = res.quantities.to_numpy()
    changed = np.abs(np.diff(q, axis=0)).sum(axis=1) > 1e-12  # qty at bar t differs from t-1
    # a change in the quantity held over bar t means an order at t-1: only mark bars
    assert not changed[~marks[1:]].any()
    assert changed[marks[1:]].all()  # prices moved, so every mark re-balances
    assert (res.turnover.to_numpy()[~marks] == 0.0).all()
    assert (res.turnover.to_numpy()[marks][1:] > 0).all()
    assert (res.costs.to_numpy()[~marks] == 0.0).all()


# -- two-leg units ---------------------------------------------------------


def _carry_panel(spot, perp, perp_rate=None):
    spot = np.asarray(spot, dtype=float)
    perp = np.asarray(perp, dtype=float)
    rate = np.full(len(spot), np.nan) if perp_rate is None else np.asarray(perp_rate, dtype=float)
    frame = _frame(spot / perp, spot_close=spot, perp_funding_rate=rate, funding_rate=-rate)
    return Panel.from_frames({"U": frame})


def test_carry_unit_books_each_leg_at_its_own_price():
    # one spot coin 100 -> 120 (+20), one perp contract short 100 -> 110 (-10): +$10 on $100
    idx = _index(4)
    panel = _carry_panel([100, 100, 120, 120], [100, 100, 110, 110])
    pair = CostModel.carry_pair(FREE, FREE)
    w = pd.DataFrame({"U": [1.0, 1.0, 0.0, 0.0]}, index=idx)
    res = run_ledger(panel, _Book(w), pair, equity=100.0)
    assert res.quantities.loc[idx[1], "U"] == pytest.approx(1.0)
    assert res.nav.loc[idx[2]] == pytest.approx(110.0)
    assert res.net.loc[idx[2]] == pytest.approx(0.10)
    assert res.meta["capital_convention"]["perp_margin"] == 1.0
    # the ratio runner reads (1.2 / 1.1 - 1) = 9.09%: second order, as carry.py says
    ratio = run_backtest(panel, _Book(w), pair, equity=100.0)
    assert ratio.net.loc[idx[2]] == pytest.approx(1.2 / 1.1 - 1.0)
    # counting 100% perp margin as capital: half a unit on the same $100, +5%
    half = run_ledger(panel, _Book(w), pair, equity=100.0, count_margin=True)
    assert half.quantities.loc[idx[1], "U"] == pytest.approx(0.5)
    assert half.net.loc[idx[2]] == pytest.approx(0.05)


@pytest.mark.parametrize("rate, expected", [(0.01, 1.1), (-0.01, -1.1)])
def test_carry_unit_funding_is_settled_on_the_perp_leg_with_the_venue_sign(rate, expected):
    # short one perp at its bar-2 mark of 110: a +1% rate is received (+$1.10), a -1% rate paid
    idx = _index(4)
    panel = _carry_panel([100, 100, 120, 120], [100, 100, 110, 110], perp_rate=[0, 0, rate, 0])
    pair = CostModel.carry_pair(FREE, FREE)
    w = pd.DataFrame({"U": [1.0, 1.0, 0.0, 0.0]}, index=idx)
    res = run_ledger(panel, _Book(w), pair, equity=100.0)
    assert res.nav.loc[idx[2]] == pytest.approx(110.0 + expected)
    assert res.carry.loc[idx[2]] == pytest.approx(expected / 100.0)
    assert res.gross.loc[idx[2]] == pytest.approx((10.0 + expected) / 100.0)


def test_carry_unit_pays_each_legs_fee_on_that_legs_notional():
    # entry at bar 0: spot $100 x 10 bps = $0.10, perp $100 x 5 bps = $0.05 -> booked on the held bar
    # exit at bar 2: spot $120 x 10 bps = $0.12, perp $110 x 5 bps = $0.055 -> booked on bar 3
    idx = _index(4)
    panel = _carry_panel([100, 100, 120, 120], [100, 100, 110, 110])
    pair = CostModel.carry_pair(
        CostModel(fee_bps=10.0, half_spread_bps=0.0, name="spot10"), CostModel(fee_bps=5.0, half_spread_bps=0.0, name="perp5")
    )
    w = pd.DataFrame({"U": [1.0, 1.0, 0.0, 0.0]}, index=idx)
    res = run_ledger(panel, _Book(w, marks=[False, True, False, True]), pair, equity=100.0)
    assert res.costs.loc[idx[1]] * res.nav.loc[idx[0]] == pytest.approx(0.15)
    assert res.costs.loc[idx[3]] * res.nav.loc[idx[2]] == pytest.approx(0.175)
    assert res.nav.loc[idx[3]] == pytest.approx(110.0 - 0.15 - 0.175)
    fills = res.fills
    assert len(fills) == 4 and set(fills["leg"]) == {"spot", "perp"}


def test_a_unit_delivered_in_dollars_trades_the_coins_drift_and_one_held_as_coins_does_not():
    # spot 100 -> 200 -> 100 with the perp alongside: the unit's basis P&L is zero,
    # but a constant-dollar unit sells half at 200 and buys it back at 100
    idx = _index(4)
    panel = _carry_panel([100, 200, 100, 100], [100, 200, 100, 100])
    pair = CostModel.carry_pair(FREE, FREE)
    w = pd.DataFrame({"U": [1.0, 1.0, 1.0, 1.0]}, index=idx)
    dollars = run_ledger(panel, _Book(w), pair, equity=100.0)
    coins = run_ledger(panel, _Book(w), pair, equity=100.0, unit_sizing="coins")
    assert dollars.quantities.loc[idx[2], "U"] == pytest.approx(0.5)
    assert dollars.turnover.loc[idx[2]] == pytest.approx(1.0)  # half a unit sold at 200 is $100 of a $100 book
    assert dollars.quantities.loc[idx[3], "U"] == pytest.approx(1.0)
    assert (coins.quantities["U"].iloc[1:] == 1.0).all() and coins.turnover.iloc[2:].sum() == 0.0
    assert dollars.meta["capital_convention"]["unit_sizing"] == "dollars"
    assert coins.meta["capital_convention"]["unit_sizing"] == "coins"


# -- round trips, whole shares, refusals -----------------------------------


def test_three_consecutive_overnight_signals_are_six_fills():
    idx = _index(6)
    panel = Panel.from_frames({"X": _frame([100.0] * 6)})
    w = pd.DataFrame({"X": [1.0, 1.0, 1.0, 0.0, 0.0, 0.0]}, index=idx)
    costs = CostModel(fee_bps=10.0, half_spread_bps=0.0, name="ten")
    res = run_ledger(panel, _RoundTrip(w), costs, equity=100.0)
    assert len(res.fills) == 6
    np.testing.assert_allclose(res.turnover.loc[idx[1:4]].to_numpy(), 2.0)
    assert res.turnover.loc[idx[4]] == 0.0
    # each round trip pays 10 bps in and 10 bps out, against a book that does not move,
    # and the next night is bought with what is left
    np.testing.assert_allclose(res.quantities.loc[idx[1:4], "X"].to_numpy(), [1.0, 0.998, 0.998**2])
    assert res.nav.iloc[-1] == pytest.approx(100.0 * (1 - 0.002) ** 3, rel=1e-9)
    same = run_backtest(panel, _RoundTrip(w), costs, equity=100.0)
    assert res.turnover.to_numpy() == pytest.approx(same.turnover.to_numpy())


def test_whole_shares_are_floored_at_the_real_fill_price_and_persist():
    idx = _index(4)
    ws = CostModel(fee_bps=0.0, half_spread_bps=0.0, whole_shares=True, name="whole")
    w = pd.DataFrame({"X": [0.25] * 4}, index=idx)
    # $250 slice at $400: no share, the cash stays
    dear = run_ledger(Panel.from_frames({"X": _frame([400, 400, 400, 400])}), _Book(w, marks=[False, True, False, False]), ws, equity=1000.0)
    assert dear.quantities.loc[idx[1], "X"] == 0.0 and dear.cash.loc[idx[1]] == pytest.approx(1000.0)
    # at $100: 2 shares, $200 held, $800 cash; the count persists through a rise
    cheap = run_ledger(Panel.from_frames({"X": _frame([100, 100, 150, 150])}), _Book(w, marks=[False, True, False, False]), ws, equity=1000.0)
    assert cheap.quantities.loc[idx[1], "X"] == 2.0 and cheap.cash.loc[idx[1]] == pytest.approx(800.0)
    assert cheap.quantities.loc[idx[3], "X"] == 2.0
    assert cheap.nav.loc[idx[2]] == pytest.approx(1100.0)


def test_whole_shares_size_on_the_real_price_of_a_synthetic_instrument():
    # the auction instrument's synthetic level is 10; the session closes at $400 then $100
    idx = _index(4)
    ws = CostModel(fee_bps=0.0, half_spread_bps=0.0, whole_shares=True, name="whole")
    w = pd.DataFrame({"X": [0.25] * 4}, index=idx)
    frame = _frame([10, 10, 10, 10], session_open=[400, 400, 100, 100], session_close=[400, 100, 100, 100])
    res = run_ledger(Panel.from_frames({"X": frame}), _Book(w, marks=[False, True, True, False]), ws, equity=1000.0)
    assert res.quantities.loc[idx[1], "X"] == 0.0  # $250 at $400
    assert res.quantities.loc[idx[2], "X"] == pytest.approx(2.0 * 100.0 / 10.0)  # 2 shares at $100, in synthetic units
    assert res.fills.iloc[0]["shares"] == 2.0 and res.fills.iloc[0]["fill_price"] == 100.0


def test_corrupt_volume_on_a_crash_bar_books_the_loss_and_refuses_a_new_order():
    idx = _index(5)
    frame = _frame([100, 100, 100, 50, 50])
    frame.loc[idx[3], "quote_volume"] = frame.loc[idx[3], "volume"] * frame.loc[idx[3], "high"] * 1.5  # VWAP outside the bar
    panel = Panel.from_frames({"X": frame})
    assert not panel.tradable().loc[idx[3], "X"] and panel.price_valid().loc[idx[3], "X"]
    held = run_ledger(panel, _Book(pd.DataFrame({"X": [1.0] * 5}, index=idx)), FREE, equity=100.0)
    assert held.net.loc[idx[3]] == pytest.approx(-0.5)
    assert held.quantities.loc[idx[4], "X"] == pytest.approx(1.0)  # carried, not liquidated
    # an order decided on the corrupt bar is refused: nothing is held over bar 4
    fresh = run_ledger(panel, _Book(pd.DataFrame({"X": [0, 0, 0, 1.0, 1.0]}, index=idx)), FREE, equity=100.0)
    assert fresh.quantities.loc[idx[4], "X"] == 0.0 and fresh.gross.loc[idx[4]] == 0.0
    assert len(fresh.fills) == 0


def test_a_bar_with_no_valid_price_liquidates_at_the_last_close():
    idx = _index(5)
    frame = _frame([100, 100, 110, 110, 110])
    frame.loc[idx[3], ["open", "high", "low", "close"]] = np.nan
    panel = Panel.from_frames({"X": frame})
    res = run_ledger(panel, _Book(pd.DataFrame({"X": [1.0] * 5}, index=idx)), FREE, equity=100.0)
    assert res.nav.loc[idx[2]] == pytest.approx(110.0)
    assert res.quantities.loc[idx[3], "X"] == pytest.approx(1.0)  # held into the bar
    assert res.cash.loc[idx[3]] == pytest.approx(110.0)  # sold at the last close, during the bar
    assert res.net.loc[idx[3]] == 0.0


def test_cash_earns_the_risk_free_rate_only_when_asked():
    idx = _index(3)
    panel = Panel.from_frames({"X": _frame([100, 100, 100])})
    flat = pd.DataFrame({"X": [0.0] * 3}, index=idx)
    zero = run_ledger(panel, _Book(flat), FREE, equity=100.0)
    assert (zero.net == 0.0).all()
    paid = run_ledger(panel, _Book(flat), FREE, equity=100.0, risk_free=0.0365)
    per_bar = 1.0365 ** (1 / 365) - 1
    assert paid.net.loc[idx[1]] == pytest.approx(per_bar)
    assert paid.nav.iloc[-1] == pytest.approx(100.0 * (1 + per_bar) ** 3)  # the opening balance earns on bar 0 too


# -- the identity with the weight runner ------------------------------------


@pytest.mark.parametrize(
    "strategy",
    [
        BuyAndHold(),
        BuyAndHold(gross=0.6),
        BuyAndHold(rebalance_on="MS"),
        BuyAndHold(rebalance_on="W"),
        TSMOM(),
        TSMOM(vol_target=None, lookback=30),
        CrossSectionalMomentum(),
    ],
    ids=lambda s: s.name,
)
def test_ledger_nav_path_equals_the_weight_runners_equity_on_a_clean_panel(strategy):
    panel = edge_world(n_symbols=4, years=2, seed=1)
    weights = run_backtest(panel, strategy, FREE)
    ledger = run_backtest(panel, strategy, FREE, engine="ledger")
    assert ledger.meta["engine"] == "ledger"
    np.testing.assert_allclose(ledger.equity.to_numpy(), weights.equity.to_numpy(), rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(ledger.gross.to_numpy(), weights.gross.to_numpy(), rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(ledger.turnover.to_numpy(), weights.turnover.to_numpy(), rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(ledger.held.to_numpy(), weights.held.to_numpy(), rtol=1e-9, atol=1e-12)


@pytest.mark.parametrize("strategy", [BuyAndHold(), BuyAndHold(rebalance_on="MS"), TSMOM()], ids=lambda s: s.name)
def test_with_fees_the_engines_differ_only_by_the_fee_the_runners_drift_leaves_out(strategy):
    """The runner drifts weights by the portfolio's *gross* return, so the fee
    it has just charged is not in its denominator: the next bar's turnover is
    measured against a book a fee too large, and a book held between marks
    is a fee too small a share of the account it sits in. The ledger's account
    is smaller by exactly the fee it paid. On a daily-rebalanced book gross
    P&L is identical (the position is re-sized every bar); on a scheduled one
    it differs by fee x weight; the equity curves agree to 1e-4 over two years
    at 9.5 bps a side. It is the ledger that is right (`docs/25` §1.2)."""
    panel = edge_world(n_symbols=4, years=2, seed=1)
    costs = CostModel.trial()
    weights = run_backtest(panel, strategy, costs)
    ledger = run_backtest(panel, strategy, costs, engine="ledger")
    scheduled = "rebalance_on" in strategy.params
    np.testing.assert_allclose(ledger.gross.to_numpy(), weights.gross.to_numpy(), rtol=1e-9, atol=1e-4 if scheduled else 1e-12)
    np.testing.assert_allclose(ledger.equity.to_numpy(), weights.equity.to_numpy(), rtol=1e-4)
    gap = (ledger.turnover - weights.turnover).abs().max()
    assert 0 < gap < 1e-3


def test_the_weight_engine_refuses_a_risk_free_rate_it_cannot_pay():
    panel = edge_world(n_symbols=2, years=1)
    with pytest.raises(ValueError):
        run_backtest(panel, BuyAndHold(), CostModel.trial(), risk_free=0.04)


# -- the switch --------------------------------------------------------------


def test_the_gates_run_on_the_ledger_engine_and_say_so(tmp_path):
    from qr.research.sweep import run_sweep
    from qr.validate.trial_log import TrialLog
    from qr.validate.gates import GateContext, run_gates

    panel = edge_world(n_symbols=4, years=3, seed=1)
    log = TrialLog(tmp_path / "trial_log.jsonl")
    log.prereg("h1", "trends persist; long-only")
    grid = TSMOM.grid(lookback=[40, 60])
    sweep = run_sweep(panel, grid, CostModel.trial(), engine="ledger", risk_free=0.03)
    best = sweep.best()
    assert sweep.results[best].meta["engine"] == "ledger"
    assert sweep.results[best].nav is not None
    ctx = GateContext(
        hypothesis_id="h1",
        panel=panel,
        strategy=next(s for s in grid if s.name == best),
        costs=CostModel.trial(),
        result=sweep.results[best],
        sweep=sweep,
        trial_log=log,
        permutations=5,
        spa_reps=50,
        benchmark="cash",
        risk_free=0.03,
        engine="ledger",
    )
    assert ctx.backtest_kwargs == {"engine": "ledger", "risk_free": 0.03}
    report = run_gates(ctx, upto=5, stop_on_fail=False)
    assert [r.number for r in report.results] == [0, 1, 2, 3, 4, 5]


def test_the_cli_takes_the_engine_flag():
    from qr.cli import _engine_kwargs, build_parser

    args = build_parser().parse_args(["gates", "--family", "tsmom", "--engine", "ledger"])
    assert _engine_kwargs(args, {"risk_free": 0.04}) == {"engine": "ledger", "risk_free": 0.04}
    assert _engine_kwargs(build_parser().parse_args(["gates", "--family", "tsmom"]), {"risk_free": 0.04}) == {}


def test_impact_on_the_ledger_matches_the_runners_to_the_account_it_compounds():
    panel = edge_world(n_symbols=4, years=1, seed=2)
    costs = CostModel.trial()
    runner = run_backtest(panel, TSMOM(lookback=30), costs, equity=1e6, charge_impact=True)
    ledger = run_backtest(panel, TSMOM(lookback=30), costs, equity=1e6, charge_impact=True, engine="ledger")
    assert ledger.cost_parts["impact"].sum() > 0
    # the runner prices impact on a constant $1m; the ledger on the account as it
    # compounds — this book loses on this world, so its orders shrink and so does impact
    assert runner.equity.iloc[-1] < 0.5
    ratio = ledger.cost_parts["impact"].sum() / runner.cost_parts["impact"].sum()
    assert 0.5 < ratio < 1.0
    assert (ledger.cost_parts.sum(axis=1) - ledger.costs).abs().max() < 1e-15


def test_the_leakage_probe_reads_the_same_on_both_engines_at_zero_cost():
    from qr.research.runner import leakage_probe

    panel = edge_world(n_symbols=4, years=2, seed=1)
    for strategy in (TSMOM(lookback=30), CrossSectionalMomentum()):
        weights = leakage_probe(panel, strategy, FREE)
        ledger = leakage_probe(panel, strategy, FREE, engine="ledger")
        np.testing.assert_allclose(ledger["gross_sharpe"].to_numpy(), weights["gross_sharpe"].to_numpy(), rtol=1e-9)
        assert ledger.attrs["spike_z"] == pytest.approx(weights.attrs["spike_z"], rel=1e-9)


def test_turnover_is_finite_when_a_symbol_is_not_tradable_on_the_bar():
    panel = edge_world(n_symbols=4, years=1, seed=1)
    fields = {k: v.copy() for k, v in panel.fields.items()}
    for k in fields:
        fields[k].iloc[:100, 0] = np.nan  # one symbol lists 100 days late
    late = Panel(fields, "1d")
    res = run_backtest(late, BuyAndHold(rebalance_on="W"), CostModel.binance_perp(), engine="ledger")
    assert not np.isnan(res.turnover).any()
    assert res.turnover.sum() > 0 and res.stats()["ann_turnover"] > 0
