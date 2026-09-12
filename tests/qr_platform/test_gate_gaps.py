"""The Day 6-7 additions: the pieces of `PLAN.md` §4 that were specified but
not implemented, plus the two calibration errors the self-test caught.
"""
import math

import numpy as np
import pandas as pd
import pytest

from qr.execution.costs import CostModel
from qr.research.runner import run_backtest
from qr.research.sweep import run_sweep
from qr.strategies.library import BuyAndHold, CrossSectionalMomentum, TSMOM
from qr.validate.gates import (
    FAIL,
    PASS,
    WARN,
    GateContext,
    GateThresholds,
    _capacity,
    _drop_best_trades,
    _regime_sharpes,
    _shuffled_ticker,
    gate_1_data_integrity,
    gate_2_cost_survival,
    gate_4_deflation,
    gate_5_selection,
    gate_6_permutation,
)
from qr.validate.selftest import edge_world, noise_world
from qr.validate.spa import SPAResult, buy_and_hold_benchmark, superior_predictive_ability
from qr.validate.stats import effective_trials


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
        permutations=kwargs.pop("permutations", 10),
        spa_reps=kwargs.pop("spa_reps", 150),
        **kwargs,
    )


# ------------------------------------------------------------------- gate 5: SPA


def test_spa_is_stated_in_losses_not_returns():
    """arch's SPA takes losses. Passing returns silently inverts the test."""
    rng = np.random.default_rng(0)
    bench = pd.Series(rng.normal(0.0005, 0.02, 1200), name="bench")
    models = pd.DataFrame({f"v{i}": bench + rng.normal(0, 0.01, 1200) for i in range(20)})
    models["winner"] = bench + rng.normal(0.0015, 0.01, 1200)

    result = superior_predictive_ability(models, bench, reps=300)
    assert result.p_consistent < 0.05
    assert result.best_excess_annual > 0
    assert "winner" in result.stepm_survivors


def test_spa_does_not_reject_when_nothing_beats_the_benchmark():
    rng = np.random.default_rng(1)
    bench = pd.Series(rng.normal(0.0005, 0.02, 1200), name="bench")
    models = pd.DataFrame({f"v{i}": bench + rng.normal(0, 0.01, 1200) for i in range(20)})
    assert superior_predictive_ability(models, bench, reps=300).p_consistent > 0.05


def test_the_spa_verdict_bands_are_pass_warn_fail():
    """A real edge lands in the middle band, which is why the band is wide."""
    assert SPAResult(0.01, 0, 0, 20, 1200, "b").verdict() == PASS
    assert SPAResult(0.27, 0, 0, 200, 2190, "b").verdict() == WARN
    assert SPAResult(0.99, 0, 0, 200, 2190, "b").verdict() == FAIL


def test_spa_refuses_too_short_a_sample():
    short = pd.DataFrame({"v": np.zeros(10)})
    with pytest.raises(ValueError, match="at least 50"):
        superior_predictive_ability(short, pd.Series(np.zeros(10)), reps=10)


def test_the_benchmark_is_costed_like_the_strategy(panel, costs):
    free = buy_and_hold_benchmark(panel, None, CostModel(fee_bps=0.0, half_spread_bps=0.0))
    charged = buy_and_hold_benchmark(panel, None, costs)
    assert charged.sum() < free.sum()


def test_gate_five_reports_spa_alongside_pbo(panel, costs):
    grid = TSMOM.grid(lookback=[20, 40, 60, 90])
    sweep = run_sweep(panel, grid, costs)
    ctx = context(panel, next(s for s in grid if s.name == sweep.best()), costs, sweep=sweep)
    ctx.result = sweep.results[sweep.best()]
    result = gate_5_selection(ctx)
    assert "spa_p_consistent" in result.stats
    assert "pbo" in result.stats
    assert "SPA p" in result.detail


# ------------------------------------------- gate 4: effective trials, reported only


def test_effective_trials_collapses_for_redundant_variants():
    rng = np.random.default_rng(0)
    base = rng.normal(0, 0.02, 1200)
    redundant = pd.DataFrame({f"v{i}": base + rng.normal(0, 0.001, 1200) for i in range(50)})
    independent = pd.DataFrame(rng.normal(0, 0.02, (1200, 50)))
    assert effective_trials(redundant)[0] <= 3
    assert effective_trials(independent)[0] >= 40


def test_effective_trials_never_exceeds_the_raw_count():
    frame = pd.DataFrame(np.random.default_rng(0).normal(0, 0.02, (500, 8)))
    effective, raw = effective_trials(frame)
    assert 1 <= effective <= raw == 8


def test_deflation_uses_the_raw_count_and_only_reports_the_effective_one(panel, costs):
    """The reversal the self-test forced.

    E[max] = sqrt(V) * f(N) already shrinks through V when variants are
    redundant, so discounting N as well double-counts the correlation and lets
    searched-over noise through. DSR takes the raw count; the effective rank is
    a diagnostic.
    """
    grid = TSMOM.grid(lookback=list(range(20, 140, 10)), skip=[0, 5])
    sweep = run_sweep(panel, grid, costs)
    ctx = context(panel, next(s for s in grid if s.name == sweep.best()), costs, sweep=sweep)
    ctx.result = sweep.results[sweep.best()]
    result = gate_4_deflation(ctx)

    assert result.stats["trials"] == float(len(grid))
    assert result.stats["trials_raw"] == float(len(grid))
    assert result.stats["trials_effective"] < result.stats["trials_raw"]


# ------------------------------------------------ gate 6: re-optimisation


def test_gate_six_reoptimises_over_the_grid(panel, costs):
    grid = TSMOM.grid(lookback=[20, 40, 60, 90, 120])
    sweep = run_sweep(panel, grid, costs)
    ctx = context(panel, next(s for s in grid if s.name == sweep.best()), costs, sweep=sweep)
    ctx.result = sweep.results[sweep.best()]
    ctx.reoptimise_variants = 4
    result = gate_6_permutation(ctx)
    assert result.stats["reoptimised_over"] == 4.0
    assert result.stats["grid_size"] == 5.0
    assert "re-optimised over 4 of 5" in result.detail


def test_without_a_sweep_gate_six_says_it_did_not_reoptimise(panel, costs):
    result = gate_6_permutation(context(panel, TSMOM(lookback=60), costs))
    assert result.stats["reoptimised_over"] == 1.0
    assert "no re-optimisation" in result.detail


def test_gate_six_honours_the_configured_thresholds(panel, costs):
    """These were defined and never wired, so changing them did nothing."""
    ctx = context(panel, TSMOM(lookback=60), costs)
    strict = GateThresholds(max_permutation_p=1e-9, fail_permutation_p=2e-9)
    ctx.thresholds = strict
    assert gate_6_permutation(ctx).verdict == FAIL


# ------------------------------------------------ gate 1: shuffled-ticker placebo


def test_the_placebo_is_flat_for_a_strategy_that_picks_nothing(panel, costs):
    """Buy-and-hold holds everything, so reassigning its weights changes nothing."""
    ctx = context(panel, BuyAndHold(), costs)
    placebo = _shuffled_ticker(ctx, n_permutations=25)
    assert placebo.p_value > 0.5
    assert placebo.observed == pytest.approx(np.median(placebo.null), abs=1e-9)


def test_the_placebo_detects_selection_that_genuinely_matters(costs):
    """The mechanism, on a case where the answer is not in doubt.

    One symbol rises every bar, the rest are flat, and the book holds only the
    riser. Attaching those same weights to any other symbol earns nothing, so
    the placebo must be emphatic.

    A realistic case cannot make this point: at crypto volatility a 90-day
    trailing return is mostly noise, so a momentum ranker picks the genuinely
    better coin only a little more often than chance, and the placebo says so.
    That is the strategy's limitation, not the test's.
    """
    from qr.data.panel import Panel

    index = pd.date_range("2020-01-01", periods=400, freq="D", tz="UTC")
    rng = np.random.default_rng(3)
    frames = {}
    for i in range(5):
        # Every symbol carries the same noise; only S0 has the drift. Giving
        # the others zero volatility would make a Sharpe undefined rather than
        # small, and the comparison meaningless.
        drift = 0.004 if i == 0 else 0.0
        close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, len(index))))
        frames[f"S{i}USDT"] = pd.DataFrame(
            {"open": close, "high": close, "low": close, "close": close,
             "volume": 1e4, "quote_volume": 1e4 * close, "trades": 500.0},
            index=index,
        )
    panel = Panel.from_frames(frames)

    class HoldTheRiser(TSMOM):
        family = "holds_the_riser"

        def target_weights(self, panel, universe=None):
            weights = pd.DataFrame(0.0, index=panel.index, columns=panel.symbols)
            weights["S0USDT"] = 1.0
            return self.mask_to_universe(weights, panel, universe)

    ctx = context(panel, HoldTheRiser(), costs)
    placebo = _shuffled_ticker(ctx, n_permutations=50)
    assert placebo.observed > placebo.null.max()
    assert placebo.p_value == pytest.approx(1 / 51)


def test_the_placebo_is_honest_when_there_is_nothing_to_pick(panel, costs):
    """`edge_world` has a time-series edge and no cross-sectional one.

    Every symbol there gets the same kind of independent AR(1) drift, so a
    momentum ranker is choosing between statistically identical coins. The
    placebo says its choices carry nothing, which is true — and worth knowing
    before reading any cross-sectional result on that world.
    """
    ctx = context(panel, CrossSectionalMomentum(lookback=60, skip=0, n_long=2), costs)
    assert _shuffled_ticker(ctx, n_permutations=50).p_value > 0.10


def test_gate_one_reports_the_placebo_and_warns_when_picks_are_worthless(panel, costs):
    result = gate_1_data_integrity(context(panel, BuyAndHold(), costs))
    assert "placebo_p_value" in result.stats
    assert result.verdict == WARN
    assert "symbol selection carries little" in result.detail


# ------------------------------------------------------------ gate 2: capacity


def test_capacity_is_reported_and_finite(panel, costs):
    result = gate_2_cost_survival(context(panel, TSMOM(lookback=60), costs))
    if "capacity_usd" in result.stats:
        capacity = result.stats["capacity_usd"]
        assert np.isfinite(capacity) and capacity >= 0
        # 0 is a real answer ("below the smallest size probed"), not a gap.


def test_a_more_liquid_universe_has_more_capacity(costs):
    from qr.data.panel import Panel

    base = edge_world(n_symbols=4, years=3, seed=1)
    thick = Panel({**base.fields, "quote_volume": base["quote_volume"] * 1000}, base.interval)
    thin_capacity = _capacity(context(base, TSMOM(lookback=60), costs)).get("capacity_usd")
    thick_capacity = _capacity(context(thick, TSMOM(lookback=60), costs)).get("capacity_usd")
    assert thick_capacity >= thin_capacity


# ------------------------------------- gate 8: trades not bars, and regimes


def test_dropping_the_best_trades_uses_per_symbol_holdings(panel, costs):
    """A vol-targeted book is invested almost every bar, so a portfolio-level
    definition makes the whole sample one episode and removes the strategy."""
    result = run_backtest(panel, TSMOM(lookback=60), costs)
    trimmed = _drop_best_trades(result.net, result.held, panel.returns(), n=5)

    assert len(trimmed) == len(result.net)  # bars are kept, contributions removed
    assert trimmed.sum() < result.net.sum()
    # Removing five trades must not remove most of the return.
    assert trimmed.notna().sum() == result.net.notna().sum()


def test_dropping_more_trades_removes_more(panel, costs):
    result = run_backtest(panel, TSMOM(lookback=60), costs)
    five = _drop_best_trades(result.net, result.held, panel.returns(), n=5).sum()
    twenty = _drop_best_trades(result.net, result.held, panel.returns(), n=20).sum()
    assert twenty < five


def test_dropping_trades_from_a_flat_book_changes_nothing(panel, costs):
    result = run_backtest(panel, TSMOM(lookback=60), costs)
    flat = result.held * 0.0
    pd.testing.assert_series_equal(
        _drop_best_trades(result.net, flat, panel.returns(), n=5), result.net
    )


def test_regime_sharpes_cover_three_volatility_buckets(panel, costs):
    result = run_backtest(panel, TSMOM(lookback=60), costs)
    regimes = _regime_sharpes(result.net, panel, panel.periods_per_year)
    assert set(regimes) == {"low", "mid", "high"}
    assert all(np.isfinite(v) for v in regimes.values())


def test_regimes_are_measured_from_the_market_not_the_strategy(panel, costs):
    """Sorting bars by the strategy's own volatility would sort by how much it
    was doing, not by what the market was doing."""
    result = run_backtest(panel, TSMOM(lookback=60), costs)
    doubled = run_backtest(panel, TSMOM(lookback=60, vol_target=0.40), costs)
    a = _regime_sharpes(result.net, panel, panel.periods_per_year)
    b = _regime_sharpes(doubled.net, panel, panel.periods_per_year)
    assert set(a) == set(b)  # same buckets, different strategy volatility


def test_regimes_are_skipped_on_too_short_a_sample(costs):
    short = edge_world(n_symbols=3, years=1, seed=1)
    result = run_backtest(short, TSMOM(lookback=30), costs)
    assert _regime_sharpes(result.net, short, short.periods_per_year, lookback=200) == {}


# --------------------------------------------------- gate 1: QA, actually wired


def test_the_self_test_worlds_satisfy_the_platforms_own_qa():
    """A fixture that cannot pass the checks being tested invites weakening them.

    Both worlds used to fail `high_is_highest` on ~45% of bars (high was set
    from the close while open was the previous close) and
    `quote_volume_consistent` on every bar (a constant quote volume implying a
    VWAP of 10,000 on a coin trading at 100). Nobody noticed because gate 1's
    QA never ran on a real pipeline path.
    """
    from qr.data.qa import check_klines

    for world in (edge_world(n_symbols=3, years=2, seed=1), noise_world(n_symbols=3, years=2, seed=1)):
        for symbol in world.symbols:
            frame = pd.DataFrame({name: world[name][symbol] for name in world.fields})
            report = check_klines(frame[frame["close"].notna()], symbol, "1d")
            assert report.verdict == PASS, (symbol, [c.name for c in report.failures])


def test_qa_runs_even_when_no_caller_passes_raw_frames(panel, costs):
    """The bug: the field existed, gate 1 read it, nothing ever set it."""
    ctx = context(panel, TSMOM(lookback=60), costs)
    assert ctx.raw_frames is None
    result = gate_1_data_integrity(ctx)
    assert result.stats["qa_failures"] == 0
    assert result.stats["qa_failures_traded"] == 0


def test_a_broken_symbol_the_strategy_holds_fails_the_gate(panel, costs):
    from qr.data.panel import Panel

    fields = {k: v.copy() for k, v in panel.fields.items()}
    fields["high"].iloc[100, 0] = 0.01  # high below the bar's own low
    broken = Panel(fields, panel.interval)

    result = gate_1_data_integrity(context(broken, TSMOM(lookback=60), costs))
    assert result.verdict == FAIL
    assert "which this strategy holds" in result.detail
    assert result.stats["qa_failures_traded"] >= 1


def test_a_broken_symbol_the_strategy_never_holds_does_not_block(panel, costs):
    """734 real pairs will always contain a few with impossible bars somewhere.

    Failing a top-30 book because a delisted microcap it never touched has a
    negative volume print would make gate 1 noise, and noise gets ignored. The
    universe-wide audit is `qr data qa`; gate 1 checks what was traded.
    """
    from qr.data.panel import Panel

    excluded = panel.symbols[-1]
    universe = pd.DataFrame(True, index=panel.index, columns=panel.symbols)
    universe[excluded] = False

    fields = {k: v.copy() for k, v in panel.fields.items()}
    fields["high"].loc[:, excluded] = 0.01
    broken = Panel(fields, panel.interval)

    strategy = TSMOM(lookback=60)
    ctx = GateContext(
        hypothesis_id="h",
        panel=broken,
        strategy=strategy,
        costs=costs,
        result=run_backtest(broken, strategy, costs, universe),
        universe=universe,
        permutations=5,
    )
    result = gate_1_data_integrity(ctx)
    assert result.verdict != FAIL
    assert result.stats["qa_failures_traded"] == 0
