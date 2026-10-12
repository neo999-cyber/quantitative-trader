# The tape, calibrated by the live result (stage 0 × stage 1)

Live fills ran **-3.46 points** below the tape on the five names traded (spread between names under one point); the 60-second mark ran **+0.29 bps** above it. The same correction applied to the fifteen names never traded live gives `CostModel.maker_measured_for(symbol)`.

| symbol | tape fill 15 min | calibrated fill | tape mark 60 s (bps) | calibrated mark | basis |
|---|---|---|---|---|---|
| 1000PEPEUSDT | 98.6% | **95.1%** | +1.02 | **+1.31** | calibrated |
| ADAUSDT | 96.3% | **92.8%** | +1.96 | **+2.25** | measured live |
| BEATUSDT | 85.8% | **82.4%** | +5.46 | **+5.76** | calibrated |
| BNBUSDT | 97.5% | **94.0%** | +0.59 | **+0.88** | calibrated |
| BTCUSDT | 97.4% | **93.9%** | +0.62 | **+0.92** | calibrated |
| CLUSDT | 92.9% | **89.4%** | +0.54 | **+0.84** | calibrated |
| DOGEUSDT | 97.6% | **94.1%** | +0.54 | **+0.84** | measured live |
| ENAUSDT | 98.9% | **95.4%** | +1.24 | **+1.54** | calibrated |
| ETHUSDT | 97.8% | **94.3%** | +0.61 | **+0.91** | calibrated |
| HYPEUSDT | 97.8% | **94.3%** | +0.82 | **+1.11** | calibrated |
| LINKUSDT | 98.0% | **94.5%** | +1.17 | **+1.46** | calibrated |
| NEARUSDT | 98.8% | **95.3%** | +1.14 | **+1.44** | calibrated |
| ONDOUSDT | 97.9% | **94.5%** | +1.19 | **+1.48** | measured live |
| SOLUSDT | 97.7% | **94.2%** | +0.42 | **+0.72** | calibrated |
| SUIUSDT | 98.4% | **95.0%** | +0.53 | **+0.82** | measured live |
| UNIUSDT | 98.4% | **95.0%** | +1.54 | **+1.84** | calibrated |
| WLDUSDT | 98.5% | **95.0%** | +1.10 | **+1.40** | calibrated |
| XAUTUSDT | 79.7% | **76.2%** | +0.75 | **+1.04** | calibrated |
| XRPUSDT | 98.3% | **94.8%** | +0.36 | **+0.65** | measured live |
| ZECUSDT | 99.0% | **95.5%** | +0.88 | **+1.18** | calibrated |

Day type, measured live: weekdays 96.0% filled, mark +0.50 bps; weekends 91.6%, +1.76 bps (`CostModel.maker_measured(day_type=...)`, and `by_dow=True` for a haircut that follows the calendar in the runner).
