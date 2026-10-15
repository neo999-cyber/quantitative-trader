# Review: cloud9markets.com, "24/7 AI trading bot" — what it is, what checks out, what it is worth to us

*15 October 2026, on the owner's "go through this in deep, run all scenarios mentioned". Read: the page,
its live desk (`hft.cloud9markets.com`), the site's home page, OpenRouter's documentation, the model's
launch coverage, the domain record. Run: every scenario the page states that can be run without calling
the model or spending anything, on our own data (`scripts/review_cloud9_scenarios.py`; outputs in
`reports/research/cloud9_scenarios_2026-10-15.json`; the one backtest counted as trial-log run 980, a
review replication, not a candidate). Nothing was signed up for, entered or downloaded as code.*

## 1. What it is

A write-up by an Australian "independent research desk" (Cloud9 Markets; domain registered 1 August
2026; contact `hello@kloud9ai.com.au`; monetised through Instagram/TikTok/Substack and "work with the
desk" consulting) of a **paper-trading decision engine** the author runs on Bitcoin:

1. **Code** computes order-book features every second from Hyperliquid's public feed: spread, depth,
   buy/sell imbalance, volatility, aggressive flow.
2. **A decision model** — `microsoft/microsoft-decision-1` through OpenRouter's Decisions API — answers
   nine fixed questions in one call with probabilities, not text: regime, 30-second bias, smart-money
   flow, thin book, quoting conditions, liquidation cascade, fake walls, whale absorption, safe to trade.
3. **Plain-code policy** turns the answers into one of GREEN LIGHT / TRADE SMALL / CAUTION / GET OUT /
   SIT OUT; thresholds live in code.
4. **A risk engine** vetoes: stale data over 3 s, answers slower than 2.5 s, a volatility kill switch,
   feed loss, fallback to code-only rules after three model errors.

The model is woken only when the market moves (5 bps, an imbalance shift, a volatility ratio crossing
1.5, an aggressive burst, walls appearing/vanishing, the book draining, plus a 30-second heartbeat). The
page gives the request shape, two Claude Code prompts to rebuild it, and an eleven-step list for taking
it live (testnet first, API wallet without withdrawal, exchange-side stops, dead-man's switch, reconcile
with the exchange, maker fees, paper-trade with and without the filter, go live tiny). It says of itself:
"a decision engine, running on paper … not a money printer … finding an edge is still the hard part".

**It is not a broker, sells nothing on the page, asks for no deposit.** The only money risk is a reader
taking the final section literally and going live levered on Hyperliquid.

## 2. The claims, checked

| claim on the page | how it was checked | result |
|---|---|---|
| "Microsoft just launched" Microsoft-Decision-1, live on OpenRouter 10 Oct 2026 | launch coverage (MarkTechPost, 9 Oct), OpenRouter model page and decision rankings, two third-party benches | **Real.** A Microsoft decision-scoring model post-trained from Qwen3.5-9B, hosted only, returns calibrated probabilities over fixed options; $0.042 per million input tokens, output free; served only by the Decisions API |
| "drop-in swap for TypeSafe's Jev" | OpenRouter's Jev guide | **Real.** Same `POST /api/alpha/decisions`, same question types (choice / noul / score), `usage.cost` on every response |
| $0.000025 a call | $0.042/M tokens implies ~600 input tokens a call; the desk's counter shows $0.000026 | consistent |
| 85–95% of seconds skipped | **run on our Binance BTCUSDT tape, 20 Sep 2026**, top-of-book and prints: 86,323 seconds, 7,539 calls, **91.3% skipped**, 5.2 calls a minute; triggers: aggressive burst 57%, imbalance shift 21%, heartbeat 17%, vol ratio 3%, 5-bps move 2% | consistent; ours is a floor (the depth triggers need L2) |
| $0.15–0.35 a day | ours $0.196 a day at their cost per call; the desk shows $0.16 a day | consistent |
| ~650 ms an answer | desk p50 646 ms; an outside bench 472 ms | consistent |
| the policy table | applied to the nine answers the desk displayed at the read | reproduces the desk's action (TRADE SMALL) |
| "start with a strategy that works without the AI … if it loses money on its own, the AI filter won't rescue it" | **run:** their baseline, a 20/50 moving-average cross on 15-minute BTC perp bars, Jan 2024 → Sep 2026, decided at the close and filled at the next open | **it loses at any realistic cost** — see §3 |
| the live desk is live | counters advance between reads, log timestamps current, cost counter moves | plausibly a real paper run; whether the model is really called cannot be proven from outside, but the cost counter is the model's own `usage.cost` |

Domain and company: 2½ months old, Cloudflare-registered; the home page is a content funnel (posts
unlocked by Instagram DM codes, a free newsletter, consulting). No regulator is involved because no
client money is.

## 3. The scenarios, run

**Wake rate** (one day of our own tape, BTCUSDT, 20 September 2026): the rule as written wakes the model
8.7% of seconds, 7,539 times a day, $0.20 a day. The page's figures stand. Worth noting what wakes it:
more than half the calls are the "aggressive flow burst" trigger, so the model is mostly asked the same
question during the same bursts.

**The baseline strategy** (MA 20/50 on 15-minute bars, 96,384 bars, 2.75 years, 1,908 trades = 695 a year):

| cost per side | round trip | gross per trade | net per trade | net total | net CAGR | Sharpe (daily) | max drawdown |
|---|---|---|---|---|---|---|---|
| free | 0 | +2.5 bps | +2.5 bps | +22.6% | +7.7% | 0.40 | −41% |
| our measured maker, 3.2 bps + 1 slippage | 8.4 bps | +2.5 | −5.9 | **−75%** | −40% | −0.95 | −80% |
| taker 5.5 + 1 | 13.0 bps | +2.5 | −10.5 | **−90%** | −56% | −1.67 | −91% |
| taker, with a 1% stop | 13.0 bps | +4.7 | −8.3 | −84% | −48% | −1.52 | −87% |

Gross it earns 2.5 bps a trade and trades 695 times a year; it needs 8–13 bps a trade to break even. Even
free it is a 7.7%/yr, 0.4-Sharpe, 41%-drawdown way to own Bitcoin. The page's own rule disqualifies its
own example, which is to its credit.

**The policy table** reproduces the desk's action from the desk's answers. The table's shape is the
finding: with cascade ≥ 0.70 or smart money ≥ 0.60 → GET OUT, thin book or fake walls ≥ 0.70 → CAUTION,
GREEN LIGHT only at Standard conditions with confidence ≥ 0.80 and safe ≥ OK.

**The desk's own 73 hours** (264,984 seconds, 18,914 decisions): GREEN LIGHT **0**, TRADE SMALL 10,988
(58%), CAUTION 3,916 (21%), GET OUT 3,413 (18%), SIT OUT 597; 596 vetoes, 27 kill switches, 30 model
errors. A filter that never goes green in three days and says "get out" one time in five is not
information a strategy can size on; it is a near-constant with a noisy red light. The page's own test
("check whether the AI's 80% really happens 80% of the time") has not been done by its author, and the
regime answer it displayed carried 26% confidence.

**Not run, and why:** anything that calls the model (calibration, the with/without-filter paper test)
needs an OpenRouter key and spend — small, but spend, which is the owner's call — and the result would be
one more untested classifier over inputs we have already tested.

## 4. What it is worth to this project

*Already ours.* Items 3–11 of its "taking it live" list are the stage-1 design restated: testnet first,
a trade-only key, caps in code, the venue as the source of truth with reconciliation every tick, maker
orders, a close-on-failure unit as the emergency stop, a typed mandate. Its risk engine's "stale data →
sit out" is our `nav_uncertain` refusal.

*Tested here already, and failed.* Four of its nine questions are mechanisms this project has run through
the gates or measured: liquidation cascades (C3, `docs/20` 1 October: no reversion after a burst, placebo-
equal), smart-money flow and open-interest positioning (C5), thin books and walls (the stage-0/1 maker
study, which found the fill rate and the adverse mark, not an edge). P3-C's verdict applies to the layer
the page adds: more modelling of the inputs we have adds nothing (`docs/31` §14). A model with no fitted
parameters answering from five numbers is a prior with a probability attached, not evidence; the page says
as much — "the decision engine is not a strategy".

*One concrete addition, cheap:* the exchange-side dead-man's switch. Hyperliquid's `scheduleCancel` has a
Binance USDⓈ-M equivalent, `POST /fapi/v1/countdownCancelAll`, which cancels every open order on a symbol
if the client stops renewing a countdown. Our sessions are short and close themselves, so stage 1 never
needed it; the carry holding's resting maker orders would benefit, and it is a dozen lines in the venue
client. Filed as a ticket for the carry harness, not done.

*Possible, not now:* a $0.20-a-day forward recording of the nine answers beside our Polymarket, Deribit and
Hyperliquid recorders, to test in months whether any probability predicts a registered quantity (the C3
burst, the next hour's return) out of sample. It is a registration with spend attached; the data-expansion
plan (`docs/31` §15) is ahead of it in the queue.

**Verdict.** Honest, well-hedged content from someone building in public; the facts it states are true
and its numbers reproduce on our data. It contains no edge and claims none. For us it is a checklist we
already run, one safety feature to add, and a reminder, now with their own 73 hours as the exhibit, that a
judgment layer over the same inputs is amber most of the time and green never.

## Sources

- Launch coverage: MarkTechPost, 9 October 2026 — "Microsoft AI Releases Microsoft-Decision-1: A Qwen3.5-9B Decision-Scoring Model"
- OpenRouter: model page `openrouter.ai/microsoft/microsoft-decision-1`; decision rankings; Jev guide `openrouter.ai/docs/guides/community/jev`
- Third-party benches: dev.to "Microsoft Decision-1 vs every decision model on OpenRouter: 6th of 14"; eesel.ai "Microsoft-Decision-1 explained"
- The page and desk: `cloud9markets.com/microsoft-ai-trading-bot.html`, `hft.cloud9markets.com`, `cloud9markets.com` (home); WHOIS for the domain
