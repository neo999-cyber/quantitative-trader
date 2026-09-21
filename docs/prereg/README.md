# Pre-registration documents (gate 0)

One per hypothesis, written and hash-stamped **before** the first run touches the data:

```bash
qr trial prereg tsmom_v1 --file docs/prereg/tsmom_v1.md
```

The stamp records the SHA-256 of the document at the moment of registration, so a document edited afterwards no longer matches its record. Gate 0 also fails if the first run for a hypothesis id predates its registration — writing the prediction after seeing the result is the thing being prevented, and doing it anyway is recorded rather than silently allowed.

Each document must state, before any data is touched:

| Section | Why it is required |
|---|---|
| **Mechanism** | Why this should work at all. Without one, a positive result is a coincidence with a narrative attached afterwards. |
| **Predicted sign and size** | A prediction you can be wrong about. "Some edge" is not one. |
| **Universe** | Fixed in advance, so the universe cannot be tuned to the result. |
| **Horizon** | The holding period, fixed before the Sharpe is known. |
| **Parameter ranges** | The grid to be swept — this is the trial count gate 4 deflates against. Widening it later is a new hypothesis. |
| **Cost model** | The frozen one, named. Costs discovered to be survivable only at a lower fee tier are not survivable. |
| **OOS period** | The holdout, named before it is opened, and opened exactly once. |
| **What would falsify this** | The honest section. If nothing would, this is not a hypothesis. |

The four trial families are registered here: `tsmom_v1`, `xsmom_v1`, `reversal_v1`, `rsi_reversal_v1` (the control).
