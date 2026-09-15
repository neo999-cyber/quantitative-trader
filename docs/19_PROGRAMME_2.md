# Programme 2: the plan, the decisions, and the week-1 log

*15 September 2026. The plan below was written from `docs/18`'s handover and
from facts verified that day against official pages and the papers
themselves; the sources are in §14. The owner's decisions and what was built
on day one follow the plan.*

## Owner's decisions (15 September 2026)

| Decision | Choice | Consequence |
|---|---|---|
| Residence | **Dubai** | Alpaca for US equities (confirm by email); IBKR stays Pro; Bybit, Binance FZE and Hyperliquid for perps; Polymarket international open; Kalshi not |
| Data budget | **$0** | QuantConnect free tier, Databento's $125 credit, Binance Vision, FRED, FINRA, SEC, EDGAR. Reassess at week 9; the only foreseeable paid item is Alpaca's $99/mo full feed, and only at live time |
| Funded evaluation | **None yet** | Buy the smallest HyroTrader tier only after a crypto family passes gates 0–9; one Topstep $50k Combine only after an intraday futures family does |

## The stopping rule, re-scoped and not loosened

`docs/10` fixed a rule in advance: eight candidates with named mechanisms
through the full gates and none surviving means *no edge is accessible at
this account size with this data*. Programme 1 ran nine families and 46
memos against **that** account size, **that** data (daily spot and ETF bars)
and **that** benchmark (buy-and-hold of a rising universe), and the handover
records the finding. The rule's premise is what Programme 2 changes — the
instruments, the resolution, the point-in-time data, and the comparator for
market-neutral books — so it starts its own counter at zero under the same
numbers: **eight gated mechanism candidates, 3× cost bar, 250 variants a
family, 2 promotions a week, 5 a quarter.** Gate 4 continues to deflate
against the cumulative trial count, 1,541 at the start; nothing is reset
there. This paragraph is the record that the counter was restarted
deliberately and why, so it cannot be read later as a quiet relaxation.

## Week 1 log

**Built on 15 September 2026, tests green, no run counted:**

- `GateContext.benchmark` (`buyhold` | `cash`) and `risk_free`; gate 5 tests
  against `qr.validate.spa.cash_benchmark` when told to, and says which
  comparator it used in its detail and in `stats["benchmark"]`. Part of the
  pre-registration, exposed as `qr gates --benchmark cash --risk-free fred`.
- `qr data riskfree-pull`: FRED DTB3 → `reference/risk_free_dtb3.parquet`
  (18,165 observations, 1954-01-04 to 2026-09-11, 3.92% on the last day).
- `CostModel.binance_perp()` (regular user 2.0/5.0 bps, 10% off in BNB;
  **unverified** until read off the account's own fee panel) and
  `CostModel.hyperliquid_perp()` (1.5/4.5 bps, verified against the venue's
  docs on 2026-09-15). Both `funding=True`.
- Funding enters **gross**, not costs: `qr.research.runner.funding_pnl`,
  sign convention longs pay a positive rate, applied only when the cost model
  settles funding. `BacktestResult.carry` keeps it visible.
- **A gate-5 defect found by the new control and closed the same day.** A
  family whose variants never took a position reached gate 5 with a PBO of
  zero, the SPA half refused to run on constant series, and the gate read
  PASS with the error in its stats. It now fails outright when no variant
  ever traded and cannot pass when SPA could not run for any other reason.
  Every Programme 1 report was computed before this change; none of the nine
  families reached gate 5 with untraded variants, so no verdict moves.
- Perp data: daily bars for every USDT perpetual and funding for every
  perpetual are being mirrored into `$QR_ROOT` (`~/qr/lake`); metrics were
  already there for 40 symbols.

- **Liquidation recorder** (`scripts/record_liquidations.py`), three venues.
  Probed live on 2026-09-15 from Dubai: Binance's futures websocket
  connects and sends nothing (its REST answers; the block is on the stream),
  so the default venue is **OKX** (`liquidation-orders`, every SWAP in one
  subscription; 5 events in a 90-second smoke) with **Bybit** second
  (`allLiquidation.<symbol>` across 770 USDT perps; 6 events in 90 seconds).
  One JSON line per event under `$QR_ROOT/liquidations/<venue>/<day>.jsonl`.
  **Running since 11:02 UTC on 15 September 2026 on the always-on box**
  (root@91.98.172.9, the host that runs the ETF share-count collector):
  `qr-liq-okx.service` and `qr-liq-bybit.service`, each in its own
  virtualenv at `/root/liq/.venv`, writing `/root/liq/data/<venue>/`.
  Binance's stream is silent from Germany as well, so it is not deployed.
  Check with `ssh 91.98.172.9 'systemctl status qr-liq-okx qr-liq-bybit;
  wc -l /root/liq/data/*/*.jsonl'`.
- **The carry unit and family C1, built ahead of week 2.** `qr/data/carry.py`
  turns a spot series, a perp series and the funding feature into one
  synthetic instrument (price = spot / perp, so its return is exactly the
  pair's; funding stored with the short leg's sign; liquidity = the thinner
  leg) and `qr data carry-build` writes it under market `carry-um`.
  `FundingCarry` (`qr/strategies/carry.py`) opens units above an annualised
  funding floor, keeps them above a lower exit, refuses to open in the top
  tail of the coin's own trailing year (the BIS crash filter), and is
  benchmarked against cash. `CostModel.carry_pair` adds the two legs' costs:
  15 bps a side, 30 a round trip, 60 stressed.
- **A second defect, found by the carry round-trip test.** The lake's panel
  loader joined the raw perp funding feature onto *every* Binance panel,
  including one that had defined `funding_rate` itself, and so flipped the
  carry unit's receipt back into a payment after loading — the file on disk
  was right and the panel in memory was wrong. It now leaves a panel's own
  `funding_rate` alone. No Programme 1 result touched this path.

**Not yet done from the week-1 list:** the Polymarket book recorder; the C1
pre-registration (drafted at `docs/prereg/p2_funding_carry_v1.md`, to be
registered only after `qr data carry-build` has run and the universe file
is checked, and before any run); the recorders running on a permanent host;
and the QuantConnect / Alpaca / Databento accounts, which only the owner can
open.

---

## 1. Context

The handover records nine pre-registered families, 1,541 runs, 46 mechanism memos, zero promotions, and ranks the causes. Three were fixed at design time:

| # | Cause (handover §5) | What actually caused it |
|---|---|---|
| 5.1 | Benchmark unbeatable | Gate 5 compared long-only timing to buy-and-hold of a rising universe |
| 5.2 | $0.35/order minimum = 35 bps at $1,000 | IBKR Pro tiered pricing on a $1,000 account |
| 5.3 | Daily bars cannot see forced flow | Closing auctions, funding, liquidations all resolve intraday |

Five more followed: forced traders sit in instruments not traded (perps, single stocks, primary market); no point-in-time alternative data; twelve-name breadth; idea generator exhausted; no market-impact model.

Current state: the connected IBKR account holds **$78.34 USD cash, no positions, cash account** (read via the IBKR connector today). Nominal budget stays ~$1,000. The engine (gates 0–11, hash-chained trial log, SHA-256 sandbox, cost models, autopilot, `scripts/collect_flows_standalone.py` still recording ETF share counts) is reused as-is.

**The plan's single principle: every one of the eight causes gets a named fix with a named resource, and no fix requires more capital than exists today except where stated (Track 3, Track 4).**

---

## 2. Root cause → fix map

| Cause | Fix | Resource (verified today) | Cost |
|---|---|---|---|
| 5.1 benchmark | Gate 5 comparator becomes **cash (3-month T-bill)** for market-neutral / carry books; buy-and-hold kept only for long-only books | FRED `DTB3` series; one parameter in `qr/validate/gates.py` | $0 |
| 5.2 per-order floor | US equities move to a **$0-commission API broker**; crypto moves to **perpetuals** (bps-only fees); futures use micro contracts (~$0.25–0.85/contract) | Alpaca ($0, fractional from $1, MOC/LOC, international); IBKR Lite if US/Singapore resident; Binance/Bybit/Hyperliquid perps 1.5–5.5 bps | $0 |
| 5.3 resolution | **Minute bars + closing-auction imbalance + 8-hour funding + 5-min OI** | QuantConnect free tier (minute, 1998→); Databento imbalance (Nasdaq 2018→, NYSE 2025→, $125 free credit); Binance Vision `futures/um` klines/metrics/fundingRate; Hyperliquid S3 archive | $0–$50 one-off |
| 5.4 instrument access | Trade **where the forced trader trades**: perps (liquidations, funding, unlocks), single stocks via fractional shares, closing auction via MOC/LOC | Same venues as above | $0 |
| 5.5 PIT alt data | Use sources that are **point-in-time by publication**: FINRA short interest (publication date in file), Reg SHO daily short volume, SEC fails-to-deliver, EDGAR Form 4 / 8-K / N-PORT (acceptance timestamps), QuantConnect ETF constituents (recorded daily since 2015), Binance funding/OI archives, on-chain vesting schedules; plus **forward recorders** for everything else | All free | $0 |
| 5.6 breadth | **3,000+ US stocks** (QuantConnect, survivorship-free) and **200–700 perps** (Binance 718 pairs since Aug 2020 on QC; Hyperliquid/Bybit) | Free | $0 |
| 5.7 generator exhausted | Replace the LLM as *source* of ideas with a **literature registry** (papers in §14, Open Source Asset Pricing's 200+ signals, Quantpedia); the LLM only parameterises and triages | Free | $0 |
| 5.8 market impact | Add a **participation-capped square-root impact model** and a hard cap of 1% of the bar's volume per order; report capacity per family | Engine change | $0 |
| Capital | **Three multipliers that need no personal capital**: funded-trader evaluations (futures: Topstep API-permitted; crypto: HyroTrader bots-permitted), WorldQuant BRAIN consultant payments, and compounding rules | §8 | $59–$150 per evaluation |

---

## 3. Week-0 decisions (owner makes these; each branches the plan, none blocks the research tracks)

**D1. Country of residence** — decides venues. Verify inside each logged-in account; third-party lists lag.

| Resident of | US equities at $0 | Crypto perps | Prediction markets | Funded accounts |
|---|---|---|---|---|
| USA | IBKR Lite (US/SG only) or Alpaca | Binance/Bybit/Hyperliquid **blocked**; Coinbase US perps (verify) | Kalshi; Polymarket US (live since 2 Dec 2025, waitlist removed May 2026) | Topstep, Apex; HyroTrader (verify US) |
| UAE / India / other non-EU | Alpaca (195+ countries; email support@alpaca.markets to confirm); IBKR Pro | Binance (verify futures enabled in-account), Bybit, Hyperliquid (no KYC, US+Ontario excluded) | Polymarket international | All |
| UK / EEA | Alpaca (EEA passported July 2026); IBKR Pro | Binance/Bybit futures restricted for retail; Hyperliquid open | Polymarket international (check country) | All |

**D2. Capital path** — pick one to start; they stack later.
- (a) Own capital only: fund to $1,000 → Track 1 live-paper at once; equities at Alpaca with fractional shares.
- (b) Own capital + one funded-trader evaluation ($59–$150): adds Track 3/4 with a $50k–$100k simulated account once an intraday family passes gates.
- (c) Own capital + WorldQuant BRAIN: adds income from equity alphas with zero capital; runs in parallel from week 1.

**D3. Data budget** — $0 (QuantConnect free + Databento credit + all free feeds) is sufficient for every family below. Optional upgrades: Alpaca Algo Trader Plus $99/mo (full SIP feed, only needed at live-trading time for Track 2), QuantConnect Researcher $60/mo (only for live nodes/tick data), Norgate Platinum ~$630/yr (only if a Track 2 family passes gate 9 and needs a second independent price source).

---

## 4. Track 0 — Setup (week 1)

### 4.1 Accounts (all free to open)
1. **QuantConnect** free plan — `quantconnect.com`. Confirms: unlimited minute/hour/daily backtests, 1 research (Jupyter) node, no live nodes, no data download. This is the research venue for Tracks 2 and 3 and for perps cross-checks.
2. **Alpaca** paper account + live application — `alpaca.markets`. Confirm by email: country supported, margin/short availability for a non-US account, MOC/LOC live. Facts: $0 commission, fractional from $1, no minimum, all accounts open as margin accounts; `cls` time-in-force orders must be whole shares and submitted before 15:50 ET.
3. **Databento** — `databento.com`; $125 credit (6-month expiry). Reserve it for `imbalance` schema pulls (Track 2, E1).
4. **Binance Futures / Bybit / Hyperliquid** (per D1). Hyperliquid needs only a wallet; fees 0.015% maker / 0.045% taker at base tier.
5. **WorldQuant BRAIN** — `worldquantbrain.com` (free; consultant invitation at 10,000 points + Gold rank; quarterly payments, Master ≥$2,000/quarter, Grandmaster ≥$8,000/quarter as published).
6. **Polymarket** (if D1 allows) — wallet + API keys; makers pay 0%.
7. **IBKR**: leave the existing account as is; switch to **IBKR Lite** only if US/SG resident. Otherwise its only use is micro futures (Track 3) once ≥$2,000 is on deposit.

### 4.2 Data pulls (free; scripted into the existing Parquet/DuckDB lake)
| Dataset | Source | Command / URL pattern | Gives |
|---|---|---|---|
| Binance USDT-M perps | `data.binance.vision` `data/futures/um/{daily,monthly}/` | daily: `aggTrades bookDepth bookTicker indexPriceKlines klines markPriceKlines metrics premiumIndexKlines trades`; monthly: adds `fundingRate` | 1-min bars, mark/index, 8h funding, 5-min OI + long/short + taker ratios, book depth |
| Bybit perps | `public.bybit.com` `trading/ premium_index/ spot_index/ spot/` | folder per symbol | second venue for funding spread (C5) |
| Hyperliquid | `s3://hyperliquid-archive/{market_data/[date]/[hour]/l2Book/[coin].lz4, asset_ctxs/[date].csv.lz4}` with `--request-payer requester` | ~monthly uploads | L2 books, funding, OI, premium per asset |
| FINRA short interest | finra.org Equity Short Interest catalog | pipe-delimited; settlement + publication dates (e.g., settle 15 Jan 2026 → due 20 Jan → published 27 Jan) | PIT short interest, twice monthly |
| FINRA daily short volume | finra.org Short Sale Volume Data + `developer.finra.org` Query API | daily files, monthly files | daily short-volume ratio |
| SEC fails-to-deliver | sec.gov Fails-to-Deliver Data | pipe-delimited zips, Feb 2004 → Aug 2026, twice monthly | FTD spikes |
| EDGAR | Form 4 (2-business-day deadline), 8-K (earnings), N-PORT | EDGAR full-text + XBRL APIs, acceptance timestamps | insider trades, earnings times, fund holdings |
| ETF constituents (PIT) | QuantConnect US ETF Constituents (2,650 ETFs, June 2009→, daily since Jan 2015, ≤1-week lag; free in cloud) | universe selection in QC | membership for Russell/S&P universes without look-ahead |
| Anomaly signals | Open Source Asset Pricing (`openassetpricing.com`, Oct 2025 release, Python package `openassetpricing`) | 200+ firm-level signals + portfolio returns | Track 2 E6 candidate list with published costs |
| T-bill | FRED `DTB3` | daily | new gate 5 comparator |

### 4.3 Forward recorders (PIT by construction; start day 1, usable after 3–12 months)
- Binance `forceOrder` liquidation stream + Hyperliquid liquidation feed → per-minute liquidation volume by symbol (not in the public archives; must be recorded).
- iShares daily holdings CSVs for IWM/IWB/IVV/IWV → shares outstanding and constituent snapshots.
- Polymarket order books for the top 200 markets (CLOB API).
- Keep `collect_flows_standalone.py` running (ETF share counts).
- Russell **December 2026** reconstitution (first semi-annual one: rank day 30 Oct, preliminary lists 13/20/27 Nov and 4 Dec, effective after close 11 Dec) → record prelim lists and minute bars of adds/deletes. This event has no history; the recorder creates it.

### 4.4 Engine changes (see §10 for specifics) — 3–4 days of work.

---

## 5. Track 1 — Crypto perpetuals (weeks 1–6; executable at today's capital)

**Why this track first:** fees are basis points with no per-order floor, shorting is native, the forced traders (funding payers, liquidated leverage, unlock recipients) trade *here*, and the benchmark is cash.

Universe: Binance USDT-M perps with listing dates from Binance Vision (PIT), top-100 by 30-day quote volume re-ranked monthly; Hyperliquid as second venue. Cost model: maker 0.018% / taker 0.045% (Binance with BNB) or 0.015% / 0.045% (Hyperliquid); funding paid and received every 8h at the archived rate; mark-price liquidation with initial/maintenance margin per tier; impact = participation cap.

| ID | Family | Mechanism (who is forced) | Data | Benchmark | Pre-registered rule sketch |
|---|---|---|---|---|---|
| C1 | Funding carry, delta-neutral | Leveraged longs pay funding; BIS WP 1087 finds carry averaging >10% p.a. (up to 60%), mostly from funding, with crash risk when carry is high | spot 1m + perp 1m + `fundingRate` | cash | Long spot / short perp when trailing-7d annualised funding > 3× round-trip cost; exit when < 1× or when carry percentile > 95 (crash-risk filter from the paper); cap gross at 2× equity |
| C2 | Cross-venue funding spread | Same payers, different venues clear at different rates | Binance + Hyperliquid funding | cash | Long perp on lower-funding venue / short on higher when spread > costs; 8h holding grid |
| C3 | Liquidation-cascade fade | Forced sellers are liquidation engines; price overshoots then reverts within minutes | `forceOrder` recorder (forward) + `metrics` OI drop + 1m bars | cash | Enter opposite to a liquidation burst > k σ of 1h liquidation volume when OI fell > x%; hold 15–60 min; maker exit |
| C4 | Pre-unlock short | Token unlock recipients (VC/team) sell after cliff dates fixed on-chain at launch | Vesting schedules (DefiLlama unlocks UI / Tokenomist; verify against vesting contracts) + perp availability | cash | Short perp T-3 to T+1 around unlocks > 2% of float; size by ADV; funding-adjusted |
| C5 | OI-conditioned reversal, mid-caps | Crowded positioning (OI up, funding up) unwinds; the March 2026 SSRN post-mortem shows plain OHLCV/funding sorts on **large caps** carry nothing → this family is restricted to ranks 30–150 and conditions on OI change and taker imbalance | `metrics` (OI, long/short ratio, taker buy/sell) + 1h bars | cash, dollar- and beta-neutral | Weekly long/short deciles on 1h-reversal × OI-change; maker execution; ≤250 variants |

Gate path: sandbox kill-test (3× cost bar) → gates 0–11 with cash benchmark → 4-week paper on Hyperliquid/Binance testnet → live at ≤25% of equity per family.

---

## 6. Track 2 — US single equities at $0 commission (weeks 2–10; research free on QuantConnect)

Broker: Alpaca (or IBKR Lite if eligible). Cost model: commission $0, half-spread from minute quotes (IEX free feed for research; SIP at live), 1 bp PFOF slippage, MOC fills at official close with impact cap. **Shorting requires ≥$2,000 equity (Reg T)**; until then every family runs long-only-vs-cash, and the long/short version is pre-registered for later.

The pattern-day-trader $25,000 minimum **no longer exists** (FINRA Regulatory Notice 26-10; effective 4 June 2026; replaced by intraday margin monitoring, transition until 20 Oct 2027). Intraday families are therefore open to this account size.

| ID | Family | Mechanism | Evidence | Data | Rule sketch |
|---|---|---|---|---|---|
| E1 | Closing-auction imbalance | Index/ETF rebalancers must trade at the close; imbalance is published from 15:50 ET; closing-price deviations revert half after the close and fully overnight | Bogousslavsky & Muravyev, JFM 2023 (close = 7.5% of volume in 2018 vs 3.1% in 2010) | Databento `imbalance` (XNAS.ITCH 2018→; XNYS/ARCX/XASE 2025→) + 1m bars | Fade the imbalance direction with a LOC at 15:50–15:55 when imbalance/paired > k; exit next open (MOO) |
| E2 | Late-day hedging momentum | Leveraged-ETF and option-market-maker gamma hedging trade with the day's move in the last 30 min | Baltussen, Da, Lammers & Martens, JFE 2021 (60+ futures, 1974–2020; reverts over next days) | SPY/QQQ/IWM minute bars (QC free); LETF AUM from issuer daily files | Position at 15:30 in the sign of the 09:30–15:30 return scaled by LETF AUM × |return|; flat at close via MOC |
| E3 | Month-end cash settlement reversal | Institutions raise cash before month-end settlement; index returns reverse around the last day that guarantees settlement | Etula, Rinne, Suominen & Vaittinen, RFS 2020 (large liquid stocks strongest) | SPY/large-cap minute bars | Pre-registered T-3…T+1 pattern; long-only-vs-cash version first |
| E4 | Post-earnings drift, small/mid caps | Under-reaction persists where arbitrage is constrained | 2025 reviews find PEAD alive in small/mid caps, diminished in large caps | EDGAR 8-K acceptance timestamps + QC Morningstar; fractional shares | Buy top-decile surprise (announcement-return proxy) at next open, hold 20–60 days; ≤$100 per name via fractionals |
| E5 | Opportunistic insider buying | Insiders who do not trade on a calendar routine carry information | Cohen, Malloy & Pomorski, JF 2012 (82 bps/month VW abnormal for opportunistic trades) | EDGAR Form 4 (2-business-day filing) or QC Quiver insider dataset | Classify routine vs opportunistic by 3-year same-month history; buy cluster opportunistic purchases; hold 1–3 months |
| E6 | Low-turnover anomaly composite | Published signals net ~4 bps/month on average, ~10 bps for the best, ~20 bps for combinations (Chen & Velikov, JFQA) — so only monthly-rebalanced combinations are pre-registered, sized as an overlay | Open Source Asset Pricing signals | QC fundamentals + OSAP | Equal-weight top-quintile composite of 5 lowest-cost signals, monthly, long-only-vs-cash; long/short version once shorting is enabled |
| E7 | Short-interest / FTD squeeze | Constrained shorts must cover; FTD spikes flag settlement stress | FINRA SI (PIT publication dates), Reg SHO daily short volume, SEC FTD | Long high-days-to-cover names with rising FTDs after publication date; hold 10 days |

Not pre-registered (evidence says the flow is already arbitraged): S&P 500 addition/deletion (Greenwood & Sammon, JF 2025: 7.4% in the 1990s → 0.3% last decade; deletions 0.1% 2010–2020). The Russell semi-annual event is recorded forward instead (§4.3).

Research venue: port `gates.py` into a QuantConnect project as project files (multi-file projects import in the research node); run gates 0–9 in the cloud on QC data; export only results (JSON) to the local trial log. Live: Alpaca API from the local machine.

---

## 7. Track 3 — Micro futures, long/short, cash-benchmarked (weeks 6–12; research free, live needs ≥$2,000–$5,000 or a funded account)

Mechanism: multi-asset time-series momentum and carry; 67 markets 1880–2016, positive in every decade (Hurst, Ooi & Pedersen, JPM 2017). Benchmark is cash by construction; shorting is native; per-contract cost ~$0.25–$0.85 + exchange/NFA fees on notional of $10k–$30k = ~0.2–0.5 bps.

Instruments: MES, MNQ, MYM, M2K, MGC, MCL, MBT, MET (CME micro). Margin: MES initial $1,320 / maintenance $1,200 per CME table (September 2026, indicative); intraday margins at Tradovate/AMP/NinjaTrader-class brokers $50–$300 for MES/MNQ.

| ID | Family | Rule sketch | Data |
|---|---|---|---|
| F1 | Trend + carry, 8 micros | Carver-style forecast scaling; 12-1 and 3 breakout speeds; carry from roll yield; volatility-targeted 10% p.a.; whole-contract rounding with the "optimal whole-contract portfolio" method | QC CME futures (free minute/daily) for research; IBKR for live |
| F2 | Intraday index momentum (funded-account version) | E2 executed in MES/MNQ; flat by close (fits daily-loss and trailing-drawdown rules) | QC minute futures |

Capital preconditions stated once: F1 live needs ≥$5,000 for 3–4 contracts; ≥$25,000 for the full set. F2 is what a funded-trader account is for.

---

## 8. Track 4 — Capital multipliers (parallel from week 1)

| Route | Facts (verified) | Step |
|---|---|---|
| **Topstep (futures)** | Bots allowed in Combine and funded accounts via TopstepX/ProjectX API; API $29/mo ($14.50 with code `topstep`); HFT prohibited; **all trading must originate from your personal device — VPS/VPN/remote servers prohibited (a server may research and record, not trade)**; must be actively monitored | Buy one $50k Combine only after F2/E2 passes gates 0–9; run it from the desktop with the monitored-automation rule |
| **Apex (futures)** | One-time evaluation fee since March 2026 ("4.0"), activation $79–$99; bots allowed in evaluation, **banned on funded accounts**; 50% consistency rule; intraday or end-of-day trailing drawdown | Use only as a second evaluation if Topstep rules bind |
| **HyroTrader (crypto)** | From $59; $100k challenge $579; 1-step 10% target, min 5 trading days; 4% daily / 6% max loss; 80–90% split; **bots via Bybit API fully supported**; fee refunded with first payout; payouts in USDT/USDC | Buy the smallest evaluation after C1/C3/C5 pass gates 0–9; the strategy's realised daily loss must be < 2% at 99th percentile before purchase (gate 11 output) |
| **FTMO (FX/CFD)** | EAs allowed; from $89, refunded on first payout | Only if a family maps to CFDs; not planned |
| **WorldQuant BRAIN** | Free; alphas simulated on their PIT data; consultant invitation at 10,000 points + Gold; quarterly payments (Master ≥$2,000, Grandmaster ≥$8,000 as published) | Translate E5/E6/E7 into BRAIN expressions from week 2; 30 minutes/day; this is income without capital |
| **Numerai** | Stake NMR; payout capped at ±5% of stake per round; $532k paid April 2025 | Optional; only after BRAIN is running |
| Regulatory watch | Aug 2026: SEC actions against two prop firms for marketing simulated accounts as live; NFA Notice I-26-12 on affiliate marketing effective 1 Dec 2026 | Treat every evaluation as simulated until the firm states otherwise in writing; withdraw payouts monthly |

---

## 9. Track 5 — Prediction markets (optional; weeks 8+; only if D1 allows)

Facts: Polymarket makers pay 0%; taker fee = shares × rate × p(1−p) with rates crypto 0.07, sports 0.05, finance/politics 0.04, geopolitics 0. Measured arbitrage: $40M extracted April 2024–April 2025 across single-market rebalancing and combinatorial arbitrage (arXiv 2508.03474); NBA markets show median 101 bps per combinatorial opportunity but 76.9% of them cap at ~14.8 shares — i.e., retail-sized by nature (arXiv 2605.00864); $1.12M in negative-risk markets (arXiv 2608.00666).

| ID | Family | Rule sketch |
|---|---|---|
| P1 | Single-market rebalancing | Buy all outcomes when Σ ask < $1 − fee; hold to resolution; size = min depth |
| P2 | Combinatorial | Pairs of logically dependent markets (LLM-triaged as in the paper); same execution |
| P3 | Maker quoting | Two-sided quotes on mid-liquidity markets at 0% maker fee; inventory limits |

Data: Gamma + CLOB + Data APIs (free); record books from week 1 (§4.3).

---

## 10. Engine changes (specific)

1. **Gate 5 comparator** in `qr/validate/gates.py`: add `benchmark ∈ {buyhold, equal_weight, cash}`; `cash` uses FRED `DTB3` daily; SPA test unchanged.
2. **Cost models** (new modules beside the existing Binance-spot and IBKR-tiered ones):
   - `alpaca_zero`: $0 commission, half-spread from quotes, 1 bp PFOF slippage, MOC = official close, whole-share constraint for `cls` orders, fractional for others.
   - `perp_binance`, `perp_hyperliquid`: maker/taker bps, funding cash flows at archived 8h stamps, mark-price liquidation, tiered margin, borrow = 0.
   - `cme_micro`: $/contract + exchange + NFA, tick-size rounding, whole contracts.
   - `impact`: `k · σ_1m · sqrt(q / V_1m)` with participation cap 1% of bar volume; output "capacity at 3× cost bar" per family.
3. **Universe modules**: PIT perp listing from Binance Vision file dates; US stocks via QC ETF-constituent universes exported as symbol lists with as-of dates.
4. **Resolution**: bar loader accepts 1m/1h; funding and OI aligned to bar timestamps; auction fields joined at 15:50–16:00.
5. **Literature registry** replaces the memo generator's brief space: one YAML record per paper in §14 (mechanism, forced party, instrument, resolution, published gross/net numbers). The generator now only proposes parameterisations inside a registry entry; triage rejects anything without a registry parent.
6. **Kill-test fixes carried forward**: the $0.35 minimum bug and the compounded-return-over-per-trade-cost ratio are unit-tested against the new models; drawdown probability in gate 11 is reported as P(≥25% below launch within 12 months) with the horizon in the label.
7. **Trial log**: new families registered under `p2_` prefix; gate 4 deflation continues to count the cumulative 1,541 runs.
8. **QuantConnect port**: `gates.py` and the sandbox splitter as project files; results only leave QC.

---

## 11. Pre-registration order and stopping rules (unchanged from the handover's policy)

Order: C1 → E1 → E2 → C3 → C5 → E5 → E4 → E7 → C2 → C4 → E3 → E6 → F1 → F2 → P1–P3.
Policy: 2 promotions/week, 5/quarter, 250 variants/family, 3× cost bar, hard stop at 8 gated candidates; `qr trial verify` before every report.
Controls per venue: hold-BTC-perp (crypto), hold-T-bill (cash-benchmarked), hold-SPY (long-only), synthetic noise (200 variants) re-run under every new cost model.

---

## 12. Twelve-week timeline

| Week | Deliverable |
|---|---|
| 1 | Accounts (§4.1), data pulls (§4.2), recorders live (§4.3), gate-5 cash comparator + perp cost model merged with tests |
| 2 | C1 pre-registered and through gates 0–9; BRAIN account active with first 20 alphas |
| 3 | E1 imbalance pull (Databento credit) + Alpaca paper account wired; E1 pre-registered |
| 4 | C1 verdict; E2 pre-registered on QC; C3 recorder has 3 weeks of liquidation data |
| 5 | E1 and E2 verdicts; C5 pre-registered; independent-model review of the new cost models (repeat the `docs/16` pattern) |
| 6 | Any passer enters 4-week paper; F1 research starts on QC futures |
| 7–8 | E5, E4, E7 verdicts; C3 first kill-test on 6 weeks of recorded liquidations |
| 9 | Paper results for the first passer; funded-evaluation purchase decision (D2b) |
| 10 | C2, C4, E3, E6 verdicts; live at ≤25% equity for any family past gate 10 |
| 11 | F1/F2 verdicts; BRAIN points review |
| 12 | Programme 2 report: per-family verdicts, capacity, paper vs backtest slippage, capital ladder for the next quarter |

---

## 13. Verification (how each step proves itself)

- **Engine**: `pytest -q` green; synthetic noise self-test fails gates 4–5 under each new cost model; planted-edge test passes; `qr trial verify` chain intact and run count printed.
- **Cost models**: re-price 100 historical Binance perp fills and 100 Alpaca paper fills against model output; error < 1 bp.
- **Data PIT-ness**: for FINRA/EDGAR/Databento joins, assert `feature_timestamp ≤ decision_timestamp` on every row (existing QA gate extended).
- **Gate 5 cash comparator**: hold-T-bill control returns SPA p ≈ 0.5 on itself; hold-SPY control fails when benchmarked against buy-and-hold (as before).
- **Track 1 paper**: 20 trading days on Hyperliquid/Binance testnet; realised funding received vs modelled within 5%; fills vs modelled within 2 bps.
- **Track 2 paper**: Alpaca paper fills for MOC/LOC vs official close: exact; PFOF slippage measured.
- **Independent review**: a separate model session reviews cost models and gate changes before any live order (as `docs/16` did).
- **Reporting rule (handover §8)**: re-derive every figure from the trial log; check flags against the record, not the report.

---

## 14. Sources verified today

Venues and rules
- IBKR Lite eligibility (US and Singapore): interactivebrokers.com/en/trading/why-ibkr-lite.php
- IBKR margin account $2,000 minimum and short-selling requirements: interactivebrokers.com/en/trading/margin-stocks.php
- IBKR micro futures commissions from $0.25/contract: interactivebrokers.com/en/pricing/commissions-futures.php
- FINRA pattern-day-trader rule eliminated 4 June 2026: finra.org/rules-guidance/notices/26-10; sec.gov SR-FINRA-2025-017
- Alpaca international, $0 commission, fractional from $1: alpaca.markets/international; EEA passporting (July 2026): businesswire 20260707116782
- Alpaca MOC/LOC rules (`cls`, 15:50 ET cutoff, whole shares): docs.alpaca.markets/docs/orders-at-alpaca
- Alpaca data plans ($0 IEX; $99 Algo Trader Plus): alpaca.markets/data
- Binance USDⓈ-M fees 0.02/0.05% (0.018/0.045 with BNB); futures unavailable in US/UK/EU/CA/AU: finder.com, datawallet.com summaries of binance.com/en/fee/futureFee
- Bybit 0.02/0.055%: bybit.com/en/announcement-info/fee-rate
- Hyperliquid fees and rebates: hyperliquid.gitbook.io/hyperliquid-docs/trading/fees; restrictions (US, Ontario): datawallet.com/crypto/hyperliquid-supported-and-restricted-countries
- CME micro margins: cmegroup.com/markets/equities/sp/micro-e-mini-sandp-500.margins.html
- Topstep API and automation rules: help.topstep.com/en/articles/11187768-topstepx-api-access
- Apex automation policy and 4.0 fees: quantvps.com/blog/apex-trader-funding-automated-trading-bots; proptradingvibes.com/blog/apex-trader-funding-rules-overview
- HyroTrader rules and API: hyrotrader.com/blog/hyrotrader-vs-breakout
- FTMO EAs allowed, fee refunded: tradingfinder.com/props/ftmo/rules
- Prop-firm regulation Q3 2026 (SEC actions, NFA I-26-12): track360.io/blog/prop-firm-regulation-news-roundup-q3-2026
- WorldQuant BRAIN consultant programme: worldquantbrain.com/consultant; worldquant.com/brain/iqc-guidelines
- Numerai staking and payouts: docs.numer.ai; github.com/numerai/docs staking.md
- Polymarket fees: docs.polymarket.com/trading/fees.md; US launch and access: coindesk.com 2026/04/28; predscope.com/guide/polymarket-us
- Kalshi historical data endpoints: docs.kalshi.com/getting_started/historical_data

Data
- QuantConnect pricing (Free $0; Researcher $60/mo): quantconnect.com/pricing; newtrading.io/quantconnect-review (13 Mar 2026)
- QuantConnect US Equities survivorship-free since 1998: quantconnect.com/data/algoseek-us-equities
- QuantConnect US ETF Constituents (2,650 ETFs, June 2009→, free in cloud): quantconnect.com/data/quantconnect-us-etf-constituents
- QuantConnect Binance crypto futures (718 pairs, Aug 2020→) and margin-rate data: quantconnect.com/data/binance-cryptofuture-price-data; …/binance-cryptofuture-margin-rate-data
- QuantConnect datasets overview (Morningstar, Reg SHO, Quiver insider, SEC filings, CME futures, Bybit/dYdX futures): quantconnect.com/docs/v2/writing-algorithms/datasets/overview
- LEAN engine Apache 2.0, local build: github.com/QuantConnect/Lean; LEAN CLI paid-tier requirement: lean.io/docs/v2/lean-cli/key-concepts/getting-started
- Databento: $125 credit and $/GB model: databento.com/pricing; Nasdaq imbalance since 2018: databento.com/datasets/XNAS.ITCH; NYSE imbalance feeds: databento.com/blog/NYSE-imbalance-feeds
- Binance Vision futures folders: s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data/futures/um/{daily,monthly}/
- Bybit public archive: public.bybit.com
- Hyperliquid archive: hyperliquid.gitbook.io/hyperliquid-docs/historical-data
- FINRA short interest schedule: finra.org/filing-reporting/regulatory-filing-systems/short-interest; data: finra.org/finra-data/browse-catalog/equity-short-interest/data
- FINRA daily short sale volume + Query API: finra.org/finra-data/browse-catalog/short-sale-volume-data
- SEC fails-to-deliver (Feb 2004 → Aug 2026): sec.gov/data-research/sec-markets-data/fails-deliver-data
- FTSE Russell semi-annual reconstitution from 2026, December schedule: lseg.com/en/ftse-russell/russell-reconstitution
- Open Source Asset Pricing (Oct 2025 release): openassetpricing.com
- Norgate Platinum ~$630/yr with historical constituents: norgatedata.com/prices.php (via alvarezquanttrading.com review)
- Sharadar bundle contents (prices 1998→, fundamentals 1990→, insiders 2005→, S&P 500 constituents 1957→): data.nasdaq.com/databases/SFA; quantrocket.com/sharadar

Mechanisms
- Schmeling, Schrimpf & Todorov, "Crypto carry", BIS WP 1087 (forthcoming Management Science): bis.org/publ/work1087.htm
- Azka Fayez Junior, "Failure of Cross-Sectional Alpha Screening on Cryptocurrency Perpetual Futures" (SSRN 6701738, Mar 2026)
- Bogousslavsky & Muravyev, "Who trades at the close?", JFM 66 (2023): ssrn.com/abstract=3485840
- Baltussen, Da, Lammers & Martens, "Hedging demand and market intraday momentum", JFE 142 (2021): ssrn.com/abstract=3760365
- Etula, Rinne, Suominen & Vaittinen, "Dash for Cash", RFS 33 (2020): doi.org/10.2139/ssrn.2528692
- Greenwood & Sammon, "The Disappearing Index Effect", JF 80 (2025): onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13410
- Lou, Polk & Skouras, "A tug of war", JFE (2019): personal.lse.ac.uk/polk/research/TugOfWar.pdf
- Cohen, Malloy & Pomorski, "Decoding inside information", JF (2012): ssrn.com/abstract=1692517
- Chen & Velikov, "Zeroing in on the expected returns of anomalies", JFQA: ssrn.com/abstract=3073681
- Hurst, Ooi & Pedersen, "A century of evidence on trend-following investing", JPM 44 (2017): ssrn.com/abstract=2993026
- PEAD 2025 evidence: anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again; quantpedia.com/strategies/post-earnings-announcement-effect
- Prediction-market arbitrage: arxiv.org/abs/2508.03474; arxiv.org/abs/2605.00864; arxiv.org/abs/2608.00666
- Carver, "Advanced Futures Trading Strategies" (2023) and pysystemtrade: qoppac.blogspot.com; github.com/robcarver17
