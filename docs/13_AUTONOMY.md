# The autonomous funnel — what runs unattended, and what may not

*Written 13 September 2026. The design behind Stages 1–4 of
`docs/10_NEXT.md` running on a laptop overnight.*

The goal: leave the machine running, come back to finished Hypothesis Reports
rather than to a queue of decisions.

## The asymmetry that decides the design

The funnel splits into two halves with opposite properties, and the split is
not about how hard the work is.

**Stages 1–3 are free to fail.** Explore the sandbox, write a mechanism memo,
run cheap kill tests. Nothing is reported, nothing is spent, and a candidate
that dies at "why will they keep being forced?" cost a page of text. A machine
should do this all night, and the more it does the better.

**Stage 4 is not.** Every variant that reaches the gates raises gate 4's
deflation bar for every family that comes after it, permanently. The trial log
is already in the thousands. So an agent that decides what to promote *after seeing
results* does two bad things, not one: given enough attempts it eventually
promotes noise, and it also spends the project's remaining ability to
demonstrate a real edge — the failure nobody notices until the edge arrives and
cannot be shown.

The naive fix is a human in the loop. It does not work: a person approving
memos at 9am is a rate limit made of availability, which is no rate limit at
all on a week when they are busy or keen. The real fix is to **fix the rule and
the quota before any run**, in code, declared into the hash-chained log. Then
the agent may promote freely, because what it cannot do is promote *more*, or
promote on a rule it invented after seeing the numbers.

Rationing by design, not by good intentions.

## What is built

| piece | what it guarantees | where |
|---|---|---|
| **Discovery sandbox** | Looking is free. A slice split by SHA-256, declared once, from which nothing is reportable — enforced in three places. | `docs/12`, `qr sandbox` |
| **Research policy** | An unattended run has a budget it cannot argue with: a promotion quota, a kill-test bar, and a stopping rule that can end the project. | `qr/research/policy.py`, `qr policy` |
| **Trial log** | Every declaration, promotion and verdict is hash-chained. A boundary or quota that moves leaves `supersedes` in the chain. | `qr/validate/trial_log.py` |
| **Sealed log** | A sensitivity analysis reads the record without writing to it, so re-scoring known families cannot inflate the count. | `docs/11`, `SealedTrialLog` |
| **Twelve gates** | The verdict itself is deterministic: formulas, the same answer every run. | `docs/03`, `docs/09` |

### The policy, as declared

    qr policy declare

Those defaults are 2 a week, 5 a quarter, ≤250 variants a family, 3x costs at
the kill test, and 8 candidates before the stopping rule fires.

* **2 a week, 5 a quarter.** `docs/10_NEXT.md`'s "three to five candidates a
  quarter, not fifty", made mechanical.
* **≤250 variants a family.** A finer grid is not free; it is paid for by
  every family that comes after.
* **3x costs.** Stage 3's bar. Not 1.2x — that lesson is written up in
  `docs/08`.
* **8 candidates.** The stopping rule. Eight genuine, named mechanisms through
  the full gates with none surviving, and the finding is: *no edge is
  accessible at this account size with this data.* Write it up, stop, hold an
  index fund.

**`counts_from` is the detail that makes the last one honest.** Nine families
have already failed and none of them had a mechanism — they were patterns,
which is the diagnosis rather than nine attempts at the cure. Counting them
would fire the stopping rule before the new plan tested a single idea, so the
count starts at the sequence where the policy was declared. The same anchor
applies to the weekly quota, because a rate limit that retroactively charges
for last week is not a rate limit, it is an outage. (A test found that one, not
a reviewer.)

## The rest of the funnel, as built

**Stage 2, the mechanism memo.** `qr/research/mechanism.py`. Claude answers the
five questions with structured outputs; `triage()` then re-decides from the
structured fields **without reference to the model's own verdict**, because a
model asked to generate candidates and judge them will judge its own work
kindly. A question-2 answer drawn from price behaviour is killed; a crude
version that compiles to one of the nine already-failed families is killed
whatever the prose says; an idea needing data the lake lacks is *blocked* with
the dataset named, not killed. Needs `ANTHROPIC_API_KEY`.

**Stage 3, the kill tests.** `qr/research/killtest.py`. Runs the crude version
on the discovery side — refusing a panel that is not stamped, rather than
trusting the caller — and asks three questions in order: does the effect exist
*in the direction the memo committed to*, is it at least 3x costs, does
anything survive. The sign check is what stops a memo being retrofitted to its
result.

**The loop.** `qr autopilot`. Every exit is recorded in the chain, so the
morning's question is answered from the log rather than from scrollback.

**The gap that building it exposed.** Almost none of the mechanisms the
research plan is organised around can be tested with what is in the lake:
funding, open interest, liquidations, index membership, unlocks. The calendar
is the only one OHLCV supports, which is why `CalendarEvent` exists. Expect the
first nights to return mostly `blocked`, pointing at the same missing dataset —
that is the machine saying what to build next, and it is a more useful answer
than another runnable pattern.

## Why this is safe to leave alone

The agent cannot:

* look at validation data while exploring — the sandbox is stamped on the
  panel, gate 0 fails a discovery run, and `write_report` refuses to write one;
* promote more than the quota, or re-write the quota quietly;
* register a hypothesis after seeing its result — gate 0 compares the
  pre-registration's sequence against the first run's;
* widen a grid past the cap;
* run past the stopping rule;
* or hide any of it, because the log is a hash chain and every check reads it
  back out.

What the agent *can* do is choose which mechanisms to think about, which is
exactly the part worth automating and the part where being wrong is cheap.

## What is still yours

Two things, deliberately.

**The gate 10/11 sizing mathematics has never been independently reviewed**
(`docs/10_NEXT.md`, "Pending review"). An LLM checking another LLM's work fails
hardest exactly where the author was motivated, which is the case in question.
That review goes to Fable 5.1 in its own session, triggered by a person, before
any real money is sized.

**Nothing goes live on its own.** The funnel ends at a Hypothesis Report and,
if something ever clears all twelve gates, at incubation — a paper record gate
10 reads. The decision to fund anything is not in this loop and should not be.
