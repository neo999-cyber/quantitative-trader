# Step 0 — the account-size sweep

*Started 13 September 2026. Step 0 of `docs/10_NEXT.md`.*

Nine pre-registered families have been run and none has passed gate 5. Two
readings fit that evidence and they imply different projects:

* the ideas are bad — the next six months are about **finding ideas**;
* the account is too small to trade them — the next six months are about
  **finding capital**.

The ETF trial found IBKR's $0.35 per-order floor eating 94% of a weekly
strategy's gross return. That is a cost of *being small*, not a verdict on a
strategy. So: re-score every family at **$1,000 / $10,000 / $100,000**, same
variants, same data, same everything, with only the account size the cost model
prices orders against changed.

    qr account-size                     # all nine, three sizes
    qr account-size --asset etf         # one trial's families
    qr account-size --only etf_reversal_v1 --sizes 1000 5000 25000 100000
    qr account-size --out reports/account_size.csv

## What this is, and what it is not

**It is a sensitivity analysis on one cost parameter.** Three consequences,
all enforced in code rather than promised in prose:

* **It writes nothing to the trial log.** The log is opened through
  `SealedTrialLog`, which reads the chain — gate 0 needs the pre-registration,
  gate 11 needs the holdout gate 9 opened — and drops every write. Re-running
  known families with a different fee searches nothing; logging 27 `run`
  records would treble the count gate 4 deflates against and raise the bar for
  every future family. The command prints the trial count before and after and
  **exits non-zero if it moved**.
* **It produces readings, not verdicts.** The output vocabulary is
  `size-independent`, `cost-bound`, `cheaper, still failing`, and
  `worse with size — check the cost model`. There is no PASS. The ETF holdout
  was opened once and is spent; these are re-scores of in-sample periods. A
  family that looks better at $100,000 has earned a place in the next round of
  pre-registration and nothing more.
* **Only the size-sensitive gates run:** 2 (cost survival), 3, 4, 5 (which
  carries the SPA test against buy-and-hold that every family has failed), and
  11 (sizing, whose entire output is a function of account size). Gates 0 and 1
  do not depend on equity and ran already. Gates 6 and 7 cost hours and cannot
  move.

**`$25,000` and similar figures that come out of this are model parameters,
not deposits.** Nothing should be funded on the strength of a sweep. "It would
work with a bigger account" is the most expensive sentence in retail trading;
an account requirement is a finding about feasibility, not a target to hit.

## The crypto half is already settled, and not by measurement

`docs/10_NEXT.md` expected crypto to be "roughly unchanged". It is stronger
than that: the four crypto families are **bit-identical** across the three
account sizes, by construction.

1. `CostModel.trial()` is purely proportional — 7.5 bps of fee and 2 bps of
   half-spread per side. `per_share_usd` and `min_commission_usd` are both
   zero, because a Binance taker pays the same basis points on a $10 order and
   a $10,000 one.
2. The family sweeps do not charge impact (`charge_impact=False`; capacity is
   gate 2's separate ladder). So `run_backtest`'s `needs_equity` is false and
   the account size never reaches the cost calculation at all.

Two things could have broken that and do not:

* **The fee tier is volume-dependent, so in principle a bigger account pays
  less.** In practice it does not, over any size in scope: the Binance spot
  *taker* fee is 10 bps flat from VIP0 through VIP2 and only falls at VIP3,
  which requires a 30-day volume no account of $100,000 reaches. The maker fee
  starts falling at VIP1; the trial is priced taker-only, so it is untouched.
  A five-figure account and a three-figure account pay exactly the same rate.
* **Market impact grows with size.** It does, and gate 2's capacity ladder is
  where that is measured. For top-30 USDT pairs turning over nine figures a
  day, $100,000 is far inside the regime where the √-law charge nets to zero
  against the half-spread already paid.

So, for the crypto side: **account size was not the binding constraint, and
the four crypto families failed on their merits.** That is the expected answer
from `docs/10_NEXT.md`, reached by reading the cost model rather than by
burning twelve runs on it — and the sweep still runs those twelve, because a
claim of exact invariance is worth confirming rather than asserting.

`tests/qr_platform/test_account_size.py` locks it:
`test_a_crypto_family_is_bit_identical_across_account_sizes` compares the net
return series, not a summary of it. If it ever fails, the finding is a
declared-size dependence in the cost model — a defect — and not a discovery
about a strategy.

## One engine defect this found before it ran

Gate 5's buy-and-hold benchmark took no account size, so on a per-order venue
it fell back to `run_backtest`'s $10,000 default while the ETF trial priced its
strategies at $1,000. Every ETF family was being asked to beat a buy-and-hold
in an account ten times larger. The direction is conservative — it flatters the
benchmark — and buy-and-hold barely trades, so no verdict in `docs/08` moves.
For this sweep it would have been fatal: the strategies would move with size
and the thing they are measured against would not, which makes the three
columns incomparable. Fixed, and written up as `docs/07_ENGINE_FIXES.md` §8.

## The ETF half needs the laptop

The cloud sandbox has no lake and cannot reach Tiingo or Binance. The five
ETF-side families (`etf_tsmom_v1`, `etf_xsmom_v1`, `etf_reversal_v1`,
`etf_buyhold_v1`, `ls_xsmom_v1`) are where the answer actually lives, because
IBKR charges per share with a floor per order and the cost in basis points
therefore collapses with order size: one leg of a twelve-ETF basket is an $83
order paying 42 bps at $1,000, and the same trade pays 0.42 bps at $100,000.

**To run it:**

    qr account-size --asset all --out reports/account_size.csv

and paste the two tables it prints into the next section.

### Results — not yet run

| hypothesis | asset | $1,000 | $10,000 | $100,000 | reading |
|---|---|---|---|---|---|
| tsmom_v1 | crypto | | | | expected `size-independent` |
| xsmom_v1 | crypto | | | | expected `size-independent` |
| reversal_v1 | crypto | | | | expected `size-independent` |
| rsi_reversal_v1 | crypto | | | | expected `size-independent` |
| etf_tsmom_v1 | etf | | | | |
| etf_xsmom_v1 | etf | | | | |
| etf_reversal_v1 | etf | | | | |
| etf_buyhold_v1 | etf | | | | |
| ls_xsmom_v1 | etf-ls | | | | |

### How to read what comes back

* Any crypto row that is **not** `size-independent` is a defect report, not a
  result. Stop and look at the cost model before looking at the Sharpe.
* `etf_reversal_v1` is the family the floor was eating; it is the one most
  likely to read `cost-bound`. A `cost-bound` reading says the small account
  cannot afford to find out whether the idea works — not that it works.
* The SPA column is the one that decides the project. Every family so far has
  failed gate 5 with *p* > 0.5 against buy-and-hold. If that *p* barely moves
  from $1,000 to $100,000, then costs were never what stood between these
  families and an edge, and the honest answer is that the ideas were the
  problem — which is what the research plan in `docs/10_NEXT.md` is already
  organised around ("who is forced to trade?", not "what pattern repeats?").
* `etf_buyhold_v1` is the control and it trades monthly with almost no
  turnover. It should improve least. If it improves *most*, the comparison in
  gate 5 is being made against a benchmark that is itself moving with account
  size, and every other row in the table needs re-reading.

## Verdict

**Pending the ETF run.** The crypto half is answered: no, $1,000 is not why
the crypto families failed.
