# `p4_etf_flow_pressure_v1_placebo` — the placebo control of `p4_etf_flow_pressure_v1`

*Registered 27 October 2026 beside the family's memo (`docs/prereg/p4_etf_flow_pressure_v1.md`). This
document names the sweep so gate 0 can find it.*

**What it is.** The primary arm's **6 variants** (`timing = t2`) on the standardised flows permuted among the
entry bars within each calendar month, with a fixed seed (`control = placebo`, `qr/strategies/etfflow.py`):
the same entry days, the same number of trades a month and the same volatility, the flows on the wrong days.
A family within one standard error of its placebo has found the calendar, not the flow.

Run: the family's command with `--hypothesis p4_etf_flow_pressure_v1_placebo --param control=placebo`.
