# Day 1–2: the data layer and the backtest core

Built on branch `claude/admiring-ptolemy-tfp528`. 152 tests, all offline.

## What now exists

| Module | What it does |
|---|---|
| `qr/config.py` | One root for everything written (`$QR_ROOT`, default `lake/`); `$QR_BINANCE_MIRROR` for the bucket mirror |
| `qr/data/binance.py` | Binance bucket loader: klines, survivorship-free universe, listing/delisting dates, checksum verification |
| `qr/data/panel.py` | Symbols aligned on one UTC index, no filling; `tradable()` is the mask positions must respect |
| `qr/data/universe.py` | Point-in-time top-N by trailing median quote volume |
| `qr/data/lake.py` | Hive-partitioned Parquet + DuckDB manifest + `manifest_hash()` |
| `qr/data/qa.py` | Gate-1 data-integrity checks |
| `qr/data/feargreed.py` | Fear & Greed as a lagged point-in-time feature |
| `qr/data/fixtures.py` | Synthetic mirrors in the bucket's exact layout (how the sandbox tests anything) |
| `qr/strategies/` | `Strategy` interface, `VolTarget`, `BuyAndHold` / `TSMOM` / `RandomEntry` |
| `qr/research/runner.py` | The backtest: one-bar shift, weight drift, costs, `leakage_probe()` |
| `qr/research/crosscheck.py` | A second engine (units + cash) and vectorbt as a third |
| `qr/execution/costs.py` | Binance spot fees by VIP tier, half-spread, square-root impact, `stressed()` |
| `qr/validate/trial_log.py` | Append-only hash-chained trial log |
| `qr/cli.py` | `qr doctor / data / fng / trial / backtest` |

## The three traps this layer is built around

1. **The universe comes from the bucket listing, never from `exchangeInfo`.** Delisted pairs stay in the bucket and vanish from the API, so an API-built universe is survivorship-biased by construction. A pair that delists mid-month leaves the book at its **last close**, not at the next rebalance.
2. **Binance spot timestamps switched from milliseconds to microseconds on 2025-01-01.** Every timestamp is judged by magnitude, per value, so a history spanning the switch is continuous. (Files also gained a header row during 2025; that is sniffed, not assumed.)
3. **The one-bar shift lives in the runner, not in strategies.** `leakage_probe()` re-runs at lag 0/1/2: an honest signal degrades smoothly from 1 to 2 and gains little at 0; a leaky one posts a Sharpe at lag 0 it cannot approach at lag 1.

The cross-check engine paid for itself on day one: it caught a one-bar misalignment in the vectorbt adapter and a book that kept "holding" a delisted pair. All three engines now agree to ~1e-3.

## What you need to run on the laptop

The cloud sandbox cannot reach `data.binance.vision` or `api.alternative.me`, so the loaders are written against a local mirror and the pull happens on your machine.

```bash
git fetch origin && git checkout claude/admiring-ptolemy-tfp528
pip install -e ".[dev,qr,research]"

export QR_ROOT=~/qr/lake
export QR_BINANCE_MIRROR=~/qr/mirror/binance

qr doctor                                   # paths and versions

# See the scale first: counts files, downloads nothing.
qr data pull --interval 1d --dry-run

# USDT pairs only, 16 concurrent. ~20-40 min depending on your line.
qr data pull --interval 1d
qr data pull --interval 1h --since 2021-01   # optional, far larger

qr data ingest --interval 1d                # mirror -> Parquet lake
qr data qa --interval 1d --out qa_1d.md     # the QA report
qr data universe --n 30 --min-history 180

qr fng pull                                 # Fear & Greed history

qr backtest --family tsmom --param lookback=90 --n 30 --crosscheck --leakage --log
qr trial verify
```

Send back `qa_1d.md` and the `manifest hash` line from `qr data ingest`. Everything after that runs against the lake, and the manifest hash is what every Hypothesis Report will cite as its data version.

## The cost model is frozen for the trial

Verified against the account's own fee panel on **11 September 2026**: 30-day spot volume 0.00 USD, so **VIP0**, with the **BNB fee discount on** — 0.07500% maker and taker.

| Component | bps per side |
|---|---|
| Binance spot taker fee (VIP0, −25% BNB) | 7.5 |
| Half-spread | 2.0 |
| **Total** | **9.5** (19 bps a round trip) |

`CostModel.trial()` is that model, it is the default for `qr backtest` and `run_backtest()`, and its `fees_verified_on` date travels into the trial log with every run — so a Hypothesis Report cannot quietly cite an unverified fee. Gate 2 additionally requires the edge to survive `stressed(2.0)`: 38 bps a round trip.

Two caveats worth keeping in view:

- **The BNB discount is conditional.** It applies only while "pay fees in BNB" stays on and there is BNB in the account to pay with. If the balance runs out mid-month the real fee silently reverts to 10 bps. `qr backtest --no-bnb` runs the unverified 12 bps-per-side version, and any strategy whose verdict flips between the two is too cost-marginal to trade.
- **The 2 bps half-spread is the weakest number here**, not the fee. Top-30 USDT pairs mostly quote inside 1 bp, so it is deliberately pessimistic, but it is a guess rather than a measurement. It is the first thing to replace once the bucket's 1h bars give a real intrabar estimate.

## Next (Day 2–3)

Gates 1–9 on `arch` / `statsmodels` / `skfolio` / `jsharpe` plus own CSCV and permutation code, and the synthetic self-test that must hold: a noise strategy searched over 200 variants **fails** at gate 4/5, a planted edge **passes**.
