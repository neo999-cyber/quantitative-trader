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

    qr account-size
    qr account-size --asset etf
    qr account-size --only etf_reversal_v1 --sizes 1000 5000 25000 100000
    qr account-size --out reports/account_size.csv

Bare, that is all nine families at the three sizes; `--asset` narrows it to one
trial's families.

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

**To run it.** The laptop checkout is on `claude/admiring-ptolemy-tfp528`
and this command does not exist on that branch, so switch first:

    git fetch origin claude/funny-faraday-nizzck
    git checkout claude/funny-faraday-nizzck
    source .venv/bin/activate
    qr account-size --asset all --out reports/account_size.csv

and paste the two tables it prints into the next section.

### Results — run 13 September 2026

Net Sharpe, and the share of gross return surviving costs, at each account
size. `qr account-size --asset all`, full output in `reports/account_size.csv`.

| hypothesis | asset | $1,000 | $10,000 | $100,000 | net/gross 1k → 100k | gate 2 | SPA *p* 1k → 100k | reading |
|---|---|---|---|---|---|---|---|---|
| tsmom_v1 | crypto | 0.582 | 0.582 | 0.582 | 0.739 → 0.739 | PASS | 0.733 → 0.733 | `size-independent` |
| xsmom_v1 | crypto | 0.277 | 0.277 | 0.277 | 0.822 → 0.822 | PASS | 0.779 → 0.779 | `size-independent` |
| reversal_v1 | crypto | −0.048 | −0.048 | −0.048 | n/a (no gross) | FAIL | 0.853 → 0.853 | `size-independent` |
| rsi_reversal_v1 | crypto | 0.539 | 0.539 | 0.539 | 0.930 → 0.930 | PASS | 0.649 → 0.649 | `size-independent` |
| etf_tsmom_v1 | etf | 0.778 | 0.949 | **0.979** | 0.781 → 0.984 | PASS | 0.941 → 0.797 | `cheaper, still failing` |
| etf_xsmom_v1 | etf | 0.574 | 0.694 | 0.797 | 0.685 → 0.950 | PASS | 0.984 → 0.957 | `cheaper, still failing` |
| etf_reversal_v1 | etf | 0.309 | 0.681 | 0.816 | 0.380 → 0.913 | **FAIL → PASS** | 0.569 → 0.953 | `cost-bound` |
| etf_buyhold_v1 | etf | 0.749 | 0.756 | 0.767 | 0.974 → 0.997 | PASS | control | `cheaper, still failing` |
| ls_xsmom_v1 | etf-ls | 0.006 | 0.148 | 0.252 | 0.019 → 0.797 | **FAIL → PASS** | 0.552 → 0.528 | `cost-bound` |

Trial count: **1541 → 1541.** The sweep searched nothing and was charged
nothing, as designed.

### What it says

**The crypto half is confirmed, to four significant figures.** All four
families are *identical* at every size — same best variant, same Sharpe, same
turnover, same everything. Not "roughly unchanged": unchanged. Account size
was never the binding constraint there, exactly as reading the cost model
predicted.

**The ETF half moves a great deal, and it does not matter.** Costs fall
sharply with size — the long-short book keeps 1.9% of its gross return at
$1,000 and 80% at $100,000 — and two families flip gate 2 from FAIL to PASS.
`etf_reversal_v1` and `ls_xsmom_v1` really were unaffordable at $1,000.

**But the SPA column never improves.** That is the column that decides the
project, and at $100,000 — a hundred times the account — not one family beats
buy-and-hold: *p* = 0.797, 0.957, 0.953, 0.528. On the crypto side, 0.649 to
0.853. The families get **cheaper without getting better**.

So the question "are they failing because they are bad ideas, or because
$1,000 makes them uneconomic?" has an answer:

> **Bad ideas.** Capital makes two of them affordable. It makes none of them
> good.

### Two checks that had to pass, and did

**The control improved least.** `docs/11` said in advance: if buy-and-hold
improves *most*, gate 5 is comparing against a benchmark that is itself moving
with size and every row needs re-reading. Buy-and-hold gained 0.023 of
net-over-gross; the others gained 0.20 to 0.53. The comparison is sound.

**`etf_reversal_v1`'s SPA got *worse* with size** — 0.569 at $1,000, 0.953 at
$100,000 — and that is correct rather than alarming. At $1,000 the benchmark
is crippled by the per-order floor too, so beating it is easy; at $100,000
buy-and-hold keeps 99.7% of its gross return and the bar is much higher. This
row only reads correctly because gate 5's benchmark is now priced at the same
account as the strategy (`docs/07` §8). Under the old code the columns would
not have been comparable with each other at all.

### One thing to note rather than chase

Gate 11 returned SKIP for every family at every size. That is the gate
refusing to size from an in-sample Sharpe, which is its whole purpose — but
the ETF families *do* have holdout records from the first ETF run. The likely
cause is that those records predate the `holdout_volatility` field gate 11
needs, and a Sharpe without the volatility behind it cannot be turned into a
position. Nothing is being sized, so nothing is blocked by it; worth knowing
before the first family that does reach gate 9.

## Two things settled elsewhere, recorded so they are not re-derived

**A second implementation of this sweep existed and was discarded.**
`qr accounts`, on `claude/admiring-ptolemy-tfp528` (commit e2ac9a0), was built
in parallel and is not in this history. Three reasons, so it is not
reintroduced by someone finding it and assuming it was lost:

* It passed `trial_log=None` to keep the log clean. That works, and it also
  blinds gate 0 to the pre-registration and leaves gate 4 deflating against
  the current sweep instead of the real log. `SealedTrialLog` keeps the reads
  and drops only the writes, which is the distinction that matters.
* It stopped at gate 2, which cuts gate 5 — and gate 5 carries the SPA test
  against buy-and-hold, the row that actually decides whether costs or the
  ideas are the problem. A cost sweep that cannot see the cost-adjusted
  comparison is answering a smaller question than the one asked.
* It did not have the `buy_and_hold_benchmark` equity fix (§ above), without
  which the three columns are not comparable anyway.

**Impact is not charged in any family run, so the cost model currently implies
unbounded capacity.** That is true, it was found while building the other
implementation, and it is *not* a Step 0 problem. Turning impact on for this
sweep was the wrong response twice over: `CostModel.impact_bps` argues
explicitly against extrapolating the √-law to orders far below the top of
book, and impact can only ever make the *larger* accounts look worse — so it
cannot change the answer to "is $1,000 too small?", only muddy it. The
treatment here stands: crypto is size-independent by construction, and if it
ever moves that is a defect report.

The capacity question is real and belongs on its own: what the ceiling
actually is, measured with a charge that is defensible at these participations
rather than one extrapolated a thousandfold below its fitted range. Nothing in
this project is near a size where it binds, which is why it can wait — but it
should not wait by being forgotten.

## Verdict

**The next six months are about finding ideas, not finding capital.**

Both halves agree. Crypto is size-independent to four significant figures, so
the account was never the constraint. The ETF families get dramatically
cheaper with size — two of them cross from unaffordable to affordable — and
still cannot beat holding the basket at a hundred times the account.

That closes the question `docs/10_NEXT.md` opened. It also means the money
question is settled in the least expensive way possible: **there is no deposit
that would rescue any of these nine.** "It would work with a bigger account"
was the sentence this sweep existed to test, and the answer is no.

What it does *not* say is that no edge exists at this size — only that these
nine do not contain one, and that cost was not what hid it. The mechanism
nights (`docs/15`) point at the actual constraint: instrument access and
missing data, not capital and not idea generation.
