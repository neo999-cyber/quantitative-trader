# What twelve self-kills say

*13 September 2026. Three autopilot nights: one crypto with the original
briefs, then one ETF and one crypto with briefs written for each market.
Twelve candidates, twelve kills, none of them by the harness.*

## The result

Every candidate was killed **by the memo itself** — `triage()`'s own checks
never had to fire. The reasons were specific, and they were right. Sorted by
what actually stopped each one:

**The payer trades an instrument we cannot trade (7 of 12).**

| candidate | the objection |
|---|---|
| `perp_funding_carry_spot_only_v1` | "the transfer is real but structurally out of reach: funding is paid on perps" |
| `quarterly_expiry_window_v1` | "the forced trade is real but delta-neutral in aggregate: rollers roll" |
| `balanced_fund_month_end_rebalance_v1` | "the named forced trader does not trade our instruments" |
| `quarter_end_window_dressing_v1` | "no forced trader whose obligation maps onto a directional spot position" |
| `december_tax_loss_wash_sale_v1` | "the mechanism is imported from equities and does not survive translation" |
| `turn_of_month_flow_v1` | "the forced trader is an equities-market-structure artefact" |
| `index_recon_forced_basket_v1` | "the mechanism is real but acts on the constituents" |

**The mechanism holds and the data is not in the lake (3 of 12).**
`liquidation_cascade_aftermath_v1`, `token_unlock_cliff_window_v1` ("blocked on
data, not on logic — passes Q1 and Q2"), `bond_fund_redemption_credit_etf_v1`.

**Nobody is actually forced (2 of 12).** `cme_weekend_closure_monday_open_v1`
("a venue constraint, not an obligation") and
`mm_inventory_reversal_overnight_v1`.

## The finding

Only two of twelve failed because the *idea* was wrong. The other ten failed
on **access**: the forced trader is in a market this project cannot reach, or
the evidence of their forcing is in a dataset it does not hold.

That is a different answer from the one the nine pattern families gave, and a
more useful one. "Who is forced to trade?" turns out to have plenty of good
answers in crypto — they are simply all in the **derivatives** market. Funding
is paid on perpetuals. Liquidations happen to leveraged positions. Expiry
rolls happen in futures and options. This project trades **spot**, and spot is
where the people who are *not* forced trade.

The equity side is the same shape with a different cause. Balanced funds,
pension flows, index trackers and tax-loss sellers are all real forced
traders, and they trade **individual securities**. The twelve-fund ETF basket
sits one level up from where the obligation bites, and the memos said so
without being prompted: the flow that moves SPY's constituents is diluted
almost to nothing by the time it reaches SPY.

## What this does not mean

**It is not the stopping rule.** That rule counts candidates that went
*through the full gates* and failed — eight of those and the answer is "no
edge is accessible". These twelve never reached a pre-registration, so the
count is untouched, and `qr policy show` still reads 0 of 8. That is the
design working: dying at a memo costs a page of text and is not evidence about
whether an edge exists.

**It is not a mistuned bar.** The kill prompt is deliberately harsh, so twelve
for twelve deserves suspicion — but the objections are substantive and
checkable one by one, not the same lazy clause twelve times. Re-reading them,
each is a claim about the world that a person would have to argue with on the
merits.

**It is not "the briefs were bad" a second time.** The first night's briefs
genuinely were wrong — equities mechanisms aimed at a crypto universe. The
second and third used briefs written for each market and produced the same
structural answer. Rewriting them a third time would be iterating on an input
that is not the binding constraint.

## The decision this surfaces

The binding constraint is **instrument access and data**, not idea generation.
There are three honest responses and they are not equivalent.

**1. Get the data, keep trading spot.** Binance futures `fundingRate` and
`openInterestHist` are public and free. They do not let this project *collect*
funding, but they are the best available signal for when the crowded side is
paying — and a spot book can express "the levered crowd is long and paying to
stay long" as a directional view. This is the cheapest step: an ingestor, no
new venue, no new cost model, no new account. It also unblocks the three
candidates that failed only on data.

**2. Trade perpetuals.** This is where the payers are, and it is the honest
reading of every crypto kill above. It is also `PLAN.md`'s Phase 4 and a much
larger step: a funding leg in the cost model, a margin model, liquidation risk
of our own, and a product that can lose more than it holds. Not at $1,000, and
not before the gate 10/11 sizing mathematics has been reviewed.

**3. Accept that spot-only has no forced-trader edge and say so.** Defensible,
and it is the finding these nights point at. It would mean the honest answer
for this account is an index fund, arrived at faster and for a better reason
than the stopping rule would have given.

The ordering is: **(1) now, because it is free and it tests whether (2) is
worth it.** If funding and open interest carry no usable signal in spot, then
(2) is a large investment with no evidence behind it and (3) becomes the
answer. If they do, (2) has a reason.

## What changed in the code because of this

`Night.shopping_list()` counted only `blocked` candidates, and triage honours
a self-kill first — so a model that *notices* the data is missing kills its own
candidate, and the dataset it named was thrown away. The first two real nights
reported "0 blocked on data" and an empty shopping list while three memos said
"blocked on data" in as many words. It now counts every candidate that named a
missing dataset, killed ones included, ranked by how many ran into each.

The verdicts are unchanged, which is the point: whether an idea survives and
whether its data exists are different questions, and only the second one
belongs on a shopping list.
