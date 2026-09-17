# Pre-registration: `p2_unlock_fade_v1` — short the perp into a scheduled insider cliff

*Drafted 17 September 2026 (`docs/research/10`), before any run. **Not
registered**: the Programme 2 counter is full (`docs/23`) and this file
becomes a registration only with the owner's yes. The counts below are
from the unlock calendar alone (`qr data unlocks-build`, schedules
mirrored 17 September 2026); no price series was looked at.*

## Mechanism

A vesting cliff is a seller with a date. Team and early-investor tokens
unlock on a schedule published at launch; the recipients sell into the
market, and the market knows the date. Keyrock's study of 16,000 unlocks
across 40 tokens finds 90% create negative price pressure, that it lands
mostly in the **thirty days before** the date (front-running of the
seller) and stabilises about **two weeks after**; team cliffs are the
worst (−25% on average), ecosystem unlocks the exception (+1.2%). The
perpetual makes the other side native: short the perp from thirty days
before the cliff to two weeks after, collect or pay funding meanwhile.

The claim is the pre-unlock drift and its stabilisation. Whether the
recipients actually sell is not observed; the calendar is.

## Predicted sign and size

**Negative price drift over the window; the short earns it.** Names with
an insider/investor cliff of at least 1% of circulating supply lose
**2% to 8%** against the perp universe over the 44-session window; a
ten-name short book earns net Sharpe **0.5 to 1.5** against cash after
Binance perp taker fees and with funding settled; net alpha t **above 2**
against cash. The long mirror loses. The ecosystem control earns nothing.
A net Sharpe above 3 is a reason to look for a schedule revision that
leaked (see Data).

## Data

- **Calendar:** DefiLlama's free per-protocol emissions dataset
  (`qr/data/unlocks.py`), raw JSON mirrored under
  `mirror/defillama/emissions/` and frozen on 17 September 2026. 105 of
  864 USDT perps matched a schedule by token symbol; **56 carry at least
  one insider/private-sale cliff ≥ 1% of documented circulating supply;
  528 such cliffs 2020–2026, 318 in-sample (2022-01 → 2025-08) on 36
  perps**; 241 are ≥ 2%, 69 ≥ 5%. Unmatched perps (BTC, ETH, most
  memecoins, and any name whose DefiLlama symbol differs) are simply
  outside the universe — no schedule, no signal.
- **Point-in-time caveat, the one that matters:** the dataset is the
  schedule *as currently documented*. Cliffs added or moved after the
  fact appear at their revised dates. The direction of harm: a cliff
  added late looks anticipated. Mitigation: the holdout is every cliff
  dated **after** the mirror was frozen (18 September 2026 onward), which
  cannot have been revised into the file; the in-sample result is read
  with the caveat and the holdout without it.
- **Prices, funding, OI:** the perp lake (`futures/um`, `futures-um`
  funding), daily bars; funding gross per the engine.

## Universe

USDT perps with a schedule, ranks 1–300 by 30-day quote volume
(`--n 300`), `min_history 60`, price valid and tradable at the decision
bar. Benchmark: **cash** (`--benchmark cash --risk-free fred`): a short
book is not a subset of the market.

## Rule and parameters

Each bar: among eligible perps whose next insider/investor cliff is at
least `min_pct` of supply and lands within `lead` days, short up to
`n_max`, the largest cliff first, equal weight, gross 1.0. Keep each
name until `post` days after its cliff. Nothing else is held; the book is
in cash when no cliff is within reach.

| Parameter | Range | Swept? |
|---|---|---|
| `lead` (days before) | 20, 30 | yes |
| `post` (days after) | 7, 14 | yes |
| `min_pct` (of supply) | 0.01, 0.02 | yes |
| `n_max` | 10 | fixed |

**8 variants.** Engine: `--engine ledger` (the first family run on it from
registration; the perp short's liability and funding are booked per the
ledger's conventions, `docs/26`).

## Cost model, benchmark, controls

`--costs perp` (Binance USDⓈ-M regular taker 5 bps + 1.5 bps half-spread
a side; 3× stressed per the standing rule). Funding is gross and can be
either sign: a crowded short into a cliff *pays* if the rate goes
negative, and the report states the carry share. Controls: **long
mirror** (`side=long`, same names and window — the mechanism says it
loses); **ecosystem cliffs** (`category=eco`, same rule on ecosystem /
community / airdrop unlocks — the study says these do not fall).

## What would falsify this

- Window drift above −2% versus the universe, or the long mirror not
  losing → no pre-unlock pressure the calendar can see.
- The ecosystem control falling as much → the effect is "any unlock",
  i.e. a supply-inflation story, and the family is re-scoped, not passed.
- Net alpha t below 2 against cash → gate 3. DSR below 0.90 over 8 →
  gate 4. SPA p above 0.5 → gate 5.
- Holdout: cliffs dated 18 September 2026 → 17 March 2027 (six months,
  ~50 cliffs at the 2025–26 rate), opened once after gates 1–8. This is
  the only test free of the revision caveat, and it is short: a positive
  holdout is reported as consistent, not as proof.

## Prior

Published (2024) and widely read; exchanges and market makers watch the
same calendars, so the drift may be front-run earlier than thirty days
and the window may be the wrong one. Expected: negative drift with
wide dispersion, gate 3 t between 1.5 and 3 on ~300 events, funding
against the book on the most-watched names. Cycle: a verdict on the
in-sample in one night; on the holdout in six months.
