# Collecting forward: the only input we can still get for nothing

*14 September 2026. What the shopping list actually contained once each entry
was priced, and why one of the four is being built.*

## The list, priced

The autopilot nights named four datasets. `docs/15` treats them as a shopping
list; this is what happened when someone tried to shop.

| | Obtainable? | Real blocker | Survives our own mechanism bar? |
|---|---|---|---|
| **ETF creation/redemption flow** | Forward, free. History is sold. | No free history exists | **Yes** — the authorised participant is forced **in our instrument** |
| **Binance liquidations** | Forward, free (live stream only) | Six months before it is usable | **No** — killed twice on transmission, not on data |
| **Index reconstitution** | Announcements are public and scattered | Scraping, and point-in-time | **No** — the forced buying is in **single stocks**; we trade ETFs |
| **Token unlocks** | Scrapeable | Point-in-time: schedules are revised retroactively | Yes, but the tokens are small and dear to trade |

Two of the four **fail on reasoning, not on data**, and that is the more
useful half of this table. Liquidations and reconstitution were each killed by
memos for a reason the data does not touch: the forced trade happens in an
instrument this project does not trade. Buying or collecting them would be work
that cannot pay off, and the earlier suggestion in this session to start
recording liquidations was wrong for exactly that reason.

## The point-in-time trap, which is what actually kills these

The instinct is that data is a purchase. For this kind of data it is not,
because what you need is **what was known on the day**, not what the source says
now. Unlock calendars are revised. Flow figures are restated. An index
membership list shows today's members. Use any of those against past dates and
the backtest has been told the future: it will look wonderful and mean nothing.

This is why "record it ourselves" is not merely the cheap option. **Data you
record yourself is point-in-time by construction** — you cannot write down what
you do not yet know. It is the same property that made the perpetual funding
data trustworthy the moment it landed.

## What was checked, and what it cost

`scripts/probe_etf_flows.py`, run before anything was built:

    HTTP 403 — {"detail":"You do not have permission to access the Mutual Fund API"}

A 403, not a 404: Tiingo's fund endpoint exists and this plan does not include
it. That leaves three doors, and one of them closes itself — **buying the
add-on to discover whether it carries history is the wrong order.** We do not
know that it does. Paying to find out is how a research budget becomes a
subscription list.

The other two are: buy history from a vendor (Intrinio, EODHD, ETF Global), or
record it. The second costs nothing but patience and is therefore the one that
does not need a decision.

## What was built

`qr data flows-collect`, designed as a cron job:

    qr data flows-collect

One line per fund per run, appended, never rewritten — a correction would
reintroduce the revision problem the whole exercise exists to avoid. It reads
the seven basket members BlackRock runs (IWM, EFA, EEM, TLT, IEF, LQD, HYG),
because that is one issuer and one endpoint: if the shape is wrong it is wrong
once rather than in four different ways. The daily change in shares
outstanding, times NAV, is the creation/redemption.

**The endpoint has never been reached from where this was written.** The
sandbox has no egress to issuer sites, so the URL and the field names come from
the documented shape, exactly as the Binance funding paths did. The first run
on a networked machine is the verification. The parser quotes the fields it
actually received, and `--dump` keeps the payload, so a wrong guess costs one
run rather than two:

    qr data flows-collect --dry-run --dump lake/flows/raw.json

## What this is worth, stated honestly

Low, and worth doing anyway.

* **A year of collection is ~250 daily observations and twelve month-ends.**
  Enough to test a daily flow signal; not remotely enough to test a month-end
  one. The dataset that arrives first is the one that answers the narrower
  question.
* **The wall does not move.** Whatever it finds still has to beat holding the
  basket, which beat the one real effect this project measured at every account
  size from $1,000 to $100,000 (`docs/15`). New data buys new mechanisms to
  test. It does not lower that bar.
* **It costs nothing and it is time-sensitive.** Not starting has a price that
  is invisible today and obvious in six months, which is the only argument for
  doing it now rather than deciding later.

`features.py` still reports `fund_flows` as blocked, and will keep doing so
until the file is long enough to test with. Collection starting is not the same
as having the data, and a registry that conflated the two would send a memo to
a kill test with eleven rows.
