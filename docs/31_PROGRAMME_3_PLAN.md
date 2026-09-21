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
