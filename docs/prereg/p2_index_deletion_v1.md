# Pre-registration: `p2_index_deletion_v1` — buy what the index funds are forced to sell, long-only

*Drafted 17 September 2026 (`docs/research/10`), before any run. **Not
registered**: the Programme 2 counter is full (`docs/23`) and this file
becomes a registration only with the owner's yes, through `qr trial
prereg`. The counts below are from the S&P 500 change table alone
(`scripts/s1_events.py`); no price series was looked at.*

## Mechanism

When S&P Dow Jones removes a company from the S&P 500 for "market
capitalization changes" — it has become too small, not because it was
acquired — every tracker must sell its entire position at the close of the
effective date, whatever the price. That sale is the forced trade; the
seller is price-insensitive by mandate and the amount is a known share of
the float. The buyer on the other side is anyone with no mandate, which is
what a $1,000 account is. The published evidence (Arnott, Kalesnik & Wu,
*FAJ* 2023, S&P 500 1989–2021): discretionary deletions beat the market by
**20.4%** in the year after the trade date; additions lag by 1.6%.

Long-only. The claim is about the deleted names after the sale, not
about front-running the sale: entry is the first open *after* the
effective date, when the forced selling is over.

## Predicted sign and size

**Positive against the exposure-matched eligible universe.** A book of the
discretionary deletions held twelve months earns **+8% to +20%** a year
beyond the universe; net alpha t **above 2** against the equal-weight
universe scaled to the book's exposure; the additions mirror earns no
more than the universe. Entering 63 sessions late (the delayed control)
captures **less than half** of the effect — if it captures as much, the
return is a value tilt, not the reconstitution sale, and the mechanism
claim is wrong even if the return is real.

## Data

- **Events:** the dated S&P 500 change table (Wikipedia, *Historical
  components of the S&P 500*, sourced to S&P press releases), read on 17
  September 2026 and frozen as `docs/prereg/data/s1_sp500_changes.csv`
  and `qc/s1_events.b64` (SHA-256 `5bd5190b…`). 407 changes; **161
  discretionary deletions** (154 from 2007, the table's complete period;
  reasons "market capitalization changes", float, or reincorporation —
  every one a forced sale at a price) and 388 additions. Removals for
  acquisition, merger, bankruptcy or spin-off are excluded: there is no
  seller at a market price.
- **Availability:** the effective date. The announcement (3–10 days
  earlier) is not used.
- **Prices:** QuantConnect's survivorship-free US equities, daily, free
  tier (`qc/s1_*.py`), as for E4, E5 and E7. Deleted names that later
  delist are carried to their last print by LEAN; that is the point of
  using it.

## Universe

Every discretionary deletion effective 2 January 2008 → 31 August 2024
(in-sample entries; the last twelve-month hold closes 31 August 2025).
Price at entry ≥ $1. Benchmark: the E5 equal-weight top-500-by-dollar-
volume book (`qc/e5_benchmark_main.py`) scaled to the book's mean
exposure, the closest available comparator, stated as such.

## Rule and parameters

1. On the first session after the effective date (plus `delay`
   sessions), buy the deleted name at the **open**, one slot of a
   `slots`-way book, whole shares, $1,000.
2. Hold `hold` sessions; sell at the open. A full book skips the name
   (logged); a slot that buys no whole share skips the name (logged).

| Parameter | Range | Swept? |
|---|---|---|
| `hold` (sessions) | 126, 252 | yes |
| `delay` (sessions after effective date) | 0, 5 | yes |
| `slots` | 10 | fixed |
| price floor | $1 | fixed |

**4 variants** (`s1_h252_d0`, `s1_h252_d5`, `s1_h126_d0`, `s1_h126_d5`);
~9 deletions a year, so a 252-session book holds roughly its ten slots.
A **$10,000 companion** at the same grid is run for sizing (gate 10/11),
not as a separate hypothesis: deleted names were S&P 500 members and
capacity is not in question below seven figures.

## Cost model, benchmark, controls

`alpaca_zero` (6 bps a round trip, charged locally from the order count;
12 stressed). Two round trips a year per slot: costs are immaterial and
the family cannot fail gate 2 on them — it can only fail on the effect.
Controls: **additions mirror** (`s1_ctrl_additions`: the added names,
same entry and hold — the mechanism says these earn nothing extra);
**delayed entry** (`s1_ctrl_delayed`: the same deletions bought 63
sessions late — separates the reconstitution sale from a value tilt).

## What would falsify this

- Deletions' twelve-month excess return below +8% over the universe, or
  the additions mirror earning as much → the effect is not there or is
  the market.
- Delayed entry capturing more than half of it → not a reconstitution
  effect; the family is a value screen and is withdrawn as such.
- Net alpha t below 2 against the exposure-matched benchmark → beta or
  small-cap exposure.
- SPA p above 0.5 → gate 5. DSR below 0.90 over 4 → gate 4.
- Holdout: the deletions effective 1 September 2024 → 31 August 2025,
  held to 31 August 2026 — one year of entries, ~12 names — opened once
  after gates 1–8. A negative holdout excess return fails; with twelve
  names a positive one is weak evidence and is reported as such.

## Prior

The paper's 20% is an average over thirty years with a wide interval and
the effect is widely published since 2023; a decay is expected. The
honest prior: positive, +5% to +15%, gate 3 t between 1.5 and 3 on ~150
events, gate 4 passing (four variants), the additions mirror flat. This
is the slowest family in the programme: a live verdict is measured in
years, which is why it is worth running only if the owner is content to
hold names for a year.
