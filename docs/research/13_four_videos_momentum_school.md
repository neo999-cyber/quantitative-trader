# 13 — The "four videos" list: what each one says, what is a rule, what we already know (12 November 2026)

The owner sent a 70-second phone recording of a short-form clip titled *4 videos that will make you disgustingly good at
trading in 24 hours* and asked for the four to be found and gone through, "the smart way", and reported on before anything
is done. Nothing here is registered, built or run.

**How they were read.** The titles were read off the clip's frames; each was resolved by title and the duration the clip's
player showed (4:10:07, "11-hour video", 1:00:44, 19:14); YouTube's automatic captions were fetched as text with `yt-dlp`
(no media), 155,600 words in all, and read from the captions: the 4-hour and 1-hour videos and the 19-minute one in full;
the 11-hour conference by its chapters — the four talks that state rules in full, the three process talks skimmed for
every block that carries a number. The captions are machine-made; a garbled term is marked (?). Three helper agents
started on the conference and were stopped by the account's usage cap before reading anything; the reading below is
first-hand. Nothing in the videos is a claim this note endorses.

| # | video | who | length, date | what it is |
|---|---|---|---|---|
| 1 | Qullamaggie Swing Trading School (`xx8GvtAxilk`, a re-upload by "QMV") | Kristjan Kullamägi, Swedish swing trader | 4 h 10 m, Sept 2020 (Twitch streams, Aug 2020) | one breakout setup taught over ~150 charts, with his scans, entry, exit and market filter |
| 2 | TraderLion Trading Conference 2024, Day 1 (`NhpCH4ZHy-s`) | seven speakers | 11 h 03 m, July 2024 | two strategy talks, one systematic survey, one market-regime talk, three process talks |
| 3 | My Swing Trading Strategy Makes Me $100k+/Month (`TPnkmGGFnhU`) | "Sean Trades", sells coaching | 1 h 00 m, Aug 2025 | a discretionary momentum system on options |
| 4 | Best Loser Wins — Flip The Switch (`siRWczImFtg`) | Tom Hougaard, UK spread-betting day trader | 19 m, Mar 2022 | one morning's FTSE trades as a lesson in process over outcome |

## 1. Qullamaggie — the one setup

- **Universe (TC2000 scans, run after the close):** the biggest gainers over one, three and six months — `100·(C/C21−1)`,
  `100·(C/C63−1)`, `100·(C/C126−1)` (he also reads them from the period's low) — in the top 7% (rank ≥ 93%, "90–95%+"),
  with dollar volume ≥ $80 M for him ("$5–20 M for small accounts, 20–50× your account") and average daily range ≥ 3.5–4%
  for him ("5–6% for you"). Tighten until each scan returns ≤ 50–60 names. [1:04–1:25, 3:10–3:12]
- **Setup:** a stock that has made a big move (top 1–2% of its time frame), then pulls back or goes sideways, finds
  support on a rising 10-, 20- or 50-day SMA ("the strongest surf the 10, strong the 20, slower the 50"), builds higher
  lows, the range gets tighter, ideally a narrow-range day before the breakout, then breaks out of the tight multi-day or
  multi-week range on high volume. Moving averages rising "at 45 degrees or more". Relative strength on market-down days.
  He shows the same shape on BTC 2012–2017 and ETH and says it works on crypto. [3:32–3:41; 1:59–2:09]
- **Entry:** the opening-range high of the breakout day (first 1-, 5- or 60-minute candle), or any time of day while the
  stop is no further away than one ATR (his own stops about half an ATR); not if the stock is already up more than its
  ADR on the day; never within three days of earnings; no scaling in. [0:28–0:29, 0:36–0:38, 2:49–2:51]
- **Exit:** sell a third to a half after three to five days, move the stop to break-even, trail the rest on the first
  close below the 10-day SMA (20-day for slower names). Stop at the entry day's low. [0:40–0:41, 1:25–1:27, 2:40–2:41]
- **Sizing and market filter:** never more than 25% of the account in one stock; a "momentum market" is the Nasdaq's
  10- and 20-day SMAs rising with the 10 above the 20 — otherwise sit in cash for weeks or months. [1:11, 1:31–1:33, 3:40]
- **Claims, all self-reported in the video:** 20–30% win rate (22–25% "last year"), winners of 5–30× initial risk,
  ~268% average annual return 2013–2019, $5 M in June 2020; a $1.5 M loss on a mis-clicked Kodak short is shown live.
- **Our nearest tests:** `tsmom_v1`, `xsmom_v1` (crypto, FAIL), `etf_tsmom_v1` (FAIL at gate 5 against holding),
  `trend_reset` (the earlier clip's rule, built, not run). Not tested anywhere: the tight-range breakout entry with the
  3–5-day partial exit and the 10-day trailing stop, as one path. His universe is high-ADR small and mid caps; he says
  outright not to trade AAPL, AMZN, GOOG or FB ("too slow"), so our 31 Nasdaq names are the wrong instrument for his
  method. The lake that matches his universe is the crypto spot lake (734 pairs with ADR 5–15%, delistings kept).

## 2. The TraderLion conference, talk by talk

**Marsten Parker — "A survey of systematic trading strategies" (1:50–3:21).** Full-time systematic since 2000, in
*Unknown Market Wizards*, author of the RealTest software; 24 example systems with their stats, daily bars, Norgate data
with historical index constituents. What he says, with the numbers: SPY buy-and-hold since inception 10% a year with a 55%
drawdown; the 50/200 golden cross Sharpe 0.76 against 0.62 for holding; price crossing 20-, 50-, 100-day averages "really
doesn't have very great results" on SPY, 200 "okay", Donchian channels slightly better; RSI(2) below 30 buy / above 70 sell
on SPY slightly beats holding with half the drawdown; the Nasdaq-100 top-5 by IBD relative strength rotated monthly earns
about three times SPY's return at the same drawdown, and testing it on today's constituents is look-ahead; a VIX
term-structure VXX system with 20% of the account; Keller–Keuning tactical allocations, flat since 2022; futures trend
following (126-day breakout, 3-ATR trail, 0.5% risk) flat for eight years then good in 2022; his own long–short breakout
system "spectacular" 1998–2002, flat after, revived in 2022; a 30%-return/15%-drawdown combination that decayed after 2022
because short-term mean reversion stopped working; mean-reversion shorts without stops lost on GME in January 2021; the
IPO system "probably permanently broken". His frame: systematic trading, done right, "could allow you to slightly beat
passive investing"; every idea "boils down to momentum or mean reversion"; his bar is 20% a year without a 20% drawdown
and "it's hard to do"; the defences against overfitting are a portfolio not a symbol, long and short, combined strategies,
few parameters and round numbers; chart-pattern study overlooks the losers, and when he coded a discretionary breakout look
"objectively the way a chart looks doesn't really make a difference". Nothing in this talk is new to this project; it is an
independent practitioner reaching the project's own conclusions, with the one momentum result (NDX top-5 rotation) that
Programme 1's `etf_xsmom`/`ls_xsmom` tests did not reproduce on their universes.

**Pradeep Bonde ("Stockbee") — "Swing trading catalysts and momentum bursts" (5:17–6:46).** Two setups. *Episodic
pivots (EP):* a catalyst — a sales or earnings surprise, or a story — re-prices a neglected stock; checklist "MAGNA 53,
cap 10×10": Massive acceleration (triple-digit growth or a large beat), Gap up, Neglect (two months to three years of
nothing; under 100 funds; no analysts, no news), Acceleration in sales (≥ 39%, two quarters running); optional: short
interest ≥ 5 days to cover, ≥ 3 analysts raising targets; market cap under $10 B, IPO within ten years. Entry at the open
(an OPG order) or after a few minutes; stop 2.5%, 10% for a conviction trade; size 50–100% of the account on a real
catalyst, 20–25% on a story; the target decided in advance (a 40–50% move), killed if the stock hesitates; claimed 70–80%
win rate on classic EPs in a fresh bull market, three or four genuine ones a year now. Variants: the *delayed-reaction EP*
(enter on the first positive day after the gap; shorts after the 3–4-day bounce that follows a gap down); the *"9 million
EP"* (a day's volume above 9 million shares when that is abnormal for the stock, on a 4%+ day — 100–300 trades a year);
"sugar babies" (names with repeated 9 M days — MARA, CVNA, COIN — that swing 40–50% in three to five days). *Momentum
bursts:* 3–5-day trades for 8–20%, mostly in high-priced names (ORLY, AZO, CMG, DECK), biotech, technology and consumer
discretionary, caps under $1 B for the small ones; the "2-Lynch" criteria: not up two days running, a linear mover, a
negative or narrow-range day before the breakout, an orderly low-volume consolidation of under ten days (longer ones need
a catalyst and 1.5–2× the 50-day average volume), closing near the high; stop at half the day's range. *Situational
awareness:* his market monitor (buying versus selling pressure, stocks up or down 25% in a quarter and a month; "all four
columns green" → buy breakouts) and the count of stocks up 20% in five days as an oscillator (below 20 → buying comes in,
above 100 → selling). He calls PEAD "structural" and says the 50% movers come from neglect, not strength. **Our nearest
tests:** `p2_pead_v1` (FAIL: t 1.37, alpha −2.9%/yr, 68% drawdown), `p2_short_squeeze_v1` (FAIL), `p2_insider_cluster_v1`
(FAIL). The EP needs point-in-time fundamentals, consensus and fund counts that the lake does not hold at $0; the
price-and-volume pieces (the 9 M day, the burst) need a small- and mid-cap universe the lake does not hold.

**John Pocorobba — "Building confidence trading earnings gaps" (9:46–11:00).** Part-time position trader, Boston IBD
meetup. *Power earnings gap (PEG):* gap ≥ 10%, volume ≥ 200% above average, EPS surprise ≥ 20% over consensus. His study
(the 2016–18 bull, the 2020–21 bull, the 2022 bear; sample size not stated): 88% of PEGs had earnings surprises in the next
two quarters while prior quarters "had very little correlation"; the gap day's close — the "high-volume close" — is the
institutional level: an undercut of 0–3% was followed by +7% over the next ten days and +18% over thirty; about 70% of PEGs
undercut by ≤ 3%, 75% by ≤ 5%; 60% of all gaps never undercut by more than 5%. *The buy rule:* after the gap day, wait for a
3–5% pullback to the 5-day EMA, buy when price recovers the high-volume close, a 5% stop, hold through the first eight weeks
("the alpha window"), add on the gap-day high; prefer names held by ≥ 400 funds and sectors whose gaps are being rewarded.
In the 2022 bear, buying the gap at the close and selling ten days later "came out ahead" (his words: a small sample).
**Our nearest test:** `p2_pead_v1` — the same mechanism (institutional under-reaction to a surprise) with a looser entry,
FAIL. The rule needs consensus estimates; a price-only version on the 31 names would have too few ≥ 10% gaps to reach a t
of 3.

**Roy and Wes Mattox — "Tracking market trends and market environments" (8:17–9:46).** Registered advisers (Charlotte,
IBD meetup). The short-term trend is the 10-day EMA against the 21-day EMA on the Nasdaq and S&P; intermediate, the 21 EMA
against the 50 SMA; long-term, two closes below the 30-week average. Eleven historical tops (1987 to 2022) where the 10/21
cross came "within 5% of the top", often a day or two after the 50-day broke on volume; re-entry on the cross up or a
follow-through day; never more than a 30% change of exposure in a day; the aim is "80% of the uptrend, miss 80% of the
downtrend"; MACD and its "price phase" as the early warning; they report +35% in their swing accounts and the 20s in core
accounts for 2024 to date, and sold Nvidia near its June peak. **Already answered:** `etf_tsmom_v1` stopped at gate 5
against holding; `review_cloud9_ma_cross_15m` failed; and Parker, on the same stage, shows index moving-average crosses
below holding. A 10/21 cross is a regime *filter*, not an edge; as a filter it can be a control arm of a registered rule.

**Marios Stamatoudis — "The two layers for building trading mastery" (0:17–1:50).** Momentum swing trader in hot
themes; risk 0.2–0.3% of the account a trade, positions sized by entry-to-stop distance and capped at 25%, win rate
25–35%, big winners 30–60× risk; "edge erosion" of breakouts across decades and wider stops raising the win rate more than
proportionally; a study of about 10,000 gap-ups of ≥ 6% ("2016(?) to 2023") in which "the majority plateau or drop a few
days after the gap". The rest is perspective, not rules.

**Dr Brett Steenbarger (3:21–5:17)** — positive psychology, strengths over problems, with a bonus interview of a 2023
US Investing Championship day trader (85% for the year; 750 trades, profitable only after cutting to 150 in the second
half; a small-cap scanner: $0.50–$11, volume ≥ 1 M, up ≥ 20%). **John Burns (6:46–8:17)** — intuition and the mental game
from an ex-pit option market maker; "stackable edges"; the only numbers are a mechanical system's win/loss mix. Neither
contains a rule to test.

## 3. Sean Trades — a discretionary momentum system on options

Market filter: long only when SPY/QQQ are above the 8- and 21-day EMAs, the 50 as "the last line of defence". Sector and
theme rotation (a sector watchlist; ARKK as the risk-on gauge; nuclear, aerospace, quantum and COIN as the 2025 themes).
TradingView screener: price > $3, change > 0.01%, market cap > $2 B, the 8/21/50 EMAs below price, sorted by volume. Weekly
chart in an uptrend or breaking a multi-month base; daily "staircase": a high-volume ignition move, a consolidation on
declining volume beside the 8/21 EMAs. Entry on the break of the pattern's prior high with 5-minute volume above its
average; stop at the low of the day or under the 8 EMA; first trim at ≥ 1.5R, 25% off at each next pivot, the last 25%
trailed on a daily close below the 8 EMA; options with enough time, never weeklies. Claims: "$100k+ a month", 500–1,000%
option returns on a 33% stock move in eight days; no record shown; coaching sold in the description. **In our terms:** the
same O'Neil/Minervini/Qullamaggie breakout as §1 with EMAs for SMAs and options for shares; nothing to test beyond §1,
and the options layer multiplies cost and gap risk on a rule that has not shown an edge.

## 4. Tom Hougaard — process over outcome

One morning on the FTSE 100 (spread bets of £1,200–3,000 a point): a long off a night retracement level at 7,436 with
adds at 7,437 and 7,442, out at 7,451–53 before the 08:00 "U-turn"; then a short that he adds to while losing (against
his own rule) and is stopped out of; then the lesson — zoom out from the 5-minute to the 15-minute chart, halve the stake,
"sell on close" of a bar closing below the two prior closes and the prior body, add 50% once it works, trail the stop above
the prior bar's high only after a new low (inside bars do not count), take profit at a double bottom around noon. He says
the day was heavily negative before it ended "outstandingly profitable"; no record beyond the narration. Nothing testable:
the levels and bars are discretionary. The one transferable idea — that process beats outcome because you never know the
next trade — is what this project's pre-registration does mechanically.

## 5. The whole, and what it means here

- **Three of the four are one school.** Qullamaggie, Sean Trades and three conference speakers teach the same thing:
  buy leading stocks breaking out of tight consolidations in a market whose short averages are rising, cut at the day's
  low, sell into strength and trail the rest on a short moving average. The fourth is about temperament.
- **The one quantitative talk agrees with this project's record.** Parker's survey has index moving-average timing
  below holding, breakouts "spectacular" only before 2002, short-term mean reversion dead since 2022, and systematic
  trading at best "slightly beating passive" — which is `docs/18` in another person's words.
- **The nasdaq31 instrument built this week is the wrong universe for this school.** Every speaker who names a universe
  wants ADR above 4%, caps under $10 B, neglect; Qullamaggie names our megacaps as the stocks not to trade. The crypto
  spot lake is the one dataset here with that character and no survivorship, and he says the setup works there.
- **What has not been tested here, exactly:** the breakout *path* — a momentum universe, a tight-range breakout on
  volume, a stop at the entry low, a partial sale after three to five days and a 10-day trailing stop — as one rule. The
  entry/exit path is the only element Programme 1's momentum tests (`tsmom`, `xsmom`) did not carry.
- **What cannot be tested at $0:** Bonde's and Pocorobba's catalyst rules (point-in-time sales growth, consensus
  surprises, fund counts, small-cap volume) — the lake has none of it; a US small/mid-cap daily set with historical
  constituents (Parker's Norgate) is a paid item, the owner's call, and `p2_pead_v1` already failed the mechanism.

## 6. Recommendation (nothing started)

One memo, if the owner wants a counter spent: **Qullamaggie's rule, made exact, on the crypto spot lake**, in-sample
2018 → August 2025 at the measured maker cost, gate 5 against the exposure-matched holding of the same momentum universe;
controls: random entries within the same universe and regime (`RandomEntry`), the universe held always-in (does the path
add anything to owning the momentum basket?), a one-day-late entry (does the breakout day matter?), and the 10/21 regime
filter on and off. Honest prior: a fail at gate 3 or 5, as every momentum rule here has; but it is the one rule in the
four videos that is new, exact and testable at $0. `trend_reset` (the earlier clip) is its sibling and stays built and
unregistered until the owner says which, if either, to register. Everything else in the list is either already answered,
needs paid data, or is not a rule.
