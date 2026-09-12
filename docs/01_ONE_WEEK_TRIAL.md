# The one-week trial: decisions and plan (agreed 11 Sept 2026)

This supersedes the timeline in `PLAN.md` §5 for the first phase. Everything else in `PLAN.md` still holds.

## Decisions made

| Topic | Decision |
|---|---|
| Hardware | **No new hardware for now.** MacBook Air M2 16 GB is the research machine (enough at the daily/swing horizon). Existing Hetzner CX23 (2 vCPU / 4 GB / 40 GB, shared with other projects) is the always-on ops box later; add a Volume (~€0.057/GB/mo) for the lake rather than resizing. Hourly CX53 (16 vCPU / 32 GB, ~€0.047/h) created and deleted per job for anything that outgrows 16 GB; Modal ($30/mo free credit) as the serverless alternative. |
| OS | macOS for research, Linux for ops → **Norgate is out** (Windows only). Equities later via Tiingo + free constituent histories (budget) or Sharadar (serious). |
| Budget | Budget path first. Spend the ~$1,000 only after the trial verdict. Priority for that money later: survivorship-free equity data (Norgate/Sharadar), then hourly compute or a workstation, then RealTest. |
| First asset class | **Crypto spot, daily bars, one venue** (Binance data; Binance or Kraken as the modelled venue depending on residency). Fixed ETF basket (SPY, QQQ, TLT, GLD…) is the second $0 trial. Single stocks wait for paid data. |
| Yardstick | The trial is judged by the **validation gates on 8–10 years of historical data**, not by two weeks of P&L. Short-window P&L is noise for any realistic system (see table below). |
| Live | Any strategy that passes gates 1–9 goes to paper/small live immediately on the CX23; sizing up follows live results tracking expectations (3–6 months). That clock runs in parallel with the heavy build. |

## Why P&L over weeks is not evidence

Probability a period ends positive, assuming roughly normal returns:

| Annual Sharpe | Month | Quarter | Year |
|---|---|---|---|
| 0.5 | 56% | 60% | 69% |
| 1.0 | 61% | 69% | 84% |
| 2.0 | 72% | 84% | 98% |

Income = edge × capital. A validated Sharpe-1 system at 15% vol on $10k expects ~$1,500/yr with a 16% chance of a losing year. The platform makes that number real instead of a mirage; it cannot change the arithmetic.

## The one-week plan (from "go")

| Day | Work | Who |
|---|---|---|
| 1–2 | Binance bucket loader (daily + 1h bars, top-30 pairs by volume, listing/delisting dates from the bucket listing), strategy interface, cost model (taker fee + spread, no funding for spot), vectorbt runner, append-only trial log | Claude |
| 2–3 | Gates 1–9 on existing libraries (vectorbt, skfolio CPCV, arch bootstrap/SPA, jsharpe PSR/DSR, own CSCV + permutation); **synthetic self-test**: a noise strategy searched over 200 variants must FAIL at gate 4/5, a planted edge must PASS | Claude |
| 3 | Run the data pull + QA report on the laptop (the cloud sandbox cannot reach Binance) | You, one command, ~15 min |
| 4–5 | Four families through all nine gates, in parallel: (1) time-series momentum, vol-targeted, top-20 coins; (2) cross-sectional momentum, weekly rebalance; (3) weekly short-term reversal; (4) the existing 3-down-day RSI setup as a **control** (expected to fail) | Claude |
| 6–7 | Read the four Hypothesis Reports, fix what they expose, rerun | Both |

Realistic: first honest verdict ~1 week after go, 10 days with one fix cycle. The minimal pipeline is 3–5k lines of glue around existing libraries; correctness (the self-test), not volume, is the long pole.

## Decision rule at the end

- **≥1 family passes gates 1–8 with positive holdout Sharpe** → start paper trading it on the CX23 that week; spend the $1,000; continue the heavy build (`PLAN.md` phases 4–6) while incubation runs.
- **All fail** → do not spend. Run the ETF-basket trial next ($0). The failure itself is the platform working.

## What does not compress
- Historical depth (8–10 years) — free for crypto and ETFs.
- The live clock after the verdict.
- The discipline: pre-registration + trial log stay in even in the minimal build. Speed without them is p-hacking.

## Resolved 11 Sept 2026 (evening)
- **Residency: Dubai.** Binance.com is available (VARA-licensed), so the crypto trial models **Binance spot** end to end: bucket data, Binance fee schedule, Binance as the paper/live venue. No US restrictions apply.
- **Fee tier verified 11 Sept 2026** against the account's own fee panel: 30-day volume 0.00 USD → **VIP0 with the BNB discount on, 0.07500% maker and taker**. With a 2 bps half-spread that is **9.5 bps per side, 19 bps a round trip**, and gate 2 tests it again at double. This is the frozen cost model for the trial (`CostModel.trial()`).
- **Accounts already held:** Binance (a few transactions over the years) and Interactive Brokers (same). IBKR is the equities/ETF/futures venue for later phases; its official MCP is connected in the cloud session. Alpaca is not needed.
- The Centaur rulebook's Rule 3 regime inputs (SPY/QQQ/VIX/DXY) and the ETF-basket second trial will use IBKR market data or Tiingo, not yfinance.

## Build progress

- **Day 1–2 done (11 Sept 2026).** Data layer, strategy interface, cost model, two-engine backtest runner and hash-chained trial log are in on `claude/admiring-ptolemy-tfp528`; 152 tests, all offline. Details and the laptop commands: `docs/02_DATA_LAYER.md`. Cost model frozen at the verified VIP0+BNB tier. Details and the laptop commands: `docs/02_DATA_LAYER.md`.
- **Day 2–3 done (11 Sept 2026).** Gates 0–9, the Hypothesis Report generator and the synthetic self-test are in; 283 tests. **The self-test passes**: searched-over noise is rejected by the deflation gates (4 and 5), a planted Sharpe-1.7 edge survives all nine. Writing it found three real bugs in the engine — gate 1 was testing the wrong signature for look-ahead, gate 5 over-rejected interchangeable variants, and the planted edge was so strong it tested nothing. Details: `docs/03_VALIDATION_ENGINE.md`.
- **Day 4–5 done (11 Sept 2026).** All four families built, pre-registered and run through all nine gates by one command (`qr families`); 327 tests. Details: `docs/04_FOUR_FAMILIES.md`. The run was a **dry run on synthetic data** and says nothing about crypto — but it works end to end, and `tsmom_v1` passing gates 0–7 and then dying at the holdout with Sharpe −1.05 is a fair demonstration of why gate 9 exists. **Waiting on you:** run `qr data pull` on the laptop (the sandbox cannot reach Binance), then `qr families` against the real lake.
- **Day 6–7 done (11 Sept 2026).** Audited the engine against `PLAN.md` §4 line by line rather than tuning it against synthetic reports. Three configured thresholds were read by nothing; Hansen SPA, the shuffled-ticker placebo, per-regime Sharpe and a capacity estimate were specified and missing; gate 6 was not re-optimising (which took its p-value on searched-over noise from 0.06 to 0.78) and gate 8 was dropping the best five *bars* rather than the best five *trades*. The self-test then caught two calibration errors of mine in the fixes. Details: `docs/05_GATE_AUDIT.md`.

- **The real run, 12 September 2026. All four families FAIL.** 734 Binance
  pairs pulled and QA'd on the laptop, top-30 point-in-time universe,
  2018–2024 in sample, 2025 onward as an untouched holdout. Not one of 425
  variants beats buy-and-hold of the same basket (SPA p = 0.83–0.91); HAC
  t-statistics of 1.08–1.93 against a 2.5 floor; deflated Sharpes of
  0.50–0.78 against 0.95; holdout Sharpes of −0.55, −0.82 and −0.39 for the
  three real families. The best variant of 200 on real crypto scored 0.749,
  worse than the best of 200 the same search finds on **pure synthetic
  noise** (1.058). Full verdict and the scoring of the four pre-registered
  predictions — five of which were wrong, all about the *mechanism* of
  failure rather than the verdict — in `docs/06_TRIAL_VERDICT.md`.
- **Four engine defects fixed afterwards (12 September 2026).** The run
  exposed four numbers that meant something other than what they said: gate 1
  failing all four families for bars the panel had already withheld from them,
  a capacity estimate double-charging the spread, gate 6's null unfair to a
  vol-targeted strategy, and a walk-forward efficiency dividing by a number
  passing through zero. All four fixed, 24 regression tests, 401 total.
  Details and what was deliberately *not* changed: `docs/07_ENGINE_FIXES.md`.
  None of them touches the verdict, which is the reason it was safe to fix
  them now.

## Decision, 12 September 2026

**Do not spend the $1,000.** The rule agreed on 11 September applies as
written: all four failed, so the next step is the **ETF-basket trial**, which
costs nothing. The platform did the job it was built for — it said no.

## Before "go" (still thinking)
- Review GitHub repos the user will share; each gets a one-by-one assessment in `docs/research/06_repo_reviews.md`: adopt / borrow / reference / skip, and where it changes `PLAN.md`.
