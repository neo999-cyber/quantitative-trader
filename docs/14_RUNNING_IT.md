# Running it — the laptop guide

*Written 13 September 2026. What to type, in order, to leave the machine
working overnight.*

Read `docs/13_AUTONOMY.md` first for *why* the boundaries are where they are.
This is the how.

## One note on pasting

Every block below is meant to be run **one line at a time**. Interactive `zsh`
does not treat `#` as a comment unless `setopt interactive_comments` is set, so
a command pasted with a trailing `# explanation` arrives at the program as an
argument and is rejected — which is exactly what an earlier version of this
document caused. Nothing here has trailing comments any more; the explanations
sit under each block.

## Once: get the laptop onto this branch

The checkout is on `claude/admiring-ptolemy-tfp528`, which has none of this.

    cd ~/quantitative-trader
    git fetch origin claude/funny-faraday-nizzck
    git checkout claude/funny-faraday-nizzck
    source .venv/bin/activate
    pip install -e ".[dev,qr,gates,ai]"
    pytest -q
    export ANTHROPIC_API_KEY=...

Expect `pytest -q` to be clean before trusting anything below.
`ANTHROPIC_API_KEY` is what the memo generator uses.

## Once: fill the lake

Needs network; the cloud sandbox has none, which is why this step is yours.

    qr data pull
    qr data ingest
    qr data qa
    qr data etf-pull
    qr data etf-ingest

`pull` fetches the Binance bucket into the local mirror — tens of thousands of
small files, so it is the slow one. `ingest` turns the mirror into the Parquet
lake and the DuckDB manifest. **Read the `qa` report before believing anything
downstream.** The two `etf-` commands are the Tiingo side, needed to finish
Step 0.

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

## Perp funding — pull it once

The mechanism nights asked for this more than anything else (`docs/15`).

    qr data funding-pull --limit 40
    qr data funding-ingest

`funding-pull` needs network and is the **verification** of paths this
repository could never check: it is written from Binance's published bucket
layout and has never met the live bucket. An empty listing means the prefix is
wrong; a parse error quotes the header that actually arrived, and that header
is the correction to make. `--limit 40` keeps the first pull small enough to
find out cheaply. Drop `--metrics` if the daily open-interest files are too
many to start with.

Once ingested, `load_panel` joins funding and open interest onto the spot
panel automatically, and `qr autopilot --asset crypto` can compile a memo to
`FundingTilt`. Nothing collects funding — no spot position can — so what the
feature supports is "the levered crowd is positioned this way and paying for
it", and a memo proposing to collect it should still be killed.

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

    qr autopilot --briefs-file my_briefs.txt

One brief per paragraph, blank line between them.

## Every morning

    qr policy show
    qr trial verify
    qr site

`policy show` is what is left of the quota and the stopping rule, `trial
verify` walks the hash chain, and `site` renders every gate report as one
page.

The night's table is printed at the end of the run and every line of it is in
the log. Three outcomes are worth reading carefully:

* **`blocked`** — a coherent mechanism the lake cannot test. The run prints the
  dataset that would unblock it. This is the most valuable output of a night
  where nothing ran; it is a shopping list, not a failure.
* **`promoted`** — a candidate went through all twelve gates. Read the report.
  Passing is the hoped-for outcome, not the target.
* **`stopped`** — the stopping rule fired. Do not raise the cap.

## What the first night actually did

*Run on 13 September 2026, `--limit 3`, crypto.*

All three candidates were **killed by the memo itself**, and the reasons were
right:

* month-end rebalancing — "the forced trader is real but trades a different
  asset class";
* quarter end — "no named forced trader in the tradable universe";
* December tax-loss selling — "crypto has no wash-sale rule".

That is the stage doing its job, on the wrong input. The briefs named payers
who trade **equities and bonds** and were aimed at a Binance spot universe. No
60/40 mandate rebalances into altcoins, and without a wash-sale rule a crypto
holder can sell and rebuy the same minute, so there is no deadline and no
forced January repurchase.

The seed briefs are now per asset class (`BRIEFS_BY_ASSET`): funding,
liquidation cascades, quarterly expiry, unlocks and the CME weekend for
crypto; balanced-fund rebalancing, quarter end, wash-sale December, turn of
month, index reconstitution and redemption pressure for the ETF basket, which
is twelve funds including SPY, TLT, LQD and HYG — precisely what a 60/40
mandate holds.

**So run both:**

    qr autopilot --asset etf --no-promote
    qr autopilot --asset crypto --no-promote

The calendar mechanisms belong to the ETF side. On the crypto side, expect
most briefs to come back **blocked**: funding, open interest, liquidations and
unlocks are the clearest payers in that market and none of their data is in
the lake. `qr/research/features.py` names what each one needs, and the run
prints the list. That is a shopping list, not a failure — and if the first
nights keep pointing at Binance futures `fundingRate` and `openInterestHist`
(both public, both free), the machine is telling you the next useful job is an
ingestor rather than another strategy.

## Can this run while you sleep?

Partly, and the honest boundary is worth knowing before you set a cron job.

**What genuinely runs unattended:** `qr autopilot`. It is one command, every
exit is recorded, and the policy stops it. On macOS wrap it so the laptop stays
awake — `caffeinate -i qr autopilot --asset crypto 2> autopilot.log`.

**What it will not do is discover anything new by running again.** Three nights
produced twelve candidates and twelve kills with one structural answer
(`docs/15`). Re-running the same briefs against the same lake re-derives the
same answer and spends API tokens doing it. The autopilot is worth running
again **after the lake changes** — a new dataset, a new primitive — and not
before.

That is the real limit on autonomy here, and it is not a missing feature. The
funnel is gated on *inputs*: new data, or new instruments. Neither arrives by
running the loop harder, and both need a decision that is yours. The machine
can tell you which input is binding — it did — but it cannot go and get one.

**So the useful overnight work is code, not runs.** Building the funding
ingestor while you slept was worth a night; running the autopilot again would
not have been.

## What is still yours

* **The gate 10/11 sizing mathematics has never been independently reviewed.**
  The prompt is in `docs/10_NEXT.md`. Fable 5.1, its own session, before any
  real money is sized. An LLM checking another LLM fails hardest exactly where
  the author was motivated, which is the case here.
* **Nothing goes live on its own.** The loop ends at a Hypothesis Report, and
  anything that clears all twelve gates goes to incubation — a paper record
  gate 10 reads over weeks. No part of this funds anything.
