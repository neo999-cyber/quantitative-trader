import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.data.universe import UniverseSpec, as_instruments, membership, rank_asof


@pytest.fixture()
def panel(frames):
    return Panel.from_frames(frames)


def test_panel_aligns_every_symbol_on_one_index(panel):
    assert panel.symbols == ["BTCUSDT", "DEADUSDT", "ETHUSDT", "LATEUSDT", "SOLUSDT"]
    assert str(panel.index.tz) == "UTC"
    assert all(f.shape == panel.close.shape for f in panel.fields.values())


def test_a_pair_outside_its_listing_window_stays_nan(panel):
    late = panel.close["LATEUSDT"]
    assert late.loc[: "2024-01-09"].isna().all()
    assert late.loc["2024-01-10":].notna().all()
    dead = panel.close["DEADUSDT"]
    assert dead.loc["2023-08-16":].isna().all()


def test_tradable_marks_exactly_the_bars_that_exist(panel):
    tradable = panel.tradable()
    assert not tradable.loc["2023-06-01", "LATEUSDT"]
    assert tradable.loc["2023-06-01", "BTCUSDT"]
    assert not tradable.loc["2024-01-01", "DEADUSDT"]


def test_returns_do_not_bridge_a_listing_gap(panel):
    returns = panel.returns()
    assert np.isnan(returns.loc["2024-01-10", "LATEUSDT"])
    assert returns.loc["2024-01-11", "LATEUSDT"] == pytest.approx(
        panel.close.loc["2024-01-11", "LATEUSDT"] / panel.close.loc["2024-01-10", "LATEUSDT"] - 1
    )


def test_a_misaligned_field_is_rejected(panel):
    broken = dict(panel.fields)
    broken["volume"] = panel.close.iloc[1:]
    with pytest.raises(ValueError, match="not aligned"):
        Panel(broken)


def test_a_naive_index_is_rejected(panel):
    naive = panel.close.copy()
    naive.index = naive.index.tz_localize(None)
    with pytest.raises(ValueError, match="UTC"):
        Panel({"close": naive})


def test_ranking_never_looks_at_the_decision_bar(panel):
    quote = panel.get("quote_volume").copy()
    asof = pd.Timestamp("2023-06-01", tz="UTC")
    # A spike on the decision bar itself must not buy SOLUSDT a seat.
    quote.loc[asof, "SOLUSDT"] = 1e15
    spec = UniverseSpec(n=2, lookback=30, min_history=30)
    assert "SOLUSDT" not in rank_asof(quote, asof, spec)


def test_ranking_picks_the_largest_by_median_quote_volume(panel):
    spec = UniverseSpec(n=2, lookback=30, min_history=30)
    chosen = rank_asof(panel.get("quote_volume"), pd.Timestamp("2023-06-01", tz="UTC"), spec)
    assert chosen == ["BTCUSDT", "DEADUSDT"]


def test_min_history_keeps_a_fresh_listing_out(panel):
    quote = panel.get("quote_volume")
    history = panel.close.notna().cumsum()
    asof = pd.Timestamp("2024-02-01", tz="UTC")
    loose = rank_asof(quote, asof, UniverseSpec(n=5, lookback=20, min_history=5), history)
    strict = rank_asof(quote, asof, UniverseSpec(n=5, lookback=20, min_history=200), history)
    assert "LATEUSDT" in loose
    assert "LATEUSDT" not in strict


def test_membership_holds_a_delisted_pair_until_its_last_bar(panel):
    frame = membership(panel, UniverseSpec(n=3, lookback=30, min_history=60))
    assert frame.loc["2023-08-15", "DEADUSDT"]
    assert not frame.loc["2023-08-16", "DEADUSDT"]
    assert frame.loc["2023-08-15"].sum() == 3


def test_membership_never_exceeds_n(panel):
    frame = membership(panel, UniverseSpec(n=2, lookback=30, min_history=60))
    assert frame.sum(axis=1).max() <= 2


def test_membership_changes_only_on_rebalance_dates(panel):
    frame = membership(panel, UniverseSpec(n=3, lookback=30, min_history=60, rebalance="MS"))
    entries = frame & ~frame.shift(1, fill_value=False)
    changed_on = sorted({d.strftime("%d") for d in entries.index[entries.any(axis=1)]})
    assert changed_on == ["01"]


def test_as_instruments_summarises_membership(panel):
    frame = membership(panel, UniverseSpec(n=3, lookback=30, min_history=60))
    summary = as_instruments(frame).set_index("symbol")
    assert summary.loc["DEADUSDT", "last_in"] == pd.Timestamp("2023-08-15", tz="UTC")
    assert summary["bars_in"].min() > 0


# ------------------------------- bars that cannot be true, from the real bucket


def _reproduce_real_defects(panel):
    """The two defects found in Binance's published archive, planted verbatim.

    BTTUSDT carries five bars of negative base volume in its first fortnight
    (2019, when nominal volumes ran to 10^11 tokens); AUDUSDT has one bar whose
    high sits below its own close. Both files' SHA-256 checksums verify, so the
    corruption is upstream of this loader.
    """
    fields = {k: v.copy() for k, v in panel.fields.items()}
    negative_volume_bar = panel.index[10]
    high_below_close_bar = panel.index[20]
    fields["volume"].loc[negative_volume_bar, "BTCUSDT"] = -6.159694e10
    fields["high"].loc[high_below_close_bar, "ETHUSDT"] = (
        fields["close"].loc[high_below_close_bar, "ETHUSDT"] * 0.997
    )
    return Panel(fields, panel.interval), negative_volume_bar, high_below_close_bar


def test_a_bar_with_negative_volume_is_not_tradable(panel):
    broken, bad_bar, _ = _reproduce_real_defects(panel)
    assert panel.tradable().loc[bad_bar, "BTCUSDT"]
    assert not broken.tradable().loc[bad_bar, "BTCUSDT"]


def test_a_bar_whose_high_is_below_its_close_is_not_tradable(panel):
    broken, _, bad_bar = _reproduce_real_defects(panel)
    assert panel.tradable().loc[bad_bar, "ETHUSDT"]
    assert not broken.tradable().loc[bad_bar, "ETHUSDT"]


def test_only_the_impossible_bars_are_excluded_not_the_symbol(panel):
    """Discarding a pair over five bad prints would reintroduce survivorship bias."""
    broken, bad_volume, bad_high = _reproduce_real_defects(panel)
    before, after = panel.tradable(), broken.tradable()
    assert after["BTCUSDT"].sum() == before["BTCUSDT"].sum() - 1
    assert after["ETHUSDT"].sum() == before["ETHUSDT"].sum() - 1
    assert after.drop(columns=["BTCUSDT", "ETHUSDT"]).equals(
        before.drop(columns=["BTCUSDT", "ETHUSDT"])
    )


def test_a_strategy_cannot_hold_an_impossible_bar(panel):
    from qr.execution.costs import CostModel
    from qr.research.runner import run_backtest
    from qr.strategies.library import BuyAndHold

    broken, bad_volume_bar, bad_price_bar = _reproduce_real_defects(panel)
    result = run_backtest(broken, BuyAndHold(), CostModel(fee_bps=0.0, half_spread_bps=0.0))
    # A held position is carried through a bar whose only defect is its
    # volume field — the price is real and so is its return (review 22, §1.1);
    # it cannot be *entered* on that bar (`test_a_new_position_is_refused_when_
    # the_decision_bar_was_not_tradable`). A bar with no valid price cannot be
    # held: the book is out at the last close, stated as a convention.
    assert result.held.loc[bad_volume_bar, "BTCUSDT"] == pytest.approx(0.25)
    assert result.held.loc[bad_price_bar, "ETHUSDT"] == 0.0


def test_clean_bars_are_unaffected_by_the_sanity_checks(panel):
    """The checks must not quietly shrink a universe that has nothing wrong."""
    mask = panel.tradable()
    assert mask.sum().sum() > 0
    assert mask.equals(panel.close.notna() & (panel.get("quote_volume").fillna(0.0) > 0.0))


# ------------------------- what a volume ranking admits that it should not


@pytest.fixture()
def mixed_market():
    """Real coins alongside the instruments a volume ranking wrongly promotes.

    Every non-crypto pair here is given the *largest* quote volume, because
    that is the real situation: on Binance the stablecoin pairs out-trade the
    coins, being conversion rails rather than speculations.
    """
    index = pd.date_range("2021-01-01", periods=700, freq="D", tz="UTC")
    rng = np.random.default_rng(0)

    def build(daily_vol, price, quote_volume):
        close = price * np.exp(np.cumsum(rng.normal(0.0, daily_vol, len(index))))
        return pd.DataFrame(
            {
                "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
                "volume": quote_volume / close, "quote_volume": quote_volume, "trades": 1e4,
            },
            index=index,
        )

    return Panel.from_frames({
        "BTCUSDT": build(0.0125, 40_000, 5e8),   # ~24% annualised: a quiet Bitcoin
        "ETHUSDT": build(0.040, 2_500, 4e8),
        "SOLUSDT": build(0.050, 100, 3e8),
        "USDCUSDT": build(0.00005, 1.0, 9e9),    # a peg, with the biggest volume
        "EURUSDT": build(0.0045, 1.1, 8e9),      # fiat, ~9% annualised
        "BTCUPUSDT": build(0.090, 10, 7e9),      # a leveraged token
        "PAXGUSDT": build(0.009, 2_000, 6e9),    # tokenised gold, ~17% annualised
    })


@pytest.fixture()
def mixed_membership(mixed_market):
    return membership(mixed_market, UniverseSpec(n=5, lookback=30, min_history=120))


def test_stablecoins_never_enter_the_universe(mixed_membership):
    """A crypto strategy holding USDC is holding cash, not taking a position."""
    assert not mixed_membership["USDCUSDT"].any()


def test_fiat_pairs_never_enter_the_universe(mixed_membership):
    assert not mixed_membership["EURUSDT"].any()


def test_leveraged_tokens_never_enter_the_universe(mixed_membership):
    """Daily-rebalanced derivatives with decay, not spot assets."""
    assert not mixed_membership["BTCUPUSDT"].any()


def test_tokenised_commodities_are_excluded_by_name_not_by_volatility(mixed_market, mixed_membership):
    """Gold runs ~17% annualised, comfortably above the floor — hence the list."""
    realised = mixed_market.returns()["PAXGUSDT"].std() * np.sqrt(365)
    assert realised > UniverseSpec().min_annual_vol
    assert not mixed_membership["PAXGUSDT"].any()


def test_a_quiet_bitcoin_is_still_admitted(mixed_market, mixed_membership):
    """The floor must not exclude a real asset in a calm stretch.

    Bitcoin's quietest 90-day windows run 25-30% annualised, so a floor set
    just above fiat would be one lull away from emptying the universe.
    """
    realised = mixed_market.returns()["BTCUSDT"].std() * np.sqrt(365)
    assert realised < 0.30
    assert mixed_membership["BTCUSDT"].any()


def test_the_real_coins_are_the_whole_universe(mixed_membership):
    held = {s for s in mixed_membership.columns if mixed_membership[s].any()}
    assert held == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}


def test_the_volatility_filter_reads_only_past_bars(mixed_market):
    """A coin that depegs tomorrow must still be excluded today."""
    from qr.data.universe import rank_asof

    spec = UniverseSpec(n=5, lookback=30, min_history=120)
    asof = mixed_market.index[400]
    volatility = (
        mixed_market.returns().rolling(spec.vol_lookback, min_periods=30).std() * np.sqrt(365)
    )
    spiked = volatility.copy()
    spiked.loc[asof:, "USDCUSDT"] = 5.0  # enormous volatility, from `asof` onward
    chosen = rank_asof(mixed_market.get("quote_volume"), asof, spec, None, spiked)
    assert "USDCUSDT" not in chosen


def test_the_exclusions_are_recorded_in_the_spec_description():
    described = UniverseSpec().describe()
    assert described["min_annual_vol"] == 0.15
    assert described["vol_lookback_bars"] == 90
    assert "PAXGUSDT" in described["exclude_symbols"]
    assert described["exclude_leveraged"] is True


def test_turning_the_filters_off_restores_the_naive_ranking(mixed_market):
    """The defect is reproducible, which is how we know the fix is the fix."""
    naive = membership(
        mixed_market,
        UniverseSpec(n=5, lookback=30, min_history=120, min_annual_vol=0.0,
                     exclude_leveraged=False, exclude_symbols=frozenset()),
    )
    assert naive["USDCUSDT"].any()
    assert naive["PAXGUSDT"].any()


def test_a_bar_whose_quote_volume_implies_a_vwap_outside_its_range_is_not_tradable(panel):
    """AAVEUSDT 2023-09-21 in the perp archive: quote volume ~1.5x what the range
    allows (24 such bars in 637,705, five dates in 2023). `qa.check_klines` flags
    it; the panel must withhold it too, or gate 1 fails a book for a bar it read."""
    fields = {k: v.copy() for k, v in panel.fields.items()}
    bar = panel.index[30]
    fields["quote_volume"].loc[bar, "BTCUSDT"] = (
        fields["volume"].loc[bar, "BTCUSDT"] * fields["high"].loc[bar, "BTCUSDT"] * 1.5
    )
    broken = Panel(fields, panel.interval)
    assert panel.tradable().loc[bar, "BTCUSDT"]
    assert not broken.tradable().loc[bar, "BTCUSDT"]
    assert (panel.tradable().sum().sum() - broken.tradable().sum().sum()) == 1
