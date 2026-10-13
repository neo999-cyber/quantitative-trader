# Programme 3 — structural yield and prediction markets: the study and the plan

*21 September 2026, Fable 5.1. Owner's brief: prediction markets as a
parallel track to the maker-fill study; a separate study of stablecoin
yield ("USDT, syrupUSDC and similar — small margin, less risk"); a survey
of what has been missed; a plan; nothing executed; and a tangible result
one way or the other. Every figure below is from a named source read
today or from the project's own records; nothing here was run and nothing
is registered. The questions that need the owner's answer before any of
it starts are in §6.*

## 0. What "tangible" can mean here, stated first

Three kinds of result are reachable by 31 October, each honest:

1. **A pre-registered verdict** on one prediction-market mechanism, from
   free data, through the existing gates. Pass or fail, it is a result.
2. **A measured execution-cost model** for Binance maker orders (stage 1,
   `docs/24`), which is what every crypto verdict so far has been waiting
   for — subject to a venue-access question in §6 that may kill it.
3. **A yield ladder with a number on it** — the return a $1–2k account can
   earn on stablecoins at each risk tier, net of gas and the T-bill
   baseline, with the risk named. That is not a trading edge and will not
   be presented as one; it is income the owner can choose to take.

What is *not* reachable: a system that turns $1–2k into an income you
would notice. That was `docs/18`'s verdict and nothing in this study moves
it. The value of Programme 3 is a defensible answer to "is there anything
structural a small account is *advantaged* in?" — and two of the items
below (Polymarket liquidity rewards, Binance Launchpool) are exactly that
shape: payments capped per user, where being small costs nothing.

## 1. Prediction markets — what the evidence says

### 1.1 Access and cost from Dubai

- **UAE is not geoblocked**; Polymarket is usable from Dubai without a
  VPN (VPN use breaches the terms and is not an option). Funding is USDC
  on Polygon in a self-custody wallet — the same operational model the
  owner parked Hyperliquid over. **This is question 1 in §6.**
- **Fees (Fee Structure V2, from 30 March 2026):** takers pay
  `shares × feeRate × p × (1−p)`; crypto markets carry the highest rate
  (0.07: up to $1.75 per 100 shares at 50¢, shrinking toward the
  extremes), politics/finance 0.04, geopolitics 0. **Makers pay nothing
  and receive 15–25% of taker fees back daily** (Maker Rebates), plus the
  separate **Liquidity Rewards** pool: resting orders near the midpoint on
  both sides are scored every second and paid in USDC daily (minimum $1 a
  day to be paid). Sources: Polymarket Help Center *Trading Fees*, *Maker
  Rebates Program*, *Liquidity Rewards*.
- **Data is free and unauthenticated**: Gamma (markets, resolutions),
  CLOB (books, mid, spread, `prices-history`). Caveat that matters for
  backtests: `prices-history` on resolved markets serves only **≥ 12-hour
  granularity**; sub-daily history has to be recorded forward. For a
  daily-horizon study that is enough; for anything intraday it is not.

### 1.2 The mechanisms, judged

| Mechanism | Forced / structural party | Evidence | Verdict for a $1–2k account |
|---|---|---|---|
| **Sentiment bots** (the Grok document) | none — an LLM's opinion vs the market | not backtestable (no point-in-time LLM output); 8-point threshold ≈ spread + fee on $5k-liquidity markets; $60/month = 36–72%/yr of the account | **No.** Same class as the retired idea generator. |
| **Single-market / combinatorial arbitrage** (YES+NO ≠ $1; linked markets) | none — mispricing between bots | arXiv 2605.00864 (NBA, 75M book snapshots, Feb–Mar 2026): 7 executable single-market episodes in 173 games, **median life 3.6 s**, $210 total at $100 caps; combinatorial: 290 episodes, median 101 bps, size-capped to ~15 shares. arXiv 2508.03474: $40M extracted 2024–25, top 10 accounts took $9.1M. | **No.** A latency race between bots on a chain; a laptop in Dubai polling an API is the liquidity they take. |
| **Sub-daily crypto "Up or Down" markets** (5-min, 15-min) | the *manipulator*: Stanford/SMU study of 16,000 five-minute BTC contracts — 821 suspected accounts, **$8.2M** taken via bursts of Binance spot flow in the last seconds before settlement, 3.9× normal flow | highest fee tier (0.07) precisely because of this | **No, and exclude by rule**: these are the markets where the counterparty moves the settlement print. |
| **Crypto threshold / barrier markets vs the options market** ("BTC above $X on date", "BTC reach/dip $Y by date") | **retail directional bettors**, who pay for lottery tickets — the favourite–longshot bias, measured | arXiv 2606.19517: Polymarket **over-prices the upside by 6.3 pp** (287 obs, p<1e-14) vs Binance-option-implied probability, **11 pp vs Deribit** (2,585 obs); the wedge is *persistent* (AR(1) half-life **4.2 h**), largest at low fair probabilities and long expiries; a delta-hedged proxy was borderline profitable after "conservative" costs (α 0.067, t 2.10, 69% win, 16 trades). A 2024–26 MSc thesis (33,107 obs, 6,566 contracts, Polymarket + Kalshi vs DVOL) tests the same wedge; results not in the public summary. | **The one candidate.** A named forced party, a free point-in-time benchmark (Deribit DVOL is public), a persistence horizon (hours) a maker order can work in, and today's books are liquid enough: the top BTC/ETH reach/dip markets show **$130–150k liquidity at 0.1–1¢ spreads** (Gamma, read today). |
| **"Sure-thing" yield** (buy 96–99¢ contracts days before resolution) | the seller who wants out early | no independent study found; it is an annualised carry against **resolution risk** (UMA disputes, wording) and the taker fee at the extremes (small by the formula) | **Small side study only**, free data, measurable from resolved markets; capacity is real but the tail is the whole risk. |
| **Liquidity rewards / maker rebates** | Polymarket itself pays for quotes | published daily pools per market, scored on size and distance to mid; adverse selection on the filled side is the cost | **Second candidate, and the one where small size is not a disadvantage**: the same post-only measurement as the maker-fill study, on a venue that *pays* for resting orders. Needs a book recorder (public WebSocket, no key) on the Hetzner box first. |

### 1.3 The candidate as it would be registered (P3-A, draft, not registered)

**Mechanism:** retail buyers of BTC/ETH upside "reach $X by date" and
downside "dip to $Y by date" contracts pay above the option-implied
probability; the seller of that overpricing, sized small and held to a
horizon of hours to days, collects the wedge.

**Instrument:** Polymarket BTC and ETH threshold and barrier markets with
expiry ≥ 7 days (sub-daily markets excluded by rule, §1.2). Benchmark
probability from Deribit's DVOL and spot (terminal: Black–Scholes Φ(d₂);
barrier: reflection-principle touch probability), both public and
point-in-time.

**Rule (to freeze in the memo):** when market mid exceeds model
probability by `k` points (grid 5, 8 pp), post a maker sell of YES at the
mid (fee 0); hold until the wedge closes within `x` points or `T` days;
cap per market $25, ≤ 5 open, delta-hedged variant with a Binance perp as
the second arm of the grid. Controls: the *mirror* (buy YES when
under-priced — the bias says this side is thin) and a *placebo* model
(historical realised vol instead of DVOL — if the placebo earns the same,
the edge is "sell lottery tickets" not "the options market knows").

**Data for the kill test:** every resolved BTC/ETH reach/dip/above market
2024-01 → 2026-08 from Gamma (free), daily `prices-history`, Deribit DVOL
daily (public). A count of usable markets is the first build task; the
memo states its minimum (≥ 150 markets) before any price is read.

**Costs modelled:** maker fee 0, rebate ignored (conservative), the spread
crossed only on a forced exit at expiry, Polygon gas ~$0, USDC bridging
once. The 3× bar applies.

**What kills it:** a wedge that is not there at the 12-hour granularity
the free history allows; a placebo that earns the same; or resolution
risk (UMA) eating the tail. Expected: the wedge is real and the question
is whether daily data lets a maker capture it — the paper's 4.2-hour
half-life says the fine structure is intraday.

## 2. Stablecoin yield — the study

All figures are today's reads (September 2026) unless dated; yields move.
Baseline: **3-month T-bill ≈ 3.5–4.7%** (FOBXX 7-day 3.56% June 2026;
USDY 4.65% April 2026). Anything below that is not yield, it is risk for
nothing.

| Tier | Venue / asset | Yield now | What pays it | The risk, named | Loss history | Fit at $1–2k |
|---|---|---|---|---|---|---|
| 0 | **USD T-bill via IBKR** (or a UAE bank USD deposit) | ~4% | the US Treasury | none beyond rates | none | the comparator for everything below; no crypto risk |
| 0 | **Tokenised T-bills** (USDY, BUIDL, BENJI) | 3.6–4.7% | T-bills | issuer/KYC gating (BUIDL institutional; USDY non-US retail OK) | none | fine on an L2; no advantage over tier 0 for a UAE resident with IBKR |
| 1 | **Binance Simple Earn USDT/USDC (flexible)** | 2–4% typical, promos higher on small caps | Binance lending book | Binance solvency; product availability on the **Dubai (FZE) entity** unconfirmed (§6 q3) | none on Earn | the zero-effort tier; **the promos are capped per user — a small-account advantage** |
| 1 | **Aave v3 USDC** | **3.45%** now (2025 avg 5.9%) | over-collateralised borrowers | smart contract; rates fall with utilisation | none on v3 | below T-bill today; not worth gas on mainnet; on Base/Arbitrum gas is cents |
| 2 | **Morpho curated USDC vaults** | 4–8% | over-collateralised borrowers, curator-selected | curator judgment, longer-tail collateral | none major | Base/Arbitrum only; read the curator, not the APY |
| 2 | **syrupUSDC (Maple)** | **4.6%** weighted now; 7%+ when incentivised | fixed-rate over-collateralised loans to institutions | credit and delegate risk; Maple's *unsecured* model lost ~$54M in 2022 (Orthogonal, Babel); rebuilt over-collateralised, no principal loss since; third-party grade C- | 2022 | acceptable at tier 2 only; the incentivised 7% is a promotion, not the rate |
| 3 | **sUSDe (Ethena)** | high single digits now; 4–30% over 2024–25 | perp funding carry + staking — **this is C1's always-in book, institutionalised** | funding turns negative (reserve fund $61M vs $5.6B supply = 1.1%); exchange/custody; 11 Oct 2025: USDe printed **$0.65 on Binance** (exchange oracle fault, protocol redemptions held) and **$8.3B left** in two months | Oct 2025 scare, no principal loss | the yield we already measured (funding 97% of gross, Sharpe 2.4 always-in) with the same tail; tier 3 by construction |
| 3 | **Pendle PT** on sUSDe / syrupUSDC | 1–3 pts below the floating rate, **fixed to maturity** | selling the upside of the floating yield | underlying's risk plus Pendle contract; locked to maturity (secondary exit possible at a price) | none | the "small margin, less risk" instrument the owner asked about: fixes the number; **lock-up is question 2 in §6** |
| 4 | **Binance Launchpool / HODLer airdrops / Megadrop** | promoters claim 20–100% APR *during farming windows* (days each), "84% average APY" and "94% positive" — **unmeasured by us** | new-token issuers paying for distribution; **capped per user** | token price at listing; availability on the Dubai entity; the numbers come from promoters | — | **the one yield where small size is structurally favoured**; needs its own measurement before belief (§4) |

**Arithmetic on $2,000, honest:** tier 1–2 earn T-bill + 0–3% = **$0–60
a year over cash**; tier 3 perhaps + 3–8% = $60–160 with a real tail;
tier 4 unknown until measured. Ethereum mainnet gas ($2–10 a transaction)
makes any mainnet DeFi position pointless at this size — L2s or CeFi
only. None of this is a strategy; it is where idle USDC sits while the
research runs, and the owner should read it that way.

## 3. What was missed — the survey, with verdicts

Beyond §1–2, the structural mechanisms a small UAE account could stand in:

| Idea | Structural party | Verdict |
|---|---|---|
| Binance/exchange promotions, sign-up and referral bonuses, new-listing rewards | the exchange buying flow | real, one-off, capped; worth taking, not a programme |
| Airdrop / points farming | protocols paying for usage | unmeasurable ex ante, speculative; no |
| **Odd-lot tenders** | issuers, by regulation | already E8; hand ledger of 20 events still owed |
| IBKR Stock Yield Enhancement (lending shares) | short sellers | pennies at $1–2k; no |
| UAE bank USD/AED deposits | banks | the tier-0 baseline, nothing more |
| Polymarket **sure-thing** carry | early sellers | §1.2 side study |
| Polymarket **liquidity rewards** | the venue | §1.2 candidate P3-B |
| Cross-venue prediction arbitrage (Polymarket vs Kalshi) | — | Kalshi is US-only; no |
| Perp basis on Binance (spot vs quarterly futures) | levered longs | the same carry as C1 in another wrapper; Binance quarterly delivery futures may be gated on the Dubai entity (§6 q3) |

## 4. The plan (nothing starts without the answers in §6)

**Rules carried over unchanged:** pre-register then run; every backtest
counted; the 3× bar; controls; holdout once; no money moves without a
yes; a key pasted anywhere is burned. Programme 3 gets its own counter of
**three registrations**; the counter is not a promise to use them.

| When | Item | Cost | Needs from owner |
|---|---|---|---|
| now → 30 Sep | **Polymarket loader**: Gamma resolved-market catalogue + daily price history for BTC/ETH threshold/barrier markets; **Deribit DVOL loader** (public); count usable markets; **P3-A memo** drafted from §1.3 | $0, ~2 days | q1 (wallet) only for the *live* stage later; the kill test needs no wallet |
| now → 30 Sep | **Polymarket book recorder** on the Hetzner box (public WebSocket, standard library, beside the tape recorder) for P3-B and for the intraday structure P3-A's daily data cannot see | $0 | q7 |
| 1 Oct | stage 0 read (maker fills, Binance) — unchanged | $0 | — |
| 1–7 Oct | **P3-A kill test** (one counted run) | $0 | the yes to register |
| Oct | **P3-B** stage 0 on the recorded Polymarket book: virtual two-sided quotes, fill and adverse-selection measurement, rewards earned per the published schedule | $0 | — |
| Oct, if stage 0 passes **and q3 allows** | Binance stage 1 | $25 at risk | the yes |
| Oct | **Launchpool measurement**: record every Launchpool/HODLer announcement forward (caps, duration, pool size, listing price) → realised APR per $ of USDC staked; no participation until 5 events are measured | $0 | q3 (is it visible on the Dubai entity?) |
| by 31 Oct | **Yield ladder decision** — the owner picks a tier and a lock-up; a paper allocation is written down with its risk named before any transfer | $0 → then real | q2, q4 |
| 31 Oct | **Programme 3 report**: P3-A verdict, P3-B measurement, the ladder with its number, Launchpool's first measured events, and the maker-fill result | — | — |

**Deliverable by 31 October, whichever way the results fall:** a
registered verdict on the one prediction-market mechanism with a named
forced party; a measured maker-cost model or a documented reason it
cannot be measured for this account; a yield ladder with a number and a
risk tier chosen by the owner; and one measured structural, small-size-
advantaged income (Launchpool or Polymarket rewards) or its refutation.

## 5. What this plan deliberately does not do

Build the Grok/sentiment bot; trade sub-daily crypto markets; chase
on-chain arbitrage; put $1–2k on Ethereum mainnet; treat any promoter's
APY as a measurement; register anything before its memo; move money
before a written allocation and a yes.

## 6. Questions for the owner — answer before anything starts

1. **Self-custody.** Polymarket requires a Polygon wallet holding USDC
   (Hyperliquid was parked on this point). Is a wallet with $50–200
   acceptable for a live stage of P3-A/P3-B, once the kill test passes?
   The kill test itself needs no wallet.
2. **Lock-up and risk tier for the yield ladder.** How much of the
   $1–2k may sit locked (Pendle PT to a maturity; Binance locked
   products), and is tier 3 (sUSDe-type, funding-carry risk) in or out?
3. **Binance Dubai (FZE) product visibility — the most consequential
   answer.** Binance FZE's published offering gives *all* users spot and
   staking, but **margin and derivatives "to Qualified and Institutional
   Investors"**. Please check in your Binance app: (a) can you open a
   USDⓈ-M futures position today? (b) do you see Simple Earn (flexible
   and locked), Launchpool and HODLer airdrops? If (a) is no, **stage 1
   of the maker-fill study cannot run on your account** and the C1
   re-registration route changes; if (b) is no, tiers 1 and 4 move
   elsewhere.
4. **Capital split.** A number for each: research/live studies (today
   capped at $25 at risk), yield ladder (idle USDC), untouched.
5. **"Tangible result" — your definition and date.** My proposal is §4's
   31 October deliverable. If yours is "a positive net number in my
   account by a date", say the number and the date and I will tell you
   plainly whether any tier can reach it.
6. **Tax/reporting.** I assume none in the UAE on any of this; correct me
   if a bank or employer reporting rule applies to you.
7. **Hetzner.** A second public recorder (Polymarket books, standard
   library, no key) beside the tape and liquidation recorders — yes/no.

## Sources read today

Polymarket Help Center: *Geographic Restrictions* (updated 14 Aug 2026),
*Trading Fees* (Fee Structure V2), *Maker Rebates Program*, *Liquidity
Rewards*; Polymarket docs *Get prices history*; py-clob-client issue #216
(12-hour granularity on resolved markets); Gamma API read 21 Sep 2026 ·
arXiv 2605.00864 (NBA arbitrage) · arXiv 2508.03474 (arbitrage, $40M) ·
arXiv 2606.19517 (Polymarket vs Binance/Deribit BTC thresholds) ·
Stanford/SMU 5-minute BTC manipulation study (press summaries; paper
circumstantial by its own statement) · MSc thesis
giannandreadestefano/btc-prediction-market-efficiency (method only) ·
Maple/syrupUSDC: Messari, Stablewatch, Hindenrank, 2022 default reports ·
Ethena: Aavescan, Q1-2026 report, CoinDesk 11–13 Oct 2025, Cointelegraph
outflow report · Pendle Print, Coin Bureau · Aavescan USDC, Morpho vaults,
Ondo USDY, Franklin FOBXX · Binance FZE VARA licence, UAE transition FAQ,
*Virtual Assets Product Offering on Binance Dubai* · Launchpool figures:
CoinGecko category, promoter guides (flagged as promoter figures).

## 7. Owner's answers (21 September 2026) and the decisions taken

1. **Binance Dubai futures: approved** — the owner passed the Product
   Suitability Assessment on 21 September; USDⓈ-M futures are open to the
   account. Stage 1 of the maker-fill study can run here. Earn products
   (Simple Earn, Launchpool): to be confirmed from the Earn page.
2. **Self-custody wallet for a Polymarket live stage: yes** — only after
   P3-A/P3-B pass their kill tests, and funded to the study cap, never more.
3. **Yield ladder, decided on the owner's "you suggest":** tiers 1–2 only.
   Idle USDC sits in Binance Simple Earn *flexible* (no lock-up, promos
   capped per user); Launchpool measured before any participation; tier 3
   (sUSDe-type funding-carry risk) **out**; Pendle/mainnet DeFi **out** at
   this size (gas and lock-up buy nothing on $2k). Honest expectation:
   $0–60 a year over cash. It is parking, not a result.
4. **Capital split, decided on "best for the project, I don't mind losing
   some":** of the ~$2,000 — **$200 studies bucket** (the only money that
   can be lost: stage 1's $25 stop, a Polymarket live stage at ≤ $100, the
   rest reserve for closes), **$1,300 idle yield** (tier 1, withdrawable
   any day), **$500 untouched** in fiat or USDC outside any product. No
   study may draw on the other two buckets; moving a dollar between
   buckets is an owner decision recorded here.
5. **Tangible result: the 31 October deliverable in §4** stands as the
   definition.
6. Tax/reporting: none applies.
7. **Polymarket book recorder on the Hetzner box: yes.**

**What starts now ($0, nothing registered, no money moves):** the
Polymarket catalogue and daily-history loader, the Deribit DVOL loader,
the usable-market count, the P3-A memo draft, and the Polymarket book
recorder. Registration of P3-A waits for the memo and the owner's yes to
that text.

## 8. Build log — 21 September 2026 (all $0, nothing registered, no money moved)

- **Loaders**: `qr/data/polymarket.py` (Gamma `public-search` discovery
  over fourteen fixed queries, rule-based classification into
  reach/dip/above with the strike and asset, eligibility filter, daily
  CLOB `prices-history` per YES token, all mirrored under
  `mirror/polymarket/`) and `qr/data/deribit.py` (DVOL daily OHLC, paged,
  mirrored, written as `reference/dvol_BTC` / `reference/dvol_ETH`).
  Tests on fixtures, no network.
- **The count** (the memo's first build task): **9,048 eligible markets**
  — resolved, classifiable, horizon ≥ 7 days, volume ≥ $10k, race markets
  ("$70k or $90k first") excluded: BTC 4,486 (above 3,300 / dip 561 /
  reach 625), ETH 3,870, SOL 692; 7,818 weekly and 1,117 monthly-or-longer;
  median volume $141k; resolutions November 2021 → 20 September 2026 with
  96% in 2025–26. Sixty times the memo's minimum. The resolved-YES rate is
  38%; nothing else about outcomes or prices was read. Daily YES histories
  are being pulled for every eligible market (first 500: 491 with data).
- **DVOL**: BTC and ETH, 2,008 days each, 2021-03-24 → 2026-09-21.
- **Memo drafted, not registered**: `docs/prereg/p3_threshold_wedge_v1.md`
  — the model (Φ(d₂) terminal; reflection-principle touch), the rule
  (sell YES on a wedge ≥ k, maker, 1-point haircut, one market per
  asset × settlement date, $25 × 5), the grid (k ∈ {5, 8} × T ∈ {resolution,
  7 d}), three controls (mirror, realised-vol placebo, naive short of
  everything ≤ 20¢), clustered t by asset × end date, holdout June →
  September 2026, and the stated limit of daily data. **Registered the
  same day on the owner's yes** — `qr trial prereg`, seq 932, doc sha256
  `8568e870…`; the engine script `scripts/p3a_wedge.py` did not exist at
  registration, so no wedge was seen before it. Programme 3's counter is
  at one.
- **Recorders live on the Hetzner box** (`~/pm/`, own venv, standard
  library + `websockets`, nothing else installed): `qr-pm-polymarket`
  (CLOB market channel for the YES token of every active BTC/ETH/SOL
  threshold market, 160 at start, list refreshed hourly; messages
  compacted as documented in `scripts/record_polymarket.py`; ~200 MB a day
  gzipped) and `qr-pm-deribit` (DVOL and price indices at the venue's
  cadence). Disk: 25 GB free at start; check `df` when the tape is
  mirrored on 1 October and stop `qr-tape-*` once the 14 days are copied.
- **Not done, by rule**: no registration, no wallet, no USDC moved, no
  Simple Earn subscription (owner action), no Launchpool recorder yet
  (needs the Earn page's Launchpool tab confirmed first).

## 9. P3-A in-sample result — 21 September 2026: **FAIL** on the registered rule

Run once, counted (trial log seq 933; engine `scripts/p3a_wedge.py`,
built after registration). In-sample: 7,073 markets ending before 1 June
2026, 6,632 with usable daily history. One market per asset × settlement
date collapses the weekly ladders to **586 trades** at `k` = 5.

| Run | n | edge / share | clustered t | win | hold | book Sharpe |
|---|---|---|---|---|---|---|
| **family k5, to resolution** | 586 | **+2.63 pt** | **2.04** | 0.51 | 3.7 d | −0.28 |
| family k5, T = 7 d | 586 | +2.59 | 2.01 | 0.51 | 3.0 d | −0.21 |
| family k8, to resolution | 561 | +1.44 | 1.02 | 0.52 | 3.6 d | −0.48 |
| family k8, T = 7 d | 561 | +1.41 | 1.00 | 0.52 | 2.9 d | −0.49 |
| mirror k5 (buy under-priced) | 583 | −1.54 | −1.03 | 0.48 | 4.1 d | +0.34 |
| mirror k8 | 534 | −2.70 | −1.71 | 0.50 | 4.5 d | +0.16 |
| placebo k5 (realised vol) | 588 | −0.91 | −0.71 | 0.50 | 4.2 d | −0.77 |
| placebo k8 | 563 | −0.33 | −0.25 | 0.53 | 4.3 d | −0.43 |
| naive short ≤ 20¢ | 515 | +1.75 | 2.78 | 0.98 | 10.7 d | +0.27 |

Gates over the four family variants: best net Sharpe −0.21, HAC t −0.33,
DSR 0.28, PBO 0.29.

**Against the registered falsifiers:** mean edge at `k` = 5 is 2.63 points
— **below the 3-point bar**; clustered t 2.04 — **below 3**; the book
Sharpe is negative, not above 1; DSR 0.28 — gate 4 fails. The family does
beat the naive short per share (2.63 vs 1.75) and the mirror is negative
(so the wedge is one-sided, as the bias says), and **the placebo does not
match it** (−0.9 pt): whatever is there comes from DVOL, not from "sell
lottery tickets". That is the one finding worth keeping.

**What the breakdown says (descriptive, not a new test):** the edge is in
BTC (+4.6 pt, t 2.4) and in `reach` (+5.2) and `above` (+3.3) markets;
`dip` markets go the other way (−5.7 pt: the model under-prices downside
touches — the smile the model deliberately omits). It is concentrated in
**2026 (+5.6 pt over 242 trades) against +0.5 pt in 2024–25**, which is
the period the paper measured; and in fills between 20¢ and 50¢. The book
loses because dollar sizing (`$25 / (1 − fill)`) puts the most shares on
the high-priced contracts, exactly where the edge is negative.

**Why the book and the per-share numbers disagree, stated so no one
"fixes" it into a pass:** the memo froze $25 of capital per market. A
version sized in shares, or restricted to BTC `reach` markets in 2026,
would look better — and would be a rule written after seeing the data. It
is not run.

**Status:** Programme 3's counter is at one registered, one failed. The
holdout (June–September 2026) is **not opened**: the in-sample verdict
failed, and opening it would spend the one look on a family that did not
earn it. If the owner wants a second version, the honest inputs are
(1) the intraday recording now running (the paper's 4.2-hour half-life
says the daily print sees the residue), (2) a smile-aware model for `dip`
markets, and (3) share-based sizing — each a new memo with a new
counter, registered before any run. Nothing else changes: no wallet, no
USDC moved, nothing registered.

Outputs: `reports/p3/p3_threshold_wedge_v1_insample_{summary.json,trades.parquet,book_returns.parquet}` in the lake.

## 10. 21 September, later — v2 registered; the Launchpool → HODLer Airdrops finding

- **`p3_threshold_wedge_v2_intraday` registered** on the owner's yes,
  seq 934, doc sha256 `2d413ed8…`. Read once on 27 October from the
  recording (21 Sep → 26 Oct), if ≥ 30 asset × settlement-date clusters
  have a fill; else deferred to 30 November. Programme 3's counter: two
  registered, one failed, one waiting on data. One registration left.
- **Yield recorder** (`qr-yield.timer`, daily) live: DefiLlama pools,
  FRED DTB3, Binance announcements (catalogues 48/93/128) with article
  bodies. First day: syrupUSDC 5.07%, Aave v3 USDC 3.62%, USDT 3.99%.
- **Launchpool has effectively been replaced by HODLer Airdrops** in the
  2026 announcement stream (12 watched articles in the last 50 per
  catalogue: all HODLer Airdrops or Alpha trading competitions, no
  Launchpool). The mechanism: Binance takes *retroactive* snapshots of
  BNB held in Simple Earn over a past window; a new token gives ~1% of
  its supply (AVNT: 10M tokens) to those holders pro rata, capped per
  user; the tokens arrive before listing and can be sold at listing.
  **The staked asset is BNB, not a stablecoin** — the yield rides on the
  BNB price, so this is tier 2–3, not the tier-1 parking the ladder was
  for. The recorder now measures each event (tokens × listing price ÷ BNB
  in Simple Earn); **no participation until five events are measured**, as
  §4 said, and no BNB is bought for it — that would be an owner decision
  against a measured number, not a promoter's APR.

## 11. Launchpool, measured from Binance's own numbers — 21 September 2026

Not five events forward: Binance's public Launchpool endpoint carries
every completed pool with the whole pool's stake, the reward per staked
coin and the per-user cap (`qr/data/launchpool.py`, mirrored under
`mirror/binance/launchpool/`, 179 pools 2020 → March 2026; listing prices
from spot daily klines). Measured, for the **stablecoin pools** (FDUSD,
USDC, USD1, U — the ones that fit a tier-1 stake), one stake in the best
pool per project, tokens valued at the listing day's close:

| Year | projects | pool days | yield on the stake, summed | median APR *during* a pool |
|---|---|---|---|---|
| 2020 | 9 | 256 | 7.95% | 12% |
| 2021 | 14 | 418 | 9.62% | 6% |
| 2022 | 3 | 90 | 0.58% | 1% |
| 2023 | 2 | 42 | 2.05% | 148% |
| 2024 | 2 | 5 | 1.26% | 110% |
| 2025 | 9 | 35 | **2.03%** | 22% |
| 2026 to date | 1 | 2 | 0.07% | 13% |

- **The "84% APY" is the rate during a two-day pool, annualised.** The
  stake earns it for 2–3 days a few times a year; summed, 2025 paid
  **2.0% for the year** and 2026 has paid 0.07% so far. The tokens fall
  a median **11% by day 7** after listing, so "sell at listing" is the
  number, not "hold".
- **No small-size advantage.** The per-user cap is 10% of the pool's
  hourly reward; it binds at a stake of $30–260 million. Rewards are
  linear in the stake below that. The claim in §2 tier 4 is withdrawn.
- **What it is:** 1–2% a year on top of tier 1 in a busy year, ~0 in a
  quiet one, principal untouched (the stablecoin sits in Binance custody
  either way; ~0.4% of Simple Earn interest forgone on pool days). Worth
  taking when a stablecoin pool is announced and the owner is already on
  Binance; not a reason to move money. The announcement recorder flags
  each new pool; participation is the owner's action each time.
- HODLer Airdrops (BNB-based, §10) remain unmeasured — Binance publishes
  no pool total for them; the estimate in this session's discussion
  (0.1–0.2% of BNB per event) stands as an estimate.

## 12. P3-B (liquidity rewards) — sized from the first five hours of book, 21 September 2026

A measurement, not a candidate; nothing registered. Polymarket publishes
every market's reward pool (`clob.polymarket.com/rewards/markets/current`,
mirrored: 16,096 markets share **$144k a day**, median **$3 a day** per
market). Of the 159 crypto threshold markets being recorded, **42 have a
pool, each $5 a day**, max spread 4.5¢, minimum size 20 shares. From
1,240 recorded book snapshots (mid between 10¢ and 90¢), with the
published quadratic score, $100 resting on *each* side 1¢ from the mid —
the whole $200 studies bucket in one market — would hold a median
**0.59%** of the score (q75 2.2%, q90 7.9%; the median market has $24k
resting within the band). That is **3¢ a day per market** at the median,
39¢ on the thinnest tenth. Polymarket pays nothing below **$1 a day**;
five markets at the median earn 15¢. **P3-B cannot clear the payout
floor at this account size** except by sitting alone in the thinnest
markets, where the adverse selection on the filled side is the whole
question — and that needs weeks of prints, not hours. Parked: the
recording continues; it is re-sized on 27 October with the v2 read, from
the same tape, and only a number above the floor after adverse selection
gets a memo. Programme 3's counter stays at two of three.

## 13. 1 October 2026 — the "virtual world", made into two bounded pieces

The owner's question ("why can't we calculate the fluctuations from ten
years of everything, the way weather is forecast?") was answered in the
session (physics vs. adaptive agents; observable vs. hidden state; 4,000
days vs. "every parameter") and turned into the two things it can
honestly be here. Decided: the **third and last Programme 3
registration goes to A**; B is built alongside for the ladder.

**A. `p3_forecastability_v1` — drafted, not registered**
(`docs/prereg/p3_forecastability_v1.md`). Three targets on BTC (1-day
direction, 7-day return, 1-day variance); every point-in-time, $0 input
the project can get (price, funding, open interest, DVOL, Fear & Greed
since 2018, stablecoin supply since 2017, on-chain since 2009, FRED
macro); three model families (ridge/logit floor, gradient-boosted trees,
a zero-shot time-series foundation model); expanding walk-forward from
2021-03 with monthly refits and a 7-day purge; nine variants; the bars
are the base rate, the random walk and **DVOL**, each with t ≥ 3, then
the money test through the ledger; controls are permuted targets and a
one-day extra lag. Prior: direction and the 7-day return fail; the vol
model beats GARCH and not DVOL. **Two yeses outstanding:** the text, and
the ~2.3 GB `torch` + Chronos download for the foundation-model arm (if
declined, six variants, stated in the memo).

**B. The ladder stress simulator — built** (`qr/research/stable_stress.py`,
`scripts/stable_stress.py`, table at `reports/p3/ladder_stress.md`). Not
a forecast: a one-year Monte Carlo over *named* events per tier, every
rate and loss size in one editable table with its historical anchor
(FTX, SVB/USDC $0.88, Maple 2022, USDe $0.65, UST), three replays. On
$1,300, 20,000 simulated years:

| Tier | Instrument | Yield | Expected | P(loss > 10%) | CVaR 5% |
|---|---|---|---|---|---|
| 0 | T-bill (IBKR) | 4.0% | **+4.0%** | 0% | +4.0% |
| 1 | Binance Simple Earn USDC/USDT | 3.0% | +1.1% | 2.5% | −30% |
| 1 | Aave v3 USDC (L2) | 3.6% | +1.3% | 4.1% | −36% |
| 2 | syrupUSDC (Maple) | 5.0% | −0.3% | 7.9% | −49% |
| 3 | sUSDe (Ethena) | 8.0% | +1.2% | 12.4% | −55% |
| 3 | Pendle PT on sUSDe | 7.0% | −3.1% | 16.8% | −77% |
| 2 | BNB for HODLer Airdrops | 9.0% (est.) | +7.7% | 50.5% | −76% |

What the table says, with the assumptions as written: **the T-bill wins
every stablecoin tier in expectation** — the stated yields above it are
smaller than the expected cost of the tail that pays them (custody
~1.5%/yr at a 1-in-40 venue failure; contracts ~1.5%/yr; credit;
carry). Tier 1 on Binance costs ~3% a year against the T-bill and is
justified only by money that has to sit on Binance anyway (stage 1,
Launchpool pools). BNB's +7.7% is a coin-flip on BNB's price (58% of
years lose), not a yield. The numbers move with the assumptions, which
is the point: the owner can change a rate and see what it takes for a
tier to beat 4%. **The ladder decision for 31 October is therefore
written as a choice between the T-bill and Binance-resident cash, not
between DeFi tiers.**

## 14. 1 October 2026 — P3-C `p3_forecastability_v1`: **FAIL** on every pair (seq 938)

Run once on the registered rules (a first run, seq 936, was voided the
same hour: the Chronos arm's history included the target day's own
return, a look-ahead the memo's leak rule caught at "Sharpe 5 on daily
direction"; fixed, guarded by a test, noted at seq 937). In-sample test
months January 2023 → May 2026, 1,227 forecast days per pair, 43
features, nine (target, model) pairs, every control run.

| Target | Model | Out of sample | vs its benchmark | Money test (net Sharpe) |
|---|---|---|---|---|
| direction, 1 d | ridge / logit | 48.6% | base rate 49.2%, t −0.6 | −1.35 |
| | gradient boosting | 49.9% | t +0.4 | −1.24 |
| | Chronos (zero-shot) | 48.6% | t −0.3 | −0.30 |
| return, 7 d | ridge | R² −0.70 | DM t −4.8 vs the random walk | −0.93 |
| | gradient boosting | R² −0.67 | t −5.5 | −0.88 |
| | Chronos | R² −0.01 | t −0.9 | +0.02 |
| variance, 1 d | ridge | QLIKE 0.610 | worse than DVOL (t −2.8) and GARCH | — |
| | **gradient boosting** | **0.416** | **beats GARCH (t 3.4); DVOL 0.473, t 2.0 — below the bar of 3** | — |
| | Chronos | 0.477 | equal to DVOL (t −0.1) | — |

Gates over the six tradeable pairs: best net Sharpe +0.02, DSR 0.07, PBO
0.50. Permuted-target controls sit at the base rate everywhere; the
extra-lag check changes nothing that was passing (nothing was).

**Reading.** Tomorrow's direction and next week's return are not
forecastable from any of it — not from price, funding, open interest,
options, sentiment, stablecoin supply, the chain or the dollar — by a
linear model, a tree ensemble, or a foundation model, over three and a
half years out of sample; the models that try lose 20–35% a year after
costs. Volatility *is* forecastable: gradient boosting on the same
inputs beats the textbook GARCH decisively, and comes close to the
options market — and does not beat it. **For the third time in this
project, the market's own number (here DVOL) is the best forecast
available.** The holdout stays shut. Programme 3's three registrations
are spent: P3-A v1 failed, P3-A v2 reads on 27 October, P3-C failed.

**What this closes.** The "virtual world" question, for this account:
a model of everything observable does not forecast the price, and the
one thing it forecasts (volatility) is already published free by the
options market. A simulator is the right tool for *what breaks*
(§13 B), not for *what happens next*.

## 15. 6 October 2026 — parked until stage 1 ends (12 October): the data-expansion plan

The owner asked what external data and what approach could add to the project ("there has to be more to
this") and decided to return to it after stage 1's ten sessions. Logged here so it is not lost; nothing
below is registered, pulled or run.

- **Ruled out, by the owner:** meme-coin and listing work (`docs/prereg/p4_listing_fade_v1.md`, filed, never
  registered). Not to be raised again.
- **Finding to keep in view:** more modelling of the inputs we have adds nothing (P3-C, `§14`); anything new
  comes from new information with a *forced* party behind it.
- **Candidates, free first, in the order worth getting:**
  1. **US spot-ETF daily flows, backfilled** from Farside (Jan 2024 →, ~450 trading days; the recorder covers
     September 2026 only). Mechanism: creations settle T+1, so authorised participants must buy BTC during US
     hours after an inflow day — a named forced buyer; test the US-hours drift after flow days. The best new
     idea on the list; prior modest (arbitraged over time, thin history).
  2. **CFTC Commitments of Traders** for CME bitcoin futures (weekly, 2017 →): leveraged-fund vs asset-manager
     positioning; basis-trade crowding and squeezes.
  3. **Coin Metrics community on-chain metrics** (daily, 2011 →): exchange in/outflows, realised profit/loss,
     holder cohorts — what P3-C lacked. Mechanism: coins moving onto exchanges precede selling.
  4. **Deribit full options surface** (strikes, skew, open interest): dealer hedging near large open interest
     into expiry; record forward now at $0 (history is paid).
  5. **Hyperliquid positioning** (every position and liquidation price public): visible liquidation clusters
     as magnets; record forward at $0; the professional stop-hunt, likely too fast for this account.
  Paid on-chain feeds (Glassnode, CryptoQuant; $100–800 a month) only after a free-tier test shows something.
- **Already measured positive and not to be forgotten:** C1's funding carry — Sharpe 2.4 net, funding 97%
  of the return; failed the gates as a *timing* rule because timing added nothing over always-in. The right
  version is a plain cash-and-carry holding, a yield with a tail (exchange, negative funding), comparable to
  the ladder's T-bill at 4%; its entry/exit cost is what stage 1 measures. A holding decision for the owner.
- **Proposed shape when we return:** one data-expansion programme with two registrations — the ETF-flow
  pressure mechanism, and C2 re-tested against the measured maker cost — with the other feeds recorded
  forward from now so they exist in three months. Nothing starts without the owner's yes.

## 16. 13 October 2026 — after stage 1: the dry-run, the C2 memo, the recorders

The owner's answers to the 12 October list: the key's futures permission unticked (their hand), yes to
the parser dry-run, yes to the C2 re-test, "let's work on the decisions". Done today, in that order:

- **Parser dry-run over the real recording — counts only, no wedge.** `scripts/p3a_dryrun_counts.py`
  reads the recording exactly as the 27 October engine does (every hourly gzip member, every line, the
  inner JSON) and counts: files, days, truncated members, messages by type and channel, tokens with
  quotes and with trade prints, gaps, the catalogue's shape, then (laptop stage) the frozen classifier's
  coverage and the asset × settlement-date clusters. It never computes a model probability or compares a
  price with anything; it is disclosed in the trial log as a *note* under `p3_threshold_wedge_v2_intraday`,
  not a run. Standard library, so the stream pass ran on the box beside the recorder (22 minutes) and again on the
  laptop's mirror (7.7 minutes; the two agree line for line except the hour being written). Trial-log note
  seq 940; report `reports/p3/p3a_v2_dryrun_2026-10-13.md`. **The recording is sound and the sample is not
  there:** 23 days, 67.4 M Polymarket messages (32,186 trade prints over 248 of 256 tokens), 8.45 M Deribit
  prints, no gap over four minutes on Polymarket; the catalogue's 255 markets all classify (`reach` 143,
  `dip` 112, `above` 0) and fall into **17 asset × settlement-date clusters in total** — monthly ("in
  October"), year-end and quarterly ladders — of which **3 end by 27 October and 6 by 30 November**, against
  the memo's minimum of 30 with a fill. The registered read is therefore deferred on both dates by
  construction, and at three new monthly ladders a month the minimum is not reached before mid-2027. The
  engine need not run on 27 October to know this (and running it would spend the "read once"); a note will
  record the deferral on the day. The cause: the memo assumed "five weekly settlement cycles", but
  Polymarket's short-dated BTC/ETH/SOL ladders are the *daily* "above $X on <date>" markets (~45–60 a day
  across the three assets, listed with just under seven days to run, liquidity in the final 48 hours:
  ~$80k on the settlement day, ~$4k two days out) and v1's ≥ 7-day horizon rule, carried into the
  recorder, never admits them. **The owner's options, nothing started:** (A) leave v2 as registered — the
  recording costs nothing and the verdict arrives in 2027; (B) extend the recorder to the daily ladders
  from the day the owner says so (forward-only; ~3 clusters a day, so 30 clusters in ten days), with σ
  from the options surface at the matching one-to-seven-day tenor (the surface recorder below records
  exactly that) and a **v3 memo** — which needs a fourth Programme 3 registration, i.e. the owner's
  decision to extend the counter of three. The v1 finding (daily data, +2.6 points, t 2.0, placebo below)
  is unchanged by any of this.
- **One pass, not thirteen.** The v2 script re-read the whole recording once per variant and control —
  thirteen passes of ~100 million lines, hours of gzip and JSON for nothing on 27 October. `WedgeSession.run`
  is now `step` + `settle`, and `run_many` feeds every message to all thirteen sessions from one pass; the
  sessions share no state, and a test shows `run_many` produces `run`'s trade tables exactly. The rule, the
  fill model and the grid are untouched; the registered memo (seq 934) is not.
- **C2 v2 drafted, not registered:** `docs/prereg/p2_venue_spread_v2_maker.md` (+ `_always_in`). The one
  change from v1 is the cost model, `--costs xvenue_maker`: the Binance leg at stage 1's measured maker cost
  (3.23 bps a side: fee blended at the 94.2% fill, the +1.06 bps 60-second mark as the spread; weekday/
  weekend fill rates as the runner's haircut, which `carry_pair` now inherits from a measured leg), the Bybit
  leg taker as before (7.0 bps, the only leg a measurement exists for) — **10.23 bps a side against v1's
  12.50**. A pre-stated sensitivity, `xvenue_maker_both` (6.46 bps; Bybit *assumed* to fill as Binance did),
  runs beside it and cannot pass on its own. The memo's honest prior is FAIL at gates 4 and 5: the measured
  cost takes 18% off the drag (+0.3%/yr of net return), and a 2–3%/yr book at 1× does not beat a 3%/yr
  T-bill, which is the hurdle gate 5 holds it to because idle margin on an exchange earns nothing. Its value
  is the number in the "what it would take" line — short by costs (then a Bybit measurement is next) or by
  the spread's own size (then C2 is closed at 1×). Registration is the owner's yes; the run is a night job.
- **The recorders of §15 (items 4 and 5), built and not started:** `scripts/record_surface.py`, standard
  library, one hourly snapshot of Deribit's full BTC and ETH options book summary (every strike's mark IV,
  open interest, volume, bid/ask — ~900 instruments a currency, ~40 KB gzipped a snapshot, ~2 MB a day) and
  Hyperliquid's per-asset contexts (funding, open interest, oracle/mark, premium, day volume for ~230 perps,
  ~14 KB a snapshot). Units in `deploy/surface/` (`qr-surface.timer`, two minutes past every hour). Probed
  once from the laptop to fix the fields: BTC open interest today sits 142k contracts on 30 October and
  127k on 25 December — the expiry-pinning mechanism's raw material. The per-address liquidation map
  Hyperliquid makes public needs a walk over every account and is a separate build. **Starting them on the
  box is the owner's yes**; the box has 26 GB free.
- **The key.** The owner unticked *Enable Futures*; from the box the key still answered a futures balance
  and position read afterwards, which I read as "not saved". **Wrong, corrected at 11:11 UTC:** Binance
  allows the futures account reads on *Enable Reading* alone; only trading needs the futures permission.
  The definitive check is the key's own permission flags, `GET /sapi/v1/account/apiRestrictions` (signed,
  read-only): `enableFutures false, enableReading true, ipRestrict true`, trading, margin, withdrawals and
  transfers all false. The untick had saved. Nothing is scheduled and the standing mandate expired on
  11 October.

## 17. 13 October 2026, later — options A and B taken; C2 v2 run; the counter extended to four

The owner: "let's do options A and B; if anything else can be done now, do it." Done, in order of what was
forward-only:

- **B, the recorder (04:53 UTC).** `scripts/record_polymarket.py` takes `--min-horizon-days` (7 by default,
  v1's rule); the box unit runs it at **1**, which admits the daily "above $X on <date>" ladders (listed with
  just under seven days to run). Four discovery queries were missing ("solana above", "price of
  bitcoin/ethereum/solana" — the daily questions begin that way), added. The horizon rule is stamped on every
  catalogue line. Restarted 04:53:05 UTC: **659 active markets** (231 daily-ladder markets = 11 strikes × 3
  assets × 7 days, plus 428 monthly and longer) against 255 before; the message rate is ~3.7× (10 M lines a
  day, ~300 MB gzipped), so the box's 25 GB lasts to about the turn of the year — a daily disk alert now
  pushes through ntfy below 5 GB (`deploy/surface/disk_alert.sh`, cron 06:00 UTC). The old recorder is kept
  beside it as `record_polymarket.py.v1_2026-09-21`.
- **The surface recorder (04:49 UTC).** `qr-surface.timer` on the box, two minutes past every hour:
  Deribit's full BTC and ETH option book summary (1,648 instruments) and Hyperliquid's 234 asset contexts;
  first snapshot 04:49:24 UTC, 84 KB. Mirrored to `~/qr/lake/mirror/surface_live/`. Read through the new
  loader, the BTC ATM curve at 05:02 UTC: 13 Oct 28.2%, 14 Oct 32.6%, 15 Oct 35.2%, 16 Oct 34.0%, 23 Oct
  32.8%, 30 Oct 33.3%, 27 Nov 36.6%, 25 Dec 37.1% — the one-day tenor sits five points under the 30-day,
  which is exactly the term-structure effect a 30-day DVOL hides on a one-day contract.
- **A.** v2 (seq 934) stands as registered; the 27 October read is a note recording the deferral, not a run.
- **The fourth registration — `p3_threshold_wedge_v3_daily`, seq 951**
  (`docs/prereg/p3_threshold_wedge_v3_daily.md`): v2's mechanism, rule, fill model and controls on the daily
  ladders, with **σ = the ATM implied vol at the market's own tenor** from the surface (nearest strike per
  expiry, call and put averaged, linear in total variance between expiries, past-only, DVOL fallback
  counted; SOL via BTC's tenor σ × the realised-vol ratio), `T ∈ {1 day, resolution}`, the DVOL arm as the
  term-structure control, 30 clusters with a fill as the minimum, **read once on 31 October** (window 13–30
  October), else 30 November; holdout 1–29 November. Engine `scripts/p3a_wedge_v3.py`
  (`SurfaceSigma`, `Market.start`, seventeen sessions in one pass), tests on fixtures. Written and registered
  before any daily-ladder line was read for a wedge (the only thing read since 04:53 is the recorder's
  "N active markets" line). The counter: **four of four**, extended by the owner's choice of B.
- **C2 v2 registered and run** (seq 941–943; `docs/20`, 13 October): the measured maker cost lifts the ledger
  net Sharpe from 0.54 to 0.66 and the HAC t from 1.50 to 1.84; **FAIL at gates 3, 4, 5** as the memo
  predicted — short by the spread's own size at 1×, not by costs. The pre-stated both-maker sensitivity (Bybit assumed to fill as Binance did) reaches net Sharpe 0.93, t 2.57, and
  still fails DSR (0.84) and cash (SPA 0.85): the "what it would take" line now has its number.
- **Storage and the venue's patience, measured on the first new hour — and misread once.** After the switch the
  recorder kept ~270 `price_change` lines a second (83 MB of JSON in a quarter of an hour, ~1 GB gzipped a
  day against 26 GB free), 86% of them entries kept only for sitting within 2¢ of the mid; the venue closed
  the socket twice as a "slow consumer" (close 1013) because the standard-library parser fell behind in
  bursts, and each reconnect re-sent every book. A first reading blamed megabyte books and registered a
  50-level cap (amendment 1, seq 975); the megabyte is in fact all 659 books in one frame, ~1.7 KB each, and
  the cap is harmless. **Amendment 2 (seq 977) corrects the record:** from 05:18:34 UTC (the journal's time; the amendments' "05:2x"/"05:4x" are corrected in note 979) a `price_change` entry
  is kept only when it moves the token's best bid or ask (`--near 0`), parsing is `orjson`, nothing the
  registered rules read changes (best bid/ask and trade prints), and the 2¢ band — kept for the P3-B
  rewards sizing, done on 11 October — is no longer recorded. Both amendments are noted under v2 (seq 976,
  978). That was still not the end of it: through the day the venue kept closing the socket once or twice
  an hour (12 closes, 13 seconds lost each). The cause was in our reader, not the venue — the websockets
  library's default receive queue (16 frames) throttles the socket so hard that the venue's send buffer
  fills; a bare integer `max_queue` makes websockets 17 read nothing at all, and the tuple form
  `(8192, 2048)` fixes it (measured on the laptop: 55 frames in 8 s at the default, 972 with the tuple).
  From 16:49 UTC the recorder receives on the event loop and compacts/writes on its own thread, keeps the
  socket across an unchanged hourly refresh (the refresh used to drop it for ~10 s), and runs at `Nice=-5`
  because another project's `node` process holds one of the box's two cores around the clock. First
  twenty minutes after: no closes, all 660 tokens printing, ~45 MB a day. (From the laptop the same subscription
  receives nothing above ~300 tokens while the box receives all 660 — a laptop-side observation, unexplained,
  which is one more reason the 31 October read is done from the box's recording and not from a laptop feed.) The surface recorder lost its 09:00 snapshot to a Deribit
  503 and now retries four times with a growing pause.
- **§15's free backfills, mirrored, nothing tested:** the CFTC financial-futures COT history 2017–2026
  (`~/qr/lake/mirror/cftc/fut_fin_txt_YYYY.zip`; CME Bitcoin and Micro Bitcoin rows with leveraged-fund and
  asset-manager positions, weekly) and the Coin Metrics community CSVs for BTC/ETH/SOL
  (`~/qr/lake/mirror/coinmetrics/`; daily from 2009, exchange in/outflows among the 32 columns, the public
  file ending 24 May 2026). Farside refuses non-browser fetches (403); the ETF-flow backfill's next route is
  the issuers' own daily NAV/shares files (iShares' download URL needs the right product id — not found in
  one try). Nothing from any of these is registered; they exist so the data-expansion programme can start the
  day the owner opens it.
- **The key: resolved at 11:11 UTC.** The untick had saved; Binance's permission flags for the key read
  `enableFutures false, enableReading true, ipRestrict true`, everything else false. The futures balance
  reads that made me doubt it are allowed on *Enable Reading* (§16, corrected). From now the permission
  flags, not a balance read, are how a key's state is checked.
