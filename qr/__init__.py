"""qr — the quantitative research platform (working name).

Layers, mirroring `docs/PLAN.md` §2:

* `qr.data`       — ingestors, reference tables, the Parquet lake, QA checks
* `qr.features`   — point-in-time feature sets
* `qr.strategies` — the `Strategy` interface and the strategy library
* `qr.research`   — backtest runners (numpy reference + vectorbt cross-check)
* `qr.validate`   — the gates, the trial log, the Hypothesis Report
* `qr.execution`  — cost models, broker adapters, reconciliation
* `qr.portfolio`  — allocation, sizing, risk

`centaur/` (the discretionary assistant) is deliberately untouched by this package.
"""
from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
