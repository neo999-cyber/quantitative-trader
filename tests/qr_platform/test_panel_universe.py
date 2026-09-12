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

    broken, bad_bar, _ = _reproduce_real_defects(panel)
    result = run_backtest(broken, BuyAndHold(), CostModel(fee_bps=0.0, half_spread_bps=0.0))
    assert result.held.loc[bad_bar, "BTCUSDT"] == 0.0


def test_clean_bars_are_unaffected_by_the_sanity_checks(panel):
    """The checks must not quietly shrink a universe that has nothing wrong."""
    mask = panel.tradable()
    assert mask.sum().sum() > 0
    assert mask.equals(panel.close.notna() & (panel.get("quote_volume").fillna(0.0) > 0.0))
