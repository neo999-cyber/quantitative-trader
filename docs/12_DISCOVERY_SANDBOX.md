# Stage 1 — the discovery sandbox

*Written 13 September 2026. Stage 1 of `docs/10_NEXT.md`, and the precondition
for everything after it.*

## The trap it removes

Every gate in this platform exists to stop a searcher fooling themselves, and
they work. The price is that **looking is expensive**: anything seen is
something the validation set is no longer innocent of, so browsing costs
evidence. Nine of nine families so far have been textbook strategies — TSMOM,
cross-sectional momentum, weekly reversal — and that is not a coincidence.
Nobody went looking, because looking had a price.

The sandbox makes looking free. A permanent slice of the data where anything
may be examined, in any order, as many times as you like, **and from which
nothing is ever reported**. Validation happens on the untouched remainder.

## How the line is drawn

    qr sandbox declare --market binance/spot --symbol-fraction 0.25
    qr sandbox declare --market tiingo/etf --mode period --period-end 2018-12-31
    qr sandbox show
    qr sandbox check --market binance/spot BTCUSDT ETHUSDT

**By a hash, not by a person.** Which symbols land in the sandbox is
`sha256(salt + symbol)`, fixed before anyone knows what is in them. A split
chosen by judgement is a split that can be re-chosen when the result
disappoints; a split chosen by SHA-256 cannot be argued with, including by the
person who ran it.

**Once, into the hash-chained trial log.** `qr sandbox declare` refuses a
second declaration for a market. Redrawing the boundary after seeing a result
is the single failure this whole idea exists to prevent, so it is not
discouraged, it is refused. `--force` exists for genuine mistakes — the wrong
market name, a fraction of 0.9 — and writes a record carrying `supersedes`, so
the chain shows that a line moved and when. Nothing can stop someone redrawing
a boundary. The log can stop them doing it invisibly.

**Two modes, because the two markets are not alike.**

| market | mode | why |
|---|---|---|
| `binance/spot` | `symbols`, 25% | 734 pairs can spare a quarter of themselves, and a symbol split is the stronger test: a finding has to survive on instruments it was never fitted to. |
| `tiingo/etf` | `period` | Twelve funds cannot spare three. There the boundary is a date and the sandbox gets the early years. |

`both` applies each rule together — the sandbox is a rectangle and everything
outside it is validation. It is the strictest and the most expensive.

### One consequence to state rather than discover later

The crypto universe is the **point-in-time top thirty by quote volume**. Remove
a quarter of all pairs before that ranking happens and validation's top thirty
is drawn from roughly 550 pairs instead of 734 — so it is a slightly different,
slightly less liquid set of names than the one `docs/06` ran on. Still deeply
liquid, and the ranking is still honest, but it is **not the same universe**,
and a future comparison between a sandbox-era result and `docs/06` has to say
so rather than treat them as like for like.

## Why it cannot leak

The sandbox's whole value is one promise: nothing from it reaches the record.
A promise with a single enforcement point is a promise one refactor away from
being broken, so there are three.

1. **`restrict()` stamps the panel.** The side travels with the data, not with
   the caller's intentions, so nothing downstream has to remember.
2. **Gate 0 fails a discovery panel.** Before any other gate runs, and
   regardless of how good the pre-registration is. A gate report computed on
   sandbox data is not a weak result, it is a category error.
3. **`write_report` refuses to write one.** Repeated at the point of writing
   because a report is the artefact that leaves the machine — it is what gets
   read, quoted and remembered — and gate 0 can be skipped with `--upto`.

`test_an_ordinary_run_is_untouched_by_any_of_this` is the fourth test that
matters: a panel that never went through `restrict()` claims no side and
behaves exactly as before. The sandbox costs nothing to anyone not using it.

## What this unlocks

Stages 2 and 3 of the research plan — write a mechanism memo, run cheap kill
tests — can now run **unattended and repeatedly**, because failures there are
free and nothing is being spent. That is the half of the funnel that should be
autonomous.

Stage 4 is the opposite and the distinction is not stylistic: every variant
raises gate 4's deflation bar for every future family, so an agent that decides
what to promote after seeing results will eventually promote noise *and* burn
the project's ability to detect a real edge. The trial log is already in the
thousands — `qr trial verify` prints the count. Autonomy there is safe only
under a promotion rule and a quota fixed in code before any run: rationing by
design, not by good intentions.

That quota is `qr/research/policy.py`, and the funnel that spends it is
`qr autopilot`. See `docs/13_AUTONOMY.md` and `docs/14_RUNNING_IT.md`.
