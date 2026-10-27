# `p4_etf_flow_pressure_v1_always_long` — the base-rate control of `p4_etf_flow_pressure_v1`

*Registered 27 October 2026 beside the family's memo (`docs/prereg/p4_etf_flow_pressure_v1.md`). This
document names the sweep so gate 0 can find it.*

**What it is.** Long on every eligible entry session whatever the flow (`control = always_long`, k ignored
and fixed at 0), at `timing = t2`, for the session or for 24 hours: **2 variants**. It is what the family has
to beat beyond cash — bitcoin's own drift over the hours the rule trades; a family that only matches it has
timed nothing.

Run: the family's command with `--hypothesis p4_etf_flow_pressure_v1_always_long --param control=always_long
--param k=0 --grid 'hold=["session","24h"]'` (no `k` grid).
