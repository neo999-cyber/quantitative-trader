# Pre-registration: `p2_pead_v1` — post-earnings-announcement drift, small and mid caps, long-only

*Written 16 September 2026, before any run. The event file was built and
counted before this document (156,537 earnings 8-Ks with a point-in-time
ticker, 2010 → 2026, 7,123 symbols); no return was looked at.*

## Mechanism

Prices under-react to earnings news and drift in its direction for weeks;
the effect has shrunk in large caps where arbitrage is cheap and persists
where it is not (2025 reviews; `docs/20` §6 E4). The forced party is the
investor who cannot or will not process the number on the day; the drift
is their delayed trade. The signal is public the moment the earnings 8-K
(Item 2.02) is accepted by EDGAR; the surprise is proxied by the
**announcement return**, the market's own first reading, so no estimate
data is needed and no look-ahead is possible: the rule enters only after
that return is observed.

Long-only (no shorting below $2,000): the bottom decile short is the pair,
pre-registered later, not claimed.

## Predicted sign and size

**Positive against the exposure-matched eligible universe.** Top-decile
events drift **+1% to +3%** over 60 sessions beyond the universe, net
alpha t **above 2** against the equal-weight eligible universe; a $1,000
four-position book with net Sharpe **0.2 to 0.5 above** that benchmark.
The 20-session hold is the shorter declared variant. A net Sharpe above 2
is a reason to look for a leak (an acceptance stamp before the release).

## Data

`reference/earnings_8k_events.parquet` (`qr/data/earnings.py`): every 8-K
with Item 2.02 in the cached EDGAR submissions of 8,186 issuers,
`published_at` = EDGAR acceptance time; ticker as of the event from the
Form 4 data sets' issuer symbol nearest in time (58% of events map; the
rest are issuers with no Form 4 in 400 days, mostly funds and trusts, and
are dropped — stated, not corrected). Amendments (8-K/A) excluded. Prices
from QuantConnect's survivorship-free US equities, daily, on the free tier
(`qc/e4_main.py`), as for E5.

## Universe

At entry: US common stock, price > $5, 20-session median dollar volume >
$5M, **market capitalisation below $10B** (small and mid caps; Morningstar
fundamentals in LEAN). The eligible universe for the benchmark is the same
without the cap filter's upper bound — the E5 equal-weight benchmark
(top-500 by dollar volume, annual rebalance; `qc/e5_benchmark_main.py`)
is reused, stated as the closest available comparator.

## Rule and parameters

Announcement session `A` = the session on which the 8-K's acceptance time
falls if before 16:00 ET, else the next session. Announcement return =
close(A) / close(A−1) − 1 (an after-close release is read on the next
session's close against the prior close). Rank each event's announcement
return against the trailing **250 events** before it (a rolling
cross-section); enter at the **open of A+1** if the event is in the top
`decile` of that window, up to `max_positions` names, equal slices, whole
shares; hold `hold` sessions; sell at the open. Highest announcement
return first when more fire than there is room.

| Parameter | Range | Swept? |
|---|---|---|
| `hold` (sessions) | 20, 60 | yes |
| `top` (share of the trailing window) | 0.10, 0.20 | yes |
| `max_positions` ($1,000 book) | 4 | fixed |
| `max_cap_usd` | 10e9 | fixed |
| `window` (events) | 250 | fixed |

**4 variants.** A $100,000 twenty-position companion is run beside it, as
for E1 and E5.

## Cost model, benchmark, controls

`alpaca_zero` (6 bps a round trip, charged locally from the order count as
for E5; 12 stressed). Benchmark: the E5 equal-weight eligible universe
scaled to the book's mean exposure. Controls: **random-event control** —
the same book on events drawn at random from the window rather than the
top decile (one QC draw; `mode=random`); **bottom-decile mirror**
(`top` applied to the *bottom* of the window, long): the mechanism says
this loses.

## What would falsify this

- Top-decile drift over 60 sessions below +1% versus the universe, or the
  bottom-decile mirror earning as much → the mechanism is not there.
- Net alpha t below 2 against the benchmark → the return is beta.
- SPA p above 0.5 → gate 5.
- DSR below 0.90 over 4 → gate 4.
- Holdout Sharpe negative or below half the deflated Sharpe → gate 9.

## Out-of-sample period

1 September 2025 → 31 August 2026, opened once after gates 1–8 (gates 1,
6 and 8 as far as an external engine allows, as for E5).

## Prior

A small positive drift that a four-position book turns into noise: gate 3
passes, gate 5's SPA fails around 0.2–0.4, as E5 did.
