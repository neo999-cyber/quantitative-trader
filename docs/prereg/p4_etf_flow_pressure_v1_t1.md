# `p4_etf_flow_pressure_v1_t1` — the diagnostic arm of `p4_etf_flow_pressure_v1`

*Registered 27 October 2026 beside the family's memo (`docs/prereg/p4_etf_flow_pressure_v1.md`), which holds
the mechanism, the rule, the cost model, the sample, the gates and the falsifiers. This document names the
sweep so gate 0 can find it.*

**What it is.** The same **6 variants** (`k ∈ {0.5, 1.0, 1.5}` × `hold ∈ {session, 24h}`) at `timing = t1`:
the issuer's row acted on at 09:00 New York during the session it is dated, as an aggregator's evening table
would have allowed — a path that exists live from 15 October 2026 and has no history. It measures whether the
effect exists one session earlier than our own data path can act; it is not eligible for the holdout verdict
or for money, whatever it shows.

**Reading.** Diagnostic positive while the primary is not: the effect is real and faster than our data path —
a data question (a live T + 1 feed, recorded forward), not a trade. Both flat: no effect at either horizon.

Run: the family's command with `--hypothesis p4_etf_flow_pressure_v1_t1 --param timing=t1`.
