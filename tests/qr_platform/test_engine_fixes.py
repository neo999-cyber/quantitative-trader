"""The four engine defects the first real four-family run exposed.

None of them changed that run's verdict — all four families failed gates 3, 4,
5 and 9 independently — but each of them made a number in the report mean
something other than what it said, and a platform whose whole claim is that it
reports honestly cannot carry those.
"""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from qr.data.panel import Panel
from qr.data.qa import check_klines
from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.strategies.library import TSMOM
from qr.validate.cpcv import walk_forward_efficiency
from qr.validate.gates import (
    FAIL,
    PASS,
    GateContext,
    _capacity,
    _excluded_bars,
    gate_1_data_integrity,
)
from qr.validate.permutation import permute_panel
from qr.validate.selftest import edge_world, noise_world


@pytest.fixture(scope="module")
def panel():
    return edge_world(n_symbols=6, years=4, seed=2)


@pytest.fixture()
def costs():
    return CostModel.trial()


def context(panel, strategy, costs, **kwargs):
    return GateContext(
        hypothesis_id="h",
        panel=panel,
        strategy=strategy,
        costs=costs,
        result=run_backtest(panel, strategy, costs),
        permutations=kwargs.pop("permutations", 5),
        **kwargs,
    )


def corrupt(panel: Panel, symbol: str, when) -> Panel:
    """Reproduce the AUDUSDT defect: one bar whose high sits below its close."""
    fields = {k: v.copy() for k, v in panel.fields.items()}
    fields["high"].loc[when, symbol] = fields["close"].loc[when, symbol] * 0.98
    return Panel(fields, panel.interval)


# ------------------------------------------------------- 1. gate 1 vs tradability


def test_qa_check_can_be_rescored_over_the_bars_that_were_allowed_through():
    index = pd.date_range("2020-01-01", periods=200, freq="D", tz="UTC")
    price = pd.Series(np.linspace(100, 120, 200), index=index)
    frame = pd.DataFrame(
        {
            "open": price,
            "high": price * 1.01,
            "low": price * 0.99,
            "close": price,
            "volume": 1_000.0,
            "quote_volume": price * 1_000.0,
        }
    )
    frame.loc[index[50], "high"] = frame.loc[index[50], "close"] * 0.98

    report = check_klines(frame, "X", "1d")
    assert report.verdict == FAIL

    kept = report.excluding(pd.DatetimeIndex([index[50]]))
    assert kept.verdict == PASS
    # The check is not silently deleted: it says how many it stopped counting.
    high = next(c for c in kept.checks if c.name == "high_is_highest")
    assert "already excluded" in high.detail


def test_rescoring_does_not_hide_a_gap_in_the_listing_window():
    index = pd.date_range("2020-01-01", periods=60, freq="D", tz="UTC").delete(30)
    price = pd.Series(np.linspace(100, 110, len(index)), index=index)
    frame = pd.DataFrame(
        {"open": price, "high": price * 1.01, "low": price * 0.99, "close": price,
         "volume": 1_000.0, "quote_volume": price * 1_000.0}
    )
    report = check_klines(frame, "X", "1d").excluding(index)
    gaps = next(c for c in report.checks if c.name == "calendar_gaps")
    # The missing bar is not in the frame at all, so it cannot be in the
    # excluded set, and the warning survives being rescored.
    assert gaps.count == 1


def test_an_index_level_failure_survives_rescoring():
    """`timezone_utc` fails with no offenders. Emptiness must not excuse it."""
    index = pd.date_range("2020-01-01", periods=40, freq="D")
    price = pd.Series(np.linspace(100, 110, 40), index=index)
    frame = pd.DataFrame(
        {"open": price, "high": price * 1.01, "low": price * 0.99, "close": price}
    )
    report = check_klines(frame, "X", "1d").excluding(index)
    assert report.verdict == FAIL


def test_gate_1_no_longer_fails_a_strategy_for_bars_it_was_never_served(panel, costs):
    """The defect that stopped all four trial families at gate 1."""
    when = panel.index[400]
    broken = corrupt(panel, panel.symbols[0], when)

    # The panel itself already refuses to make that bar tradable...
    assert when in _excluded_bars(context(broken, TSMOM(lookback=60), costs))[panel.symbols[0]]
    # ...and the raw bars really do fail QA, so this is not a weakened check.
    raw = check_klines(
        pd.DataFrame({f: broken[f][panel.symbols[0]] for f in broken.fields}).dropna(subset=["close"]),
        panel.symbols[0],
        "1d",
    )
    assert raw.verdict == FAIL

    result = gate_1_data_integrity(context(broken, TSMOM(lookback=60), costs))
    assert result.verdict != FAIL
    assert result.stats["qa_failures_on_raw_bars"] >= 1
    assert result.stats["qa_failures_traded"] == 0


def test_gate_1_still_fails_on_a_defect_the_panel_did_let_through(panel, costs):
    """Only *excluded* bars are forgiven. A tradable bad bar still blocks."""
    symbol = panel.symbols[0]
    fields = {k: v.copy() for k, v in panel.fields.items()}
    # taker_buy_base above volume is a column-misalignment failure that
    # `Panel.tradable()` does not look at, so nothing withholds these bars.
    fields["taker_buy_base"] = fields["volume"] * 2.0
    broken = Panel(fields, panel.interval)
    result = gate_1_data_integrity(context(broken, TSMOM(lookback=60), costs))
    assert result.verdict == FAIL
    assert result.stats["qa_failures_traded"] >= 1


# ------------------------------------------------------------- 2. impact and capacity


def raw_law() -> CostModel:
    """The unmodified square-root law, which double-counts the spread."""
    return replace(CostModel.trial(), net_impact_against_spread=False)


def impact(model: CostModel, participation: float, sigma: float = 0.03, adv: float = 1e8) -> float:
    return float(model.impact_bps(np.array([participation * adv]), np.array([adv]), np.array([sigma]))[0])


def test_a_tiny_order_is_charged_no_impact_at_all():
    """The $10,000-capacity defect, as a unit test.

    A $500 order against $100m of daily volume is half a millionth of the
    book. The unmodified law charged about 2 bps for it — more than the
    half-spread it is supposed to sit on top of.
    """
    assert impact(raw_law(), 5e-6) > 0.5
    assert impact(CostModel.trial(), 5e-6) == 0.0


def test_netting_converges_to_the_square_root_law_where_the_law_is_large():
    model, raw = CostModel.trial(), raw_law()
    assert impact(model, 0.10) == pytest.approx(impact(raw, 0.10) - model.half_spread_bps, rel=1e-9)
    assert impact(model, 0.10) / impact(raw, 0.10) > 0.95


def test_impact_is_continuous_and_monotone_where_it_switches_on():
    model = CostModel.trial()
    charged = [impact(model, p) for p in (1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1)]
    assert all(b >= a for a, b in zip(charged, charged[1:]))
    # No jump at the crossover: it leaves zero continuously.
    crossover = (model.half_spread_bps * 1e-4 / model.impact_coef / 0.03) ** 2
    assert impact(model, crossover * 1.001) < 0.05


def test_netting_only_ever_lowers_the_charge():
    """No gate can be made easier to pass by this, at any size."""
    model, raw = CostModel.trial(), raw_law()
    for p in (1e-7, 1e-5, 1e-3, 1e-2, 1.0):
        assert impact(model, p) <= impact(raw, p) + 1e-12


def test_a_maker_order_keeps_the_full_law():
    """Netting exists because the taker path already paid the spread."""
    maker = replace(CostModel.trial(), use_maker=True)
    assert impact(maker, 5e-6) == pytest.approx(impact(raw_law(), 5e-6), rel=1e-9)


def test_the_cost_stress_multiplier_still_scales_impact():
    model = CostModel.trial()
    assert impact(model.stressed(2.0), 0.05) == pytest.approx(2 * impact(model, 0.05), rel=1e-9)


def test_capacity_reports_its_band_and_says_when_it_is_extrapolated(panel, costs):
    stats = _capacity(context(panel, TSMOM(lookback=60), costs))
    assert stats["impact_coef"] == costs.impact_coef
    assert stats["capacity_usd_pessimistic"] <= stats["capacity_usd"] <= stats["capacity_usd_optimistic"]
    assert isinstance(stats["capacity_extrapolated"], bool)
    assert any(k.startswith("impact_drag_at_") for k in stats)


def test_removing_the_double_count_raises_capacity(costs):
    """The regression test for the number the user called out."""
    base = edge_world(n_symbols=8, years=4, seed=3)
    quote = base["quote_volume"]
    deep = Panel({**base.fields, "quote_volume": quote / quote.mean().mean() * 1e8}, base.interval)
    strategy = TSMOM(lookback=60)
    fixed = _capacity(context(deep, strategy, costs))
    before = _capacity(context(deep, strategy, raw_law()))
    assert fixed["capacity_usd"] >= before["capacity_usd"]
    # The ladder steps in factors of three, so it can round the improvement
    # away. The drag it is derived from cannot, and that is the measurement.
    for rung in ("impact_drag_at_1e+03", "impact_drag_at_1e+04", "impact_drag_at_1e+05"):
        assert fixed[rung] < before[rung]
    assert fixed["impact_drag_at_1e+03"] == 0.0


# --------------------------------------------------------- 3. walk-forward efficiency


def _wfe_frame(is_returns, oos_returns, n_windows=6, n_obs=1200):
    """A two-variant frame whose walk-forward windows have chosen returns."""
    index = pd.date_range("2018-01-01", periods=n_obs, freq="D", tz="UTC")
    edges = np.linspace(0, n_obs, n_windows + 1).astype(int)
    values = np.zeros(n_obs)
    for w, (is_r, oos_r) in enumerate(zip(is_returns, oos_returns), start=1):
        values[edges[w] : edges[w + 1]] = oos_r
        if w == 1:
            values[: edges[1]] = is_r
    return pd.DataFrame({"v": values}, index=index)


def test_walk_forward_efficiency_does_not_explode_on_a_cancelling_denominator():
    """The reversal family reported WFE 13.62. This is why.

    Anchored training windows whose returns very nearly cancel leave the
    pooled ratio dividing by almost nothing, and a ratio with a denominator
    passing through zero is a random number of arbitrary magnitude. The median
    of the per-window ratios cannot do that, because each window brings its own
    denominator and the median ignores the one that blew up.
    """
    n_obs, n_windows = 1800, 6
    index = pd.date_range("2018-01-01", periods=n_obs, freq="D", tz="UTC")
    edges = np.linspace(0, n_obs, n_windows + 1).astype(int)
    values = np.full(n_obs, 0.001)
    # Window 3 trains on everything before it; make that training mean tiny
    # while every window's own out-of-sample return stays healthy.
    values[edges[1] : edges[3]] = -0.001 * (edges[1] / (edges[3] - edges[1]))
    frame = pd.DataFrame({"v": values}, index=index)

    walk = walk_forward_efficiency(frame, 365.0, n_windows=n_windows)
    assert walk.attrs["wfe_windows"] >= 3
    assert np.isfinite(walk.attrs["wfe"])
    # The pooled figure is the one that can run away; the median must not.
    assert abs(walk.attrs["wfe"]) < 5
    assert "wfe_window" in walk.columns


def test_walk_forward_efficiency_is_one_when_nothing_degrades():
    index = pd.date_range("2018-01-01", periods=1200, freq="D", tz="UTC")
    frame = pd.DataFrame({"v": np.full(1200, 0.001)}, index=index)
    walk = walk_forward_efficiency(frame, 365.0)
    assert walk.attrs["wfe"] == pytest.approx(1.0, rel=1e-6)
    assert walk.attrs["wfe_pooled"] == pytest.approx(1.0, rel=1e-6)


def test_windows_with_no_in_sample_edge_are_dropped_not_counted_as_zero():
    index = pd.date_range("2018-01-01", periods=1200, freq="D", tz="UTC")
    frame = pd.DataFrame({"v": np.full(1200, -0.001)}, index=index)
    walk = walk_forward_efficiency(frame, 365.0)
    assert walk.attrs["wfe_windows"] == 0
    assert np.isnan(walk.attrs["wfe"])


# ------------------------------------------------ 4. the volatility-preserving null


def clustered_panel(n_symbols: int = 5, n: int = 1500, seed: int = 0) -> Panel:
    """A panel with genuine GARCH-style volatility clustering.

    `edge_world` has constant volatility, so it cannot tell the two nulls
    apart: there is no clustering there to preserve or destroy. The confound
    gate 6 hit is a property of real markets, so the test needs a fixture that
    has it.
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range("2019-01-01", periods=n, freq="D", tz="UTC")
    symbols = [f"C{i}USDT" for i in range(n_symbols)]
    market = np.zeros(n)
    sigma2 = np.full(n, 0.02**2)
    for t in range(1, n):
        sigma2[t] = 1e-5 + 0.12 * market[t - 1] ** 2 + 0.86 * sigma2[t - 1]
        market[t] = rng.normal(0.0005, np.sqrt(sigma2[t]))
    close = {}
    for s_i, symbol in enumerate(symbols):
        idio = rng.normal(0, 0.01, n) * np.sqrt(sigma2 / sigma2.mean())
        close[symbol] = 100.0 * np.exp(np.cumsum(0.8 * market + idio))
    close = pd.DataFrame(close, index=index)
    fields = {
        "open": close.shift(1).bfill(),
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": pd.DataFrame(1e4, index=index, columns=symbols),
        "quote_volume": close * 1e4,
    }
    fields["high"] = np.maximum(fields["high"], fields["open"])
    fields["low"] = np.minimum(fields["low"], fields["open"])
    return Panel(fields, "1d")


def _vol_path(panel: Panel) -> pd.Series:
    return panel.returns().abs().mean(axis=1).rolling(20).mean().dropna()


def test_the_fixture_really_does_cluster():
    path = _vol_path(clustered_panel())
    assert path.autocorr(lag=5) > 0.7


def test_plain_permutation_destroys_volatility_clustering():
    panel = clustered_panel(seed=7)
    real, null = _vol_path(panel), _vol_path(permute_panel(panel, seed=1))
    assert pd.concat([real, null], axis=1).dropna().corr().iloc[0, 1] < 0.3


def test_the_vol_preserving_null_keeps_the_volatility_path():
    panel = clustered_panel(seed=7)
    real, null = _vol_path(panel), _vol_path(permute_panel(panel, seed=1, preserve_volatility=True))
    assert pd.concat([real, null], axis=1).dropna().corr().iloc[0, 1] > 0.8


def test_the_vol_preserving_null_still_destroys_the_time_ordering():
    """It must give up the ordering of direction, which is the whole point."""
    panel = clustered_panel(seed=7)
    trended = Panel(
        {**panel.fields, "close": panel.close},
        panel.interval,
    )
    shuffled = permute_panel(trended, seed=1, preserve_volatility=True)

    def signed_autocorr(p: Panel) -> float:
        r = p.returns()
        return float(np.nanmean([np.sign(r[s]).autocorr(lag=1) for s in p.symbols]))

    assert abs(signed_autocorr(shuffled)) < 0.06


def test_the_vol_preserving_null_keeps_listing_windows_and_prices_positive():
    panel = clustered_panel(seed=11)
    shuffled = permute_panel(panel, seed=2, preserve_volatility=True)
    assert shuffled.close.notna().equals(panel.close.notna())
    assert bool((shuffled.close.dropna(how="all") > 0).all().all())


def test_the_two_nulls_give_materially_different_answers(costs):
    """The claim `docs/07_ENGINE_FIXES.md` §3 makes, and the only one it makes.

    Not that one null is harder — measured over six seeds it went three each
    way. Only that the choice matters, which is what justifies reporting both.
    """
    panel = clustered_panel(n_symbols=4, n=700, seed=5)
    strategy = TSMOM(lookback=40)
    medians = {}
    for flag in (False, True):
        medians[flag] = np.median(
            [
                run_backtest(
                    permute_panel(panel, seed=i, preserve_volatility=flag), strategy, costs
                ).sharpe(gross=True)
                for i in range(12)
            ]
        )
    spread = abs(medians[True] - medians[False])
    assert spread > 0.05, medians


def test_the_two_nulls_are_reported_separately_by_gate_6(costs):
    from qr.validate.gates import gate_6_permutation

    panel = clustered_panel(n_symbols=4, n=500, seed=3)
    result = gate_6_permutation(
        context(panel, TSMOM(lookback=30), costs, permutations=4, vol_preserving_permutations=4)
    )
    assert "bar_permutation_p_value" in result.stats
    assert "bar_permutation_vol_preserved_p_value" in result.stats
    assert "not binding" in result.detail


def test_the_second_null_can_be_switched_off(costs):
    from qr.validate.gates import gate_6_permutation

    panel = clustered_panel(n_symbols=4, n=500, seed=3)
    result = gate_6_permutation(
        context(panel, TSMOM(lookback=30), costs, permutations=4, vol_preserving_permutations=0)
    )
    assert "bar_permutation_vol_preserved_p_value" not in result.stats


# ------------------------------------------- 5. the two operational traps this cost


def test_run_gates_announces_each_gate_before_it_starts(panel, costs):
    """Silence is indistinguishable from a hang, and a real run was killed on it."""
    from qr.validate.gates import run_gates

    lines: list[str] = []
    run_gates(context(panel, TSMOM(lookback=60), costs), upto=2, progress=lines.append)

    # Before, not only after: an announcement that arrives when the gate ends
    # does not help anyone staring at gate 6 for forty minutes.
    assert lines[0].strip().startswith("gate 0")
    assert lines[0].strip().endswith("…")
    assert any("PASS" in line or "FAIL" in line or "WARN" in line or "SKIP" in line for line in lines)
    assert any(line.rstrip().endswith("s)") for line in lines)


def test_an_empty_lake_is_refused_with_the_root_it_looked_in(tmp_path, capsys):
    """`QR_ROOT` pointed one directory too high cost this project three runs.

    The failure was a `ValueError: no symbols in the lake match that query`
    three frames inside `load_panel`, which reads as a filter problem. It is
    not one, and the message never named the directory it had looked in.
    """
    import argparse

    from qr.cli import _load_panel
    from qr.data.lake import Lake
    from qr.config import Paths

    lake = Lake(Paths(tmp_path).ensure())
    with pytest.raises(SystemExit) as exit_info:
        _load_panel(lake, "1d")
    assert exit_info.value.code == 2
    message = capsys.readouterr().err
    assert str(tmp_path) in message
    assert "QR_ROOT" in message
    assert "qr data ingest" in message


# ------------------------------ 6. the lag-spike statistic, and the panel it runs on


def _rsi_world(n=1500, seed=0, bounce=0.0):
    """Random walk with real volume variation, optionally with a planted
    one-bar bounce after three down closes — a causal short-horizon edge."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    symbols = [f"S{i}USDT" for i in range(6)]
    close, volume = {}, {}
    for symbol in symbols:
        r = rng.normal(0.0003, 0.04, n)
        if bounce:
            for t in range(3, n):
                if r[t - 1] < 0 and r[t - 2] < 0 and r[t - 3] < 0:
                    r[t] += bounce
        close[symbol] = 100 * np.exp(np.cumsum(r))
        volume[symbol] = rng.lognormal(10, 0.8, n)
    close = pd.DataFrame(close, index=index)
    volume = pd.DataFrame(volume, index=index)
    open_ = close.shift(1).bfill()
    return Panel(
        {
            "open": open_,
            "high": np.maximum(close, open_) * 1.005,
            "low": np.minimum(close, open_) * 0.995,
            "close": close,
            "volume": volume,
            "quote_volume": volume * close,
        },
        "1d",
    )


def test_the_lag_spike_statistic_is_not_a_ratio_of_two_noise_terms(costs):
    """`spike_ratio` accused the trial's control family of a look-ahead.

    It is S(1) / max(S(0), S(2)), and when both lags score near zero that is a
    ratio of noise to noise. Over worlds with nothing planted in them it
    produced values from 0.98 to `inf`. `spike_z` measures the same gap in
    standard errors, so it cannot divide by zero and orders the worlds sanely.
    """
    from qr.research.runner import leakage_probe
    from qr.strategies.library import RSIReversal

    ratios, zs = [], []
    for seed in range(4):
        probe = leakage_probe(_rsi_world(seed=seed), RSIReversal(), costs)
        ratios.append(probe.attrs["spike_ratio"])
        zs.append(probe.attrs["spike_z"])

    # No edge is planted in any of these, so none of them should look like one.
    assert all(abs(z) < 3.0 for z in zs), zs
    # ...which the ratio does not manage: it is unbounded over the same worlds.
    assert max(abs(r) for r in ratios if np.isfinite(r)) > 1.5 or any(
        not np.isfinite(r) for r in ratios
    )


def test_rsi_reversal_does_not_read_the_bar_it_predicts(costs):
    """The accusation, tested directly. A look-ahead earns a Sharpe in data
    with nothing in it; an honest strategy earns roughly nothing."""
    from qr.research.runner import leakage_probe
    from qr.strategies.library import RSIReversal

    for seed in range(3):
        probe = leakage_probe(_rsi_world(seed=seed), RSIReversal(), costs)
        assert abs(probe.loc[1, "gross_sharpe"]) < 1.0, seed


def test_the_probe_still_catches_a_planted_look_ahead(costs):
    """The fix must not be a way of never warning again."""
    from qr.research.runner import leakage_probe
    from qr.strategies.base import Strategy

    class Oracle(Strategy):
        family = "oracle"

        def target_weights(self, panel, universe=None):
            return self.normalise(
                self.mask_to_universe((panel.returns() > 0).astype(float), panel, universe)
            )

    probe = leakage_probe(_rsi_world(seed=0), Oracle(), costs)
    # The peek lands on lag 0, so lag 1 sits far *below* its neighbours — a
    # large |z| either way is the signature the flat case does not produce.
    assert abs(probe.attrs["spike_z"]) > 10


def test_restricting_the_panel_to_the_universe_changes_no_number(costs):
    """The 734-column panel: 4.5x faster, and it must be bit-identical."""
    from qr.cli import _restrict_to_universe
    from qr.data.universe import UniverseSpec, membership

    panel = edge_world(n_symbols=40, years=4, seed=4)
    spec = UniverseSpec(n=8, lookback=30, min_history=90)
    universe = membership(panel, spec)
    small, small_universe = _restrict_to_universe(panel, universe)
    assert len(small.symbols) < len(panel.symbols)

    strategy = TSMOM(lookback=60)
    full = run_backtest(panel, strategy, costs, universe)
    cut = run_backtest(small, strategy, costs, small_universe)
    assert float((full.net - cut.net).abs().max()) == 0.0
    assert full.sharpe() == cut.sharpe()


def test_the_restriction_keeps_every_symbol_the_universe_ever_admits(costs):
    """Membership is decided on the full panel; only what it never chose goes."""
    from qr.cli import _restrict_to_universe
    from qr.data.universe import UniverseSpec, membership

    panel = edge_world(n_symbols=40, years=4, seed=4)
    universe = membership(panel, UniverseSpec(n=8, lookback=30, min_history=90))
    small, small_universe = _restrict_to_universe(panel, universe)
    ever = {s for s in panel.symbols if bool(universe[s].any())}
    assert set(small.symbols) == ever
    assert small_universe.equals(universe[list(small.symbols)])


# ---------------------------------- 7. the sweep: every other ratio in the engine


def test_the_noise_floor_is_one_standard_error_of_a_sharpe():
    from qr.validate.stats import sharpe_standard_error

    assert sharpe_standard_error(365, 365.0) == pytest.approx(1.0)
    assert sharpe_standard_error(2557, 365.0) == pytest.approx(0.378, abs=1e-3)
    # More data, a tighter floor — the thing a fixed constant could not express.
    assert sharpe_standard_error(10_000, 365.0) < sharpe_standard_error(1_000, 365.0)
    assert np.isnan(sharpe_standard_error(0))


def test_net_over_gross_refuses_a_gross_return_that_is_only_just_positive():
    """`gross_ann > 0` passes for 0.1% a year, and the ratio then means nothing.

    Gate 2 compares it against a 60% floor, so a strategy earning essentially
    nothing could pass a gate about surviving costs.
    """
    from qr.research.runner import _net_over_gross

    index = pd.date_range("2018-01-01", periods=2000, freq="D", tz="UTC")
    rng = np.random.default_rng(0)
    noise = pd.Series(rng.normal(0, 0.02, 2000), index=index)
    # Positive mean, but a Sharpe far inside one standard error of zero.
    barely = noise - noise.mean() + 1e-7
    assert barely.mean() > 0
    assert np.isnan(_net_over_gross(barely * 0.9, barely, 365.0))

    # A real gross return still produces a real ratio.
    real = noise - noise.mean() + 0.002
    ratio = _net_over_gross(real * 0.8, real, 365.0)
    assert np.isfinite(ratio) and ratio == pytest.approx(0.8, rel=1e-6)


def test_gate_2_fails_rather_than_passes_when_the_ratio_is_not_measurable(panel, costs):
    """The `nan` must not be read as a pass. Gate 2 already gets this right."""
    from qr.strategies.base import Strategy
    from qr.validate.gates import gate_2_cost_survival

    class Flat(Strategy):
        family = "flat"

        def target_weights(self, panel, universe=None):
            return pd.DataFrame(0.0, index=panel.index, columns=panel.symbols)

    result = gate_2_cost_survival(context(panel, Flat(), costs))
    assert result.verdict == FAIL
    assert "nothing to survive" in result.detail


def test_neighbourhood_retention_refuses_a_peak_within_noise_of_zero(costs):
    """A peak Sharpe of 0.02 beside a neighbour at 0.03 is 150% "retention"."""
    from qr.research.sweep import neighbourhood_retention, run_sweep

    panel = edge_world(n_symbols=5, years=3, seed=6)
    grid = TSMOM.grid(lookback=[20, 40, 60, 90], vol_target=[0.2])
    sweep = run_sweep(panel, grid, costs)

    # Force the peak to sit inside the noise floor and check it is refused.
    flattened = sweep.stats.copy()
    flattened["sharpe"] = [0.02, 0.03, 0.01, 0.015][: len(flattened)]
    from dataclasses import replace as dc_replace

    flat_sweep = dc_replace(sweep, stats=flattened)
    out = neighbourhood_retention(flat_sweep, flat_sweep.names[0])
    assert np.isnan(out["retention"]), out


def test_gate_8_says_so_when_the_plateau_cannot_be_measured(costs):
    """A check that could not run must not be silent — silence reads as a pass."""
    from dataclasses import replace as dc_replace

    from qr.research.sweep import run_sweep
    from qr.validate.gates import gate_8_robustness

    panel = edge_world(n_symbols=5, years=3, seed=6)
    # Spaced inside the 25% neighbour tolerance, so neighbours exist to measure.
    grid = TSMOM.grid(lookback=[40, 45, 50, 55], vol_target=[0.2])
    sweep = run_sweep(panel, grid, costs)

    flattened = sweep.stats.copy()
    flattened["sharpe"] = np.linspace(0.02, 0.035, len(flattened))
    flat_sweep = dc_replace(sweep, stats=flattened)
    best = flat_sweep.names[0]

    ctx = context(panel, next(s for s in grid if s.name == best), costs, sweep=flat_sweep)
    result = gate_8_robustness(ctx)
    assert not np.isfinite(result.stats.get("neighbourhood_retention", float("nan")))
    assert "not measurable" in result.detail, result.detail


def test_the_crosscheck_reports_a_scale_relative_error_too(panel, costs):
    """The pointwise error divides by an equity a ruinous strategy drives to zero."""
    from qr.research import crosscheck

    result = run_backtest(panel, TSMOM(lookback=60), costs)
    comparison = crosscheck.compare(panel, result, costs)
    assert np.isfinite(comparison.scale_relative_error)
    # On a healthy curve the two measures agree closely; they diverge only when
    # the denominator of the pointwise one is collapsing.
    assert comparison.scale_relative_error <= max(comparison.max_relative_error, 1e-9) * 10


# --------------------------------------- gate 8 told two failures apart at last


def _decomposition_reading(net, panel):
    """The sentence gate 8 would print for this return series."""
    from qr.validate.factors import decompose, factor_table
    from qr.validate.gates import GateThresholds

    d = decompose(net, factor_table(panel), panel.periods_per_year)
    thresholds = GateThresholds()
    explained = d.r_squared
    return (
        "market"
        if np.isfinite(explained) and explained >= thresholds.min_factor_r2
        else "neutral"
    ), d


def test_a_book_with_no_market_exposure_is_not_called_the_market():
    """`ls_xsmom_v1` failed gate 8 with beta -0.06 and was told it was the market.

    A dollar-neutral book cannot be market exposure, and the same sentence had
    just been printed against a beta of 0.98. A verdict that fires either way
    says nothing — which went unnoticed for as long as every family tested was
    long-only.
    """
    from qr.validate.selftest import noise_world

    panel = noise_world(n_symbols=6, years=6, seed=11)
    market = panel.returns().mean(axis=1)

    rng = np.random.default_rng(0)
    unrelated = pd.Series(
        rng.normal(0.0, float(market.std()), len(market)), index=market.index, name="net"
    )
    reading, d = _decomposition_reading(unrelated, panel)
    assert reading == "neutral"
    assert abs(d.betas.get(d.dominant_factor, 0.0)) < 0.25

    beta_book = (market * 0.95).rename("net")
    reading, d = _decomposition_reading(beta_book, panel)
    assert reading == "market"
    assert d.r_squared > 0.25


def test_the_two_readings_are_decided_by_what_the_factors_explain():
    """R-squared, not a beta threshold: the question is how much is accounted for."""
    from qr.validate.gates import GateThresholds

    assert GateThresholds().min_factor_r2 == 0.25


# ------------------------------- a monthly book that traded every day for months


def _oracle_held(panel, target, freq):
    """Carry the drifted book forward; trade only on rebalance bars.

    Written as an explicit loop precisely because it is the definition rather
    than the optimisation — if the engine's closed form disagrees with this,
    the closed form is wrong.
    """
    from qr.strategies.base import rebalance_mask

    marks = rebalance_mask(panel.index, freq).to_numpy()
    rr = panel.returns().fillna(0.0).to_numpy()
    values = np.zeros_like(target.to_numpy())
    prev = np.zeros(target.shape[1])
    for i in range(len(target)):
        # The book held over bar i is yesterday's book grown by *yesterday's*
        # move; bar i's move has not happened when it is set. (Until
        # 2026-09-15 this grew it by rr[i], a one-bar look-ahead.)
        grow = rr[i - 1] if i > 0 else np.zeros(target.shape[1])
        port = 1.0 + float((prev * grow).sum())
        drifted = (prev * (1.0 + grow) / port) if port else prev * (1.0 + grow)
        values[i] = target.to_numpy()[i] if marks[i] else drifted
        prev = values[i]
    return pd.DataFrame(values, index=target.index, columns=target.columns)


def test_a_monthly_book_trades_twelve_times_a_year_not_three_hundred_and_sixty_five():
    """The drift used to be computed by the strategy, one bar out of phase.

    `run_backtest` holds the book from bar t-1 and drifts it by bar t's return.
    A strategy can only drift its own t-1 target by t-1's return — t's has not
    happened. The two disagreed by one day's move on every bar between
    rebalances and the engine charged the disagreement as a trade, so a book
    scheduled to rebalance twelve times a year traded on all 365 of them, for
    about nine times the cost. Every ETF family ran this way.
    """
    from qr.execution.costs import CostModel
    from qr.research.runner import run_backtest
    from qr.strategies.library import BuyAndHold
    from qr.validate.selftest import noise_world

    panel = noise_world(n_symbols=12, years=6, seed=3)
    result = run_backtest(panel, BuyAndHold(rebalance_on="MS"), CostModel.etf_trial(), equity=1_000.0)

    years = len(panel) / panel.periods_per_year
    traded_bars = float((result.turnover > 1e-12).sum())
    assert 10 <= traded_bars / years <= 13


def test_the_engine_agrees_with_a_loop_that_is_the_definition():
    from qr.execution.costs import CostModel
    from qr.research.runner import drift, run_backtest
    from qr.strategies.library import BuyAndHold
    from qr.validate.selftest import noise_world

    panel = noise_world(n_symbols=8, years=5, seed=9)
    result = run_backtest(panel, BuyAndHold(rebalance_on="MS"), CostModel.etf_trial(), equity=1_000.0)

    target = BuyAndHold().target_weights(panel).shift(1).fillna(0.0)
    held = _oracle_held(panel, target, "MS")
    expected = (held - drift(held.shift(1).fillna(0.0), panel.returns().shift(1))).abs().sum().sum()
    assert np.isclose(float(result.turnover.sum()), float(expected), rtol=1e-6)
    assert np.allclose(result.held.to_numpy(), held.to_numpy(), atol=1e-12)


def test_a_strategy_that_trades_every_bar_is_untouched_by_the_schedule():
    """The identity case. A crypto family must be bit-for-bit what it was."""
    from qr.execution.costs import CostModel
    from qr.research.runner import run_backtest
    from qr.strategies.library import BuyAndHold
    from qr.validate.selftest import noise_world

    panel = noise_world(n_symbols=6, years=4, seed=2)
    model = CostModel.trial()
    implicit = run_backtest(panel, BuyAndHold(), model)
    explicit = run_backtest(panel, BuyAndHold(rebalance_on="D"), model)
    assert np.allclose(implicit.net, explicit.net)
    assert np.allclose(implicit.turnover, explicit.turnover)


def test_an_unknown_rebalance_frequency_is_refused_rather_than_ignored():
    from qr.strategies.library import BuyAndHold
    from qr.validate.selftest import noise_world

    panel = noise_world(n_symbols=4, years=2, seed=1)
    with pytest.raises(ValueError, match="rebalance_on"):
        BuyAndHold(rebalance_on="fortnightly").target_weights(panel)
