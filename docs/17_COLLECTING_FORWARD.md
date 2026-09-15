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

## The first live run

**The endpoint and the field names were right.** The first attempt on a
networked machine reached the iShares screener, parsed seven funds and their
share counts, and then crashed formatting them for the screen — `table()` takes
a frame and was handed a list.

Worth recording because of which part broke. The fetch and the parse were the
guesses, written against a documented shape nobody could load; the print was
the part that could have been checked here and was not. Both now have tests,
and the print has one of its own.

### What the screener actually publishes

Seven funds, with **net assets and NAV but no share count**. It does not need
one: net assets are shares times NAV by definition, so the count is their
quotient — a division, not an estimate. Rows record which of the two they came
from (`shares_basis`), because the two fail differently.

**And that exposes the question that decides whether any of this is worth
collecting: precision.** A daily creation is on the order of 0.1% of a fund. If
the issuer publishes net assets to four significant figures, the flow is
smaller than the rounding — every day would read as either zero or a step of
0.05% — and *collecting for a year does not fix it*, because the missing
information was never published.

So `--dry-run` now prints the raw figures rather than passing them through
`table()`, whose four-significant-figure formatting is exactly what would hide
this, and reports the significant digits per fund. `precision_warning()` says
so in a sentence when the source is too coarse, on the first run rather than in
six months.

If the warning fires, this dataset is dead as a free source and the honest
options are a vendor or nothing — which is a much better thing to learn on day
one than after a year of cron jobs.

### The answer, and a check that was measuring the wrong thing

The live counts:

| | derived shares | rounds to |
|---|---|---|
| EFA | 739,199,999.43 | 739,200,000 |
| EEM | 464,850,001.75 | 464,850,000 |
| IWM | 271,200,000.46 | 271,200,000 |
| HYG | 184,599,999.59 | 184,600,000 |

**Every one is a multiple of 50,000 shares — the iShares creation unit** — with
a sub-share remainder from dividing by a four-decimal NAV. So the source is
exactly as precise as the process it describes: creations happen in whole
units, and whole units are what it reports. For HYG, the smallest fund here,
50,000 shares is 0.027%, comfortably inside a day's flow. **The dataset works.**

The first version of the check would have said so for the wrong reason. It
counted significant digits in *net assets* and got 13 to 17 — an emphatic
all-clear. But the screener does not publish net assets and a share count
independently: it publishes a count, and net assets are that count times the
NAV. The trailing digits are arithmetic, not information, and the check was
reading its own multiplication.

`share_quantum()` asks the question that was meant: what step do the published
counts actually move in? `significant_digits()` is kept, and its docstring now
says what it is not for.

That is the fourth time in two days that the reassuring number turned out to be
measuring something other than what it said — and the first time it was caught
before anything was built on it rather than after.

## Scheduling it, which is the part that actually went wrong

The first attempt was `crontab -e` and a line of instructions with a `#`
comment. Two failures, both avoidable:

* `crontab -e` opens an editor. Quitting it saves nothing, and `no crontab for
  anoop — using an empty one` followed by `no changes made` means exactly that.
* The comment line was then pasted into the shell, which answered `command not
  found: #`. Interactive `zsh` does not treat `#` as a comment — the same trap
  `docs/14` already documents for `qr data ingest # …`. Twice now.

**And a daily alarm is the wrong shape anyway.** A MacBook Air asleep at 22:00
never fires one, and a missed day cannot be recovered: nobody publishes a past
day's share count. That is the difference between this dataset and every other
one in the project — with Binance klines a gap is a re-download, here a gap is
permanent.

So the collector is built to be run **often** and to do nothing most of the
time. `already_recorded_today()` is checked *before* the request, so
twenty-three of twenty-four hourly attempts cost one file read. `--force`
overrides it, because a second reading in a day is a fact about the day.

### On the server, which is where it belongs

The Hetzner box is always on, which is the whole argument:

    */30 9-23 * * 1-5  cd ~/quantitative-trader && .venv/bin/qr data flows-collect >> ~/flows.log 2>&1

Install it without an editor:

    (crontab -l 2>/dev/null; echo '*/30 9-23 * * 1-5 cd ~/quantitative-trader && .venv/bin/qr data flows-collect >> ~/flows.log 2>&1') | crontab -
    crontab -l

Every half hour on weekdays; the first successful one each day records and the
rest exit immediately.

### On the laptop, if the server is not set up yet

`cron` is the wrong tool on macOS — it does not catch up after sleep. `launchd`
does: a `StartInterval` job runs at the next wake if its slot was missed.

    qr data flows-collect --print-launchd > ~/Library/LaunchAgents/com.qr.flows.plist
    launchctl load ~/Library/LaunchAgents/com.qr.flows.plist

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
