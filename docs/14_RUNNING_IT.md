# Running it — the laptop guide

*Written 13 September 2026. What to type, in order, to leave the machine
working overnight.*

Read `docs/13_AUTONOMY.md` first for *why* the boundaries are where they are.
This is the how.

## Once: get the laptop onto this branch

The checkout is on `claude/admiring-ptolemy-tfp528`, which has none of this.

    cd ~/quantitative-trader
    git fetch origin claude/funny-faraday-nizzck
    git checkout claude/funny-faraday-nizzck
    source .venv/bin/activate
    pip install -e ".[dev,qr,gates,ai]"
    pytest -q                       # expect a clean run before trusting anything
    export ANTHROPIC_API_KEY=...    # the memo generator needs it

## Once: fill the lake

Needs network; the cloud sandbox has none, which is why this step is yours.

    qr data pull        # Binance bucket -> local mirror (tens of thousands of files)
    qr data ingest      # mirror -> Parquet lake + DuckDB manifest
    qr data qa          # read this before believing anything downstream
    qr data etf-pull && qr data etf-ingest      # the ETF side, if you want Step 0 finished

## Once, and irreversibly: the two pre-commitments

**Read these before typing them.** Both are refused a second time, and both
are the kind of decision that is worthless if it can be revisited after a
disappointing result. A forced change is possible and is recorded in the chain
as a supersession, where any later reader will find it.

    qr sandbox declare --market binance/spot --symbol-fraction 0.25 \
        --note "stage 1: a quarter of the pairs, free to explore, never reported"

    qr sandbox declare --market tiingo/etf --mode period --period-end 2018-12-31 \
        --note "twelve funds cannot spare three; the boundary is a date"

    qr policy declare --note "2/week, 5/quarter, 3x costs, stop at eight mechanisms"

Check them:

    qr sandbox show
    qr policy show

What you are fixing, and why it cannot be nudged later:

* **A quarter of the crypto pairs become unreportable forever.** That is the
  price of being able to look at them freely. Note the consequence in
  `docs/12`: validation's top-30 is then drawn from ~550 pairs rather than 734,
  so it is not the same universe `docs/06` ran on.
* **Two promotions a week, five a quarter.** Every variant that reaches the
  gates raises gate 4's bar for every family after it, permanently.
* **Eight mechanisms, then stop.** If eight candidates with named payers go
  through the full gates and none survives, the finding is that no edge is
  accessible at this account size with this data — write it up, hold an index
  fund. That is fixed now precisely so it cannot be renegotiated at the time.

## Finish Step 0 while you are there

    qr account-size --asset all --out reports/account_size.csv

Paste the two tables into `docs/11_ACCOUNT_SIZE_SWEEP.md`. The crypto rows must
read `size-independent`; anything else is a defect report, not a result.

## Every night

    qr autopilot --asset crypto 2> autopilot.log

That is the whole command. It works through the briefs until the briefs run
out or the policy stops it, and for each one:

1. **Memo.** Claude answers the five questions for one candidate.
2. **Triage.** The harness re-decides without reference to the model's own
   verdict — a "mechanism" that turns out to be a statement about prices is
   killed, a restatement of an already-failed family is killed, an idea needing
   data the lake lacks is *blocked* rather than killed.
3. **Kill test**, in the sandbox only. Does the effect exist, in the direction
   the memo committed to? Is it ≥3× costs? Does anything survive the floor?
4. **Quota**, checked before the memo is even written, so a night cannot spend
   compute learning something known at the start.
5. **Pre-register, then the twelve gates** on validation data, then the report.

To watch it think without letting it register anything:

    qr autopilot --no-promote --limit 3

To point it at your own ideas:

    qr autopilot --briefs-file my_briefs.txt      # blank line between briefs

## Every morning

    qr policy show      # what is left of the quota and the stopping rule
    qr trial verify     # the chain, unbroken
    qr site             # every gate report as one page

The night's table is printed at the end of the run and every line of it is in
the log. Three outcomes are worth reading carefully:

* **`blocked`** — a coherent mechanism the lake cannot test. The run prints the
  dataset that would unblock it. This is the most valuable output of a night
  where nothing ran; it is a shopping list, not a failure.
* **`promoted`** — a candidate went through all twelve gates. Read the report.
  Passing is the hoped-for outcome, not the target.
* **`stopped`** — the stopping rule fired. Do not raise the cap.

## What will probably happen, so the result can disagree

Most briefs will be **blocked**, not killed. Funding, liquidations, index
inclusion and unlocks are the mechanisms with the clearest payers, and none of
their data is in the lake — `qr/research/features.py` names what each one
needs. The calendar family is the only mechanism today's data can actually
test.

That is a real answer to "who is forced to trade?", and it says the next
useful engineering job is probably an ingestor for Binance futures
`fundingRate` and `openInterestHist` — both public, both free — rather than
another strategy. If the first few nights come back as a list of blocked ideas
pointing at the same dataset, that is the machine telling you what to build,
and it is worth more than another momentum variant that happened to be
runnable.

## What is still yours

* **The gate 10/11 sizing mathematics has never been independently reviewed.**
  The prompt is in `docs/10_NEXT.md`. Fable 5.1, its own session, before any
  real money is sized. An LLM checking another LLM fails hardest exactly where
  the author was motivated, which is the case here.
* **Nothing goes live on its own.** The loop ends at a Hypothesis Report, and
  anything that clears all twelve gates goes to incubation — a paper record
  gate 10 reads over weeks. No part of this funds anything.
