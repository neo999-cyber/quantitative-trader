"""The gate pipeline: `docs/PLAN.md` §4, turned into code.

Every idea runs these in order and **stops at the first FAIL**. That ordering
is the whole design: the cheap, decisive tests come first, so a leaky signal is
caught by gate 1 before anyone spends an afternoon admiring its CPCV paths, and
nothing downstream can rescue a strategy that does not survive its own costs.

A WARN does not stop the run but demands a written justification in the trial
log — `TrialLog.note()` — and an unjustified WARN is treated as a FAIL by the
report.

Gates 0-9 are here. Gate 10 (incubation) needs live time and gate 11 (sizing)
is a portfolio decision, so both belong after the trial verdict rather than in
this pipeline.

The thresholds are those in the plan, in one place, as `GateThresholds`. They
are deliberately awkward to change in passing: loosening a threshold to get a
pass is the single easiest way to make this entire apparatus worthless, so a
changed threshold is a visible change to a named default with a git blame.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from qr.data.panel import Panel
from qr.data.qa import check_klines
from qr.execution.costs import CostModel
from qr.research.runner import BacktestResult, leakage_probe, run_backtest
from qr.research.sweep import Sweep, neighbourhood_retention
from qr.strategies.base import Strategy
from qr.validate import stats as st
from qr.validate.cpcv import combinatorial_purged_cv, walk_forward_efficiency
from qr.validate.cscv import cscv, is_oos_degradation
from qr.validate.factors import Decomposition, decompose, factor_table
from qr.validate.permutation import PermutationSuite, bar_permutation_test, random_entry_test
from qr.validate.trial_log import TrialLog

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"


@dataclass(frozen=True)
class GateThresholds:
    """Every number a verdict turns on. Changing one is a visible decision."""

    # gate 1. A daily strategy earning a gross Sharpe above 8 over years of
    # data has a bug, not an edge; the shape test only warns, because a genuine
    # short-horizon reversal produces the same shape as a leak.
    implausible_sharpe: float = 8.0
    max_spike_ratio: float = 1.50
    # gate 2
    min_net_over_gross: float = 0.60
    fail_net_over_gross: float = 0.50
    cost_stress: float = 2.0
    # gate 3
    min_tstat: float = 3.0
    fail_tstat: float = 2.5
    min_psr: float = 0.95
    # gate 4
    min_dsr: float = 0.95
    fail_dsr: float = 0.90
    # gate 5
    max_pbo: float = 0.10
    fail_pbo: float = 0.20
    # A high PBO only fails when the selected variant actually loses out of
    # sample this often; otherwise the variants are interchangeable, not overfit.
    max_prob_oos_loss: float = 0.10
    max_spa_p: float = 0.05
    # gate 6
    max_permutation_p: float = 0.05
    fail_permutation_p: float = 0.10
    # gate 7
    min_path_ratio: float = 0.50
    min_share_positive: float = 0.90
    min_wfe: float = 0.50
    # gate 8
    min_neighbour_retention: float = 0.70
    max_free_params: int = 5
    min_round_trips: int = 50
    min_profitable_years: float = 2 / 3
    # gate 9
    min_holdout_ratio: float = 0.50


@dataclass
class GateResult:
    number: int
    name: str
    verdict: str
    detail: str
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def blocking(self) -> bool:
        return self.verdict == FAIL

    def row(self) -> dict[str, Any]:
        return {"gate": self.number, "name": self.name, "verdict": self.verdict, "detail": self.detail}


@dataclass
class GateContext:
    """Everything the gates read. Assembled once, never mutated by a gate."""

    hypothesis_id: str
    panel: Panel
    strategy: Strategy
    costs: CostModel
    result: BacktestResult
    sweep: Sweep | None = None
    universe: pd.DataFrame | None = None
    trial_log: TrialLog | None = None
    manifest_hash: str | None = None
    holdout_panel: Panel | None = None
    holdout_universe: pd.DataFrame | None = None
    raw_frames: dict[str, pd.DataFrame] | None = None
    thresholds: GateThresholds = field(default_factory=GateThresholds)
    permutations: int = 200
    bootstrap_reps: int = 2000
    seed: int = 0

    @property
    def periods_per_year(self) -> float:
        return self.panel.periods_per_year

    @property
    def trial_count(self) -> int:
        """Variants tried. The sweep if there is one, else the whole trial log."""
        if self.sweep is not None:
            return len(self.sweep)
        if self.trial_log is not None:
            return max(1, self.trial_log.trial_count(self.hypothesis_id))
        return 1


# --------------------------------------------------------------------- gates


def gate_0_preregistration(ctx: GateContext) -> GateResult:
    """Was the hypothesis written down before the data was touched?"""
    if ctx.trial_log is None:
        return GateResult(0, "pre-registration", SKIP, "no trial log supplied; exploratory only")
    records = ctx.trial_log.records(kind="prereg", hypothesis_id=ctx.hypothesis_id)
    if not records:
        return GateResult(
            0,
            "pre-registration",
            FAIL,
            f"no pre-registration for {ctx.hypothesis_id!r}: this run is exploratory, not a test",
        )
    first_run = next(iter(ctx.trial_log.records(kind="run", hypothesis_id=ctx.hypothesis_id)), None)
    stats = {"doc_sha256": records[0].payload.get("doc_sha256"), "registered_at": records[0].ts}
    if first_run is not None and first_run.seq < records[0].seq:
        return GateResult(
            0,
            "pre-registration",
            FAIL,
            "the first run predates the pre-registration: the hypothesis was written after seeing results",
            stats,
        )
    return GateResult(0, "pre-registration", PASS, f"registered {records[0].ts[:19]}", stats)


def gate_1_data_integrity(ctx: GateContext) -> GateResult:
    """QA on the bars, plus the one-switch leakage probe."""
    stats: dict[str, Any] = {}
    detail_parts: list[str] = []
    verdict = PASS

    if ctx.raw_frames:
        reports = [check_klines(f, s, ctx.panel.interval) for s, f in sorted(ctx.raw_frames.items())]
        failures = [r.symbol for r in reports if r.verdict == FAIL]
        warnings = [r.symbol for r in reports if r.verdict == WARN]
        stats["qa_failures"], stats["qa_warnings"] = len(failures), len(warnings)
        if failures:
            return GateResult(
                1, "data integrity", FAIL, f"QA failed for {', '.join(failures[:5])}", stats
            )
        if warnings:
            verdict = WARN
            detail_parts.append(f"{len(warnings)} symbols with QA warnings")

    probe = leakage_probe(ctx.panel, ctx.strategy, ctx.costs, ctx.universe)
    honest = float(probe.loc[1, "gross_sharpe"])
    spike = probe.attrs.get("spike_ratio", float("nan"))
    stats.update(
        {
            "lag0_gross_sharpe": float(probe.loc[0, "gross_sharpe"]),
            "lag1_gross_sharpe": honest,
            "lag2_gross_sharpe": float(probe.loc[2, "gross_sharpe"]),
            "peek_ratio": probe.attrs.get("peek_ratio", float("nan")),
            "spike_ratio": spike,
        }
    )

    # The blocking test is magnitude, not shape. A daily strategy does not earn
    # a gross Sharpe of 8 over years of bars; one that appears to is reading the
    # future somewhere inside its own signal, where the runner's shift cannot
    # reach it.
    if np.isfinite(honest) and abs(honest) > ctx.thresholds.implausible_sharpe:
        return GateResult(
            1,
            "data integrity",
            FAIL,
            f"gross Sharpe {honest:.1f} at the honest lag is not a plausible daily edge; "
            f"the signal is reading the bar it predicts",
            stats,
        )
    if np.isfinite(spike) and spike > ctx.thresholds.max_spike_ratio:
        verdict = WARN
        detail_parts.append(
            f"Sharpe peaks at the reported lag ({spike:.2f}x its neighbours): either a "
            f"genuinely one-bar-ahead signal or a look-ahead — say which in the trial log"
        )
    else:
        detail_parts.append(f"no lag spike (peak/neighbours {spike:.2f})")
    return GateResult(1, "data integrity", verdict, "; ".join(detail_parts) or "clean", stats)


def gate_2_cost_survival(ctx: GateContext) -> GateResult:
    """Does the edge survive its own costs, and twice them?"""
    result = ctx.result
    ratio = result.stats()["net_over_gross"]
    stressed = run_backtest(
        ctx.panel, ctx.strategy, ctx.costs.stressed(ctx.thresholds.cost_stress), ctx.universe
    )
    stressed_sharpe = stressed.sharpe()
    stats = {
        "gross_sharpe": result.sharpe(gross=True),
        "net_sharpe": result.sharpe(),
        "net_over_gross": ratio,
        "ann_turnover": result.stats()["ann_turnover"],
        "cost_drag_ann": result.stats()["cost_drag_ann"],
        f"sharpe_at_{ctx.thresholds.cost_stress:g}x_costs": stressed_sharpe,
        "cost_model": ctx.costs.describe(),
    }
    if not np.isfinite(ratio):
        return GateResult(2, "cost survival", FAIL, "gross return is not positive; there is nothing to survive", stats)
    if ratio < ctx.thresholds.fail_net_over_gross:
        return GateResult(2, "cost survival", FAIL, f"costs eat {1 - ratio:.0%} of gross return", stats)
    if stressed_sharpe <= 0:
        return GateResult(2, "cost survival", FAIL, f"negative at {ctx.thresholds.cost_stress:g}x costs", stats)
    if ratio < ctx.thresholds.min_net_over_gross:
        return GateResult(2, "cost survival", WARN, f"only {ratio:.0%} of gross return survives costs", stats)
    return GateResult(
        2,
        "cost survival",
        PASS,
        f"{ratio:.0%} of gross survives; Sharpe {stressed_sharpe:.2f} at {ctx.thresholds.cost_stress:g}x costs",
        stats,
    )


def gate_3_significance(ctx: GateContext) -> GateResult:
    """HAC t, PSR, bootstrap CI, and the track record against MinTRL."""
    net = ctx.result.net.dropna()
    moments = st.moments(net)
    t_stat, p_value, lags = st.hac_tstat(net)
    psr = st.probabilistic_sharpe(net, moments_=moments)
    lower, upper, _ = st.stationary_bootstrap_ci(
        net, ctx.periods_per_year, reps=ctx.bootstrap_reps, seed=ctx.seed
    )
    mintrl = st.min_track_record_length(net, moments_=moments)

    stats = {
        "hac_tstat": t_stat,
        "hac_pvalue": p_value,
        "hac_lags": float(lags),
        "psr": psr,
        "sharpe_ci_lower": lower,
        "sharpe_ci_upper": upper,
        "min_track_record_length": mintrl,
        "observations": float(moments.n),
        "skew": moments.skew,
        "kurtosis": moments.kurtosis,
    }
    if not np.isfinite(t_stat) or t_stat < ctx.thresholds.fail_tstat:
        return GateResult(3, "single-strategy significance", FAIL, f"HAC t = {t_stat:.2f}", stats)
    if lower <= 0:
        return GateResult(
            3, "single-strategy significance", FAIL, f"bootstrap 95% CI [{lower:.2f}, {upper:.2f}] includes zero", stats
        )
    if math.isfinite(mintrl) and mintrl > moments.n:
        return GateResult(
            3,
            "single-strategy significance",
            WARN,
            f"needs {mintrl:.0f} bars to be distinguishable from zero; has {moments.n}",
            stats,
        )
    if t_stat < ctx.thresholds.min_tstat or psr < ctx.thresholds.min_psr:
        return GateResult(
            3, "single-strategy significance", WARN, f"t = {t_stat:.2f}, PSR = {psr:.2f}", stats
        )
    return GateResult(
        3, "single-strategy significance", PASS, f"t = {t_stat:.2f}, PSR = {psr:.3f}, CI excludes zero", stats
    )


def gate_4_deflation(ctx: GateContext) -> GateResult:
    """Deflate for how hard the search was. Needs an honest trial count."""
    net = ctx.result.net.dropna()
    n_trials = ctx.trial_count
    if ctx.sweep is not None and len(ctx.sweep) >= 2:
        variance = float(ctx.sweep.per_period_sharpes().var(ddof=1))
    else:
        # No sweep to measure dispersion from: fall back to the sampling
        # variance of a Sharpe estimate, 1/T, which is the conservative floor.
        variance = 1.0 / max(1, len(net))
    dsr, benchmark = st.deflated_sharpe(net, n_trials, sharpe_variance=variance)
    _, p_value, _ = st.hac_tstat(net)
    haircut, adjusted_p = st.haircut_sharpe(
        ctx.result.sharpe(), n_trials, p_value / 2.0, method="bhy"
    )
    annual_sharpe = ctx.result.sharpe()
    min_btl = st.min_backtest_length(n_trials, max(annual_sharpe, 0.25))
    years = len(net) / ctx.periods_per_year

    stats = {
        "trials": float(n_trials),
        "sharpe_variance": variance,
        "deflation_benchmark_per_period": benchmark,
        "dsr": dsr,
        "haircut_sharpe_bhy": haircut,
        "adjusted_p_bhy": adjusted_p,
        "min_backtest_length_years": min_btl,
        "sample_years": years,
    }
    if not np.isfinite(dsr) or dsr < ctx.thresholds.fail_dsr:
        return GateResult(
            4,
            "multiple-testing deflation",
            FAIL,
            f"DSR = {dsr:.2f} over {n_trials} trials: the best of this search is what noise would give",
            stats,
        )
    if haircut <= 0:
        return GateResult(4, "multiple-testing deflation", FAIL, "the Harvey-Liu haircut removes the entire Sharpe", stats)
    if math.isfinite(min_btl) and min_btl > years:
        return GateResult(
            4,
            "multiple-testing deflation",
            WARN,
            f"{n_trials} trials need {min_btl:.1f} years to mean anything; the sample is {years:.1f}",
            stats,
        )
    if dsr < ctx.thresholds.min_dsr:
        return GateResult(4, "multiple-testing deflation", WARN, f"DSR = {dsr:.2f}", stats)
    return GateResult(
        4, "multiple-testing deflation", PASS, f"DSR = {dsr:.3f} over {n_trials} trials, haircut Sharpe {haircut:.2f}", stats
    )


def gate_5_selection(ctx: GateContext) -> GateResult:
    """PBO over the whole variant matrix, plus IS/OOS degradation."""
    if ctx.sweep is None or len(ctx.sweep) < 2:
        return GateResult(
            5,
            "selection overfitting",
            SKIP,
            "only one variant was run, so nothing was selected; PBO does not apply",
        )
    matrix = ctx.sweep.returns
    result = cscv(matrix, n_blocks=16)
    degradation = is_oos_degradation(matrix)
    stats = {**result.summary(), "is_oos_rank_correlation": degradation.attrs["rank_correlation"]}
    verdict = result.verdict(
        ctx.thresholds.fail_pbo, ctx.thresholds.max_pbo, ctx.thresholds.max_prob_oos_loss
    )
    detail = f"PBO = {result.pbo:.2f} over {result.n_splits} splits of {len(ctx.sweep)} variants"
    if verdict == FAIL:
        detail += (
            f"; the in-sample winner loses out of sample {result.prob_oos_loss:.0%} of the time"
        )
    elif verdict == WARN and result.pbo > ctx.thresholds.max_pbo:
        detail += (
            f"; selection is arbitrary but stays profitable out of sample "
            f"({result.prob_oos_loss:.0%} losing) — the variants are interchangeable"
        )
    return GateResult(5, "selection overfitting", verdict, detail, stats)


def gate_6_permutation(ctx: GateContext) -> GateResult:
    """Masters bar permutation, and a random-entry percentile."""
    from qr.strategies.library import RandomEntry

    observed = ctx.result.sharpe(gross=True)
    evaluate = lambda p: run_backtest(p, ctx.strategy, ctx.costs, ctx.universe).sharpe(gross=True)
    permutation = bar_permutation_test(
        ctx.panel, evaluate, observed, n_permutations=ctx.permutations, seed=ctx.seed
    )

    time_in_market = ctx.result.stats()["time_in_market"]
    n_held = max(1, int(round(len(ctx.panel.symbols) * time_in_market / 4)))
    random_entry = random_entry_test(
        lambda s: run_backtest(
            ctx.panel, RandomEntry(n_held=n_held, hold=20, seed=s), ctx.costs, ctx.universe
        ).sharpe(gross=True),
        observed,
        n_permutations=min(200, ctx.permutations),
        seed=ctx.seed,
    )
    suite = PermutationSuite([permutation, random_entry])
    stats = {f"{r.name}_{k}": v for r in suite.results for k, v in r.summary().items()}
    verdict = suite.verdict
    detail = (
        f"bar permutation p = {permutation.p_value:.3f} ({permutation.percentile:.0f}th percentile); "
        f"random entry p = {random_entry.p_value:.3f}"
    )
    return GateResult(6, "permutation", verdict, detail, stats)


def gate_7_cross_validation(ctx: GateContext) -> GateResult:
    """A distribution of out-of-sample path Sharpes, and walk-forward efficiency."""
    matrix = ctx.sweep.returns if ctx.sweep is not None else ctx.result.net.to_frame(ctx.strategy.name)
    purge = _lookback_of(ctx.strategy)
    result = combinatorial_purged_cv(
        matrix, ctx.periods_per_year, n_groups=10, k=2, purge=purge, embargo=max(5, purge // 4)
    )
    walk = walk_forward_efficiency(matrix, ctx.periods_per_year, n_windows=6, purge=purge)
    wfe = walk.attrs.get("wfe", float("nan"))
    stats = {**result.summary(), "walk_forward_efficiency": wfe, "purge_bars": float(purge)}

    verdict = result.verdict(ctx.thresholds.min_path_ratio, ctx.thresholds.min_share_positive)
    if verdict == PASS and np.isfinite(wfe) and wfe < ctx.thresholds.min_wfe:
        verdict = WARN
    detail = (
        f"median path Sharpe {result.median_path:.2f} = {result.ratio_to_is:.0%} of in-sample; "
        f"{result.share_positive:.0%} of {len(result.path_sharpes)} paths positive; WFE {wfe:.2f}"
    )
    return GateResult(7, "cross-validated OOS", verdict, detail, stats)


def gate_8_robustness(ctx: GateContext) -> GateResult:
    """Parameter plateau, trade count, per-year profitability, factor alpha."""
    stats: dict[str, Any] = {}
    problems: list[str] = []
    warnings: list[str] = []
    net = ctx.result.net.dropna()
    result_stats = ctx.result.stats()

    n_params = len([k for k, v in ctx.strategy.params.items() if v is not None])
    stats["free_parameters"] = float(n_params)
    if n_params > ctx.thresholds.max_free_params:
        problems.append(f"{n_params} free parameters (limit {ctx.thresholds.max_free_params})")

    round_trips = result_stats["round_trips"]
    stats["round_trips"] = round_trips
    if round_trips < ctx.thresholds.min_round_trips:
        problems.append(f"only {round_trips:.0f} round trips")

    if ctx.sweep is not None and len(ctx.sweep) > 1:
        retention = neighbourhood_retention(ctx.sweep, ctx.strategy.name)
        stats.update({f"neighbourhood_{k}": v for k, v in retention.items() if k != "variant"})
        median = retention.get("retention", float("nan"))
        if np.isfinite(median) and median < ctx.thresholds.min_neighbour_retention:
            problems.append(f"neighbours keep only {median:.0%} of the peak Sharpe (a spike, not a plateau)")

    by_year = net.groupby(net.index.year).sum()
    profitable = float((by_year > 0).mean()) if len(by_year) else float("nan")
    stats["years"] = float(len(by_year))
    stats["share_profitable_years"] = profitable
    if np.isfinite(profitable) and profitable < ctx.thresholds.min_profitable_years:
        problems.append(f"profitable in only {profitable:.0%} of years")

    # Drop the best year and the best five bars: does anything remain?
    if len(by_year) > 1:
        without_best_year = net[net.index.year != by_year.idxmax()]
        stats["sharpe_without_best_year"] = st.annualised_sharpe(without_best_year, ctx.periods_per_year)
        if stats["sharpe_without_best_year"] <= 0:
            problems.append("the entire result is one year")
    trimmed = net.drop(net.nlargest(5).index)
    stats["sharpe_without_best_5_bars"] = st.annualised_sharpe(trimmed, ctx.periods_per_year)
    if stats["sharpe_without_best_5_bars"] <= 0:
        problems.append("the entire result is five bars")

    try:
        decomposition = decompose(net, factor_table(ctx.panel), ctx.periods_per_year)
        stats.update(decomposition.summary())
        if decomposition.verdict() == FAIL:
            problems.append(
                f"alpha t = {decomposition.alpha_tstat:.2f} against "
                f"beta {decomposition.betas.get(decomposition.dominant_factor, float('nan')):.2f} "
                f"to {decomposition.dominant_factor}: this is the market, not the strategy"
            )
        elif decomposition.verdict() == WARN:
            warnings.append(f"alpha t = {decomposition.alpha_tstat:.2f}")
    except ValueError as exc:
        warnings.append(f"factor decomposition unavailable ({exc})")

    if problems:
        return GateResult(8, "robustness and regime", FAIL, "; ".join(problems), stats)
    if warnings:
        return GateResult(8, "robustness and regime", WARN, "; ".join(warnings), stats)
    return GateResult(
        8,
        "robustness and regime",
        PASS,
        f"{n_params} parameters, {round_trips:.0f} round trips, profitable in {profitable:.0%} of years",
        stats,
    )


def gate_9_holdout(ctx: GateContext) -> GateResult:
    """The untouched period, opened exactly once."""
    if ctx.holdout_panel is None:
        return GateResult(9, "true holdout", SKIP, "no holdout period supplied")
    if ctx.trial_log is not None:
        opened = ctx.trial_log.records(kind="holdout", hypothesis_id=ctx.hypothesis_id)
        if opened:
            return GateResult(
                9,
                "true holdout",
                FAIL,
                f"the holdout was already opened on {opened[0].ts[:19]}; it is not a holdout any more",
                {"first_opened": opened[0].ts},
            )

    holdout = run_backtest(ctx.holdout_panel, ctx.strategy, ctx.costs, ctx.holdout_universe)
    in_sample = ctx.result.sharpe()
    out_sample = holdout.sharpe()
    ratio = out_sample / in_sample if np.isfinite(in_sample) and in_sample > 0 else float("nan")
    stats = {
        "holdout_sharpe": out_sample,
        "in_sample_sharpe": in_sample,
        "holdout_over_in_sample": ratio,
        "holdout_bars": float(len(holdout.net)),
        "holdout_max_drawdown": holdout.stats()["max_drawdown"],
    }
    if ctx.trial_log is not None:
        ctx.trial_log.append("holdout", ctx.hypothesis_id, {"stats": stats, "strategy": ctx.strategy.describe()})

    if not np.isfinite(out_sample) or out_sample <= 0:
        return GateResult(9, "true holdout", FAIL, f"holdout Sharpe {out_sample:.2f}", stats)
    if not np.isfinite(ratio) or ratio < ctx.thresholds.min_holdout_ratio:
        return GateResult(9, "true holdout", WARN, f"holdout keeps only {ratio:.0%} of in-sample Sharpe", stats)
    return GateResult(9, "true holdout", PASS, f"holdout Sharpe {out_sample:.2f} ({ratio:.0%} of in-sample)", stats)


GATES: list[Callable[[GateContext], GateResult]] = [
    gate_0_preregistration,
    gate_1_data_integrity,
    gate_2_cost_survival,
    gate_3_significance,
    gate_4_deflation,
    gate_5_selection,
    gate_6_permutation,
    gate_7_cross_validation,
    gate_8_robustness,
    gate_9_holdout,
]


def _lookback_of(strategy: Strategy) -> int:
    """The longest lookback a strategy uses — how far purging has to reach."""
    lookback_keys = {"hold", "skip"}
    numeric = [
        int(v)
        for k, v in strategy.params.items()
        if isinstance(v, (int, float))
        and not isinstance(v, bool)
        and ("lookback" in k or k in lookback_keys)
    ]
    return max(numeric) if numeric else 0


@dataclass
class GateReport:
    """The eleven-row table, as far as it got."""

    hypothesis_id: str
    results: list[GateResult]
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        verdicts = [r.verdict for r in self.results]
        if FAIL in verdicts:
            return FAIL
        return WARN if WARN in verdicts else PASS

    @property
    def stopped_at(self) -> GateResult | None:
        return next((r for r in self.results if r.verdict == FAIL), None)

    @property
    def warnings(self) -> list[GateResult]:
        return [r for r in self.results if r.verdict == WARN]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([r.row() for r in self.results])


def run_gates(
    ctx: GateContext,
    upto: int = 9,
    stop_on_fail: bool = True,
    skip: Sequence[int] = (),
) -> GateReport:
    """Run the gates in order, stopping at the first FAIL.

    `stop_on_fail=False` runs them all anyway, which is useful when writing a
    report on a strategy you already know fails — seeing *how far* it gets and
    what the later gates say is often more informative than the first failure.
    It is not the mode a decision should be made in.
    """
    results: list[GateResult] = []
    for gate in GATES:
        number = int(gate.__name__.split("_")[1])
        if number > upto:
            break
        if number in skip:
            continue
        result = gate(ctx)
        results.append(result)
        if ctx.trial_log is not None:
            ctx.trial_log.gate(ctx.hypothesis_id, result.number, result.name, result.verdict, result.stats)
        if result.blocking and stop_on_fail:
            break
    return GateReport(
        ctx.hypothesis_id,
        results,
        {
            "strategy": ctx.strategy.describe(),
            "costs": ctx.costs.describe(),
            "trials": ctx.trial_count,
            "manifest_hash": ctx.manifest_hash,
            "symbols": ctx.panel.symbols,
            "start": str(ctx.panel.index[0]) if len(ctx.panel) else None,
            "end": str(ctx.panel.index[-1]) if len(ctx.panel) else None,
            "thresholds": ctx.thresholds.__dict__,
        },
    )
