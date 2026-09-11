# The Regime Checker

Analyse the current yield curve, VIX term structure, and DXY (Dollar Index), plus the SPY and QQQ trend.
Are we in a Risk-On or Risk-Off macro environment right now? Give me a confidence score.

Score each component from -1 (risk-off) to +1 (risk-on) and show your evidence:
1. SPY trend: price vs 50/200-day MAs; higher highs & higher lows vs lower highs & lower lows; 20-day return.
2. QQQ trend: same.
3. VIX level: <15 calm, 15-20 normal, 20-25 cautious, 25-30 stressed, >30 crisis; a >25% rise in a week is a spike.
4. VIX term structure: VIX / VIX3M below 1 = contango (normal), above 1 = backwardation (stress).
5. Yield curve: 10y minus 3m. Inverted = warning; rapid re-steepening from inversion = recession signal.
6. Dollar: DXY 20-day change. Sharp dollar strength drains global liquidity.
7. Bonds vs stocks: S&P earnings yield vs 10y yield; SPY vs TLT 20-day relative performance.

Then: weighted composite, regime label (RISK_ON > +0.2, RISK_OFF < -0.2, else NEUTRAL), and a confidence
score that reflects both the size of the composite and how many components agree.

If the regime is RISK_OFF, say explicitly: "Longs fight the tide. Cash is a position." and list what
WOULD change your mind.

Live version: `centaur regime` (add `--earnings-yield 0.045` for the bonds-vs-stocks component).
