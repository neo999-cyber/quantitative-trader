# Statistical rigor for trading-hypothesis testing: methods, thresholds, and Python libraries (as of Sept 2026)

## 0. The core problem in one paragraph

A backtest Sharpe ratio is a *sample statistic selected from a search*. Three things inflate it: (a) sampling noise (a true-zero strategy can show SR≈1 over a few years), (b) selection under multiple testing (you keep the best of N variants, and the expected maximum of N noise draws grows like √(2 ln N)), and (c) non-normality/serial dependence that make the naive SR standard error wrong. Everything below is machinery for deflating (a)–(c), plus separate gates for the non-statistical ways a backtest lies (leakage, survivorship, costs). Bailey, Borwein, López de Prado & Zhu's "Pseudo-Mathematics and Financial Charlatanism" ([AMS Notices 2014](https://www.ams.org/notices/201405/rnoti-p458.pdf)) is the canonical statement: with only 5 years of daily data, trying more than ~45 independent configurations virtually guarantees an in-sample SR≈1 with expected out-of-sample SR≈0.

---

## 1. Multiple testing and backtest overfitting

### 1.1 Harvey, Liu & Zhu — "...and the Cross-Section of Expected Returns" (t > 3)
[SSRN 2249314](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314). **Plain language:** hundreds of "factors" have been tested on the same US equity data; under Bonferroni/Holm/BHY corrections for that family, the hurdle for a new claim is t ≈ 3.0, not 2.0. For your own platform the family is *your* trial log, but 3.0 is the practitioner default because your own count is always an under-count. Companions: Harvey & Liu "Evaluating Trading Strategies" ([SSRN 2474755](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2474755)); "Lucky Factors" ([SSRN 2528780](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2528780)); "False (and Missed) Discoveries in Financial Economics" ([SSRN 3073799](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3073799)). Implementation: `statsmodels.stats.multitest.multipletests(method='holm' | 'fdr_bh' | 'fdr_by')`.

### 1.2 Harvey & Liu — "Backtesting" (haircut Sharpe ratio)
[SSRN 2345489](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345489); code at [people.duke.edu/~charvey/backtesting](https://people.duke.edu/~charvey/backtesting/); R port [`SharpeRatio.haircut`](https://rdrr.io/github/braverock/quantstrat/man/SharpeRatio.haircut.html). **Plain language:** convert the backtest SR to a p-value (given T), apply Bonferroni / Holm / BHY for N trials, convert back to an SR. The haircut is *nonlinear*: SR 0.4 might be cut to ~0, SR 2.5 only ~25%. Inputs: SR, sample length, frequency, N trials, average correlation among trials (~0.2–0.4 for related variants).

### 1.3 Bailey & López de Prado — Deflated Sharpe Ratio (DSR) and Probabilistic Sharpe Ratio (PSR)
- PSR / MinTRL: "The Sharpe Ratio Efficient Frontier" ([SSRN 1821643](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643)).
- DSR: ([SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551), [PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)).
- 2025–26 updates: López de Prado, Lipton & Zoonekynd "How to Use the Sharpe Ratio" ([SSRN 5520741](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5520741), code [zoonek/2025-sharpe-ratio](https://github.com/zoonek/2025-sharpe-ratio)) — closed-form SR sampling distribution under non-normal *and* autocorrelated returns; López de Prado & Porcu "The Deflated Sharpe Ratio: A Unified Framework" ([SSRN 7198158](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7198158)).

**Plain language.** PSR(SR*) = Φ[ (SR − SR*)·√(T−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²) ] — the probability the true SR exceeds SR*, penalising negative skew and fat tails. DSR is PSR with SR* replaced by the *expected maximum* SR among N trials with variance V of trial SRs: E[max] ≈ √V·[(1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(N·e))], γ = 0.5772. N must be the *effective* number of independent trials — cluster correlated trials and use the number of clusters.
**Minimum Track Record Length:** MinTRL = 1 + [1 − γ₃SR + (γ₄−1)/4·SR²]·(z_α/(SR−SR*))². Gaussian, SR*=0, 95%: years ≈ (1.645/SR_annual)² → SR 0.5 ⇒ ~10.8 yrs; SR 1.0 ⇒ ~2.7 yrs; SR 1.5 ⇒ ~1.2 yrs; SR 2.0 ⇒ ~0.7 yr (double for 99%).
**Post-selection shrinkage (2026):** Pav, "Post Selection Estimation of Sharpe Ratios" ([arXiv 2606.01650](https://arxiv.org/abs/2606.01650)) — James–Stein shrinkage as a point-estimate companion to DSR.

### 1.4 Probability of Backtest Overfitting (PBO) via CSCV; Minimum Backtest Length
"The Probability of Backtest Overfitting" ([SSRN 2326253](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253)). **Plain language (CSCV):** take the T×N matrix of returns for all N variants; split T into S blocks (S=16 ⇒ 12,870 combinations); for each combination, pick the in-sample best variant and record its out-of-sample *rank*; PBO = fraction of combinations where the IS-best is below median OOS. Also yields IS-vs-OOS degradation slope. **Use:** whenever you optimise over a grid. **MinBTL:** ≈ 2·ln(N)/E[max SR]² years; with 5 years of data, at most ~45 independent configurations before expected OOS SR ≈ 0 at IS SR 1.

### 1.5 Data-snooping tests: White's Reality Check, Hansen's SPA, Romano–Wolf StepM
- White ([Econometrica 2000](https://onlinelibrary.wiley.com/doi/abs/10.1111/1468-0262.00152)): bootstrap the *max* of relative performance over all models vs a benchmark.
- Hansen SPA ([SSRN 264569](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569)): studentised, re-centred; less sensitive to irrelevant alternatives.
- Romano & Wolf StepM ([Econometrica 2005](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1468-0262.2005.00615.x)): returns the *set* of models that beat the benchmark while controlling FWER.
- Model Confidence Set (Hansen–Lunde–Nason): the set of models statistically indistinguishable from the best.
All three are in `arch` (`arch.bootstrap.SPA`, `StepM`, `MCS`) — [docs](https://bashtage.github.io/arch/multiple-comparison/multiple-comparison_examples.html). `block_size` from `optimal_block_length` (Politis–White).

**Practitioner numbers:** t ≥ 3 (HLZ); haircut SR > 0 at 5% under Holm/BHY; DSR ≥ 0.95; PBO < 0.10 pass, 0.10–0.20 warn; SPA/StepM consistent p < 0.05; T ≥ MinTRL and MinBTL.

---

## 2. Cross-validation for time series and the AFML toolkit

### 2.1 Why `TimeSeriesSplit` / plain K-fold fail
Labels built from forward windows overlap; a test observation's label shares price path with adjacent training labels ⇒ leakage. A 2026 benchmark, "When Alpha Disappears: A One-Switch Benchmark for Decision-Time Leakage" ([arXiv 2605.23959](https://arxiv.org/pdf/2605.23959)), shows a single decision-timing switch (signal known at close vs. tradeable at next open) can flip results; "Spurious Predictability in Financial Machine Learning" ([arXiv 2604.15531](https://arxiv.org/pdf/2604.15531)) quantifies how much apparent ML predictability is artefact.

### 2.2 Walk-forward, purged K-fold, embargo, CPCV
- **Walk-forward (Pardo)**: optimise on window, apply unchanged to the next, roll. *Walk-forward efficiency* (annualised OOS return ÷ annualised IS return) ≥ 50–60% is the usual pass. Weakness: a single path.
- **Purged K-fold + embargo** (AFML ch. 7): drop training samples whose label windows overlap the test fold; add an embargo (≈1% of T).
- **Combinatorial Purged CV (CPCV)** (AFML ch. 12): N groups, k test groups ⇒ C(N,k) splits that tile into φ full backtest paths; report the *distribution* of path Sharpes.
- **Evidence:** Arian, Norouzi & Seco, "Backtest overfitting in the machine learning era" (KBS 2024; [SSRN 4778909](https://www.ssrn.com/abstract=4778909)) — CPCV had the lowest PBO and best DSR; walk-forward was the worst at false-discovery prevention.

### 2.3 AFML toolkit — what each piece is for
- **Triple-barrier labels**: which of {profit-take, stop, time-out} is hit first; path-aware, volatility-scaled.
- **Meta-labeling**: primary model gives side; secondary model predicts P(primary is right) ⇒ bet sizing / filtering.
- **Fractional differentiation**: stationarity while preserving memory.
- **Feature importance MDI / MDA / SFI / Clustered FI** ([SSRN 3517595](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3517595)).
- **Bet sizing**: size ∝ 2·Φ(z) − 1.
- **Effective number of trials**: cluster strategy return series (ONC) → number of clusters = N for DSR.

### 2.4 Library status for this block (GitHub API, 11 Sept 2026)
| Library | Status | Notes |
|---|---|---|
| [hudson-and-thames/mlfinlab](https://github.com/hudson-and-thames/mlfinlab) | 4,923 stars, last push 2023-10-02, license "Other" | **Not open source.** "All rights reserved licence", Business/Enterprise tiers. Old open snapshots survive in unmaintained forks ([quantopian/mlfinlab](https://github.com/quantopian/mlfinlab), [jmrichardson/mlfinlab](https://github.com/jmrichardson/mlfinlab)) — reference code, not dependencies. |
| [skfolio/skfolio](https://github.com/skfolio/skfolio) | 2,376★, BSD-3, pushed 2026-09-09 | `skfolio.model_selection`: `WalkForward`, `CombinatorialPurgedCV`, `MultipleRandomizedCV`, `cross_val_predict`, `optimal_folds_number`. Best-maintained open CPCV today. |
| [eslazarev/purged-cross-validation](https://github.com/eslazarev/purged-cross-validation) (`pip install purgedcv`) | 32★, MIT, created 2026-05, JOSS paper | sklearn-compatible `PurgedKFold`, embargo, `CombinatorialPurgedCV`, `WalkForwardSplit`; stats: PSR, DSR, PBO, MinTRL. Young but exactly the AFML CV surface with a permissive license. |
| [tschm/jsharpe](https://github.com/tschm/jsharpe) (`pip install jsharpe`) | 22★, MIT, pushed 2026-09-08 | PSR, MinTRL, SR variance under non-Gaussian returns, autocorrelation handling, FDR/FWER screening. |
| [esvhd/pypbo](https://github.com/esvhd/pypbo) | 140★, **AGPL-3.0**, pushed 2026-07-06 | `pbo.pbo(rtns_df, S=16, ...)`; also PSR, DSR, MinTRL, MinBTL, stochastic dominance. AGPL matters if the platform is ever distributed. |

---

## 3. Significance of a single strategy

| Method | What it does | When | Source | Implementation |
|---|---|---|---|---|
| **HAC (Newey–West) t-test** | Regress returns on a constant with HAC covariance | Always, first pass | Newey–West 1987 | `sm.OLS(r, np.ones(T)).fit(cov_type='HAC', cov_kwds={'maxlags': L})`; L≈floor(4(T/100)^{2/9}) |
| **Lo (2002) SR standard error** | SE(SR) ≈ √((1+SR²/2)/T) iid; corrected annualisation under serial correlation | Reporting SR with error bars | [FAJ 2002](https://www.tandfonline.com/doi/abs/10.2469/faj.v58.n4.2453) | jsharpe; quantstats `smart_sharpe` |
| **Ledoit–Wolf robust SR test** | Studentised stationary-bootstrap CI for SR under fat tails and dependence | Comparing two strategies | [JEF 2008](http://www.ledoit.net/jef2008_abstract.htm) | [majkee15/RobustSharpeRatioHAC](https://github.com/majkee15/RobustSharpeRatioHAC) or `arch.bootstrap.StationaryBootstrap` |
| **Block / stationary bootstrap of SR** | Resample blocks so autocorrelation survives | CIs; drawdown distributions | Politis & Romano 1994; Politis & White 2004 | `arch.bootstrap.StationaryBootstrap`, `optimal_block_length`; [tsbootstrap](https://github.com/astrogilda/tsbootstrap) (95★, MIT) |
| **Monte Carlo permutation test (Masters)** | Permute *bars* (log-changes), re-run and re-optimise the system on each permutation; p = (#perm ≥ real + 1)/(n+1). Tests "is the pattern real" and estimates training bias | After optimisation; rule-based systems | Masters, *Permutation and Randomization Tests for Trading System Development*; Apress repo [testing-and-tuning-market-trading-systems](https://github.com/Apress/testing-and-tuning-market-trading-systems) (C++: `MCPT_BARS`, `MCPT_TRN`, `CSCV_MKT`, `BOOT_RATIO`) | No authoritative Python port; write yourself (≥1,000 permutations) |
| **Shuffle-signals vs shuffle-returns** | Shuffling the *signal* tests whether timing matters; shuffling *returns* destroys autocorrelation your strategy may legitimately exploit | Signal-based strategies | [Susan Potter 2026](https://www.susanpotter.net/quant/monte-carlo-permutation-tests-strategy-significance/) | numpy |
| **Randomised-entry benchmark** | Many random strategies with the *same* trade count and holding period; your SR must beat the 95th percentile | Discretionary-style entries, exit-rule testing | [Robot Wealth](https://robotwealth.com/benchmarking-backtest-results-against-random-strategies/) | numpy |
| **Trade-level vs bar-level bootstrap** | Trade-level resampling gives drawdown/ruin distributions but *cannot* test edge (SR is permutation-invariant with fixed sizing). Bar-level permutation with re-simulation tests edge. | Trade-level for sizing/risk; bar-level for significance | DaruFinance 2026 ([repo](https://github.com/DaruFinance/Monte-Carlo-paper)): trade-order MC filters added no OOS predictive value | numpy/arch |

---

## 4. Regime and stability

- **Parameter surface (plateau vs spike)**: neighbours (±20–30% in each parameter) must keep ≥ ~70% of performance. Report the *median* of the neighbourhood, not the peak.
- **Sensitivity analysis**: perturb costs ±50%, slippage ×2, start date ±1 year, universe definition; result must not flip sign.
- **Stationarity**: ADF and KPSS together (`statsmodels.tsa.stattools.adfuller`, `kpss`; `arch.unitroot`).
- **Structural breaks**: CUSUM (`statsmodels.stats.diagnostic.breaks_cusumolsresid`); [deepcharles/ruptures](https://github.com/deepcharles/ruptures) (2,080★, BSD-2) — apply to strategy return mean/vol to locate where the edge changed.
- **Hidden Markov regimes**: [hmmlearn](https://github.com/hmmlearn/hmmlearn) (3,422★, last push 2024-10); `statsmodels.tsa.regime_switching`; statistical jump models ([arXiv 2402.05272](https://arxiv.org/pdf/2402.05272)). Report strategy SR *per regime*.
- **Alpha decay**: McLean & Pontiff ([JF 2016](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365)): returns 26% lower out-of-sample, 58% lower post-publication. Chen & Zimmermann ([openassetpricing.com](https://www.openassetpricing.com/)): 98% of clearly-significant predictors replicate, but returns concentrate right after information release. Alpha Architect's review of 215 alt-beta strategies: median 73% SR deterioration live vs backtest ([post](https://alphaarchitect.com/2016/05/beware-of-backtest-overfitting/)). **Practical rule:** plan on live SR ≈ 40–60% of the *deflated* backtest SR.

---

## 5. Cost realism

- **Impact**: square-root law, cost ≈ Y·σ_daily·√(Q/V_daily), Y≈0.5–1 ([Bouchaud](https://bouchaud.substack.com/p/the-square-root-law-of-market-impact); Maitrier & Bouchaud 2026 [SSRN 5287772](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5287772)). Almgren & Chriss for temporary/permanent decomposition.
- **Retail slippage model** (per side): half-spread + fees + impact + latency. Defaults: US large-cap 1–3 bps half-spread, small-cap/illiquid 10–50 bps; crypto majors 1–5 bps spread plus taker fees ~2–10 bps; √-law impact once your order exceeds ~1% of interval volume. Stress-test at 2× baseline. "Implementation Risk in Portfolio Backtesting" ([arXiv 2603.20319](https://arxiv.org/pdf/2603.20319)) quantifies how much *engine choices* alone move results.
- **Borrow**: shorts pay stock-loan fees (hard-to-borrow names tens of % per year) and face recalls — every short-side anomaly must be re-run with a borrow schedule.
- **Crypto perps funding**: paid every 8h (or 1h); a persistent +0.01%/8h is ~11%/yr against longs; sign flips in stress.
- **Survivorship / look-ahead / point-in-time**: use a universe with delisted names and delisting returns; fundamentals as-first-reported; index membership historical. [Potter's taxonomy of backtest lies](https://www.susanpotter.net/quant/backtest-bias-taxonomy/).

---

## 6. Position-sizing math and the 1% rule

- **Kelly**: discrete f* = p − (1−p)/b; continuous f* = μ/σ². Growth at fraction k of Kelly is (2k − k²) of maximum: half-Kelly keeps 75% of growth at half the volatility. Drawdown law: P(wealth ever falls to fraction x) = x^{2/k − 1} ⇒ full Kelly has a 50% chance of a 50% drawdown; half-Kelly 12.5%; quarter-Kelly 0.8%. Thorp ([PDF](https://gwern.net/doc/statistics/decision/2006-thorp.pdf)).
- **The 1% rule** is *fixed-fractional* betting. Map to Kelly with your (OOS, haircut) win rate and payoff: p=0.45, b=1.33 ⇒ f*≈3.6%, so 1% ≈ 0.27·Kelly — roughly quarter-Kelly for a typical system. Its virtue: insensitive to your (overfit) edge estimate; its cost: under-bets strong edges and over-bets zero edges. Correct usage: keep 1% as a *cap*, and let fractional Kelly on deflated statistics decide whether to bet less.
- **Optimal f (Vince)**: fragile (assumes the largest historical loss bounds the future loss). Use only with drawdown constraints.
- **Volatility targeting**: Moreira & Muir ([SSRN 2659431](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431)); Harvey et al. ([Man Group](https://www.man.com/insights/the-impact-of-volatility-targeting)): benefits concentrate in risk assets.
- **Drawdown-constrained Kelly**: Busseti, Ryu & Boyd ([arXiv 1603.06183](https://arxiv.org/abs/1603.06183)): convex program bounding P(drawdown > α) < β; solvable with cvxpy.
- quantstats exposes `kelly_criterion`, `risk_of_ruin`, `probabilistic_sharpe_ratio`, `smart_sharpe`.

---

## 7. Event-study methodology for catalyst hypotheses

- **Canon**: MacKinlay (1997), Brown & Warner (1985), Kothari & Warner ([chapter](https://www.jufinance.com/mag/dba5/event_study_chapter_1_2008_vol_1.pdf)): short-horizon tests are reliable; long-horizon tests are mis-specified and low-powered.
- **Design**: estimation window (e.g. [−250, −30]) → normal-return model → abnormal returns in the event window → aggregate. **CAR** for short windows; **BHAR** for long horizons with matched-firm or calendar-time portfolio benchmarks.
- **Test statistics**: cross-sectional t; Patell; BMP for event-induced variance; Kolari–Pynnönen adjustment when events **cluster in calendar time** (earnings seasons) — or block-bootstrap across event dates.
- **How many events**: with σ_CAR ≈ 4% for a 3-day window: N=50 gives SE≈0.57% (~40% power for a 1% CAR); N=200 gives SE≈0.28% (~94% power); detecting 0.5% at 80% power needs N≈500. Practical floor: ≥100–200 independent events spanning ≥3 years and ≥2 regimes.
- **Domain references**: insider buying — Lakonishok & Lee ([PDF](https://www.lsvasset.com/pdf/research-papers/Insider-Trades-Informative.pdf)): clustered purchases in small firms are informative, sells are not; insider purchases + options ([JCF 2024](https://www.sciencedirect.com/science/article/abs/pii/S0929119924000750)): purchases are only informative when *prior* options volume is low; "Insider filings as trading signals — does it pay to be fast?" ([FRL 2024](https://www.sciencedirect.com/science/article/pii/S1544612324015435)).
- **Python**: [LemaireJean-Baptiste/eventstudy](https://github.com/LemaireJean-Baptiste/eventstudy) (69★, GPL-3.0, 2023); write BMP/Kolari–Pynnönen yourself (short).

---

## 8. Other libraries and toolkits (status verified 11 Sept 2026)

| Library | Stars / license / last push | What it gives you |
|---|---|---|
| [bashtage/arch](https://github.com/bashtage/arch) | 1,562 / NCSA-style / 2026-08-10 | `SPA`, `StepM`, `MCS`, `StationaryBootstrap`, `CircularBlockBootstrap`, `optimal_block_length`; `arch.unitroot`. The single most important dependency for this platform. |
| [statsmodels](https://github.com/statsmodels/statsmodels) | 11,619 / BSD-3 / 2026-09-09 | HAC covariances, `multipletests`, `adfuller`, `kpss`, CUSUM, Markov-switching. |
| [quantstats](https://github.com/ranaroussi/quantstats) | 7,625 / Apache-2.0 / 2026-07-20 | Tear sheets; PSR, `smart_sharpe`, `kelly_criterion`, `risk_of_ruin`. |
| [eyenoticeall/Lacuna](https://github.com/eyenoticeall/Lacuna) (`lacuna-quant`) | 2 / MIT / created 2026-08-25, v0.14 alpha | `SignalStudy(...).audit()` with PASS/WARN/FAIL across leakage, overfitting (PBO/CSCV, PSR/DSR, Reality Check, SPA), fragility, costs. Ambitious, brand-new, single-author — evaluate, don't depend. |
| [quantskills/skill-backtest-overfit](https://github.com/quantskills/skill-backtest-overfit) | 34 / GPL-3.0 / 2026-09-08 | Agent "skill": `overfit_report.py` computing DSR, PBO, purged CV, Harvey–Liu haircut → JSON PASS/FAIL. |
| [holdout-labs/factor-qc](https://github.com/holdout-labs/factor-qc) | 0 / MIT / 2026-09 | "Fail-closed" gate: DSR/PBO/haircut/MinTRL with severity. |
| [rubenbriones/Probabilistic-Sharpe-Ratio](https://github.com/rubenbriones/Probabilistic-Sharpe-Ratio) | 130 / no license / 2020 | Reference notebook implementations of PSR/DSR/MinTRL. |
| Practitioner pages | Quantpedia on Quantopian's IS-vs-OOS study: backtest SR has R² < 0.025 for live SR. Palomar, *Portfolio Optimization* ch. 8.3 ([online](https://portfoliooptimizationbook.com/book/8.3-dangers-backtesting.html)). Unbiased-Alpha checklist: OOS SR ≥ 40–50% of IS, ≤3–5 free parameters, 50–100 trades per parameter, beat the best random strategy. |

---

## 9. The hypothesis-validation pipeline (run on every idea, in this order)

Stop at the first FAIL; a WARN requires an explicit written justification in the trial log.

| # | Gate | Procedure | Pass | Warn / Fail |
|---|---|---|---|---|
| 0 | **Pre-registration** | Write the economic mechanism, predicted sign and magnitude, universe, horizon, parameter *ranges*, cost model, and the OOS period *before* running anything. Append to an immutable trial log (every variant run increments N). | Document exists, hash-stamped | No doc ⇒ exploratory only |
| 1 | **Data integrity** | PIT fundamentals; delisted names included; timestamps aligned to *decision time*; one-switch leakage test (lag the signal by +1 bar: performance should degrade smoothly, not collapse; lead by −1 bar: if SR explodes you have a leak); shuffled-ticker placebo. | All checks clean | Any leak ⇒ FAIL |
| 2 | **Economic sanity & cost survival** | Gross and net (spread + fees + √-law impact + borrow/funding); capacity at intended size. | Net SR ≥ 60% of gross; positive at 2× costs | Net/gross < 50% ⇒ FAIL |
| 3 | **Single-strategy significance** | HAC t-stat; PSR(SR*=0); stationary-bootstrap 95% CI (≥2,000 resamples); T vs MinTRL. | t ≥ 3.0; PSR ≥ 0.95; CI excludes 0; T ≥ MinTRL | 2.5 ≤ t < 3 ⇒ WARN; t < 2.5 ⇒ FAIL |
| 4 | **Multiple-testing deflation** | N_eff = clusters of correlated trials across the trial log; DSR; Harvey–Liu haircut (Holm, BHY); MinBTL. | DSR ≥ 0.95; haircut SR > 0 under Holm at 5%; T ≥ MinBTL | DSR 0.90–0.95 ⇒ WARN; below ⇒ FAIL |
| 5 | **Selection-process overfitting** | CSCV PBO over the full variant matrix (S=16); IS-vs-OOS degradation; SPA + StepM vs benchmark (buy-and-hold and random-entry baseline). | PBO < 0.10; degradation slope > 0; SPA p < 0.05; chosen variant ∈ StepM set | PBO 0.10–0.20 ⇒ WARN; > 0.20 ⇒ FAIL |
| 6 | **Permutation tests** | Masters bar-permutation with re-optimisation (≥1,000 perms); signal-shuffle; random-entry percentile. | p < 0.05 (p < 0.01 if N_eff > 20); above 95th percentile of random | p 0.05–0.10 ⇒ WARN |
| 7 | **Cross-validated OOS distribution** | CPCV (N=8–10 groups, k=2) ⇒ φ paths; walk-forward as second view. | Median path SR > 0.5× IS SR; ≥ 90% of paths SR > 0; WFE ≥ 50% | Median < 40% of IS ⇒ FAIL |
| 8 | **Robustness / regime** | Parameter neighbourhood (±25%) retains ≥ 70% of SR; ≤ 5 free parameters and ≥ 50–100 trades per parameter; profitable in ≥ 2/3 of calendar years; not reliant on a single regime; remove best 5 trades and best year — still positive; costs ×2 still positive. | All | Spike surface or single-year dependence ⇒ FAIL |
| 9 | **True hold-out** | One untouched period (≥ 12 months or ≥ MinTRL) opened exactly once. | Hold-out SR ≥ 50% of deflated backtest SR, same sign | Negative ⇒ FAIL |
| 10 | **Incubation** | Paper or minimal-size live ≥ 3–6 months; compare live vs expected; expect ~26–58% decay. | Live t-stat trending toward expectation; no unexplained cost gap | Cost gap > 2× model ⇒ back to gate 2 |
| 11 | **Sizing** | Kelly from *hold-out/deflated* SR; bet ≤ ¼–½ Kelly; volatility target; drawdown constraint with P(DD > 25%) ≤ 5–10%; the 1% rule as a hard per-trade cap. | — | — |

**Minimum sample sizes (rules of thumb)**
- Return observations: T ≥ MinTRL — daily data at 95%: SR 0.5 ⇒ ~11 yrs, SR 1 ⇒ ~2.7 yrs, SR 1.5 ⇒ ~1.2 yrs, SR 2 ⇒ ~0.7 yr.
- Versus trials: T ≥ MinBTL ≈ 2 ln(N_eff)/SR_target² years — 5 years of data supports at most ~45 independent configurations at SR 1.
- Trades: ≥ 30 for any statistic; ≥ 100 for t-tests; 50–100 per free parameter; ≥ 500 for per-regime breakdowns.
- Resampling: ≥ 1,000 permutations, 2,000–10,000 bootstrap draws, CSCV S=16, CPCV ≥ 8 groups.
- Events: ≥ 100–200 independent events for a ~1% CAR; ~500 for 0.5%.

**Method → library map**

| Method | Library / function |
|---|---|
| HAC t-test | statsmodels `OLS.fit(cov_type='HAC')` |
| Bonferroni / Holm / BHY | statsmodels `multipletests` |
| Harvey–Liu haircut SR | Duke programs; quantstrat R; quantskills skill |
| PSR / DSR / MinTRL | jsharpe; purgedcv; pypbo; quantstats; zoonek notebooks |
| PBO (CSCV), MinBTL, degradation | pypbo (AGPL); purgedcv (MIT); own ~100 lines |
| Reality Check / SPA / StepM / MCS | arch `SPA, StepM, MCS` |
| Stationary / block bootstrap | arch `StationaryBootstrap`, `optimal_block_length`; tsbootstrap |
| Ledoit–Wolf robust SR test | RobustSharpeRatioHAC; or arch + studentisation |
| Masters MCPT | C++ reference; own numpy |
| Purged K-fold, embargo, CPCV, walk-forward | skfolio `model_selection`; purgedcv |
| Triple-barrier, meta-labeling, frac-diff, feature importance | mlfinlab (paid); open forks as reference |
| ADF / KPSS | statsmodels; arch.unitroot |
| CUSUM / changepoints | statsmodels; ruptures |
| HMM regimes | hmmlearn; statsmodels `MarkovRegression` |
| Drawdown-constrained Kelly | cvxpy (Busseti–Ryu–Boyd) |
| Event study CAR/CAAR | eventstudy (GPL-3.0); own BMP/Kolari–Pynnönen |
| Portfolio construction | skfolio; Riskfolio-Lib |
| Tear sheets | quantstats; pyfolio-reloaded |

**Recommended dependency set for a solo platform:** `arch` + `statsmodels` (inference backbone, permissive), `skfolio` or `purgedcv` (CPCV), `jsharpe` (PSR/DSR/MinTRL/FDR), `tsbootstrap` (optional), `ruptures` + `hmmlearn` (regimes), `quantstats` (reporting); write your own CSCV/PBO rather than take an AGPL dependency on pypbo; treat mlfinlab forks as reading material.

---

## Sources (selected)
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345489 · https://people.duke.edu/~charvey/backtesting/ · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2474755 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3073799
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5520741 · https://github.com/zoonek/2025-sharpe-ratio · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7198158 · https://arxiv.org/abs/2606.01650
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253 · https://www.ams.org/notices/201405/rnoti-p458.pdf
- https://onlinelibrary.wiley.com/doi/abs/10.1111/1468-0262.00152 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569 · https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1468-0262.2005.00615.x
- https://www.ssrn.com/abstract=4778909 · https://arxiv.org/pdf/2605.23959 · https://arxiv.org/pdf/2604.15531 · https://arxiv.org/pdf/2603.20319 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3517595
- https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365 · https://www.openassetpricing.com/ · https://alphaarchitect.com/2016/05/beware-of-backtest-overfitting/
- https://bouchaud.substack.com/p/the-square-root-law-of-market-impact · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5287772 · https://www.susanpotter.net/quant/backtest-bias-taxonomy/
- https://gwern.net/doc/statistics/decision/2006-thorp.pdf · https://arxiv.org/abs/1603.06183 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431 · https://www.man.com/insights/the-impact-of-volatility-targeting
- https://www.jufinance.com/mag/dba5/event_study_chapter_1_2008_vol_1.pdf · https://www.lsvasset.com/pdf/research-papers/Insider-Trades-Informative.pdf · https://www.sciencedirect.com/science/article/abs/pii/S0929119924000750
- https://github.com/hudson-and-thames/mlfinlab · https://github.com/skfolio/skfolio · https://github.com/eslazarev/purged-cross-validation · https://github.com/tschm/jsharpe · https://github.com/esvhd/pypbo · https://github.com/bashtage/arch · https://github.com/statsmodels/statsmodels · https://github.com/astrogilda/tsbootstrap · https://github.com/hmmlearn/hmmlearn · https://github.com/deepcharles/ruptures · https://github.com/ranaroussi/quantstats · https://github.com/Apress/testing-and-tuning-market-trading-systems · https://github.com/DaruFinance/Monte-Carlo-paper · https://github.com/eyenoticeall/Lacuna · https://github.com/quantskills/skill-backtest-overfit · https://github.com/LemaireJean-Baptiste/eventstudy
- https://www.buildalpha.com/monte-carlo-permutation/ · https://robotwealth.com/benchmarking-backtest-results-against-random-strategies/ · https://www.susanpotter.net/quant/monte-carlo-permutation-tests-strategy-significance/ · https://portfoliooptimizationbook.com/book/8.3-dangers-backtesting.html · https://unbiased-alpha.com/how-to-avoid-backtest-overfitting-hypothesis-driven-strategy-discovery
