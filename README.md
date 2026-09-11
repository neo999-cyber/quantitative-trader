# Centaur Trader

**AI does the grind. You apply the veteran filter. Nothing gets bought until it survives the gauntlet.**

This repo turns the "Centaur Method" into working software:

1. **Quantitative screens** (the AI grind) - a historical pattern matcher with real backtests, a macro
   regime checker with a confidence score, an options-flow flagger, and an earnings-call catalyst
   synthesizer that cross-references insider trades.
2. **The Veteran Trader's Rulebook as code** - five rules, run as a gauntlet. One failure = ABORT.
3. **The daily workflow** - `centaur evening` writes the brief, `centaur morning` hands you the candidates,
   `centaur gauntlet` culls them, `centaur size` does the 1% math, `centaur journal` closes the loop and
   feeds your results back into tomorrow's prompt.

Everything except the earnings-call summariser runs with free data (Yahoo Finance) and no API keys.
Everything except live data fetching also runs fully offline.

---

## Install

```bash
git clone <this repo> && cd quantitative-trader
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ai]"        # drop `,ai` if you don't need the Claude-powered catalyst step
cp .env.example .env              # optional: ANTHROPIC_API_KEY, UNUSUAL_WHALES_API_KEY, account settings
centaur --help
```

Account settings live in `centaur.json` (or `~/.centaur.json`), environment variables (`CENTAUR_EQUITY`,
`CENTAUR_RISK_PCT`, ...) or CLI flags (`--equity`, `--risk-pct`). Defaults: $10,000 equity, 1% risk,
1:3 minimum, $20M/day liquidity floor.

```json
{ "equity": 25000, "risk_pct": 0.01, "min_reward_risk": 3.0, "min_avg_dollar_volume": 20000000 }
```

Run the tests any time: `pytest -q`.

---

## The daily workflow

### 1. The evening before - the AI grind

```bash
centaur evening                      # S&P 500, 10 years, top 5
centaur evening --tickers NVDA AMD   # or your own list / --universe-file my.txt
```

This runs the regime check, scans the universe for the setup, backtests the setup on every hit
(and pooled across the index), pulls unusual call flow for the hits, and writes:

- `briefs/YYYY-MM-DD.md` - the Morning Brief (regime, table of candidates, signals, flow, checklist)
- `briefs/YYYY-MM-DD.json` - the same, machine-readable
- `briefs/YYYY-MM-DD/candidates/<TICKER>.json` - a pre-filled candidate file per hit (entry = last
  close, stop = 1.5 ATR, target = 1:3 by construction, resistance levels from swing highs, next earnings
  date). **These are templates.** The chart decides the real stop and target.

If your journal has closed trades, the brief ends with the feedback block to paste into your AI prompt.

### 2. The morning brief - the human review

```bash
centaur morning
```

Prints the latest brief and lists the candidate files. Pull up each chart, read the news, then edit the
candidate file: put the stop where the thesis is invalidated, put the target where the chart says it is
realistic, write the catalyst in one sentence, add the fundamental and flow signals you can actually verify.

### 3. The cull - the gauntlet

```bash
centaur gauntlet briefs/2026-09-10/candidates/AAPL.json
centaur gauntlet examples/candidate_aapl.json --regime examples/regime_risk_on.json --offline
```

```
=== GAUNTLET: AAPL LONG  entry 150.00  stop 145.00  target 165.00 ===
[PASS] R1 Asymmetry Check (1:3 minimum): reward:risk 1:3.00 (risk $5.00, reward $15.00)
[PASS] R2 Confluence Matrix (Rule of 3): 3 signals across 3 categories: fundamental, sentiment_flow, technical
[PASS] R3 Macro Regime Filter: RISK_ON (composite +0.46, confidence 82%) does not oppose a long
[PASS] R4 Catalyst & Liquidity Check: $9,500M/day liquidity; catalyst: Buyback announcement ...; earnings 2026-10-29 is outside the window
[PASS] R5 Sleep Test (position sizing): risk $100.00 (1.0% of $10,000) / $5.00 per share => 20 shares ...

EXECUTION PLAN: buy 20 shares @ 150.00; hard stop 145.00 (set it in the broker immediately); take partial profits at 165.00 (1:3.0).

VERDICT: TAKE
```

Put resistance at 158 into the same candidate and Rule 1 fails ("realistic reward:risk to that level is
only 1:1.60"). Feed it a RISK_OFF regime and Rule 3 fails. Exit code is `0` for TAKE, `2` for ABORT,
so it composes with shell scripts.

### 4. The execution

```bash
centaur size --entry 150 --stop 145 --target 165
# risk $100.00 (1.0% of $10,000) / $5.00 per share => 20 shares (...)   reward:risk 1:3.00
```

Set the hard stop in the broker the moment the fill prints. Set the limit for partial profits at the 1:3 target.

### 5. The journal

```bash
centaur journal open AAPL --entry 150 --stop 145 --target 165 --shares 20 \
    --ai-thesis "3-day capitulation, 64% hist. win rate" --why "3 categories, risk-on, buyback catalyst" \
    --gauntlet report.json
centaur journal close <id> --exit-price 165 --reason target --lessons "partial at 1:3 worked"
centaur journal stats          # win rate, avg win/loss in R, expectancy
centaur journal feedback       # the markdown block to paste into tomorrow's AI prompt
```

---

## The screens (the four prompts, as code)

| Prompt | Command | What it does |
|---|---|---|
| Historical Pattern Matcher | `centaur scan` / `centaur backtest --tickers AAPL` | 3 consecutive down days on above-average volume with RSI(14) < 30; per-ticker and pooled 5-day forward-return stats over 10 years (n, win rate, mean/median, edge vs baseline, t-stat). All parameters are flags: `--down-days --volume-multiple --rsi-max --horizon --years`. |
| Catalyst Synthesizer | `centaur catalyst --ticker XYZ --transcript call.txt` | Claude reads the transcript and returns strict JSON: top 3 bullish, top 3 bearish (with evidence and category), tone, dated catalysts. Then cross-references with the last 30 days of Form 4 insider trades: **confirms / contradicts / unconfirmed**. The insider half works without an API key. |
| Options Flow Vulture | `centaur flow --tickers ... [--provider unusualwhales]` | Flags call buckets with volume > 300% of the 30-day average expiring within 14 days. With no paid API it builds its own baseline from daily chain snapshots; the `baseline_days` column tells you how honest the baseline is (run it daily). |
| Regime Checker | `centaur regime [--earnings-yield 0.045]` | SPY/QQQ trend, VIX level and spike, VIX/VIX3M term structure, 10y-3m yield curve, DXY 20-day change, bonds vs stocks. Weighted composite -> RISK_ON / NEUTRAL / RISK_OFF with a confidence score that blends magnitude and component agreement. |

The literal prompts, ready to paste into Claude, are in [`prompts/`](prompts/) together with a system
prompt that forces the AI to output candidates in the JSON shape `centaur gauntlet` reads.

---

## The rulebook (`centaur/rules/rulebook.py`)

| Rule | Fails when |
|---|---|
| **R1 Asymmetry** | reward:risk < 1:3, or a resistance level (support for shorts) between entry and target caps the *realistic* reward below 1:3. |
| **R2 Confluence** | fewer than 3 signals, or fewer than 3 distinct categories. Three technical signals count as one reason. Categories: `technical`, `fundamental`, `sentiment_flow`, `macro`, `statistical`. |
| **R3 Macro regime** | long in RISK_OFF or short in RISK_ON. Only exception: `defensive: true` + `conviction: "high"` (and it warns you). No regime assessment at all also fails. |
| **R4 Catalyst & liquidity** | average dollar volume below the floor, position > 1% of daily dollar volume, empty catalyst, or earnings inside the holding window (+1 day buffer). Unknown earnings date passes with a warning. |
| **R5 Sleep test** | the 1% (configurable, hard-capped at 2%) risk budget does not buy even one share, or the position would need leverage. Otherwise it returns the share count. |

`run_gauntlet()` runs all five and returns `TAKE` only if every one passes.

---

## Candidate file format

```json
{
  "ticker": "AAPL", "direction": "long",
  "entry": 150.0, "stop": 145.0, "target": 165.0,
  "signals": [
    "technical: bouncing off the 200-day moving average",
    "fundamental: $90B buyback announced",
    "sentiment_flow: unusual institutional call buying (4.2x, 12 DTE)"
  ],
  "catalyst": "Buyback into an oversold tape",
  "avg_dollar_volume": 9500000000,
  "resistance_levels": [170.0, 182.5],
  "support_levels": [],
  "next_earnings": "2026-10-29",
  "holding_days": 10,
  "defensive": false, "conviction": "normal",
  "ai_thesis": "what the AI said, for the journal"
}
```

---

## Offline and testing

- `--synthetic` on any data command uses deterministic random walks (dry runs, demos).
- `--csv-dir DIR` reads `DIR/<TICKER>.csv` (Date,Open,High,Low,Close,Volume). The Yahoo provider writes
  exactly this format into `.cache/prices/`, so you can copy a cache and work offline.
- `examples/` holds a passing candidate, a failing one, and RISK_ON / RISK_OFF regime files.
- `pytest -q` runs ~55 tests with synthetic data; no network needed.

## Notes and caveats

- Yahoo Finance is free and rate-limited. The first full S&P 500 scan downloads ~500 x 10 years and is cached
  for 12 hours; subsequent runs are fast. `centaur.data.universe.refresh_sp500()` updates the bundled
  constituent snapshot from Wikipedia.
- Backtest statistics ignore slippage and are per-setup, not per-portfolio. Treat n < 20 as anecdote.
- The free options-flow baseline needs ~30 daily runs to mean anything; `baseline_days` is printed so you
  can't fool yourself.
- The catalyst summariser uses Claude Opus 5 with structured outputs and server-side refusal fallbacks.
  Set `ANTHROPIC_API_KEY` (or `ant auth login`). Override the model with `--model` or `CENTAUR_CLAUDE_MODEL`.
- None of this is financial advice. The system exists to make you *slower and stricter*, not to pick winners.
