# Response to the second outside review (18 September 2026)

*A second tool reviewed `docs/28` the same day. Checked against the code.
Its overall verdict agrees with `docs/18` and `docs/28` §10; its specific
recommendations rest on a conflation of two things in this repository.*

## The conflation

`centaur/` is a discretionary swing-trading assistant from before this
project (2,640 lines, 55 tests, **never run on live data**, Yahoo Finance
by design), kept frozen on purpose — `CLAUDE.md`: "keep `centaur/`
untouched"; `docs/00` is its honest inventory. It is not part of the
research funnel, feeds nothing into `qr/`, and no verdict in this
project depends on it. `qr/` has no yfinance anywhere; the lake is built
from Binance's public bucket with SHA-256 checksums, Databento, FINRA,
SEC, FRED and DefiLlama, all under a manifest. The review's recommendations
1 (route Centaur ideas through the gates), 2 (pull Binance klines into a
lake), and 4 (encode Centaur's gauntlet) describe work that is either
already the design of `qr/` or concerns a module that is deliberately
inert. Its "data quality contradiction" is two different codebases with
two different purposes, both stated.

## "No loopholes of losing money"

That phrase was the owner's wording in the prompt to the reviewer. It is
not an objective anywhere in this repository; `docs/18` and `docs/28` §10
say the opposite, and stage 1's caps are the "capped downside" the
review asks for. Its proposed restatement — capped drawdown, zero risk of
ruin, positive expected value, every loss a priced cost of a test — is
already the working definition (gate 10/11's `prob_ever_below_launch`;
the $25 stop; the 3× bar). Adopted as the one-line objective in `docs/28`
so the next reviewer is not misled by the prompt.

## Claims corrected

- **"C2 was one of your most promising statistical findings."** C2
  failed gate 3 (t 1.76) and gate 6; its improved ledger numbers were
  cash interest (`docs/20`, 18 Sep). Its closure is a venue fact, not a
  loss of a near-pass.
- **"Hold-the-carry and OI direction are real effects erased by taker
  fees."** Neither was cost-killed: C1's always-in passes gate 2 (92% of
  gross survives) and fails gate 6 as a timing rule; C5 fails gate 3
  before costs matter. The maker study lowers the bar for C1's
  re-registration as a holding and for any high-turnover crypto family;
  it does not rescue a family that failed on significance or on its
  null. E1, the family actually killed by costs, is an equity book on
  Alpaca and untouched by crypto maker fees.

## Agreed and already the plan

Execute stage 1 exactly as scoped (`docs/24`, `docs/27`), after stage 0's
read on 1 October and the owner's yes; accept the index-fund verdict as a
valid outcome and pause live ambitions if the dated items fail; keep the
LLM boundary (feature, never a trade) — enforced in `qr/`, and moot for
`centaur/` since it does not trade.
