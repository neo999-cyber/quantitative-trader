# Response to the Antigravity review (18 September 2026)

*The review answered `docs/28`'s six questions. Written on Fable 5.1, the
model this repo uses for reviewing gate mathematics. Every claim below is
checked against the code and the trial log, not against the review's
own reading of them. Verdict on the review first; then each claim, held
or corrected; then what is adopted.*

## Verdict on the review

**Right on the direction, wrong on several facts about the machine.** Its
diagnosis — that literature-sourced anomalies are the wrong hunting
ground for a retail account, that turnover at this size is the enemy, and
that the one real effect (carry) deserves a cleaner test as a *holding* —
matches this project's own record. But three of its five "weaknesses"
describe gates this project does not have: the multiple-testing penalty
is per hypothesis, not global; carry and market-neutral books were
benchmarked against cash, not buy-and-hold, throughout Programme 2; and
adverse selection is measured, and is a registered pass criterion, in the
maker study it says is blind to it. A reviewer that had opened
`qr/validate/gates.py` or any night script would have seen all three.
Its blueprint restates controls the stage-1 harness already has, plus an
"AI regime layer" that is itself a timing hypothesis and would have to be
gated like one.

## Claim by claim

| # | Review's claim | Finding |
|---|---|---|
| W1 | All 18 candidates are decades-old textbook anomalies | **Half right.** E4 (PEAD), E5 (insider clusters), E7 (short squeeze), turn-of-month and the Programme 1 families are literature. C1 (funding-rule carry), C2 (cross-venue funding spread), C5 (OI-conditioned reversal), E1 (Nasdaq closing-cross imbalance from ITCH), C6 (vesting cliffs) are crypto- or microstructure-native and post-2020. The direction — stop sourcing fast-cycle ideas from papers — was already the recorded decision (`docs/20`, 18 Sep; `docs/research/10`). |
| W2a | "Global DSR penalty" across unrelated exploratory runs over-deflates | **Wrong.** `GateContext.trial_count` is `trial_log.trial_count(self.hypothesis_id)`: gate 4 deflates over the family's own counted variants (C6: 8; C1 v2: 64). The Codex review of 15 Sep checked exactly this ("gate 4 is per hypothesis"). |
| W2b | Delta-neutral carry compared to BTC/SPY buy-and-hold | **Wrong for Programme 2.** Every C1/C2/C5 run took `--benchmark cash --risk-free fred` (night scripts, gate reports' `context`). Programme 1 did use buy-and-hold for long-only spot books, which was correct for them; the change was made for Programme 2 and is stated in `docs/20` §1. C1 failed gate 1 (implausible gross Sharpe) and gate 6 (permutation), not gate 5. |
| W2c | The 3× cost bar kills genuine 10–15%/yr yield strategies | **Wrong on the example.** The bar is the effect against its own round-trip cost; a low-turnover carry clears it easily: C1 v2 gate 2 PASS, 92% of gross survives, Sharpe 2.81 at 2× costs. What killed C1 was gate 6. The bar is severe for high-turnover ideas by design. |
| W3 | Stage 0 assumes harmless passive fills; adverse selection is a blind spot | **Wrong as stated, right as an addition.** `docs/24`'s registered rule has two parts: ≥ 70% filled in 15 min **and median mark-to-mid 60 s after the fill < 2 bps**; the replay records it (first day: 0.84 bps Binance, 1.38 Bybit, medians); stage 1 logs the mid 60 s after each fill (`study_marks`). **Adopted:** log the mid at +5 s and +300 s as well, and report the mean and the tails beside the median. The registered threshold stays on the 60 s median. |
| W4 | Daily turnover at 15 bps round trip burns ~38%/yr on $1,000 | **Right**, and it is the project's own finding (`docs/18`, the fixed-cost table in `docs/27`). Programme 2's crypto families rebalanced daily or weekly, not by the minute; the minute bars were for the decision, not the holding. |
| W5 | Bybit/OKX/Hyperliquid unavailable; Binance is the sole venue | **Right**, recorded in `docs/27` and `docs/28` §8. OKX was the owner's choice to reject, not a restriction. |
| Q1 | The gates kill true positives (delta-neutral, carry) | **Not shown.** The two mechanisms it names for false negatives are W2a/W2b, which do not exist. The positive evidence that the gates pass a real effect is `qr selftest`: a planted edge must pass and planted noise must fail, and it does. A reviewer who wants to show a false negative should name the gate and the number. |
| Q2 | Re-run C1 and C5 on the ledger; the rest are dead | **Partly adopted.** C1's always-in book is real (`docs/23`: Sharpe 2.4, funding 97% of gross) and was a *control*, never a registered holding — the review is right that "hold the carry" deserves its own registration, and that is what the maker re-registration plan is. What it misses: the bar-permutation null is wrong for a holding whose risk is *when* the basis losses arrive (the BIS paper's point; C1 v2's p = 0.99 means the permuted worlds pay *more*), so the re-registration needs a mechanism-preserving null, which `docs/25` step 8 already lists. C5 (t 1.68 on the weights engine, 2.03 on the ledger) is a fair candidate for a clean re-run; both wait on the eleven-run re-run the owner has on his list. |
| Q3 | Fill rate alone is insufficient; add adverse excursion at +5/+60/+300 s | **Adopted** (see W3). |
| Q4 | Run the C3 liquidation event study now on the data since 15 Sep | **Adopted with a condition.** C3 is a row in the plan, not a pre-registration; running the event study first and registering after would make the run exploratory. The order is: write `docs/prereg/p2_liquidation_fade_v1.md` now (threshold, horizons, universe, null, falsifiers), register it, and run the kill test when the recorded event count reaches the minimum the memo states — likely early October rather than late. Note the recorders carry OKX and Bybit liquidations; Binance's `!forceOrder` stream sends nothing to the host (`scripts/record_tape.py`), so C3 is an OKX/Bybit *signal* traded on Binance, which the memo must say. |
| Q5a | Systematic delta-neutral carry, weekly rebalance, funding > 12% APR | **This is C1.** Short the highest-funding perps against spot on a threshold, rebalanced daily/weekly, was the registered rule; it failed gate 6 as a timing rule and its always-in control is the holding. The route back is the maker re-registration with the right null (Q2), not a new family. |
| Q5b | Cointegrated crypto perp pairs, Kalman hedge, ±2.5σ, 2–7 day holds | **A legitimate new input**, not yet tried here; low turnover, Binance-only, gate-able on the existing perp lake. Risks the memo must face: crypto cointegration is notoriously unstable out of sample; the Fayez (SSRN 2026) result that plain perp sorts carry nothing; a parameter-rich construction (pairs × lookback × z-threshold × Kalman) that gate 4 will deflate hard. Proposed to the owner as a candidate, with a small frozen grid. |
| Q5c | Options variance-risk premium on IBKR (iron condors, 30–45 DTE, SPY/QQQ) | **A legitimate new input with a stated contradiction.** The VRP is real and well documented; the review's own §1 warns against strategies that "win 99 days and lose the account on day 101", which is this one's shape. At $1–2k one condor's max loss is 10–20% of the account; IBKR's $0.65/contract on four legs both ways is $5.20 against a $30–50 credit. It needs an options data source the lake does not have and a tail-risk gate that bites. Proposed as a candidate for the owner's decision, not endorsed. |
| Q6 | Stop if the goal is a living from $1k; continue if the goal is the stack | **Agreed**, and it is `docs/18`'s verdict and `docs/28` §10. |
| §5 | Blueprint: kill switch, delta neutrality, 1.5× cap, HMM regime layer, RL placement, half-Kelly | The kill switch, session stop, pause, close-all and reconciliation exist in `qr/execution/study.py` and were rehearsed on 18 Sep; the study runs at 1×, stricter than 1.5×. Sizing is gate 10/11 (`prob_ever_below_launch`), not half-Kelly, on purpose. An HMM/GMM regime switch that enables or disables strategies is a timing overlay — a hypothesis with its own variant count and null — and would be registered and gated like any other; it does not get a pass for being "AI". RL for placement distance is out of scope until stage 1 has measured fills at the touch. |
| §6 | Four-week roadmap | Week 2 (adverse excursion horizons) adopted as is. Week 1 (C3) adopted with registration first. Week 3 (pairs) needs the owner's yes. Week 4 (kill switch) is done. |

## Adopted, in order

1. `qr/execution/tape.py` and `study.py`: marks at +5 s and +300 s beside
   the registered 60 s; mean and 90th percentile reported with the
   median.
2. `docs/prereg/p2_liquidation_fade_v1.md` drafted for the owner's yes;
   the kill test runs at a pre-stated minimum event count, not a date.
3. Two candidate inputs for the owner: cointegrated perp pairs (Binance,
   2–7 day holds) and the options VRP on IBKR. Neither is registered.
4. The C1 always-in holding becomes the object of the maker
   re-registration, with a mechanism-preserving permutation null.

## Not adopted

A regime-classifier layer with authority to enable strategies; RL
placement; half-Kelly; any change to gate 4's scope, gate 5's
benchmarks, or the 3× bar — the review's arguments for those rest on
the machine being something it is not.
