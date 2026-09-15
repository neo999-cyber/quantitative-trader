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
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from qr.config import REPO_ROOT
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
from qr.validate.permutation import (
    PermutationSuite,
    bar_permutation_test,
    random_entry_test,
    shuffled_ticker_test,
)
from qr.data.sandbox import sandbox_side
from qr.validate.spa import buy_and_hold_benchmark, cash_benchmark, superior_predictive_ability
from qr.portfolio import sizing
from qr.validate import forward
from qr.validate.trial_log import TrialLog, content_hash

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"


@dataclass(frozen=True)
class GateThresholds:
    """Every number a verdict turns on. Changing one is a visible decision."""

    # gate 1. A daily strategy earning a gross Sharpe above 8 over years of
    # data has a bug, not an edge; the shape test only warns, because a genuine
    # short-horizon reversal produces the same shape as a leak.
    implausible_sharpe: float = 8.0
    #: How far lag 1 may stand above its neighbours, in standard errors of a
    #: Sharpe over the sample. Three is the usual "not noise" line, and this
    #: replaces a ratio that divided by a Sharpe which could be zero — see
    #: `leakage_probe` and `docs/07_ENGINE_FIXES.md` §5.
    max_spike_z: float = 3.0
    max_spike_ratio: float = 1.50
    # Above this, reassigning the weights to random symbols does about as
    # well: the symbol selection carries nothing.
    max_placebo_p: float = 0.50
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
    # SPA is conservative with many correlated models, so only an emphatic
    # p fails: above one half the benchmark beats the best of the search
    # more often than not.
    fail_spa_p: float = 0.50
    # gate 6
    max_permutation_p: float = 0.05
    fail_permutation_p: float = 0.10
    # gate 7
    min_path_ratio: float = 0.50
    min_share_positive: float = 0.90
    min_wfe: float = 0.50
    # gate 8
    #: How much of the net return the factor set must explain before a low
    #: alpha can be called market exposure. Below this the factors account for
    #: nothing and the honest reading is that there is no return to explain.
    min_factor_r2: float = 0.25
    min_neighbour_retention: float = 0.70
    max_free_params: int = 5
    min_round_trips: int = 50
    min_profitable_years: float = 2 / 3
    # gate 9
    min_holdout_ratio: float = 0.50
    # gate 11. The four caps in `SizingPolicy`, and the floor below which a
    # position is too small for the venue to be worth the trouble.
    min_leverage: float = 0.05
    # gate 10. Three months of daily bars. Short enough that incubation is a
    # decision rather than a career, long enough that a dead strategy shows it.
    min_forward_observations: int = 63
    #: Forward Sharpe as a fraction of in-sample. Below this the edge is gone;
    #: between this and `warn_forward_ratio` it is worth another month.
    min_forward_ratio: float = 0.50
    warn_forward_ratio: float = 0.70
    #: Realised cost over modelled cost. Gate 2 decided every family this
    #: project has run, so a cost model that is a third light in the real
    #: world means gate 2 was scoring a fiction.
    max_cost_ratio: float = 1.30
    #: Worst single-bar disagreement between the live book and the researched
    #: book, as a fraction of gross exposure. This is a wiring check, so the
    #: tolerance is for rounding to whole shares, not for judgement.
    max_weight_error: float = 0.02


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
    #: The live paper record, if this hypothesis is in incubation. Gate 10
    #: reads it; nothing else does.
    forward_log: TrialLog | None = None
    holdout_universe: pd.DataFrame | None = None
    raw_frames: dict[str, pd.DataFrame] | None = None
    thresholds: GateThresholds = field(default_factory=GateThresholds)
    permutations: int = 200
    bootstrap_reps: int = 2000
    spa_reps: int = 1000
    #: How many variants gate 6 re-optimises over on each permuted dataset.
    reoptimise_variants: int = 25
    #: Permutations for gate 6's second, volatility-preserving null. `None`
    #: means "the same as `permutations`"; 0 skips it, which halves gate 6's
    #: cost at the price of the diagnostic.
    vol_preserving_permutations: int | None = None
    #: Account size the cost model prices orders against. Only a venue charging
    #: per order rather than per dollar cares, but for one it decides the
    #: verdict: at $1,000 an ETF basket leg costs 42 bps, at $100,000 it costs
    #: 0.42. A gate that re-runs a backtest must use the same account the sweep
    #: did or it is pricing a different strategy.
    equity: float | None = None
    #: The market's calendar, for gate 1's gap check. "continuous" for crypto,
    #: "xnys" for anything listed in New York — an exchange series measured
    #: against a 365-day calendar reports one "gap" for every weekend it ever
    #: had.
    calendar: str = "continuous"
    #: What gate 5 asks the best variant to beat, once the search is paid for.
    #: "buyhold" — equal-weight the same universe, costed with the same model
    #: — is the right null for a long-only spot book: the question is whether
    #: timing adds anything to owning the coins. It is the wrong null for a
    #: book that is dollar-neutral, beta-neutral or a carry trade, because
    #: such a book is not a subset of the market's exposure and a rising
    #: market is not what it claims to beat. "cash" compounds `risk_free`
    #: per bar instead. Programme 1 ran nine families against "buyhold"; the
    #: construction guaranteed the answer (`docs/20_PROGRAMME_2.md`, §1).
    #: The choice is part of the pre-registration, not a knob to turn after
    #: seeing which comparator a family beats.
    benchmark: str = "buyhold"
    #: The annualised **decimal** risk-free rate the "cash" benchmark
    #: compounds at: one number, or a dated series (FRED DTB3 via
    #: `qr data riskfree-pull`). None means zero, which is the pessimistic
    #: direction for the strategy only when rates are negative.
    risk_free: "pd.Series | float | None" = None
    seed: int = 0

    @property
    def backtest_kwargs(self) -> dict[str, float]:
        return {"equity": self.equity} if self.equity else {}

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
    # The sandbox is where looking is free, and the price of that freedom is
    # that nothing found there counts. A gate report computed on discovery data
    # is not a weak result, it is a category error, and it fails here rather
    # than three gates later so that no part of the run can be mistaken for
    # evidence. See `qr/data/sandbox.py`.
    if sandbox_side(ctx.panel) == "discovery":
        return GateResult(
            0,
            "pre-registration",
            FAIL,
            "this panel is the discovery sandbox; nothing computed on it is reportable. "
            "Re-run the candidate against the validation side.",
            {"sandbox_side": "discovery"},
        )
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
    runs = ctx.trial_log.records(kind="run", hypothesis_id=ctx.hypothesis_id)
    first_run = next(iter(runs), None)
    latest = records[-1]
    stats = {
        "doc_sha256": latest.payload.get("doc_sha256"),
        "registered_at": records[0].ts,
        "registrations": len(records),
        "source": latest.payload.get("source"),
    }
    if first_run is not None and first_run.seq < records[0].seq:
        return GateResult(
            0,
            "pre-registration",
            FAIL,
            "the first run predates the pre-registration: the hypothesis was written after seeing results",
            stats,
        )

    # A document re-registered *after* a run is an amendment made with results
    # in hand. Amending before anything has been run is legitimate — a defect
    # in the universe found during setup has to be fixable — so the test is
    # ordering, not count.
    if first_run is not None and any(r.seq > first_run.seq for r in records):
        return GateResult(
            0,
            "pre-registration",
            FAIL,
            "the hypothesis was re-registered after a run: an amendment made with results in hand",
            stats,
        )

    # The hash is only worth stamping if it is checked. A document edited after
    # registration still satisfies "a pre-registration exists" and no longer
    # describes what was predicted.
    source = latest.payload.get("source")
    if source and source != "inline":
        path = Path(source)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.exists():
            stats["doc_missing"] = str(path)
            return GateResult(
                0, "pre-registration", WARN, f"registered document {source} is no longer on disk", stats
            )
        if content_hash(path.read_text(encoding="utf-8")) != latest.payload.get("doc_sha256"):
            return GateResult(
                0,
                "pre-registration",
                FAIL,
                f"{source} has been edited since it was registered: its hash no longer matches",
                stats,
            )
        stats["doc_verified"] = True

    return GateResult(0, "pre-registration", PASS, f"registered {records[0].ts[:19]}", stats)


def gate_1_data_integrity(ctx: GateContext) -> GateResult:
    """QA on the bars, plus the one-switch leakage probe."""
    stats: dict[str, Any] = {}
    detail_parts: list[str] = []
    verdict = PASS

    # QA runs on the symbols the strategy actually **held** — the only ones
    # whose bars entered the result. A universe of 734 real pairs always
    # contains a few with impossible prints somewhere in their history, and
    # failing a top-30 book because a delisted microcap it never touched had a
    # negative volume in 2022 would make gate 1 noise; noise gets ignored.
    # The universe-wide audit is `qr data qa`, which is a separate job.
    #
    # It is also scored only over the bars the strategy was allowed to read.
    # `Panel.tradable()` already withholds bars whose values cannot be true, so
    # failing the strategy for those is the platform objecting to data it had
    # itself refused to serve. The first real four-family run stopped all four
    # here for exactly that reason, on AUDUSDT and BTTUSDT, over six bars
    # nothing had traded. The raw count survives as `qa_failures_on_raw_bars`:
    # the corruption does not vanish, it stops being the strategy's fault.
    frames = ctx.raw_frames if ctx.raw_frames is not None else _panel_frames(ctx)
    if frames:
        excluded = _excluded_bars(ctx)
        raw = [
            check_klines(f, s, ctx.panel.interval, calendar=ctx.calendar)
            for s, f in sorted(frames.items())
        ]
        reports = [r.excluding(excluded.get(r.symbol, pd.DatetimeIndex([], tz="UTC"))) for r in raw]
        failed = {r.symbol for r in reports if r.verdict == FAIL}
        warned = {r.symbol for r in reports if r.verdict == WARN}
        traded = _traded_symbols(ctx)
        blocking = sorted(failed & traded)

        stats["qa_failures"] = len(failed)
        stats["qa_warnings"] = len(warned)
        stats["qa_failures_traded"] = len(blocking)
        stats["qa_failed_symbols"] = sorted(failed)[:20]
        stats["qa_failures_on_raw_bars"] = len({r.symbol for r in raw if r.verdict == FAIL})
        stats["qa_bars_excluded"] = int(sum(len(v) for v in excluded.values()))

        if blocking:
            return GateResult(
                1,
                "data integrity",
                FAIL,
                f"QA failed for {', '.join(blocking[:5])}, which this strategy holds",
                stats,
            )
        if warned & traded:
            verdict = WARN if verdict == PASS else verdict
            detail_parts.append(f"{len(warned & traded)} held symbols with QA warnings")

    probe = leakage_probe(ctx.panel, ctx.strategy, ctx.costs, ctx.universe)
    honest = float(probe.loc[1, "gross_sharpe"])
    spike = probe.attrs.get("spike_ratio", float("nan"))
    spike_z = probe.attrs.get("spike_z", float("nan"))
    stats.update(
        {
            "lag0_gross_sharpe": float(probe.loc[0, "gross_sharpe"]),
            "lag1_gross_sharpe": honest,
            "lag2_gross_sharpe": float(probe.loc[2, "gross_sharpe"]),
            "peek_ratio": probe.attrs.get("peek_ratio", float("nan")),
            "spike_ratio": spike,
            "spike_z": spike_z,
            "sharpe_standard_error": probe.attrs.get("sharpe_standard_error", float("nan")),
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
    # The shuffled-ticker placebo: keep every bar's weights, attach them to the
    # wrong coins. A strategy that genuinely selects symbols collapses; one that
    # is market timing in cross-sectional clothing does not, because which coin
    # it held never mattered. Reported always, because the answer is a fact
    # about what the strategy *is* — for a timing family a high p is expected
    # and needs a note, not a fix.
    placebo = _shuffled_ticker(ctx)
    if placebo is not None:
        stats.update({f"placebo_{k}": v for k, v in placebo.summary().items()})
        if placebo.p_value > ctx.thresholds.max_placebo_p:
            verdict = WARN if verdict == PASS else verdict
            detail_parts.append(
                f"shuffled-ticker placebo p = {placebo.p_value:.2f}: attaching these weights to "
                f"random symbols does about as well, so the symbol selection carries little — "
                f"expected for a timing strategy, damning for a cross-sectional one"
            )

    # Decided on `spike_z`, the gap in standard errors, not on the ratio: a
    # ratio of two Sharpes that are both noise is itself noise, and it accused
    # the trial's control family of a look-ahead it does not have.
    if np.isfinite(spike_z) and spike_z > ctx.thresholds.max_spike_z:
        verdict = WARN
        detail_parts.append(
            f"Sharpe peaks at the reported lag, {spike_z:.1f} standard errors above its "
            f"neighbours: either a genuinely one-bar-ahead signal or a look-ahead — "
            f"say which in the trial log"
        )
    elif np.isfinite(spike_z):
        detail_parts.append(f"no lag spike ({spike_z:+.1f} standard errors over its neighbours)")
    else:
        detail_parts.append("lag profile not measurable")
    return GateResult(1, "data integrity", verdict, "; ".join(detail_parts) or "clean", stats)


def _cost_attribution(result) -> dict[str, float]:
    """Each cost's share of the total drag over the whole run."""
    parts = getattr(result, "cost_parts", None)
    if parts is None or parts.empty:
        return {}
    totals = parts.sum()
    grand = float(totals.sum())
    if not np.isfinite(grand) or grand <= 0:
        return {}
    return {name: float(value) / grand for name, value in totals.items()}


def _dominant_cost(attribution: dict[str, float]) -> str:
    """Which of the four it mostly was, when one of them clearly dominates.

    A verdict of "costs eat 62% of gross return" is a dead end; the same
    sentence with "almost all of it the per-order commission" is a direction,
    and it is a different direction from "almost all of it borrow". Silent
    unless one component is most of the bill, because naming a 40/35/25 split
    would be picking a winner out of noise.
    """
    if not attribution:
        return ""
    name, share = max(attribution.items(), key=lambda kv: kv[1])
    if share < 0.6:
        return ""
    wording = {
        "commission": "the per-order commission",
        "spread": "the spread",
        "impact": "market impact",
        "borrow": "the borrow fee on the short leg",
    }.get(name, name)
    return f" — {share:.0%} of it {wording}"


def gate_2_cost_survival(ctx: GateContext) -> GateResult:
    """Does the edge survive its own costs, and twice them?"""
    result = ctx.result
    ratio = result.stats()["net_over_gross"]
    stressed = run_backtest(
        ctx.panel,
        ctx.strategy,
        ctx.costs.stressed(ctx.thresholds.cost_stress),
        ctx.universe,
        **ctx.backtest_kwargs,
    )
    stressed_sharpe = stressed.sharpe()
    capacity = _capacity(ctx)
    attribution = _cost_attribution(result)
    stats = {
        **capacity,
        **{f"cost_share_{k}": v for k, v in attribution.items()},
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
    blame = _dominant_cost(attribution)
    if ratio < ctx.thresholds.fail_net_over_gross:
        return GateResult(
            2, "cost survival", FAIL, f"costs eat {1 - ratio:.0%} of gross return{blame}", stats
        )
    if stressed_sharpe <= 0:
        return GateResult(2, "cost survival", FAIL, f"negative at {ctx.thresholds.cost_stress:g}x costs", stats)
    if ratio < ctx.thresholds.min_net_over_gross:
        return GateResult(
            2,
            "cost survival",
            WARN,
            f"only {ratio:.0%} of gross return survives costs{blame}",
            stats,
        )
    detail = f"{ratio:.0%} of gross survives; Sharpe {stressed_sharpe:.2f} at {ctx.thresholds.cost_stress:g}x costs"
    ceiling = capacity.get("capacity_usd")
    if ceiling and np.isfinite(ceiling):
        detail += f"; capacity about ${ceiling:,.0f} before impact takes a further 10% of gross"
    return GateResult(2, "cost survival", PASS, detail, stats)


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
    raw_trials = ctx.trial_count
    n_trials = raw_trials
    effective = raw_trials

    # The effective trial count is **reported, not used**, and that is a
    # deliberate reversal. `PLAN.md` §4 asks for deflation against an effective
    # count from clustering, and the estimator below does measure it correctly
    # (200 TSMOM variants have an effective rank near 5, because their return
    # series correlate above 0.95). But feeding it to the DSR double-discounts
    # the correlation: E[max] = sqrt(V) * f(N) already shrinks through **V**,
    # the variance of the trial Sharpes, which is itself small precisely when
    # the variants are redundant. Discounting N as well let the searched-over
    # noise world through gate 4 in the self-test — the exact failure this
    # whole apparatus exists to prevent. So DSR takes the raw count, and the
    # effective count stays in the report as the diagnostic it should have
    # been: a large gap between the two says the grid is finer than the search.
    if ctx.sweep is not None and len(ctx.sweep) >= 2:
        effective, _ = st.effective_trials(ctx.sweep.returns)

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
    # MinBTL on the RAW count: it asks how much data a search of that breadth
    # needs, and a fine grid really is a broad search however correlated it is.
    min_btl = st.min_backtest_length(raw_trials, max(annual_sharpe, 0.25))
    years = len(net) / ctx.periods_per_year

    stats = {
        "trials": float(n_trials),
        "trials_raw": float(raw_trials),
        "trials_effective": float(effective),
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
            f"DSR = {dsr:.2f} over {n_trials} trials (effective rank {effective}): "
            f"the best of this search is what noise would give",
            stats,
        )
    if haircut <= 0:
        return GateResult(4, "multiple-testing deflation", FAIL, "the Harvey-Liu haircut removes the entire Sharpe", stats)
    if math.isfinite(min_btl) and min_btl > years:
        return GateResult(
            4,
            "multiple-testing deflation",
            WARN,
            f"{raw_trials} trials need {min_btl:.1f} years to mean anything; the sample is {years:.1f}",
            stats,
        )
    if dsr < ctx.thresholds.min_dsr:
        return GateResult(4, "multiple-testing deflation", WARN, f"DSR = {dsr:.2f}", stats)
    return GateResult(
        4,
        "multiple-testing deflation",
        PASS,
        f"DSR = {dsr:.3f} over {n_trials} trials (effective rank {effective}), "
        f"haircut Sharpe {haircut:.2f}",
        stats,
    )


BENCHMARKS = ("buyhold", "cash")


def benchmark_series(ctx: GateContext) -> pd.Series:
    """The comparator gate 5 tests against, chosen by `ctx.benchmark`.

    Both are costed or compounded on the panel's own index so that SPA
    aligns them with the variants without dropping bars.
    """
    if ctx.benchmark == "buyhold":
        return buy_and_hold_benchmark(ctx.panel, ctx.universe, ctx.costs, ctx.equity)
    if ctx.benchmark == "cash":
        return cash_benchmark(ctx.panel.index, ctx.periods_per_year, ctx.risk_free)
    raise ValueError(f"unknown benchmark {ctx.benchmark!r}; known: {', '.join(BENCHMARKS)}")


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

    # PBO and SPA answer different questions and a family can pass one while
    # failing the other. PBO asks whether *selecting* the winner carries
    # information; SPA asks whether the winner beats buy-and-hold at all, once
    # the search is paid for. A family whose variants all merely track the
    # market has a low PBO — the same variant does win every time — and nothing
    # worth trading. Only SPA says so.
    spa_verdict = None
    stats["benchmark"] = ctx.benchmark
    try:
        benchmark = benchmark_series(ctx)
        spa_result = superior_predictive_ability(
            matrix, benchmark, ctx.periods_per_year, reps=ctx.spa_reps, seed=ctx.seed
        )
        stats.update(spa_result.summary())
        spa_verdict = spa_result.verdict(ctx.thresholds.max_spa_p, ctx.thresholds.fail_spa_p)
    except (ValueError, RuntimeError) as exc:
        stats["spa_error"] = str(exc)
    verdict = result.verdict(
        ctx.thresholds.fail_pbo, ctx.thresholds.max_pbo, ctx.thresholds.max_prob_oos_loss
    )
    detail = f"PBO = {result.pbo:.2f} over {result.n_splits} splits of {len(ctx.sweep)} variants"
    if spa_verdict is None and "spa_error" in stats:
        # Half the gate did not run. PBO alone cannot pass a family: a set of
        # variants that never took a position has a PBO of zero — the same
        # variant "wins" every split — and no return to speak of. Found by
        # the Programme 2 control (a flat book against cash) on 2026-09-15;
        # before this, the report read PASS with the error tucked in stats.
        never_traded = "non-zero variance" in stats["spa_error"]
        verdict = FAIL if never_traded else (WARN if verdict == PASS else verdict)
        detail += (
            "; SPA could not run — no variant ever took a position"
            if never_traded
            else f"; SPA could not run ({stats['spa_error']}), so this gate cannot pass"
        )
        return GateResult(5, "selection overfitting", verdict, detail, stats)
    if verdict == FAIL:
        detail += (
            f"; the in-sample winner loses out of sample {result.prob_oos_loss:.0%} of the time"
        )
    elif verdict == WARN and result.pbo > ctx.thresholds.max_pbo:
        detail += (
            f"; selection is arbitrary but stays profitable out of sample "
            f"({result.prob_oos_loss:.0%} losing) — the variants are interchangeable"
        )

    if spa_verdict is not None:
        p = stats["spa_p_consistent"]
        against = "cash" if ctx.benchmark == "cash" else "buy-and-hold"
        detail += f"; SPA p = {p:.3f} vs {against}"
        if spa_verdict == FAIL:
            verdict = FAIL
            detail += (
                " — no variant beats simply holding cash"
                if ctx.benchmark == "cash"
                else " — no variant beats simply holding the universe"
            )
        elif spa_verdict == WARN and verdict == PASS:
            verdict = WARN
        survivors = int(stats.get("stepm_survivors", 0))
        if survivors:
            detail += f" ({survivors} variant(s) survive Romano–Wolf StepM)"
    return GateResult(5, "selection overfitting", verdict, detail, stats)


def gate_6_permutation(ctx: GateContext) -> GateResult:
    """Masters bar permutation **with re-optimisation**, and two cheaper nulls.

    The re-optimisation is what makes this the strongest test in the pipeline.
    Re-running only the chosen variant on permuted data asks "is this variant
    better than chance"; re-running the **whole search** and keeping its best
    asks "is my *procedure* better than chance", which is the question, because
    the procedure is what produced the variant.

    At full grid size that is variants x permutations backtests, so the search
    is re-run over an evenly spread subgrid of at most
    `ctx.reoptimise_variants`. The direction of that approximation is stated in
    the report: a subgrid null is **weaker** than the full-grid null and
    **stronger** than no re-optimisation, so the p-value it produces is
    optimistic relative to a complete Masters test and conservative relative to
    the naive one.

    **Two nulls, one verdict.** Masters' permutation destroys volatility
    clustering along with the time ordering, and a vol-targeted strategy earns
    a Sharpe premium from clustering with no directional skill whatever. The
    observed statistic contains that premium; the null has been stripped of it.
    So for these families gate 6's number is "no timing edge" and "vol
    targeting behaves differently without clustering" added together. A second
    null keeps each bar's volatility in place and permutes only the
    standardised residual, which separates them.

    On six synthetic worlds with clustering and no timing edge the two nulls
    disagree by about 0.2 in p, **in neither direction consistently** — three
    seeds each way. That is not a bias to correct for; it is a sensitivity
    wider than the gap between this gate's own pass band (0.05) and fail band
    (0.10), which is worth knowing about a verdict.

    The **plain Masters null remains the binding one**, deliberately. It is
    what the pre-registrations name, and swapping a decision rule for a kinder
    one after seeing the answer is the exact move pre-registration exists to
    stop, however good the reasoning. The second null is reported as evidence
    and is there to be pre-registered by whatever runs next.
    """
    from qr.strategies.library import RandomEntry

    if ctx.sweep is not None and len(ctx.sweep) > 1 and ctx.sweep.strategy_class is not None:
        names = ctx.sweep.subgrid(ctx.reoptimise_variants)
        grid = ctx.sweep.rebuild(names)
    else:
        grid = [ctx.strategy]

    def best_over_grid(panel: Panel) -> float:
        scores = [run_backtest(panel, s, ctx.costs, ctx.universe, **ctx.backtest_kwargs).sharpe(gross=True)
            for s in grid]
        finite = [s for s in scores if np.isfinite(s)]
        return max(finite) if finite else float("nan")

    # The observed statistic must be the same statistic as the null: the best
    # over this grid on the real data, not the Sharpe of the chosen variant.
    observed = best_over_grid(ctx.panel) if len(grid) > 1 else ctx.result.sharpe(gross=True)
    permutation = bar_permutation_test(
        ctx.panel, best_over_grid, observed, n_permutations=ctx.permutations, seed=ctx.seed
    )

    time_in_market = ctx.result.stats()["time_in_market"]
    n_held = max(1, int(round(len(ctx.panel.symbols) * time_in_market / 4)))
    random_entry = random_entry_test(
        lambda s: run_backtest(
            ctx.panel,
            RandomEntry(n_held=n_held, hold=20, seed=s),
            ctx.costs,
            ctx.universe,
            **ctx.backtest_kwargs,
        ).sharpe(gross=True),
        observed,
        n_permutations=min(200, ctx.permutations),
        seed=ctx.seed,
    )
    suite = PermutationSuite([permutation, random_entry])
    stats = {f"{r.name}_{k}": v for r in suite.results for k, v in r.summary().items()}
    stats["reoptimised_over"] = float(len(grid))
    stats["grid_size"] = float(len(ctx.sweep)) if ctx.sweep is not None else 1.0

    # Binding verdict: the pre-registered nulls only.
    verdicts = {
        r.verdict(ctx.thresholds.max_permutation_p, ctx.thresholds.fail_permutation_p)
        for r in suite.results
    }
    verdict = FAIL if FAIL in verdicts else (WARN if WARN in verdicts else PASS)
    reopt = (
        f"re-optimised over {len(grid)} of {len(ctx.sweep)} variants"
        if ctx.sweep is not None and len(grid) > 1
        else "single variant, no re-optimisation"
    )
    detail = (
        f"bar permutation p = {permutation.p_value:.3f} ({permutation.percentile:.0f}th percentile, "
        f"{reopt}); random entry p = {random_entry.p_value:.3f}"
    )

    n_vol = ctx.permutations if ctx.vol_preserving_permutations is None else ctx.vol_preserving_permutations
    if n_vol:
        vol_null = bar_permutation_test(
            ctx.panel,
            best_over_grid,
            observed,
            n_permutations=n_vol,
            seed=ctx.seed + 100_000,
            preserve_volatility=True,
        )
        stats.update({f"{vol_null.name}_{k}": v for k, v in vol_null.summary().items()})
        stats["vol_preserved_verdict"] = vol_null.verdict(
            ctx.thresholds.max_permutation_p, ctx.thresholds.fail_permutation_p
        )
        detail += (
            f"; volatility-preserving null p = {vol_null.p_value:.3f} "
            f"({vol_null.percentile:.0f}th percentile, reported, not binding)"
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
    stats = {
        **result.summary(),
        "walk_forward_efficiency": wfe,
        "walk_forward_efficiency_pooled": walk.attrs.get("wfe_pooled", float("nan")),
        "walk_forward_windows": float(walk.attrs.get("wfe_windows", 0)),
        "purge_bars": float(purge),
    }

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

    # "Free" means *searched over*, not "present in the constructor". A vol
    # target held fixed at 0.20 across every variant is a policy choice and
    # costs no degrees of freedom; a lookback swept over forty values costs
    # one. Counting constructor arguments would fail every strategy with a
    # couple of fixed implementation knobs and let a two-argument strategy
    # swept over ten thousand combinations through.
    n_params = _free_parameters(ctx)
    stats["free_parameters"] = float(n_params)
    stats["constructor_parameters"] = float(len([v for v in ctx.strategy.params.values() if v is not None]))
    if n_params > ctx.thresholds.max_free_params:
        problems.append(f"{n_params} swept parameters (limit {ctx.thresholds.max_free_params})")

    round_trips = result_stats["round_trips"]
    stats["round_trips"] = round_trips
    if round_trips == 0:
        return GateResult(
            8,
            "robustness and regime",
            FAIL,
            "the strategy never took a position: its entry condition did not fire once",
            stats,
        )
    if round_trips < ctx.thresholds.min_round_trips:
        problems.append(f"only {round_trips:.0f} round trips")

    if ctx.sweep is not None and len(ctx.sweep) > 1:
        retention = neighbourhood_retention(ctx.sweep, ctx.strategy.name)
        stats.update({f"neighbourhood_{k}": v for k, v in retention.items() if k != "variant"})
        median = retention.get("retention", float("nan"))
        if np.isfinite(median) and median < ctx.thresholds.min_neighbour_retention:
            problems.append(f"neighbours keep only {median:.0%} of the peak Sharpe (a spike, not a plateau)")
        elif not np.isfinite(median) and retention.get("n_neighbours"):
            # A `nan` here means the peak is too close to zero to divide by, so
            # the plateau test could not run. Skipping it silently is how a
            # missing check gets read as a passed one, which is the failure
            # mode this whole pipeline exists to prevent.
            warnings.append(
                f"parameter plateau not measurable: peak Sharpe "
                f"{retention.get('peak_sharpe', float('nan')):.2f} is within noise of zero"
            )

    by_year = net.groupby(net.index.year).sum()
    profitable = float((by_year > 0).mean()) if len(by_year) else float("nan")
    stats["years"] = float(len(by_year))
    stats["share_profitable_years"] = profitable
    if np.isfinite(profitable) and profitable < ctx.thresholds.min_profitable_years:
        problems.append(f"profitable in only {profitable:.0%} of years")

    # Drop the best year and the best five trades: does anything remain?
    if len(by_year) > 1:
        without_best_year = net[net.index.year != by_year.idxmax()]
        stats["sharpe_without_best_year"] = st.annualised_sharpe(without_best_year, ctx.periods_per_year)
        if stats["sharpe_without_best_year"] <= 0:
            problems.append("the entire result is one year")

    # Trades, not bars. Dropping the five best *bars* removes five days, which
    # a strategy holding for weeks barely notices; dropping the five best
    # *holding episodes* removes the positions that actually made the money.
    # The distinction is the whole point of the check.
    trimmed = _drop_best_trades(net, ctx.result.held, ctx.panel.returns(), n=5)
    stats["sharpe_without_best_5_trades"] = st.annualised_sharpe(trimmed, ctx.periods_per_year)
    stats["sharpe_without_best_5_bars"] = st.annualised_sharpe(
        net.drop(net.nlargest(5).index), ctx.periods_per_year
    )
    if stats["sharpe_without_best_5_trades"] <= 0:
        problems.append("the entire result is five trades")

    # Per-regime Sharpe, by trailing realised volatility of the book's own
    # universe. A strategy that only works in one volatility regime is a bet on
    # that regime, and crypto supplies all three within any two-year window.
    regimes = _regime_sharpes(net, ctx.panel, ctx.periods_per_year)
    stats.update({f"sharpe_in_{name}_vol": value for name, value in regimes.items()})
    losing = [name for name, value in regimes.items() if np.isfinite(value) and value <= 0]
    if len(losing) >= 2:
        problems.append(f"loses money in {' and '.join(losing)} volatility regimes")
    elif losing:
        warnings.append(f"negative in the {losing[0]}-volatility regime")

    try:
        decomposition = decompose(net, factor_table(ctx.panel), ctx.periods_per_year)
        stats.update(decomposition.summary())
        if decomposition.verdict() == FAIL:
            # Two different failures wear the same alpha t-statistic, and until
            # the first dollar-neutral family ran they were never told apart:
            # "this is the market, not the strategy" was printed against a beta
            # of 0.98 and against a beta of -0.06 alike. The second is a false
            # statement — a book with no market exposure cannot be the market —
            # and a sentence that fires either way carries no information.
            #
            # R-squared decides it rather than a beta threshold, because the
            # question is how much of the return the factors account for, and
            # that is what R-squared measures. Below a quarter, they do not
            # account for it: there is no alpha, and no beta to blame either.
            beta = decomposition.betas.get(decomposition.dominant_factor, float("nan"))
            explained = decomposition.r_squared
            if np.isfinite(explained) and explained >= ctx.thresholds.min_factor_r2:
                reading = "this is the market, not the strategy"
            else:
                reading = (
                    f"the factors explain only {max(explained, 0.0):.0%} of it, so this is "
                    f"neutral around nothing rather than market exposure"
                )
            problems.append(
                f"alpha t = {decomposition.alpha_tstat:.2f} against "
                f"beta {beta:.2f} to {decomposition.dominant_factor}: {reading}"
            )
        elif decomposition.verdict() == WARN:
            warnings.append(f"alpha t = {decomposition.alpha_tstat:.2f}")
    except ValueError as exc:
        warnings.append(f"factor decomposition unavailable ({exc})")

    if problems:
        # Warnings ride along with a FAIL rather than being dropped. A gate that
        # failed for one reason was silently discarding everything else it had
        # found, including "this check could not run at all" — and a check
        # nobody is told about is indistinguishable from one that passed.
        detail = "; ".join(problems + [f"(also: {w})" for w in warnings])
        return GateResult(8, "robustness and regime", FAIL, detail, stats)
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

    holdout = run_backtest(
        ctx.holdout_panel, ctx.strategy, ctx.costs, ctx.holdout_universe, **ctx.backtest_kwargs
    )
    in_sample = ctx.result.sharpe()
    out_sample = holdout.sharpe()
    ratio = out_sample / in_sample if np.isfinite(in_sample) and in_sample > 0 else float("nan")
    stats = {
        "holdout_sharpe": out_sample,
        "in_sample_sharpe": in_sample,
        "holdout_over_in_sample": ratio,
        "holdout_bars": float(len(holdout.net)),
        "holdout_max_drawdown": holdout.stats()["max_drawdown"],
        # Gate 11 sizes on this. A Sharpe without the volatility behind it
        # cannot be turned into a position.
        "holdout_volatility": float(holdout.net.std(ddof=1) * np.sqrt(ctx.periods_per_year)),
    }
    if ctx.trial_log is not None:
        ctx.trial_log.append("holdout", ctx.hypothesis_id, {"stats": stats, "strategy": ctx.strategy.describe()})

    if not np.isfinite(out_sample) or out_sample <= 0:
        return GateResult(9, "true holdout", FAIL, f"holdout Sharpe {out_sample:.2f}", stats)
    if not np.isfinite(ratio) or ratio < ctx.thresholds.min_holdout_ratio:
        return GateResult(9, "true holdout", WARN, f"holdout keeps only {ratio:.0%} of in-sample Sharpe", stats)
    return GateResult(9, "true holdout", PASS, f"holdout Sharpe {out_sample:.2f} ({ratio:.0%} of in-sample)", stats)


def gate_10_forward(ctx: GateContext) -> GateResult:
    """Incubation: the only gate that looks at bars nobody had.

    It runs three checks in a deliberate order — wiring, then cost, then
    decay — because they fail for different reasons and only the last one is
    about the strategy. A book that never matched the research is a defect
    and more incubation does not fix it; a cost model that was optimistic
    invalidates gate 2 for every family, not just this one.

    The decay check is last and is the weakest of the three. Sixty-three
    observations cannot establish that a Sharpe is real, and this gate never
    claims they can: a PASS here says the record is *consistent with* the
    research, which is the strongest thing three months can say.
    """
    log = ctx.forward_log if ctx.forward_log is not None else ctx.trial_log
    if log is None:
        return GateResult(10, "incubation", SKIP, "no forward record supplied")

    records = forward.frame(log, ctx.hypothesis_id)
    summary = forward.summarise(records, ctx.periods_per_year)
    stats = summary.as_dict()
    need = ctx.thresholds.min_forward_observations

    if summary.observations == 0:
        return GateResult(10, "incubation", SKIP, "not yet incubating", stats)
    if summary.observations < need:
        return GateResult(
            10,
            "incubation",
            SKIP,
            f"incubating: {summary.observations} of {need} observations "
            f"since {summary.first}",
            stats,
        )

    # 1. Wiring. Did the live system hold the book the research asked for?
    if summary.checked_bars == 0:
        wiring = WARN, "no bar carried an expected book, so nothing checked the wiring"
    elif summary.checked_bars < summary.observations:
        wiring = WARN, (
            f"only {summary.checked_bars} of {summary.observations} bars carried "
            "an expected book"
        )
    else:
        wiring = None
    if np.isfinite(summary.max_weight_error) and summary.max_weight_error > ctx.thresholds.max_weight_error:
        return GateResult(
            10,
            "incubation",
            FAIL,
            f"the live book diverged from the researched book by "
            f"{summary.max_weight_error:.1%} of gross on its worst bar; this is a "
            f"wiring defect, not a decay, and incubating longer will not fix it",
            stats,
        )

    # 2. Cost. Was the model that decided gate 2 telling the truth?
    if np.isfinite(summary.cost_ratio) and summary.cost_ratio > ctx.thresholds.max_cost_ratio:
        return GateResult(
            10,
            "incubation",
            FAIL,
            f"trading cost {summary.cost_ratio:.2f}x what the cost model predicted "
            f"({summary.realised_cost:.4f} against {summary.expected_cost:.4f}); "
            f"gate 2 scored this family on a cost that does not exist",
            stats,
        )

    # 3. Decay. The weak check, and the one everybody means.
    in_sample = ctx.result.sharpe()
    stats["in_sample_sharpe"] = in_sample
    ratio = (
        summary.net_sharpe / in_sample
        if np.isfinite(in_sample) and in_sample > 0 and np.isfinite(summary.net_sharpe)
        else float("nan")
    )
    stats["forward_over_in_sample"] = ratio
    window = f"{summary.observations} observations, {summary.first} to {summary.last}"

    if not np.isfinite(summary.net_sharpe) or summary.net_sharpe <= 0:
        return GateResult(
            10,
            "incubation",
            FAIL,
            f"forward Sharpe {summary.net_sharpe:.2f} over {window}",
            stats,
        )
    if not np.isfinite(ratio):
        return GateResult(
            10,
            "incubation",
            WARN,
            f"forward Sharpe {summary.net_sharpe:.2f} over {window}, with no "
            "positive in-sample Sharpe to compare it against",
            stats,
        )
    if ratio < ctx.thresholds.min_forward_ratio:
        return GateResult(
            10,
            "incubation",
            FAIL,
            f"forward keeps {ratio:.0%} of in-sample Sharpe over {window}",
            stats,
        )
    if ratio < ctx.thresholds.warn_forward_ratio:
        return GateResult(
            10,
            "incubation",
            WARN,
            f"forward keeps {ratio:.0%} of in-sample Sharpe over {window}; "
            "worth another month before it is believed",
            stats,
        )

    detail = (
        f"forward Sharpe {summary.net_sharpe:.2f} ({ratio:.0%} of in-sample) over "
        f"{window}; consistent with the research, which is the strongest claim "
        f"{summary.observations} observations can support"
    )
    if wiring is not None:
        return GateResult(10, "incubation", wiring[0], f"{detail} — but {wiring[1]}", stats)
    return GateResult(10, "incubation", PASS, detail, stats)


def gate_11_sizing(ctx: GateContext) -> GateResult:
    """How much money — and the refusal to answer from the in-sample Sharpe.

    The Sharpe this gate sizes on must come from data the strategy was not
    fitted to: the forward record if it is incubating, otherwise the holdout
    that gate 9 opened. There is no fallback to the in-sample number. A
    strategy that has not reached gate 9 does not get a size, because the only
    Sharpe available for it is the one the search maximised, and sizing off
    that is how a real edge still ends in a blown account.
    """
    sharpe = volatility = float("nan")
    basis = ""

    log = ctx.forward_log if ctx.forward_log is not None else ctx.trial_log
    if log is not None:
        records = forward.frame(log, ctx.hypothesis_id)
        if len(records) >= ctx.thresholds.min_forward_observations:
            summary = forward.summarise(records, ctx.periods_per_year)
            net = records["net_return"].astype(float).dropna()
            sharpe = summary.net_sharpe
            volatility = float(net.std(ddof=1) * np.sqrt(ctx.periods_per_year))
            basis = f"the forward record ({summary.observations} observations)"

    if not np.isfinite(sharpe) and ctx.trial_log is not None:
        opened = ctx.trial_log.records(kind="holdout", hypothesis_id=ctx.hypothesis_id)
        if opened:
            stats9 = opened[-1].payload.get("stats", {})
            sharpe = float(stats9.get("holdout_sharpe", float("nan")))
            volatility = float(stats9.get("holdout_volatility", float("nan")))
            basis = "the holdout"

    if not np.isfinite(sharpe) or not np.isfinite(volatility):
        return GateResult(
            11,
            "sizing",
            SKIP,
            "no out-of-sample Sharpe to size from; this gate will not size off "
            "the in-sample number",
            {},
        )

    held = ctx.result.held
    max_weight = float(held.abs().max().max()) if held.size else 1.0
    plan = sizing.size(sharpe, volatility, max_weight=max_weight, equity=ctx.equity)
    stats = {**plan.as_dict(), "sizing_basis": basis, "max_single_weight": max_weight}

    if plan.leverage <= 0:
        return GateResult(11, "sizing", FAIL,
                          f"{basis} gives Sharpe {sharpe:.2f}; there is nothing to size", stats)

    money = f", ${plan.notional:,.0f} on ${ctx.equity:,.0f}" if ctx.equity else ""
    detail = (
        f"{plan.leverage:.2f}x from {basis}{money}; the {plan.binding.replace('_', ' ')} "
        f"cap binds, and P(ever {int(sizing.SizingPolicy().loss_from_launch * 100)}% below "
        f"launch equity) is {plan.prob_ever_below_launch:.1%}"
    )
    if plan.leverage < ctx.thresholds.min_leverage:
        return GateResult(11, "sizing", WARN, f"{detail} — too small to be worth trading", stats)
    if plan.notes:
        return GateResult(11, "sizing", PASS, f"{detail}; {plan.notes[0]}", stats)
    return GateResult(11, "sizing", PASS, detail, stats)


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
    gate_10_forward,
    gate_11_sizing,
]


def _traded_symbols(ctx: GateContext) -> set[str]:
    """Symbols the strategy actually held at any point."""
    held = ctx.result.held
    return {str(c) for c in held.columns[(held.abs() > 1e-12).any(axis=0)]}


def _panel_frames(ctx: GateContext) -> dict[str, pd.DataFrame]:
    """Per-symbol OHLCV frames reconstructed from the panel.

    So gate 1's QA check cannot be skipped by a caller forgetting to pass
    `raw_frames` — which is exactly what happened: the field existed, gate 1
    read it, and no pipeline ever set it, so the check never ran on real data
    at all. Each symbol's rows are trimmed back to its own listing window,
    because the panel's outer join pads every pair with NaN and those pads are
    not gaps in that pair's history.
    """
    if not _traded_symbols(ctx):
        return {}
    frames: dict[str, pd.DataFrame] = {}
    for symbol in _traded_symbols(ctx):
        columns = {name: ctx.panel[name][symbol] for name in ctx.panel.fields}
        frame = pd.DataFrame(columns)
        frames[symbol] = frame[frame["close"].notna()]
    return frames


def _excluded_bars(ctx: GateContext) -> dict[str, pd.DatetimeIndex]:
    """Per symbol, the bars the panel refused to make tradable.

    Only bars the symbol actually has: a NaN pad outside a pair's listing
    window is untradable too, but it is not a bar and `_panel_frames` has
    already trimmed it away.
    """
    tradable = ctx.panel.tradable()
    present = ctx.panel.close.notna()
    blocked = present & ~tradable
    return {
        str(symbol): pd.DatetimeIndex(blocked.index[blocked[symbol].to_numpy()])
        for symbol in blocked.columns
        if bool(blocked[symbol].any())
    }


def _capacity(ctx: GateContext, give_up_fraction: float = 0.10) -> dict[str, float]:
    """Roughly how much money this strategy can take before impact bites.

    Square-root impact means the drag grows with the square root of
    participation, so doubling size costs about 1.41x the impact per dollar.
    This walks the equity up until impact has eaten `give_up_fraction` of gross
    return and reports where that happens.

    **Read the number as one significant figure and as a statement about the
    cost model, not about Binance.** It inherits `impact_coef`, which is 1.0
    because that is the round number the literature clusters around, not
    because anything here was calibrated against fills — this account has never
    sent an order. Two strategies' capacities are comparable to each other, and
    the direction of the ordering is informative; the absolute level carries
    the coefficient's uncertainty, which is at least a factor of two either way.

    The first trial run made the case for saying so out loud: it reported
    $10,000 for a top-30 book against pairs trading nine figures a day, because
    the √-law was being extrapolated a thousandfold below the participations it
    is fitted over and was charging basis points of "impact" for orders smaller
    than the spread. `CostModel.net_impact_against_spread` fixes that
    double-count. It does not fix the coefficient, so the answer is reported
    with the band that halving and doubling it produces — which is the honest
    width — and with `capacity_extrapolated`, which says whether the book is
    even operating inside the range the √-law was fitted over. At this
    account's size it will not be, and the right reading of the whole figure is
    then "impact is not the binding constraint", not a dollar amount.
    """
    from qr.research.runner import volume_adv

    gross_annual = ctx.result.gross.mean() * ctx.periods_per_year
    adv = volume_adv(ctx.panel)
    if adv is None or not np.isfinite(gross_annual) or gross_annual <= 0:
        return {}
    turnover = (ctx.result.held - ctx.result.held.shift(1)).abs().fillna(0.0)
    volatility = ctx.panel.returns().rolling(30, min_periods=5).std()
    adv_aligned = adv.reindex_like(turnover)
    vol_aligned = volatility.reindex_like(turnover)

    def annual_drag(equity: float) -> float:
        impact = ctx.costs.impact_bps(turnover * equity, adv_aligned, vol_aligned)
        drag = (turnover * pd.DataFrame(impact, index=turnover.index, columns=turnover.columns)).sum(axis=1)
        return float(drag.mean() * ctx.periods_per_year * 1e-4)

    budget = give_up_fraction * gross_annual
    ladder = (1e3, 1e4, 3e4, 1e5, 3e5, 1e6, 3e6, 1e7, 3e7, 1e8, 3e8, 1e9)
    # 0.0 means "below the smallest size probed", which is a real answer for a
    # strategy trading illiquid names. Returning NaN there reads as "unknown"
    # and would let a capacity problem pass as a missing measurement.
    capacity = 0.0
    drags: dict[str, float] = {}
    for equity in ladder:
        drag = annual_drag(equity)
        drags[f"impact_drag_at_{equity:.0e}"] = drag
        if drag > budget:
            break
        capacity = equity

    # The same walk under a coefficient twice and half the assumed one. The
    # band is wide on purpose: it is the width of what is actually known.
    def capacity_at(coef: float) -> float:
        model = replace(ctx.costs, impact_coef=coef)
        found = 0.0
        for equity in ladder:
            impact = model.impact_bps(turnover * equity, adv_aligned, vol_aligned)
            frame = pd.DataFrame(impact, index=turnover.index, columns=turnover.columns)
            if float((turnover * frame).sum(axis=1).mean() * ctx.periods_per_year * 1e-4) > budget:
                break
            found = equity
        return found

    # The median participation the book runs at the capacity figure, which is
    # the one number that says whether the impact model is being used inside
    # its calibration range or extrapolated below it.
    traded = turnover * max(capacity, ladder[0])
    with np.errstate(divide="ignore", invalid="ignore"):
        participation = (traded / adv_aligned).where(turnover > 0)
    values = participation.to_numpy(dtype=float).ravel()
    values = values[np.isfinite(values) & (values > 0)]
    median_participation = float(np.median(values)) if len(values) else float("nan")
    return {
        "capacity_usd": capacity,
        "capacity_usd_pessimistic": capacity_at(ctx.costs.impact_coef * 2.0),
        "capacity_usd_optimistic": capacity_at(ctx.costs.impact_coef * 0.5),
        "gross_annual_return": gross_annual,
        "impact_budget_annual": budget,
        "impact_coef": float(ctx.costs.impact_coef),
        "median_participation_at_capacity": median_participation,
        # True means the book never reaches the participations the square-root
        # law was fitted over, so the capacity figure is an extrapolation.
        "capacity_extrapolated": bool(np.isfinite(median_participation) and median_participation < 1e-3),
        **drags,
    }


def _shuffled_ticker(ctx: GateContext, n_permutations: int = 100):
    """Gate 1's placebo, scored on gross returns so costs cannot muddy it."""
    returns = ctx.panel.returns().fillna(0.0)
    ppy = ctx.periods_per_year

    def score(weights: pd.DataFrame) -> float:
        series = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)
        sd = series.std(ddof=1)
        return float(series.mean() / sd * math.sqrt(ppy)) if sd > 0 else 0.0

    weights = ctx.result.weights
    if weights.shape[1] < 2 or not (weights.abs().to_numpy() > 0).any():
        return None
    return shuffled_ticker_test(score, weights, score(weights), n_permutations, ctx.seed)


def _drop_best_trades(net: pd.Series, held: pd.DataFrame, returns: pd.DataFrame, n: int = 5) -> pd.Series:
    """`net` with the contribution of its `n` most profitable trades removed.

    A **trade** is a contiguous holding of *one symbol*, which is what a trader
    means by the word and what `round_trips` already counts. A portfolio-level
    definition is useless here: a vol-targeted book is invested almost every
    bar, so the whole sample is one "episode" and removing the best five
    removes the strategy.

    The contribution is subtracted from the affected bars rather than the bars
    being deleted, so the series keeps its length and its autocorrelation
    structure — deleting bars would flatter the Sharpe by shortening the sample
    as well as removing the winners.
    """
    live = held.abs() > 1e-12
    if not live.to_numpy().any():
        return net
    pnl = (held * returns.reindex_like(held).fillna(0.0)).fillna(0.0)
    starts = live & ~live.shift(1, fill_value=False)
    trade_id = starts.cumsum().where(live)

    totals: list[tuple[float, str, float]] = []
    for symbol in held.columns:
        ids = trade_id[symbol].dropna()
        if ids.empty:
            continue
        for identifier, value in pnl[symbol].groupby(ids).sum().items():
            totals.append((float(value), symbol, float(identifier)))
    if not totals:
        return net
    best = sorted(totals, reverse=True)[:n]

    mask = pd.DataFrame(False, index=held.index, columns=held.columns)
    for _, symbol, identifier in best:
        mask[symbol] |= trade_id[symbol] == identifier
    return net - pnl.where(mask, 0.0).sum(axis=1)


def _regime_sharpes(net: pd.Series, panel: Panel, periods_per_year: float, lookback: int = 60) -> dict[str, float]:
    """Sharpe within each trailing-volatility tercile of the universe.

    Terciles of a trailing cross-sectional volatility estimate, computed from
    the panel rather than from the strategy's own returns — using the
    strategy's own volatility would sort bars by how much the strategy was
    doing, not by what the market was doing.
    """
    market = panel.returns().mean(axis=1, skipna=True)
    trailing = market.rolling(lookback, min_periods=lookback // 2).std().reindex(net.index)
    usable = trailing.dropna()
    if len(usable) < 3 * lookback:
        return {}
    low, high = usable.quantile([1 / 3, 2 / 3])
    buckets = {
        "low": net[trailing <= low],
        "mid": net[(trailing > low) & (trailing <= high)],
        "high": net[trailing > high],
    }
    return {
        name: st.annualised_sharpe(values, periods_per_year) if len(values) > 30 else float("nan")
        for name, values in buckets.items()
    }


def _free_parameters(ctx: GateContext) -> int:
    """How many parameters the search actually varied.

    From the sweep when there is one — the honest source, since it is the
    record of what was tried. Without a sweep there is nothing to measure, so
    it falls back to counting the strategy's own non-None parameters, which
    over-counts and is the safe direction to be wrong in.
    """
    if ctx.sweep is not None and len(ctx.sweep) > 1:
        frame = ctx.sweep.param_frame()
        return int(sum(frame[column].astype(str).nunique() > 1 for column in frame.columns))
    return len([v for v in ctx.strategy.params.values() if v is not None])


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
    progress: Callable[[str], None] | None = None,
) -> GateReport:
    """Run the gates in order, stopping at the first FAIL.

    `stop_on_fail=False` runs them all anyway, which is useful when writing a
    report on a strategy you already know fails — seeing *how far* it gets and
    what the later gates say is often more informative than the first failure.
    It is not the mode a decision should be made in.

    `progress` is called with a line before each gate starts and another when it
    finishes. That exists because gate 6 re-optimises a 25-variant subgrid over
    100 permuted panels of 734 symbols, which is tens of minutes of complete
    silence, and silence is indistinguishable from a hang — a real run was
    killed on the suspicion. A gate that announces itself before it begins costs
    nothing and answers the question.
    """
    results: list[GateResult] = []
    for gate in GATES:
        number = int(gate.__name__.split("_")[1])
        if number > upto:
            break
        if number in skip:
            continue
        label = " ".join(gate.__name__.split("_")[2:])
        if progress is not None:
            progress(f"  gate {number} {label}…")
        started = time.perf_counter()
        result = gate(ctx)
        if progress is not None:
            progress(f"  gate {number} {result.name}: {result.verdict} ({time.perf_counter() - started:.0f}s)")
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
            "sandbox_side": sandbox_side(ctx.panel),
            "start": str(ctx.panel.index[0]) if len(ctx.panel) else None,
            "end": str(ctx.panel.index[-1]) if len(ctx.panel) else None,
            "thresholds": ctx.thresholds.__dict__,
        },
    )
