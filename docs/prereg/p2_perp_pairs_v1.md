# Pre-registration: `p2_perp_pairs_v1` — mean reversion of linked perpetual pairs, dollar-neutral

*Drafted and registered 18 September 2026 on the owner's yes, as the
tenth Programme 2 candidate — the one new input both outside reviews
proposed (`docs/29` Q5b). The pair list, the grid and the controls are
fixed here before any run; no price series was looked at beyond checking
that every pair exists in the lake with ≥ 700 days of overlap.*

## Mechanism

Two perpetuals on economically linked assets — the same layer, sector or
narrative — are bought and sold by the same crowd on the same news, so
their log-price spread has a level it returns to over days. What moves it
away is flow that lands on one leg first: a listing, an unlock, a
liquidation, an ETF headline. The trade takes the other side of that
one-legged flow and waits for the second leg to catch up, dollar-neutral,
so it earns the *relative* move and nothing of the market's. The forced
trader is whoever had to act on one leg only; the claim is a low-turnover
reversion, not cointegration as a theorem.

Long-short on Binance USDⓈ-M perps (the short leg is native); funding on
both legs is settled gross by the engine.

## Predicted sign and size

**Positive against cash.** Best variant net Sharpe **0.6 to 1.2** after
Binance perp taker fees, positive excess over cash with net alpha t
**above 2**; the random-pairs control earns **less than half** of the
family's net Sharpe; 20–60 round trips a year per pair, positions held
2–10 days. A net Sharpe above 3 is a reason to look for a leak.

## Data and universe

The perp lake (`futures/um`, daily bars 2020-01 → 2025-08, funding
gross). **Twenty frozen pairs** (`qr/strategies/pairs.py::LINKED`):
SOL/AVAX, NEAR/APT, ARB/OP, ETH/BTC, LTC/BCH, DOGE/1000SHIB, UNI/AAVE,
SUI/APT, LINK/DOT, ADA/XRP, FIL/AR, ETC/LTC, XLM/XRP, INJ/SEI, STX/ORDI,
PENDLE/AAVE, LDO/RPL, CRV/CVX, GMX/DYDX, ZEC/XMR. A pair trades only when
both legs are tradable; a pair whose younger leg lists late enters when
the window is full. Universe filter: `--n 300 --min-history 120`.
Benchmark: **cash** (`--benchmark cash --risk-free fred`).

## Rule and parameters (frozen)

Per pair, each bar, from the last `lookback` bars only: hedge ratio β by
OLS of log a on log b (kept if 0.25 ≤ β ≤ 4); spread = log a − β log b;
z = (spread − mean)/sd over the window; the pair is *reverting* if the
spread's AR(1) ρ < 0.95 and its half-life ≤ lookback/2. Enter when
reverting and |z| ≥ `entry` (z ≥ entry: short a, long b; z ≤ −entry the
reverse); exit when |z| ≤ `exit_z` or after `max_hold` bars or when a leg
stops trading; flat for at least one bar between trades. Up to `n_max`
pairs open, equal risk per pair, legs split 1 : β in dollars; gross 1.0.

| Parameter | Range | Swept? |
|---|---|---|
| `lookback` (bars) | 60, 120 | yes |
| `entry` (σ) | 2.0, 2.5 | yes |
| `max_hold` (bars) | 5, 10 | yes |
| `exit_z` | 0.5 | fixed |
| `n_max` | 10 | fixed |

**8 variants.** Engine: `--engine ledger`. Costs: `--costs perp`.

## Controls

- **Random pairs** (`p2_perp_pairs_v1_random`): the same rule on twenty
  pairs drawn at random, seed 20260918, from the eligible names,
  excluding the linked ones. If unrelated pairs revert as much, the
  effect is "any spread reverts" — a property of the z-score
  construction, not of the economic link — and the family is re-scoped
  as such, not passed.
- **Gate 6's permutation null** applies as registered.

## What would falsify this

- Best net Sharpe below 0.6, or net alpha t below 2 against cash.
- The random control within half of the family's net Sharpe.
- DSR below 0.90 over 8 → gate 4. SPA p above 0.5 → gate 5.
- Holdout: 1 September 2025 → 31 August 2026, opened once after gates 1–8.

## Prior

Crypto pairs reversion is a well-known and unstable trade: the two
reviews that proposed it also warn of it, and an SSRN result of March
2026 finds plain perp sorts carry nothing. The honest prior: a positive
but fragile Sharpe in-sample around 0.5, the random control uncomfortably
close, gate 4 or 5 failing. If the linked pairs beat the random ones
clearly, that is the finding worth a second version.
