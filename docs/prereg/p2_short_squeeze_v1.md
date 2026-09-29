# Pre-registration: `p2_short_squeeze_v1` — crowded shorts with rising fails-to-deliver, long-only

*Written 17 September 2026, before any run. The counts below were read
from the FINRA short-interest and SEC fails-to-deliver mirrors alone; no
price series was looked at (the price used for the filter is the SEC
file's own last-fail price, not a return).*

## Mechanism

A short position that is both crowded (many days of average volume to
cover) and under settlement stress (fails-to-deliver rising, so borrow is
scarce) faces forced covering: the lender recalls, the broker buys in, or
the short capitulates on any rally. That covering is the forced trade;
the long that fronts it is the strategy. Both inputs are public on a
schedule — FINRA publishes short interest about nine business days after
the 15th and the last day of each month; the SEC publishes fails about two
weeks after each half-month — so the rule reads nothing before its
publication date, and the effect it claims is the one *after* both
publications.

Long-only (no shorting below $2,000). This is a squeeze bet, not a
short-of-crowded-shorts bet; the reverse is not claimed.

## Predicted sign and size

**Positive against the exposure-matched eligible universe.** Top-ten
names by days-to-cover among those with rising fails earn **+1% to +4%**
over 10 sessions beyond the universe, with high dispersion; net alpha t
**above 2** against the equal-weight eligible universe; a $1,000
five-position book with net Sharpe **0.2 to 0.5 above** that benchmark.
The mirror (lowest days-to-cover among the same names) earns nothing.
A net Sharpe above 2 is a reason to look for a leak (a publication stamp
earlier than the data could have been public).

## Data

- **FINRA consolidated short interest** (`mirror/finra/shortinterest`,
  179 settlement dates 2019-01-15 → 2026-08-31, `qr/data/short_data.py`):
  `short_interest`, `adv`, `days_to_cover` per symbol and settlement
  date. Availability: the FINRA file's HTTP `Last-Modified` where it is
  credible (observed 12–41 calendar days after settlement, median 17),
  else **settlement + 20 calendar days**, whichever is *later* — the
  conservative reading; FINRA's stated schedule is about nine business
  days.
- **SEC fails-to-deliver** (`mirror/sec/ftd`, half-months 2017-06b →
  2026-08b): per symbol and half, the sum of fails × price (`fails_value`)
  and the last fail price. Availability: the SEC file's `Last-Modified`
  where credible (files from 2021 on; observed 13–37 days after the
  half's end, median 15) else **half-end + 20 calendar days**, whichever
  is later. Files before December 2020 all carry the 2020-12-19 stamp of
  a site migration and use the rule.
- Prices from QuantConnect's survivorship-free US equities, daily, on the
  free tier (`qc/e7_*.py`, events shipped as `qc/e7_events.b64`), as for
  E4 and E5. Reg SHO daily short volume is mirrored but **not used** by
  this rule; a second version may add it.

## Universe

At the SI settlement date `S`: symbol in the FINRA file with `adv ≥ 1M`
shares (2,121 names a date, median) and a fail price **≥ $5**; US common
stock at entry (LEAN's `HasFundamentalData` and price > $5 re-checked at
the open). The eligible universe for the benchmark is the E5 equal-weight
top-500-by-dollar-volume book, annual rebalance (`qc/e5_benchmark_main.py`),
the closest available comparator, stated as such.

## Rule and parameters

For each settlement date `S` (the 15th or the last day of the month):

1. `rising` = the symbol's `fails_value` in the half-month ending at `S`
   is at least **2×** the prior half's and at least **$500,000**.
2. Among `rising` names in the universe, rank by `days_to_cover` at `S`,
   highest first (median 458 qualifying names a date, minimum 33; the
   10th-ranked name's days-to-cover has median 10.7).
3. Entry session `E` = the first session after **both** the SI file and
   the FTD file for that half are available (rule above), at the **open**;
   up to `n` names, equal slices, whole shares, $1,000 book.
4. Hold `hold` sessions; sell at the open. A name already held is not
   re-bought; positions from the previous publication that have not
   expired stay (so the book can briefly hold up to 2·`n` names).

| Parameter | Range | Swept? |
|---|---|---|
| `n` (names a publication) | 5, 10 | yes |
| `hold` (sessions) | 10, 20 | yes |
| `rising` multiple / floor | 2×, $500k | fixed |
| `adv` floor | 1M shares | fixed |

**4 variants** (1,709 top-10 events over 179 dates, 541 distinct symbols).
No $100,000 companion: the names are by construction the ones a $100,000
book would move.

## Cost model, benchmark, controls

`alpaca_zero` (6 bps a round trip, charged locally from the order count;
12 stressed; these names have wider spreads than E4/E5's, so a **20 bps**
stress is also reported). Benchmark: the E5 equal-weight eligible universe
scaled to the book's mean exposure. Controls: **low-cover mirror** — the
same rule with the `n` *lowest* days-to-cover among the same `rising`
names (the mechanism says this earns nothing); **random control** — `n`
names drawn at random from the `rising` set each date (one QC draw).

## What would falsify this

- Top-ten drift over 10 sessions below +1% versus the universe, or the
  low-cover mirror earning as much → the mechanism is not there.
- Net alpha t below 2 against the benchmark → the return is beta or
  small-cap exposure.
- SPA p above 0.5 → gate 5. DSR below 0.90 over 4 → gate 4.
- Holdout Sharpe negative or below half the deflated Sharpe → gate 9.

## Out-of-sample period

1 September 2025 → 31 August 2026, opened once after gates 1–8 (gates 1,
6 and 8 as far as an external engine allows, as for E4 and E5).

## Prior

Squeeze candidates are the most-watched list in retail markets since
2021; whatever drift exists is likely front-run by the publication date.
Expected: a positive but noisy top-ten drift, wide dispersion, gate 3 t
between 1 and 2, gate 4 and 5 failing as E4 and E5 did.
