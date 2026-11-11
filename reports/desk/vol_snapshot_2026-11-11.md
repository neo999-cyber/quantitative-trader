# Volatility snapshot — 11 November 2026 (descriptive; nothing registered, nothing run through the engine)

Asked by the owner: "there is huge volatility in the stock market and it is affecting crypto too; how can we make
use of it, and learn about this". Public endpoints only: Binance spot daily klines and perp funding, Deribit's DVOL
index, CBOE's own VIX history file, the box's desk sheet of the same morning. The S&P 500 itself could not be
fetched (FRED timed out from the laptop and from the box; Stooq, Yahoo and Nasdaq refused), so the equity side is
VIX alone. Closed UTC days to 10 November; percentiles are within the last 365 days (252 sessions for VIX).

| | now | before | reading |
|---|---|---|---|
| BTC close | 73,796 | −11.9% over 30 days, −4.7% over 7 | −14.8% from the 90-day high; largest daily move in 14 days 5.6% |
| ETH close | 2,053 | −19.1% over 30 days, −9.7% over 7 | −26.0% from the 90-day high; largest daily move 8.0% |
| BTC realised vol, 7 / 30 / 90 days | 55% / 36% / 41% | | the week is at the 85th percentile, the month at the 35th |
| ETH realised vol, 7 / 30 / 90 days | 90% / 51% / 57% | | 91st / 42nd |
| BTC DVOL (30-day implied) | 39 | 38 a month ago, 35 three months ago | high 44 on 30 October; 38th percentile; 4 points over 30-day realised, 16 under the week's |
| ETH DVOL | 56 | 52, 49 | high 61 on 30 October; 47th percentile; 5 points over 30-day realised |
| VIX close | 19.5 | 15.2 a month ago | 16.6 → **28.2 on 5 November** → 25.6 → 19.9 → 19.5; last-year median 17.1, maximum 31.1 (27 March 2026); 78th percentile; four days of +2 points or more in 30 sessions |
| BTC daily return against the day's change in VIX | correlation **−0.68** over 20 sessions | −0.39 over 60, −0.40 over 250 | on the 23 days VIX rose more than 2 points in the last 250 sessions BTC fell on 19, mean −2.6% |
| BTC perp funding, annualised | +7.8% over 7 days, +7.3% over 30 | +6.2% over 90, 3.5% over 365 | no negative print in the last 21; at 1× on capital 3.49% over 30 days against a 4.12% bill |
| Daily-ladder recording (v3) | 108 asset × date clusters seen, 87 settled | 60 seen, 39 settled on 27 October | the ceiling for the 30 November read; the minimum is 30 *with a fill* |

What it says, in order of how sure it is:

1. **The stock-market spike was one day and is fading.** VIX jumped from 16.6 to 28.2 on 5 November and closed at
   19.5 three sessions later — above its median, below March's peak.
2. **Bitcoin traded as a high-beta risk asset through it.** Its link to the day's change in VIX nearly doubled.
3. **The option market does not price a volatile regime in crypto.** DVOL is below its one-year median and barely
   moved in the month; the past week's realised vol is far above it. Implied over 30-day realised is an ordinary
   4–5 points: there is no rich insurance premium to sell and no cheap one to buy.
4. **Leverage has not been flushed.** Funding stayed positive on every print and is twice the year's average; the
   carry at 1× is still under the bill.

**Disclosure (a look, not a test):** one conditional figure was computed — BTC's return on the session *after* those
23 VIX-spike days: +0.71% against −0.06% on all days, standard deviation 3.63%, t 0.93, positive on 13 of 23. Noise.
Any later memo on equity-volatility spillover must cite this look as seen before drafting.

What the project's own results say about using volatility: variance is forecastable and already priced (P3-C, P5:
nothing beats DVOL), direction is not (the same two runs, six models); buying after forced selling does not pay (C3);
ETF flow pressure does not carry to the next session (P4); timing the carry loses to holding it (P4). The one open
test that a fast market feeds is the registered ladder read of 30 November.
