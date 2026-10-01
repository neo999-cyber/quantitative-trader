# Stablecoin ladder — one-year loss distributions on $1,300 (Monte Carlo, 20,000 years, assumptions in `qr/research/stable_stress.py`)

| Tier | Instrument | Stated yield | Expected | P(loss) | P(loss > 10%) | CVaR 5% | Worst 1% | Expected $ | CVaR 5% $ |
|---|---|---|---|---|---|---|---|---|---|
| 0 | US T-bill (IBKR) | 4.0% | **+4.00%** | 0.0% | 0.0% | +4.0% | +4.0% | +52 | +52 |
| 1 | Binance Simple Earn flexible USDC/USDT | 3.0% | **+1.14%** | 5.4% | 2.5% | -30.0% | -59.4% | +15 | -389 |
| 1 | Aave v3 USDC (Base/Arbitrum) | 3.6% | **+1.25%** | 8.7% | 4.1% | -35.8% | -59.7% | +16 | -465 |
| 2 | syrupUSDC (Maple) | 5.0% | **-0.27%** | 24.5% | 7.9% | -48.5% | -70.9% | -4 | -631 |
| 3 | sUSDe (Ethena) | 8.0% | **+1.17%** | 17.9% | 12.4% | -55.1% | -87.8% | +15 | -716 |
| 3 | Pendle PT on sUSDe (fixed to maturity) | 7.0% | **-3.07%** | 27.8% | 16.8% | -76.9% | -91.6% | -40 | -999 |
| 2 | BNB in Simple Earn for HODLer Airdrops | 9.0% | **+7.65%** | 57.8% | 50.5% | -75.5% | -80.6% | +99 | -982 |

## Assumptions (edit these, not the code)

| Instrument | Event | Rate / yr | Loss low / mode / high | Applies with prob. | Anchor |
|---|---|---|---|---|---|
| Binance Simple Earn flexible USDC/USDT | exchange failure / withdrawal halt | 0.025 | 20% / 60% / 100% | 100% | FTX 2022: one failure in ~40 top-5 venue-years since 2018; creditors paid at petition prices years later |
| Binance Simple Earn flexible USDC/USDT | USDC/USDT depeg print, recovers | 0.333 | 2% / 8% / 15% | 10% | USDC $0.88 for two days, March 2023; loss only if forced to sell |
| Binance Simple Earn flexible USDC/USDT | Earn product gating (days illiquid) | 0.500 | 0% / 0% / 1% | 100% | promo caps, pauses; a time cost, not a principal loss |
| Aave v3 USDC (Base/Arbitrum) | smart-contract exploit | 0.025 | 20% / 60% / 100% | 100% | no v3 principal loss in four years at $20B+; blue-chip base rate |
| Aave v3 USDC (Base/Arbitrum) | bad debt socialised | 0.100 | 0% / 1% / 5% | 100% | CRV November 2023 bad debt on Aave v2, ~0.1% of pool |
| Aave v3 USDC (Base/Arbitrum) | USDC depeg print, recovers | 0.333 | 2% / 8% / 15% | 10% | as above |
| Aave v3 USDC (Base/Arbitrum) | L2 sequencer / bridge incident | 0.100 | 0% / 5% / 50% | 30% | bridge hacks 2022; L2 funds usually recoverable |
| syrupUSDC (Maple) | borrower default in the pool | 0.250 | 1% / 5% / 20% | 100% | 2022 unsecured losses ~5% of outstanding; now over-collateralised |
| syrupUSDC (Maple) | smart-contract / delegate failure | 0.040 | 20% / 60% / 100% | 100% | industry base rate |
| syrupUSDC (Maple) | USDC depeg print, recovers | 0.333 | 2% / 8% / 15% | 10% | as above |
| syrupUSDC (Maple) | withdrawal queue (weeks illiquid) | 0.500 | 0% / 0% / 3% | 100% | fixed-term loans: exits queue in stress |
| sUSDe (Ethena) | funding negative for a quarter (yield < 0) | 0.500 | 1% / 3% / 6% | 100% | 2022-style funding regime; reserve fund 1.1% of supply |
| sUSDe (Ethena) | exchange/custody failure of a hedge venue | 0.100 | 5% / 15% / 40% | 100% | hedges sit on exchanges; FTX-type loss on one venue's share |
| sUSDe (Ethena) | depeg print on one venue, recovers | 0.500 | 10% / 25% / 35% | 10% | USDe $0.65 October 2025; loss only if liquidated/forced |
| sUSDe (Ethena) | protocol failure (UST-type) | 0.020 | 80% / 95% / 100% | 100% | UST 2022; different design, kept as the tail |
| Pendle PT on sUSDe (fixed to maturity) | funding negative for a quarter (yield < 0) | 0.500 | 1% / 3% / 6% | 100% | inherits sUSDe |
| Pendle PT on sUSDe (fixed to maturity) | exchange/custody failure of a hedge venue | 0.100 | 5% / 15% / 40% | 100% | inherits sUSDe |
| Pendle PT on sUSDe (fixed to maturity) | depeg print on one venue, recovers | 0.500 | 10% / 25% / 35% | 10% | inherits sUSDe |
| Pendle PT on sUSDe (fixed to maturity) | protocol failure (UST-type) | 0.020 | 80% / 95% / 100% | 100% | inherits sUSDe |
| Pendle PT on sUSDe (fixed to maturity) | Pendle contract failure | 0.040 | 20% / 60% / 100% | 100% | industry base rate |
| Pendle PT on sUSDe (fixed to maturity) | early exit at a discount | 0.500 | 1% / 3% / 8% | 50% | secondary exit before maturity in stress |
| BNB in Simple Earn for HODLer Airdrops | exchange failure / withdrawal halt | 0.025 | 20% / 60% / 100% | 100% | as Simple Earn |
| BNB in Simple Earn for HODLer Airdrops | price of the staked asset | — | lognormal, vol 65%/yr | 100% | yield is BNB rate + airdrops (estimate 8%); principal is BNB |

## Historical replays (deterministic)

- **SVB March 2023 (USDC $0.88, 2 days)**: USDC-holding tiers, not forced: +0%; forced to sell at the trough: -12%
- **UST May 2022 (algorithmic, to zero)**: sUSDe-type design: n/a — different mechanism; the tail event above keeps it at 2%/yr; T-bill, Simple Earn, Aave, Maple: +0%
- **USDe October 2025 ($0.65 print, one exchange)**: holder, no leverage: +0%; lent as collateral with that oracle, liquidated: -35%; Earn on another venue: +0%
