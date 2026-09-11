# What actually exists today (honest inventory)

Commit `aef567f`, branch `claude/loving-maxwell-mu44wv`. One Python package, `centaur`, 2,640 lines,
55 unit tests, all passing on synthetic data. **Nothing has been run against live market data** because
the build sandbox blocks Yahoo Finance, Wikipedia and every other data host. Treat the live paths as
untested until you run `centaur regime` on your own machine.

## Built and tested (offline, synthetic data)

| Piece | File | State |
|---|---|---|
| Indicators: Wilder RSI, SMA/EMA, ATR, down-streaks, relative volume, swing highs/lows, trend state | `centaur/indicators.py` | Tested against a textbook RSI example |
| Pattern matcher: "3 down days on above-average volume, RSI<30" + per-ticker and pooled N-day forward-return backtest | `centaur/screens/pattern_matcher.py` | Tested. Correct exclusion of incomplete forward windows. **No costs, no stops, single-setup stats only** |
| Regime checker: SPY/QQQ trend, VIX level, VIX/VIX3M, 10y-3m curve, DXY, bonds-vs-stocks -> RISK_ON/OFF + confidence | `centaur/screens/regime.py` | Tested on constructed inputs. **Weights and thresholds are hand-picked, not fitted or validated** |
| Options flow: >3x 30-day avg call volume within 14 DTE; Unusual Whales adapter; free chain-snapshot baseline | `centaur/screens/options_flow.py` | Flagging logic tested. **Unusual Whales endpoint path is a guess (configurable); the free baseline needs 30 daily runs to mean anything** |
| Catalyst: Claude structured-output transcript summary + insider Form 4 cross-reference | `centaur/screens/catalyst.py` | Insider half tested. **Claude call never executed (no API key in sandbox)** |
| Rulebook: R1 asymmetry with resistance walls, R2 confluence (3 categories), R3 regime, R4 catalyst+liquidity+earnings window, R5 1% sizing | `centaur/rules/` | Fully tested, including the worked 20-share example |
| Journal: JSONL, R-multiples, expectancy, feedback block for prompts | `centaur/journal.py` | Tested |
| Evening brief / morning review / candidate templates | `centaur/brief.py`, `centaur/cli.py` | Tested end to end with synthetic data |
| Data layer: Yahoo (yfinance) with 12h CSV cache, offline CSV provider, synthetic provider | `centaur/data/provider.py` | Only CSV and synthetic exercised. **yfinance path untested; Yahoo is unofficial and rate-limited** |
| S&P 500 universe | `centaur/data/sp500.csv` | **Snapshot from memory, current constituents only -> survivorship bias in any backtest run on it** |
| Prompt library (the four prompts + evening screen + system prompt) | `prompts/` | Text only |

## What it is

A disciplined **discretionary swing-trading assistant** for US equities: daily bars, one canned setup,
a macro dashboard, a rule gauntlet that says TAKE/ABORT, and a journal. It enforces process. It is
good at stopping you from taking bad trades.

## What it is not (yet)

- Not a general hypothesis-testing engine. One hard-coded setup; no strategy abstraction; no
  parameter sweeps; no walk-forward; no multiple-testing correction; no cost model.
- Not multi-asset. No crypto, no forex, no futures; daily bars only; no intraday.
- Not survivorship-bias-free. Current S&P 500 list, no delisted names, no point-in-time membership.
- Not a portfolio backtester. It measures per-signal forward returns, not a strategy's equity curve
  with position sizing, overlapping trades, stops and costs.
- No storage layer beyond CSV cache; no scheduler; no dashboard.
- The regime model and the rule thresholds are opinions encoded as numbers, not fitted models.

Keep: the rulebook/gauntlet, the journal, the candidate schema, the prompt library, the CLI shape.
Replace: the data layer, the universe, the backtest core. Extend: the screens into a strategy library.
