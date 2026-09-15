# Where this project is, and what happens next

> **Superseded, 15 September 2026 — read `docs/18_THE_VERDICT.md` first.**
> The plan below was carried out in full. Stages 1–4 were built, the autopilot
> was run to exhaustion, and the pending gate 10/11 review has been done
> (`docs/16`). Nothing on this page is an open task; it is kept for the
> reasoning, which is still the best account of *why* the funnel is shaped the
> way it is.

*Written 13 September 2026, as a handoff. A new session should be able to
read this file alone and pick up without re-deriving anything.*

## State

The validation engine runs **gates 0–11**, complete. 560 tests pass.

**Nine families have been pre-registered and run. None has passed gate 5.**
Buy-and-hold beat every one of them (SPA *p* > 0.5 in all cases, across two
asset classes and well over a thousand variants). The full record is in `docs/06` (crypto)
and `docs/08` (ETF), and `qr site` renders it as one page.

Nothing has ever been traded. No live order has ever been placed.

## The goal, stated so it cannot drift

Find out whether a tradeable edge exists at this account size — and if one
does, get it through all twelve gates and into a small live position.

**Passing is the hoped-for outcome, not the target.** If "get a family
through the gates" becomes the objective, enough attempts will produce a pass
by chance and it will be worthless. The gates are an instrument; the question
is whether an edge exists, and *no* is a permitted answer.

### The stopping rule, fixed in advance

> If **eight candidates with genuine, named mechanisms** go through the full
> gates and none survives, the finding is: *no edge is accessible at this
> account size with this data.* Write it up, stop, hold an index fund.

This is written down now, before anyone is attached to a result, precisely so
it cannot be renegotiated later.

---

## Step 0 — the account-size sweep (do this first, ~1 day)

**The question.** Gate 11 caps leverage near 0.2x on a $1,000 account. The
ETF trial found IBKR's $0.35 per-order floor eating 94% of a weekly
strategy's gross return. So: are the nine families failing because they are
bad ideas, or because $1,000 makes them uneconomic?

**The method.** Re-run all nine at $1,000 / $10,000 / $100,000. Same
variants, same data, same everything — only `--equity` changes. This is a
sensitivity analysis on one cost parameter, **not a new search**, so it adds
nothing to the trial count and gate 4 is unaffected. Record it as such.

**What it cannot do.** The ETF holdout was opened once already and is spent.
These are re-scores of in-sample periods. A family that "passes" at $100,000
here has *not* earned a verdict; it has earned a place in the next round of
pre-registration.

**Expected answer, so the result can disagree with it.** The per-order floor
is an IBKR equities problem. Binance spot charges ~0.1% with **no minimum per
order** and at $1,000 the market-impact term is negligible — so account size
was never the binding constraint on the crypto side. Expect ETFs to improve
with size and crypto to be roughly unchanged, which would mean the crypto
families failed on their merits. If crypto *does* move with account size,
something is wrong with the cost model and that is the finding.

**Why it is worth a day.** It decides what the next six months are about:
finding ideas, or finding capital. Those are different projects.

**Status (13 September 2026): DONE — `docs/11_ACCOUNT_SIZE_SWEEP.md`.**
The answer is **finding ideas, not finding capital**: crypto is size-independent
to four significant figures, and the ETF families get much cheaper with size
without the SPA test against buy-and-hold improving at all. No deposit rescues
any of the nine.

Original note:
`qr account-size` runs it, writing nothing to the trial log and producing
readings rather than verdicts. The crypto half is answered already, and more
strongly than expected: the four crypto families are *bit-identical* across
the three sizes, because the Binance model is purely proportional and the
taker fee is flat from VIP0 to VIP2. Account size was not the binding
constraint there. The ETF half needs the lake and must run on the laptop.

**Note on capital.** `$25,000` and similar figures that come out of this are
*model parameters*, not deposits. Nothing should be funded on the strength of
this sweep. "It would work with a bigger account" is the most expensive
sentence in retail trading; an account requirement is a finding about
feasibility, not a target to go and hit.

---

## The research plan, after Step 0

The nine families so far were all *patterns* — "things that went up keep
going up." Nobody pays for a pattern. The ideas that survive are transfers:
someone is **forced to trade** regardless of price, and somebody collects.

**The generating question is "who is forced to trade?"** Leveraged crypto
longs paying funding every eight hours. Index funds that must buy on the day
a stock joins. Liquidation cascades. Vesting insiders. Month-end pension
rebalances. Tax-loss selling in December. Each has a payer you can name.

### Stage 1 — the discovery sandbox (~3 days)

The missing infrastructure, and currently a self-inflicted trap: every
exploratory look risks contaminating the evidence, which makes browsing
expensive, which is why we keep testing textbook strategies.

Carve off a permanent discovery set — a slice of symbols and an early period
— where anything may be looked at, freely, and from which nothing is ever
reported. Validation happens on the untouched remainder. This is what makes
exploration free.

**Status (13 September 2026): built — `docs/12_DISCOVERY_SANDBOX.md`.**
`qr sandbox declare` draws the line by SHA-256, once, into the trial log, and
refuses to redraw it. Three enforcement layers keep a sandbox result out of the
record. Declare the two boundaries on the laptop before any exploration starts.

### Stage 2 — mechanism before code (~2 days per candidate)

A one-page memo before anything runs:

1. Who is forced to trade, and why?
2. Why will they keep being forced? *(If the answer is "momentum works",
   there is no mechanism. Kill it here.)*
3. Who is on the other side today, and why has the effect not gone?
4. What would make it stop working?
5. Crudest possible version, and its gross return before costs.

Most candidates die at (2), on paper, for free.

### Stage 3 — cheap kill tests in the sandbox (~1 day per survivor)

- Does the effect exist at all?
- Is it at least **3x** trading costs? Not 1.2x — that lesson was expensive.
- Does the turnover survive the per-order floor at the size Step 0 found?

**Status (13 September 2026): Stages 2 and 3 are built.** `qr autopilot` runs
memo -> triage -> kill test unattended; `docs/14_RUNNING_IT.md` is the laptop
guide. Triage re-decides without reference to the model's own verdict, and a
candidate needing data the lake lacks is *blocked* with the dataset named
rather than killed — see `qr/research/features.py`. Today only the calendar
family is runnable; every other mechanism on the list above waits on data.

### Stage 4 — pre-register and run the gates (~1 week each)

**Three to five candidates a quarter, not fifty.** Every additional variant
raises gate 4's bar for every future family, and the log is already in the
thousands — `qr trial verify` prints the count, which is the only figure worth
quoting because a written-down one goes stale the next time anything runs.
Searching wider is not the lever. Choosing better is.

### Running stages 2 and 3 as parallel agents (worth trying, when we get there)

Stages 2 and 3 are the one part of this project shaped for multi-agent
orchestration: eight mechanism candidates are **independent of each other**,
each needs the same fixed treatment (write the memo, answer the six
questions, run the kill tests), and the outputs are comparable. One sub-agent
per candidate, fanned out, then merged and ranked — instead of one at a time.
The `Workflow` tool does exactly this.

Two limits on it, so the idea does not get applied where it does not belong:

**It costs multiples, not a little more.** Each agent carries its own context.
A fan-out of eight is not eight times *one prompt*, it is eight times
*everything each agent needs to know*, and this project's background is not
small. It is worth it when the work is genuinely parallel and the alternative
is eight sequential sessions. It is waste anywhere the next step depends on
the exact state left by the last one — which is most of this codebase, where
a sloppy handoff means a wrong trial count rather than a stylistic miss.

**It is not a substitute for the gates, and specifically not for the pending
gate 10/11 review.** An LLM checking another LLM's work catches some things
and misses others, and it fails hardest exactly where the author was
motivated — which is the case in question. The gates are deterministic:
formulas, a hash chain, the same verdict every run. That is strictly better
than an agent with opinions, and the reason the sizing-maths review is routed
to a separate human-triggered session rather than an automated reviewer.

So: fan out the *search*, never the *verdict*.

### Honest odds

At $1,000, roughly **1 in 5** that something clears all twelve gates and is
worth trading. Better above $25,000, mostly on the equities side. The crypto
side is where a small account can genuinely compete — no per-order floor, and
734 pairs including names too small for real capital to touch.

---

## Pending review — DONE (14 September 2026)

**Status: run — `docs/16_GATE_11_SIZING_REVIEW.md`.** The algebra is correct
and the number is mislabelled: the formula gives P(ever 25% below *launch*
equity), not P(ever draw down 25% from the peak), which over the infinite
horizon is 100% at every leverage. Half Kelly still fails a 10% budget on every
reading; quarter Kelly is borderline, not "not close"; the plan's constraints
were a conjunction, not a contradiction; and the 0.2x single-name result has
no account-size term. Fixes are listed at the end of that document for a build
session, **and were applied the same day**: the quantity is renamed
(`prob_ever_below_launch`, `SizingPolicy.loss_from_launch` /
`loss_tolerance`) in `qr/portfolio/sizing.py`, the gate 11 verdict string and
`docs/09`; the tautological test is joined by a second published anchor (half
Kelly, ⅛) and a Monte Carlo that shares no algebra with the formula; the
Kelly ceiling moved from 0.25, where it could never bind, to 0.5, where it
binds if the loss budget is loosened; and a malformed policy is now refused at
construction. Item 5 — whether gate 11 should also report a finite-horizon
peak-to-trough estimate with the Sharpe standard error carried into the
verdict — is a design decision and is **still open**. The original prompt is
kept below for the record.

Gates 10 and 11 were written on 13 September 2026 and **their mathematics had
not been independently checked.** Per `CLAUDE.md`, that review belongs to
Fable 5.1 in its own session. It is not urgent — both gates are inert until
something reaches gate 9 — but one claim from it is already informing
decisions: that half-Kelly carries a 42% chance of a 25% drawdown, and that
the plan's two sizing constraints contradict each other.

The author wrote both the formula and the test that confirms it, which is
exactly the arrangement that let the rebalance-phase defect survive three
write-ups (`docs/08`).

**Trigger it before any real money is sized, and before `docs/09`'s sizing
claims are relied on in a decision.** The prompt (as run):

> Audit the mathematics in `qr/portfolio/sizing.py` and
> `docs/09_INCUBATION_AND_SIZING.md`. Do not fix anything, do not write code
> — report what is wrong or unjustified.
>
> 1. `drawdown_probability()`. It claims P(ever draw down more than D) =
>    `(1-D)**(2m/s**2)`, with *m* the log drift and *s* the volatility of the
>    levered book. Is that the correct expression for the maximum drawdown of
>    a geometric Brownian motion, and are *m* and *s* computed correctly from
>    the leverage, Sharpe and volatility passed in?
> 2. `_drawdown_cap()`. It inverts the above in closed form using
>    `q = 2m/s**2 = (2*SR/(f*sigma)) - 1`. Verify that algebra.
> 3. The claim that a full-Kelly book has exactly a 50% chance of ever
>    halving, used as the known-answer test. Is that the right anchor, and
>    does the code reproduce it for the right reason rather than by
>    coincidence?
> 4. The table in `docs/09` giving P(ever drawdown > 25%) as 75% / 42% / 13%
>    / 7.5% for full / half / quarter / fifth Kelly. Recompute it.
> 5. The document's claim that the plan's two constraints — "fractional Kelly
>    (1/4 to 1/2)" and "P(DD > 25%) <= 5–10%" — contradict each other. Is
>    that sound, or an artefact of reading "eventual" drawdown where the plan
>    meant a finite horizon?
> 6. Whether an infinite-horizon drawdown probability is the right thing to
>    size on at all, given a strategy nobody intends to hold forever.
>
> Assume the author was motivated to find an interesting result and say where
> that shows.

## Also deferred

- **`qr site` and Chronicle stay separate.** The record is offline and mostly
  failures; Chronicle's market page is an operating surface. When a family
  finally passes, qr posts *one row* to
  `POST /api/agent/market/strategies` — promotion is the event Chronicle
  exists for, and the graveyard stays here. Chronicle's "Gate" is currently a
  boolean off `deployWorthy`; it should become the real gate number at that
  point. Not before — today the bridge would post zero rows.
