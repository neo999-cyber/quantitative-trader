# The Options Flow Vulture

Write (or run) a Python script that flags stocks where call option volume is > 300% of the 30-day average,
specifically in strikes expiring within 14 days.

Requirements:
- Data source: Unusual Whales (or FlowAlgo) if an API key is available; otherwise build the 30-day baseline
  from daily option-chain snapshots and report how many days of baseline exist.
- Flag only calls. Ignore contracts with volume < 500. Compute days-to-expiry from today.
- Note when volume exceeds open interest (new positioning rather than closing trades).
- Output per flag: ticker, expiration, strike, volume, 30-day average, ratio, DTE, OI, note.
- Sort by ratio descending. Print JSON.

Interpretation rules for the trader:
- Flow is ONE category (sentiment_flow). It never justifies a trade alone.
- Short-dated call sweeps ahead of a known event (earnings, FDA date) are often hedges or lottery
  tickets - mark them "event-driven" and lower confidence.
- Flow that persists over 2+ days and is confirmed by price holding above VWAP is stronger than a single print.

Reference implementation: `centaur flow --tickers ... [--provider unusualwhales]`.
