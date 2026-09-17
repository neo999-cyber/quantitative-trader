# Forced flows in FX and single stocks — where a small account is not the loser

*17 September 2026, Opus 5, web research only; no run, nothing registered.
Written because the owner asked for new inputs after Programme 2 closed at
eight (`docs/23`). The lens is Programme 2's — **who is forced to trade,
when, and can a $1–2k account be on the other side** — with a second
filter the earlier research (`05`, `07`) did not apply: mechanisms where
being small is an advantage or at least not a handicap. Figures are the
sources' own; nothing here has been re-derived on our data.*

## Filters

1. A named forced trader with a known clock (fix, index date, tender deadline).
2. Effect size stated by someone, against the round-trip cost *at our size*
   under the 3× cost rule (`docs/26`).
3. Data at $0 or near it, point-in-time by construction.
4. Capacity: either irrelevant (we are tiny) or a *ceiling that excludes
   funds* — the only structural edge a retail account has.

## FX

### F1. Tokyo 9:55 fix on gotobi days (5th/10th/15th/20th/25th/30th)

- **Forced trader:** Japanese importers settle foreign invoices on gotobi
  days; banks pre-hedge the known USD demand before the 09:55 JST fix.
  Academic basis: Ito & Yamada, *Puzzles in the Forex Tokyo "Fixing"*,
  NBER w22820.
- **Size (practitioner replication, HistData 1-min bars 2007–2026, seven
  JPY pairs, Newey-West + Holm):** pre-fix rise ~4–5 pips 07:00–09:55;
  **post-fix reversal ~3 pips by 10:15–10:20**, significant across all
  seven pairs post-Covid.
- **Frequency:** ~72 days a year × 7 pairs.
- **Cost at our size:** IBKR IDEALPRO 0.2 bps, **$2 minimum per order**,
  25k-unit minimum lot. 3 pips on USD/JPY ≈ 2 bps. Round trip at $25k
  notional: $4 commission = 1.6 bps + ~0.3 bps spread → the effect is
  ~1× cost, fails the 3× rule. At $100k notional (margin ~$2.5–4k): 0.7 bps
  round trip → ~3× — **only passable at the top of the owner's "$2,000 if a
  proper system emerges" line, levered ~25×.**
- **Data:** HistData / Dukascopy free minute or tick bars, bid only or
  indicative — the same "prices, not the orders" caveat the replication
  itself states.
- **Verdict:** the cleanest forced flow in FX, and the cost bar is the
  whole question. Testable at $0. If registered, the capacity line has to
  be written as a *floor*, not a ceiling: below ~$60k notional the
  commission minimum eats it.

### F2. London 4pm fix at month-end (equity-hedge rebalancing)

- **Forced trader:** passive and hedged funds rebalance currency hedges
  against the WM/R 4pm fix; the size follows the month's equity return
  (Melvin & Prins 2013; Krohn, Mueller & Whelan, *JF* 2024 — ~2 bps
  systematic pre-/post-fix swings around fixes generally).
- **Size (replication, 138 month-ends 2015–2026):** pre-fix move **~2 bps
  per 1% of the month's S&P return** in GBP, CHF, AUD, NZD (JPY opposite);
  post-fix reversal offsets 41–75% of it. A 5% equity month → ~10 bps drift,
  ~5 bps reversal.
- **Frequency:** 12 a year (quarter-ends larger).
- **Cost:** as F1. 5 bps against a 0.7–2 bps round trip is fine on paper;
  **twelve events a year is the problem** — gate 3 needs decades to reach
  significance on twelve observations, and the replication's own p-values
  come from 138 events.
- **Verdict:** real, small, too rare to validate on its own; a companion to
  F1, not a family.

### Rejected in FX

- **Retail CFD/spread-bet FX**: the counterparty is the broker and the
  spread is the edge's size. Not a venue for this project.
- **Carry and trend in FX**: the same families that failed nine times in
  Programme 1; crowded for decades (`05` §C).

## Single stocks

### S1. Index deletions — buy what the index funds are forced to sell

- **Forced trader:** every S&P 500 / Russell tracker sells a deleted name
  at the close of the effective date, regardless of price.
- **Size:** Arnott, Kalesnik, Wu, *Earning Alpha by Avoiding the Index
  Rebalancing Crowd*, FAJ 2023: in the year after an S&P 500 change,
  **discretionary deletions beat the market by 20.4%**, additions lag by
  1.6%; deletions are almost always small/mid-cap deep value.
- **Frequency:** a handful to ~20 S&P discretionary deletions a year;
  Russell 2000 deletions in the hundreds each June (the reconstitution is
  going semi-annual from 2026 — `docs/20` sources).
- **Cost at our size:** negligible — one buy, one sell a year per name at
  $0 commission; a $1–2k account holds 3–5 names.
- **Data:** S&P Dow Jones index-change press releases (free, dated —
  point-in-time by construction); prices from Tiingo/Alpaca as for E5.
- **Gate concern:** power. Twenty events a year for ten years is 200
  twelve-month holds; gate 3's t-stat on a *twelve-month* horizon is the
  hard part, and the paper's 20% carries a wide interval. A test needs the
  full history of changes (1990s on), which the press releases give.
- **Verdict:** the strongest single-stock candidate — a forced seller, a
  long horizon that makes costs irrelevant, and no capacity constraint
  that binds at our size. It is a slow strategy: a verdict takes years of
  live time, not weeks.

### S2. Spin-offs — the first weeks of a mismatched shareholder base

- **Forced trader:** index funds and mandate-constrained holders receive
  shares of the spun entity they cannot hold and sell them in the first
  days; the literature (McConnell et al. JPM 2015; Cusatis, Miles &
  Woolridge) has spin-offs beating benchmarks by **~13–17% in year one**,
  microcaps (<$100m) more, after **underperforming in the first five
  trading days**.
- **Frequency:** ~20–40 US spin-offs a year.
- **Data:** Form 10 / 8-K on EDGAR (free, point-in-time); prices as S1.
- **Cost:** as S1, negligible.
- **Verdict:** same shape as S1 (forced selling, long hold), fewer events,
  more heterogeneous. A candidate, second to S1; the two could be one
  pre-registration ("forced-sale events") with two sub-hypotheses, which
  gate 4 would then count as two.

### S3. Odd-lot tender offers (already E8 in the backlog, `docs/20` §8)

- **Forced trader:** the *issuer* — a tender or closed-end-fund repurchase
  that takes odd lots (<100 shares) in full without proration, by
  regulation designed to protect small holders. Funds cannot be odd-lotters;
  **a $1–2k account can be nothing else.**
- **Size:** practitioner sites claim 8–14% premiums on CEF tenders at
  15–25% annualised; a GitHub "paper" claims +25% a trade on 30 events
  from yfinance — **not credible as stated** (yfinance, delisted names
  estimated, no proration or termination history). Treat the premium as
  unmeasured until reconstructed from offer documents.
- **Frequency:** 2–10 actionable a year. Position cap 99 × price, i.e.
  $500–$5,000 — exactly this account.
- **Broker:** needs corporate-action elections (IBKR does; Alpaca to
  confirm, as the backlog says). Deal-termination risk 5–15% per event.
- **Verdict:** not a gated family — too few events, each unique — but the
  one mechanism in this document where small size is *required*. The
  backlog's plan stands: reconstruct 20 completed events from their
  original terms by hand, then decide whether it is an income line.

### Rejected in stocks

- **SPAC trust arbitrage**: yields T-bill-plus, redemption rates >95% in
  2026, institutional cash management. Nothing for $1k.
- **Dividend capture, ex-date effects, calendar effects**: bps-level and
  already on the stop-list (`05`).
- **Closing-auction and late-day flows**: tested as E1 and E2; failed.

## Ranking, and what a registration would need

| Rank | Candidate | Forced trader | Stated size | Events/yr | Cost at $1–2k | Data | Blocker |
|---|---|---|---|---|---|---|---|
| 1 | S1 index deletions | trackers | +20%/yr vs market | 5–20 (S&P), 100s (Russell) | negligible | $0, PIT | 12-month horizon: slow to validate, slow to live |
| 2 | F1 Tokyo gotobi fix | importers via banks | ~3 pips reversal | ~500 pair-days | ≈ effect at $25k; 3× at $100k | $0 minute bars | needs ~$100k notional → ~$3k margin, 25× |
| 3 | S2 spin-offs | index funds | +13–17% yr 1 | 20–40 | negligible | $0, PIT | heterogeneous; fewer events |
| 4 | S3 odd-lot tenders | issuers | unmeasured (8–14% claimed) | 2–10 | broker election | EDGAR | not gate-able; hand ledger of 20 events first |
| 5 | F2 month-end 4pm fix | hedge rebalancers | ~5 bps reversal | 12 | fine | $0 | too rare alone |

None of these is registered. Under the stopping rule the counter is full
and a registration needs the owner's yes and a written mechanism memo
first (`docs/prereg/` format). What each would cost before a run:

- **S1/S2:** a loader for index-change and spin-off event lists (free
  sources, a day), an event-study instrument for the runner (hold *n*
  bars from an event date — the auction instrument's pattern), and the
  Tiingo/Alpaca daily bars already used for E5. No data spend.
- **F1:** a Dukascopy tick → minute-bar ingestor for seven JPY pairs (a
  day), a fixing-window instrument (two bars a day, as `intraday-xnas`),
  and an IBKR forex cost model with the $2 minimum and the 25k lot.
  No data spend. The pre-registration must state the notional floor.
- **S3:** no engine work; twenty offer documents and a hand ledger.

## Sources

- Ito & Yamada, *Puzzles in the Forex Tokyo "Fixing"*, NBER w22820 — nber.org/system/files/working_papers/w22820/w22820.pdf
- Krohn, Mueller & Whelan, *Foreign Exchange Fixings and Returns Around the Clock*, JF 79 (2024) — onlinelibrary.wiley.com/doi/full/10.1111/jofi.13306
- Melvin & Prins, *Equity hedging and exchange rates at the London 4pm Fix* (ECB FX workshop 2013)
- Practitioner replications (HistData minute bars): forexdetox.substack.com/p/the-tokyo-fix-reversal-anomaly-on ; forexdetox.substack.com/p/the-4-pm-london-fix-anomaly-at-month
- Euromoney, *Trading is predictable during WM 4pm fix, says Pragma*
- Arnott, Kalesnik & Wu, *Earning Alpha by Avoiding the Index Rebalancing Crowd*, FAJ 79(2) 2023 — tandfonline.com/doi/full/10.1080/0015198X.2023.2173506
- McConnell et al., *The Stock Price Performance of Spin-Off Subsidiaries*, JPM 2015; spin-off summaries at maaizkhan.substack.com/p/the-10-alpha-hidden-in-plain-sight, stockspinoffinvesting.com/the-40-rule
- Odd-lot tenders: oddlottender.com/odd-lot-tenders-guide, wallethacks.com/odd-lot-tender-offer; the uncredited "oddly" repo (github.com/KorroAi/oddly) for the claim rejected above
- SPAC market 2026: freewritings.law/2026/06/the-resurgence-of-spacs, arc-group.com/trust-overfunding-deal-starved-spac-market
- IBKR forex commissions — interactivebrokers.com/download/newMark/PDFs/commissionsForex.pdf
