# The Historical Pattern Matcher

Scan the S&P 500 for stocks that have dropped 3 consecutive days on above-average volume, but have an
RSI(14) below 30. For each hit, tell me the historical 5-day forward return of this exact setup on that
stock over the last 10 years, and the pooled result across the whole index.

Definitions (use these exactly):
- "Down day": close lower than the previous close.
- "Above-average volume": the day's volume exceeds the mean of the previous 20 sessions.
- The 3 down days must ALL be above-average volume days, and RSI(14, Wilder) on the third day is < 30.
- "5-day forward return": close 5 sessions after the signal day divided by the signal-day close, minus 1.
- Exclude signals from the last 5 sessions from the statistics (their forward window is incomplete).

Report, per hit: ticker, signal date, close, RSI, streak length, relative volume, 20-day average dollar
volume, number of historical occurrences, win rate, mean and median forward return, best/worst, and the
edge versus the stock's unconditional 5-day return. Then the pooled statistics with n.

If you cannot actually run this over price data, say so and instead produce the code that would
(the `centaur scan` command in this repo implements it; use `centaur scan --json`).

Finish with the top 5 hits ranked by edge x sqrt(n), each as a candidate JSON block.
