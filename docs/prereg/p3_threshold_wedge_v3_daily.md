# Pre-registration: `p3_threshold_wedge_v3_daily` — the same wedge, on Polymarket's daily BTC/ETH/SOL ladders

*Drafted 13 October 2026 after the parser dry-run (`reports/p3/p3a_v2_dryrun_2026-10-13.md`,
trial-log note 940) showed that the recording v2 reads holds 17 settlement
ladders in total and cannot reach v2's minimum sample before 2027. The
owner chose option B of `docs/31` §16 — record the daily ladders forward
and write this memo — and with it **a fourth Programme 3 registration**;
the counter of three is extended to four by that decision. Written before
any line of the daily-ladder recording was read for a wedge: the recorder
admitted them at 04:53 UTC today, and nothing has been read since but the
hourly "N active markets" line. v2 (seq 934) stands as registered and is
deferred by its own rule; v1's daily finding (+2.6 points at k = 5, t 2.0,
placebo below, `docs/31` §9) is the only wedge number known. This memo
changes the **universe and the volatility input**; the mechanism, the
rule, the fill model and the controls are v2's.*

## Mechanism

Unchanged: retail buyers of BTC/ETH/SOL threshold contracts pay above the
options-implied probability; a maker sells the overpricing. The paper's
wedge has a 4.2-hour half-life; the daily ladders are where Polymarket's
short-dated crypto flow actually is (liquidity in the final 48 hours:
~$80k a market on the settlement day, ~$4k two days out, read on the
active list on 13 October), so this is the population the mechanism names.

## Predicted sign and size

**Positive.** Per filled share, mean net edge **≥ 3 points** at k = 5,
clustered t **≥ 3**; the mirror < half of it; the placebo (realised vol)
clearly below the family; the naive short beaten per share; the DVOL arm
(the term-structure control) **not** above the family — if a 30-day vol
prices these 1–7-day contracts better than the tenor-matched one, the
"wedge" is a volatility-term-structure artefact, not retail overpricing.
Book net Sharpe above 1.0 on the $200 sleeve. An edge above 15 points or
a fill rate above 90% is a leak.

## Data (frozen)

- **Polymarket book recording**, `qr-pm-polymarket` on the Hetzner box,
  `--min-horizon-days 1` from **13 October 2026 04:53 UTC**: `book`,
  `price_change` (compacted as before), `last_trade_price` for every
  active BTC/ETH/SOL threshold market, the daily ladders included; the
  list refreshed hourly, the horizon rule stamped on every catalogue line.
- **Universe**: the daily ladders only — markets of kind `above` ("Will
  the price of Bitcoin be above $76,000 on October 13?") whose life from
  listing to settlement is **under eight days** (they are listed with just
  under seven). Settlement: the Binance 1-minute close at 12:00 ET on the
  date, from the market's own description. Monthly and longer markets
  belong to v2 and are not in this universe.
- **Deribit surface recording**, `qr-surface.timer` from **13 October
  2026 04:49 UTC**: every BTC and ETH option's mark IV, open interest and
  underlying at two minutes past each hour.
- **Deribit DVOL and price indices**, `qr-pm-deribit`, as v2.
- **Window**: 13 October 04:53 UTC → 30 October 2026 23:59 UTC, **read
  once on 31 October** (the Programme 3 report day). **Minimum sample,
  stated now:** at least **30 asset × settlement-date clusters with a
  fill** at k = 5, T = 1, else the read is deferred to 30 November with
  the window extended to 29 November, and this memo is not touched. Three
  ladders settle a day, so the window holds up to 54.
- **Resolutions**: from Gamma at read time; unresolved markets dropped and
  counted.

## Model (frozen)

Φ(d₂) terminal (every daily market is a terminal `above`); S = the Deribit
price index at the decision time; τ to the market's settlement in years;
**σ = the ATM implied vol at the market's own tenor**, from the latest
surface snapshot at or before the decision time (at most two hours old):
per expiry, the mark IV of the strike nearest the underlying, call and put
averaged; interpolated **linearly in total variance** between the two
bracketing expiries, flat beyond the ends (`qr/execution/pm_replay.py`,
`SurfaceSigma`). When no snapshot is within two hours the decision is
priced off DVOL and **counted** (`surface_fallbacks`, reported per run; a
run with more than 10% fallbacks is reported as such). **SOL**: BTC's
tenor-matched σ × the past-only 30-day realised-vol ratio, as v2 scales
DVOL.

## Rule and fill model (frozen, as v2)

Decision times every hour on the hour UTC. `wedge = best_bid − p_model`;
if no position and `wedge ≥ k`, post a sell of YES at the best ask
(joining). Filled only when a `last_trade_price` prints **at or above** our
ask after the post, within `TTL` = 4 hours, else cancelled. Exit when
`wedge ≤ x` at a decision time (post a buy at the best bid, same fill
rule; unfilled after TTL, cross at the ask and pay the crypto-tier taker
fee 0.07 × p(1−p)); or settlement at 0/1; or `T` days after the fill,
crossing. One position per market; one market per asset × settlement
date (the largest wedge); ≤ 5 open; $25 per market on the $200 sleeve.

| Parameter | Range | Swept? |
|---|---|---|
| `k` (entry wedge, points) | 5, 8 | yes |
| `T` (max hold, days) | **1**, to resolution | yes |
| `x` (exit wedge) | 2 | fixed |
| `TTL` (hours) | 4 | fixed |

**4 variants.** Fees: maker 0; taker only on a forced cross; rewards
ignored. `T = 1` is the version that leaves before the settlement print.

## Controls

Mirror (buy the under-priced side at the best bid, same σ); placebo (σ =
past-only 30-day realised vol from the Deribit index); **DVOL arm** (σ =
DVOL, i.e. v2's model on this universe — the term-structure control);
naive short of every YES with best bid ≤ 20¢ at first sight, held to
resolution; gate 6's permutation of decision times within a market. All
seventeen sessions run on one pass of the stream.

## Statistics

Per-share edge, SE clustered by asset × settlement date; DSR over 4; the
book's hourly P&L aggregated to days for Sharpe. Fill rate per variant
and side. **Diagnostic, not a gate:** the edge of positions carried to
settlement against positions exited early — the daily markets settle on
one Binance minute, and a short held into that minute near the strike is
exposed to it; the split says how much of any edge is that exposure.

## What would falsify this

- Edge < 3 points at k = 5, or clustered t < 3; the placebo matching; the
  mirror within half; the naive short not beaten; the DVOL arm above the
  family; DSR < 0.90.
- A fill rate below 30% ("the ask never trades").
- Surface fallbacks above 10% of decisions make the σ claim unproven; the
  run is then reported with the DVOL arm as the primary and says so.
- **Holdout**: the recording from 1 November → 29 November, read once,
  only if the in-sample passes.

## Prior

Where v2's monthly markets trade a few hundred dollars a day and rarely
print, the daily ladders print all day in their last 48 hours, so the
fill rule should bind far less and the sample arrives in days instead of
years. Against that: the wedge the paper measured decays in hours, and a
market that lives seven days with its liquidity at the end may be priced
by the same bots that price Deribit; the tenor-matched σ removes the
easiest false positive (a 30-day vol applied to a one-day contract). Honest
expectation: fills yes, an edge of a few points at k = 5 with the mirror
losing, and the t short of 3 in eighteen days; the 30 November read
decides, and the DVOL arm says whether v1's daily wedge was partly the
term structure.
