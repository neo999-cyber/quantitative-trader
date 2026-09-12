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
