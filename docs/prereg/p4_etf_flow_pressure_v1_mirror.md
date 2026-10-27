# `p4_etf_flow_pressure_v1_mirror` — the mirror control of `p4_etf_flow_pressure_v1`

*Registered 27 October 2026 beside the family's memo (`docs/prereg/p4_etf_flow_pressure_v1.md`). This
document names the sweep so gate 0 can find it.*

**What it is.** The primary arm's **6 variants** (`k ∈ {0.5, 1.0, 1.5}` × `hold ∈ {session, 24h}`,
`timing = t2`) with the sides reversed (`control = mirror`): short after inflows, long after outflows. It
should lose what the family earns; a positive mirror says the family's return is not the mechanism's.

Run: the family's command with `--hypothesis p4_etf_flow_pressure_v1_mirror --param control=mirror`.
