# Pre-registration: `rsi_reversal_v1` — the 3-down-day RSI setup (**the control**)

*Written 11 September 2026, before the first run.*

## What this is for

This is `centaur/screens/pattern_matcher.py`'s `SetupSpec`, ported unchanged and run as a systematic strategy: three consecutive down closes, each on above-average volume, with RSI(14) below 30, held for five bars. The port is verified bit-for-bit against the original in `tests/qr_platform/test_families.py`.

**It is in the trial to fail.** A validation engine that passes everything it is shown is worthless, and the only way to know it can say no is to hand it something that should get one. The three real families are tested against the market; this one tests the engine.

Stating that in advance matters. If I ran this without pre-registering the expectation and it failed, I would have learned nothing — a failure is only evidence about the engine if the prediction preceded it. And if it *passes*, that is a genuine surprise that demands the engine be checked before the strategy is believed.

## Mechanism

The claimed mechanism is capitulation: a short sharp decline on rising volume with an oversold oscillator marks sellers exhausting themselves, and price mean-reverts.

The mechanism is not absurd — short-horizon reversal after forced selling is the same argument as `reversal_v1`. What is absent is any reason to believe *these particular three conditions at these particular thresholds* isolate it. The setup was chosen by eye, on US equities, from a discretionary rulebook. It has never been costed, never been swept, and never met a multiple-testing correction.

## Predicted sign and size

**No edge after costs.** Predicted net Sharpe: **−0.3 to +0.3**, indistinguishable from zero.

Specific prediction about *how* it fails, recorded so the mechanism of failure can be checked rather than just the verdict:

> **It will fail gate 8 on trade count, not on return.** On 900 bars of random walk the three-down-days-on-volume condition fires 19 times and RSI < 30 fires 32 times, and they coincide **zero** times. The conjunction is far rarer than either component, because a short sharp drop and a sustained oversold reading are different things. A setup that produces almost no trades cannot clear the 50-round-trip minimum however good its win rate looks on the handful it gets.

## Universe

`binance_spot_top30`, identical to the other three families. Deliberately identical: a control that ran on a different universe would not be a control.

## Horizon

Daily bars, five-bar holding period. Overlapping signals extend the holding rather than doubling the size.

## Parameter ranges

| Parameter | Range | Swept? |
|---|---|---|
| `down_days` | 2, 3, 4 (3 values) | yes |
| `rsi_max` | 25, 30, 35 (3 values) | yes |
| `hold` | 3, 5, 10 (3 values) | yes |
| `volume_multiple` | 1.0 | fixed |
| `volume_window` | 20 | fixed |
| `rsi_period` | 14 | fixed |

**27 variants.** Six constructor parameters, three swept. Gate 8 counts the swept ones — a threshold held fixed costs no degrees of freedom — so three is within the limit of five. The original setup's six hand-chosen constants are a fair criticism of it, but they are not what gate 8 measures.

## Cost model

`CostModel.trial()`: 9.5 bps per side, fee tier verified 11 September 2026. Identical to the other families.

## Out-of-sample period

The final 12 months, opened exactly once — if it gets that far, which it should not.

## What would falsify this

The prediction here is *failure*, so falsification means the setup **passing**. If it clears gates 1–8:

1. Check the engine first, not the strategy. A control passing is evidence about the engine before it is evidence about the market.
2. Check the trade count specifically: if gate 8 passed on round trips, either the crypto universe fires this setup far more often than a random walk does (plausible — crypto has real capitulation episodes) or there is a bug in the setup port.
3. Only then treat it as a finding, and note that the Centaur rulebook has been carrying an unvalidated setup that turns out to be real.

## Prior

Fails at gate 8, most likely on round trips, possibly earlier at gate 3 on significance for want of observations. A pass would be the most interesting result of the entire trial and the one I would trust least without re-checking.
