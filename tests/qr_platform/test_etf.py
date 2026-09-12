"""The ETF trial's data layer and cost model.

Two things here have no crypto analogue and both can ruin an ETF backtest
silently: dividend adjustment, and a commission charged per share with a
per-order floor.
"""
import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.data.tiingo import LocalTiingo, TiingoDaily, to_frame
from qr.data.universe import ETF_BASKET, fixed_basket
from qr.execution.costs import CostModel


def tiingo_rows(n=250, start="2020-01-02", price=100.0, dividend=0.0, adjusted=True, seed=0):
    """Rows in Tiingo's own shape, with a dividend stream if asked for.

    The adjusted series is built the way a real back-adjustment works: the
    traded price drifts sideways while the adjusted price compounds the
    distributions, which is exactly the case that separates a correct loader
    from one that quietly loses the bond sleeve's entire return.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n, tz=None)
    raw = price * np.exp(np.cumsum(rng.normal(0.0, 0.005, n)))
    factor = np.ones(n)
    if dividend:
        per_period = dividend / 4.0
        for i in range(n):
            if i and i % 63 == 0:  # quarterly
                factor[i:] *= 1.0 + per_period
    rows = []
    for i, day in enumerate(dates):
        row = {
            "date": day.strftime("%Y-%m-%dT00:00:00.000Z"),
            "open": raw[i] * 0.999,
            "high": raw[i] * 1.004,
            "low": raw[i] * 0.996,
            "close": raw[i],
            "volume": 1_000_000 + i,
            "divCash": 0.0,
            "splitFactor": 1.0,
        }
        if adjusted:
            row.update(
                {
                    "adjOpen": raw[i] * 0.999 * factor[i],
                    "adjHigh": raw[i] * 1.004 * factor[i],
                    "adjLow": raw[i] * 0.996 * factor[i],
                    "adjClose": raw[i] * factor[i],
                    "adjVolume": 1_000_000 + i,
                }
            )
        rows.append(row)
    return rows


# ------------------------------------------------------------- the adjustment


def test_the_loader_reads_adjusted_prices_not_traded_ones():
    """A bond ETF's whole return is in the distributions."""
    rows = tiingo_rows(n=504, dividend=0.04)
    frame = to_frame(rows)
    assert frame.attrs["adjusted"] is True

    # Seven quarterly distributions of 1% over 504 business days. The clean
    # invariant is the ratio of the two series, which is the adjustment factor
    # itself; the difference of the two *returns* carries a price factor too.
    factor = frame["close"].iloc[-1] / frame["close_unadjusted"].iloc[-1]
    assert factor == pytest.approx(1.01**7, rel=1e-9)

    total_return = frame["close"].iloc[-1] / frame["close"].iloc[0] - 1
    price_return = frame["close_unadjusted"].iloc[-1] / frame["close_unadjusted"].iloc[0] - 1
    # Which is several percent of compounding that unadjusted prices simply do
    # not contain — the whole return of a bond sleeve, in the wrong direction.
    assert total_return - price_return > 0.06


def test_the_traded_price_is_kept_because_share_counts_need_it():
    frame = to_frame(tiingo_rows(n=300, dividend=0.05))
    assert "close_unadjusted" in frame
    assert not np.allclose(frame["close"], frame["close_unadjusted"])
    # Dollar volume is computed on what actually changed hands.
    assert np.allclose(frame["quote_volume"], frame["volume"] * frame["close_unadjusted"])


def test_a_feed_with_no_adjusted_columns_is_flagged_rather_than_trusted():
    frame = to_frame(tiingo_rows(n=100, adjusted=False))
    assert frame.attrs["adjusted"] is False
    assert np.allclose(frame["close"], frame["close_unadjusted"])


def test_the_mirror_round_trips_and_filters_by_date(tmp_path):
    mirror = LocalTiingo(tmp_path)
    mirror.write("SPY", tiingo_rows(n=300), {"name": "SPDR S&P 500", "exchangeCode": "NYSE ARCA"})
    assert mirror.tickers() == ["SPY"]

    loader = TiingoDaily(mirror)
    full = loader.load("SPY")
    assert len(full) == 300
    clipped = loader.load("SPY", start=full.index[100].date(), end=full.index[199].date())
    assert len(clipped) == 100

    instruments = loader.instruments(["SPY"])
    assert instruments.loc[0, "symbol"] == "SPY"
    assert instruments.loc[0, "bars"] == 300
    assert bool(instruments.loc[0, "adjusted"])


def test_a_missing_ticker_says_which_one_and_where(tmp_path):
    with pytest.raises(FileNotFoundError, match="TLT"):
        TiingoDaily(LocalTiingo(tmp_path)).load("TLT")


# ------------------------------------------------------------- the fixed basket


def test_the_basket_spans_equities_duration_and_real_assets():
    assert len(ETF_BASKET) == len(set(ETF_BASKET))
    for expected in ("SPY", "TLT", "GLD", "HYG"):
        assert expected in ETF_BASKET


def test_fixed_basket_membership_needs_no_ranking(tmp_path):
    mirror = LocalTiingo(tmp_path)
    for ticker in ("SPY", "TLT", "GLD"):
        mirror.write(ticker, tiingo_rows(n=260, seed=hash(ticker) % 100))
    loader = TiingoDaily(mirror)
    panel = Panel.from_frames(
        {t: loader.load(t) for t in ("SPY", "TLT", "GLD")},
        fields=("open", "high", "low", "close", "volume", "quote_volume"),
    )
    members = fixed_basket(panel, ["SPY", "TLT"])
    assert members["SPY"].all() and members["TLT"].all()
    assert not members["GLD"].any()


def test_membership_still_stops_at_an_inception_date(tmp_path):
    """A fund that did not exist yet is out of the book, like a delisted pair."""
    mirror = LocalTiingo(tmp_path)
    mirror.write("SPY", tiingo_rows(n=300, start="2020-01-02"))
    mirror.write("DBC", tiingo_rows(n=150, start="2020-08-03"))
    loader = TiingoDaily(mirror)
    panel = Panel.from_frames(
        {t: loader.load(t) for t in ("SPY", "DBC")},
        fields=("open", "high", "low", "close", "volume", "quote_volume"),
    )
    members = fixed_basket(panel, ["SPY", "DBC"])
    assert not bool(members["DBC"].iloc[0])
    assert bool(members["DBC"].iloc[-1])


def test_a_basket_with_nothing_in_the_panel_refuses_instead_of_emptying(tmp_path):
    """The failure that let an ETF run reach gate 6 over a crypto lake.

    Every basket name was absent, so membership was all-False, every strategy
    held nothing, and the gates reported verdicts on an empty book. An empty
    universe is never a legitimate one — it is a pointed-at-the-wrong-lake bug,
    and it has to stop the run and say so.
    """
    mirror = LocalTiingo(tmp_path)
    mirror.write("BTCUSDT", tiingo_rows(n=260))
    loader = TiingoDaily(mirror)
    panel = Panel.from_frames(
        {"BTCUSDT": loader.load("BTCUSDT")},
        fields=("open", "high", "low", "close", "volume", "quote_volume"),
    )
    with pytest.raises(ValueError) as caught:
        fixed_basket(panel, ETF_BASKET)
    message = str(caught.value)
    assert "SPY" in message and "BTCUSDT" in message
    assert "etf-ingest" in message


def test_a_partly_present_basket_runs_and_names_what_is_absent(tmp_path):
    """Half a basket is a run worth having, but not silently: the pre-registered
    universe is all twelve, and the caller has to be able to say which it got."""
    mirror = LocalTiingo(tmp_path)
    for ticker in ("SPY", "TLT"):
        mirror.write(ticker, tiingo_rows(n=260, seed=hash(ticker) % 100))
    loader = TiingoDaily(mirror)
    panel = Panel.from_frames(
        {t: loader.load(t) for t in ("SPY", "TLT")},
        fields=("open", "high", "low", "close", "volume", "quote_volume"),
    )
    members = fixed_basket(panel, ETF_BASKET)
    assert members["SPY"].any() and members["TLT"].any()
    assert set(members.attrs["missing"]) == set(ETF_BASKET) - {"SPY", "TLT"}


# --------------------------------------------------------------- the commission


def _one_order(turnover=0.083, price=700.0):
    index = pd.date_range("2024-01-02", periods=1, freq="D", tz="UTC")
    return (
        pd.DataFrame({"SPY": [turnover]}, index=index),
        pd.DataFrame({"SPY": [price]}, index=index),
    )


def test_a_per_share_commission_is_not_a_basis_point_fee():
    """The cost in bps depends on order size, which a rate cannot express."""
    model = CostModel.ibkr_etf()
    turnover, prices = _one_order()
    charged = {eq: model.commission_bps(turnover, eq, prices).iloc[0, 0] for eq in (1e3, 1e4, 1e5, 1e6)}
    # Strictly decreasing in account size: the $0.35 floor dominates a small
    # order and vanishes into a large one.
    values = list(charged.values())
    assert all(b < a for a, b in zip(values, values[1:])), charged
    assert charged[1e3] > 40      # one leg of a twelve-ETF basket at $1,000
    assert charged[1e6] < 0.1     # the same trade at a million


def test_the_order_minimum_is_the_binding_cost_for_a_small_account():
    """At $1,000 an ETF basket is dearer than Binance, not cheaper."""
    ibkr = CostModel.ibkr_etf()
    turnover, prices = _one_order()
    assert ibkr.commission_bps(turnover, 1_000, prices).iloc[0, 0] > CostModel.trial().linear_bps


def test_the_minimum_is_charged_per_order_not_per_held_bar():
    """Holding is not trading. Without this the floor is charged every day."""
    model = CostModel.ibkr_etf()
    index = pd.date_range("2024-01-02", periods=3, freq="D", tz="UTC")
    turnover = pd.DataFrame({"SPY": [0.5, 0.0, 0.0]}, index=index)
    prices = pd.DataFrame({"SPY": [700.0] * 3}, index=index)
    charged = model.commission_bps(turnover, 10_000, prices)
    assert charged.iloc[0, 0] > 0
    assert charged.iloc[1, 0] == 0.0 and charged.iloc[2, 0] == 0.0


def test_the_one_percent_cap_bounds_a_tiny_order():
    model = CostModel.ibkr_etf()
    turnover, prices = _one_order(turnover=0.000_01, price=5.0)
    # $0.10 of notional cannot be charged $0.35; the cap is 1%.
    assert model.commission_bps(turnover, 1_000, prices).iloc[0, 0] == pytest.approx(100.0)


def test_the_crypto_cost_model_ignores_prices_entirely():
    """The ETF path must not perturb the crypto one. Same numbers, either way."""
    crypto = CostModel.trial()
    index = pd.date_range("2024-01-02", periods=4, freq="D", tz="UTC")
    turnover = pd.DataFrame({"BTCUSDT": [0.4, 0.1, 0.0, 0.25]}, index=index)
    prices = pd.DataFrame({"BTCUSDT": [60_000.0] * 4}, index=index)
    assert crypto.per_share_usd == 0.0
    without = crypto.charge(turnover)
    with_prices = crypto.charge(turnover, equity=10_000, prices=prices)
    assert np.allclose(without.to_numpy(), with_prices.to_numpy())


def test_the_stress_multiplier_scales_the_commission():
    model = CostModel.ibkr_etf()
    turnover, prices = _one_order()
    base = model.commission_bps(turnover, 10_000, prices).iloc[0, 0]
    assert model.stressed(2.0).commission_bps(turnover, 10_000, prices).iloc[0, 0] == pytest.approx(2 * base)


def test_the_ibkr_schedule_starts_unverified():
    """Same discipline as the Binance tier: a human checks it before a trial."""
    assert CostModel.ibkr_etf().describe()["fees_verified_on"] == "unverified"


# ------------------------------------------------------------------ the calendar


def _etf_panel(tmp_path, n=1200):
    mirror = LocalTiingo(tmp_path)
    for ticker in ("SPY", "TLT"):
        mirror.write(ticker, tiingo_rows(n=n, seed=hash(ticker) % 100))
    loader = TiingoDaily(mirror)
    return Panel.from_frames(
        {t: loader.load(t) for t in ("SPY", "TLT")},
        fields=("open", "high", "low", "close", "volume", "quote_volume"),
    )


def test_an_etf_panel_annualises_by_sessions_not_calendar_days(tmp_path):
    """A stock exchange is shut about a hundred days a year.

    The lookup said 365 bars a year for any daily panel, which is right for
    crypto and wrong for everything else: annualising ~252 sessions by 365
    multiplies the Sharpe by sqrt(365/252) = 1.20. Nothing downstream would
    catch it, because every figure in the report would be inflated by the same
    consistent factor — gate 3's threshold included.
    """
    panel = _etf_panel(tmp_path)
    assert 230 < panel.periods_per_year < 275


def test_a_daily_crypto_panel_still_reads_exactly_365(tmp_path):
    """Measurement must not introduce drift where the assumption was right."""
    from qr.validate.selftest import noise_world

    assert noise_world(n_symbols=3, years=4, seed=1).periods_per_year == 365.0


def test_a_panel_too_short_to_measure_falls_back_to_the_nominal_figure(tmp_path):
    """Two months of bars cannot tell a holiday calendar from a quiet week."""
    panel = _etf_panel(tmp_path, n=40)
    assert panel.periods_per_year == 365.0


def test_the_asset_switch_picks_the_lake_partition(tmp_path):
    """The crypto and ETF bars share a root; only source/market separate them.

    An `--asset etf` run that forgot to say so read 734 Binance pairs, found no
    SPY, and ran the gates over an empty book.
    """
    from argparse import Namespace

    from qr.cli import _partition

    assert _partition(Namespace(asset="etf")) == ("tiingo", "etf")
    assert _partition(Namespace(asset="crypto")) == ("binance", "spot")
    assert _partition(Namespace()) == ("binance", "spot")


# ------------------------------------------------------------------- QA checks


def _etf_frame(**kwargs):
    return to_frame(tiingo_rows(**kwargs))


def test_an_adjusted_series_is_not_reported_as_column_misalignment():
    """The check that called eleven of twelve real ETFs corrupt.

    `quote_volume` is the notional that actually changed hands, so it is built
    from the traded price; the OHLC columns are dividend-adjusted. Comparing
    the implied VWAP against the adjusted range fails every bar before the last
    distribution — and the only fund that passed was the one that pays none.
    """
    from qr.data.qa import check_klines

    report = check_klines(_etf_frame(n=400, dividend=0.06), "HYG")
    check = next(c for c in report.checks if c.name == "quote_volume_consistent")
    assert check.verdict == "PASS", check.offenders[:3]


def test_the_check_still_catches_a_genuinely_misaligned_column():
    """The fix must not be a way of never failing."""
    from qr.data.qa import check_klines

    frame = _etf_frame(n=400, dividend=0.06)
    frame["quote_volume"] = frame["quote_volume"] * 100.0  # price in cents
    report = check_klines(frame, "HYG")
    assert next(c for c in report.checks if c.name == "quote_volume_consistent").verdict == "FAIL"


def test_the_session_calendar_knows_what_the_exchange_does():
    from qr.data.qa import trading_sessions

    sessions = trading_sessions("2024-01-01", "2024-12-31")
    assert len(sessions) == 252  # the NYSE's 2024
    for shut in ("2024-01-01", "2024-01-15", "2024-03-29", "2024-06-19", "2024-11-28"):
        assert pd.Timestamp(shut, tz="UTC") not in sessions  # incl. Good Friday
    for shut in ("2012-10-29", "2012-10-30", "2001-09-12"):
        assert pd.Timestamp(shut, tz="UTC") not in trading_sessions("2001-01-01", "2013-01-01")


def test_weekends_are_not_missing_bars_for_a_market_that_is_shut():
    """Under the continuous calendar every ETF carries thousands of "gaps".

    A check that fires on every instrument forever is one the reader learns to
    skip, which is worse than not having it: it was the only WARN standing
    between gate 1 and a clean ETF report.
    """
    from qr.data.qa import check_klines

    frame = _etf_frame(n=1000)
    sessions = check_klines(frame, "SPY", calendar="xnys")
    continuous = check_klines(frame, "SPY", calendar="continuous")
    gaps = {r.name: r for r in sessions.checks}["calendar_gaps"]
    assert len(gaps.offenders) < 25  # holidays only; the fixture is bdays
    assert len({r.name: r for r in continuous.checks}["calendar_gaps"].offenders) > 300


# ------------------------------------------------- the traded price in the panel


def _basket_panel(tmp_path, n=800, dividend=0.04):
    mirror = LocalTiingo(tmp_path)
    for ticker in ("SPY", "TLT", "GLD"):
        mirror.write(ticker, tiingo_rows(n=n, dividend=dividend, seed=hash(ticker) % 100))
    loader = TiingoDaily(mirror)
    return Panel.from_frames({t: loader.load(t) for t in ("SPY", "TLT", "GLD")})


def test_the_panel_carries_the_price_that_actually_changed_hands(tmp_path):
    """Share counts and a per-share commission key off the traded price.

    The panel's field list stopped at OHLCV, so the traded price was dropped at
    the lake boundary and every consumer silently fell back to the adjusted
    close. For SPY in 2007 those differ by a third, so the commission was
    computed on a third more shares than the order would have bought.
    """
    panel = _basket_panel(tmp_path)
    assert "close_unadjusted" in panel.fields
    factor = panel["close"] / panel["close_unadjusted"]
    assert (factor > 1.0).any().any()  # dividends were actually paid


def test_gate_one_sees_the_same_bars_the_qa_command_does(tmp_path):
    """The four-family ETF run failed gate 1 on data `qr data qa` called clean.

    Gate 1 rebuilds each symbol's frame from the panel, so a column the panel
    never carried was a column the check could not see — and without the traded
    price the VWAP check has nothing to reconcile the adjusted range against.
    """
    from qr.validate.gates import _panel_frames, gate_1_data_integrity
    from qr.validate.gates import GateContext
    from qr.execution.costs import CostModel
    from qr.research.runner import run_backtest
    from qr.strategies.library import BuyAndHold

    panel = _basket_panel(tmp_path)
    strategy = BuyAndHold()
    costs = CostModel.etf_trial()
    ctx = GateContext(
        hypothesis_id="etf_buyhold_v1",
        panel=panel,
        strategy=strategy,
        costs=costs,
        result=run_backtest(panel, strategy, costs),
        calendar="xnys",
    )
    for symbol, frame in _panel_frames(ctx).items():
        assert "close_unadjusted" in frame.columns, symbol
    assert gate_1_data_integrity(ctx).stats["qa_failures"] == 0


def test_a_permuted_panel_keeps_the_traded_price_with_its_bar(tmp_path):
    """Otherwise gate 6's null prices commissions off a different series."""
    from qr.validate.permutation import permute_panel

    panel = _basket_panel(tmp_path)
    permuted = permute_panel(panel, seed=3)
    assert "close_unadjusted" in permuted.fields
    ratio = (permuted["close"] / permuted["close_unadjusted"]).stack().dropna()
    original = (panel["close"] / panel["close_unadjusted"]).stack().dropna()
    # The same multiset of adjustment factors, in a different order.
    assert np.isclose(sorted(ratio)[len(ratio) // 2], sorted(original)[len(original) // 2])
