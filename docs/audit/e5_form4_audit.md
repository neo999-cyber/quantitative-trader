# E5 labelling audit — Form 4 parser, 15 September 2026

**Requirement** (`docs/prereg/p2_insider_cluster_v1.md`): 100 filings sampled
without looking at subsequent returns, hand-labelled as qualifying or not;
the parser must reach 95% precision on qualifying signals before the
hypothesis is registered.

**Sample.** The SEC insider-transactions data set for 2025 Q1
(`2025q1_form345.zip`, SHA-256 recorded by the loader; 109,997
non-derivative transaction rows across 50,606 filings). The first parser
(code P, acquired, officer or director, price and shares present, no 10b5-1
flag, ≥ $25,000) flagged 1,340 filings. 100 of them were drawn with
`random_state=20260915` and labelled from the filing's own fields and
footnotes only — no price series was loaded at any point (none exists in
the lake for US stocks). Labels and reasons: `e5_form4_labels_2025q1.csv`.

**Definition applied.** Qualifying = an officer's or director's own
open-market purchase: personal, spouse, own trust, own LLC or partnership.
Not qualifying = purchases in a placement, offering, IPO or negotiated
transaction; under a 10b5-1 plan; through an employee stock purchase plan,
dividend reinvestment or 401(k); a debt exchange; by an institution whose
board designee is the "director"; and filings whose issuer has no trading
symbol. An ambiguous footnote counts against the parser.

**First parser: 76 / 100 = 76% precision.** Every miss was visible in the
data set's own columns: five untraded issuers (`NONE`, `N/A`), four
institutional reporting owners, four 10%-owners buying through funds, one
10b5-1 plan stated only in a footnote, eight placements/offerings/negotiated
purchases, one ESPP, one DRIP, one 401(k), one ambiguous.

**Rules added** (`qr/data/form4.py::exclusion_reasons`, tested one per
rule): issuer must have a trading symbol; the submission's 10b5-1 flag;
entity reporting owners by name (LLC, L.P., Fund, Capital, Partners, …; a
trust is kept); TenPercentOwner buying indirectly; filing-level footnotes
naming a placement, offering, negotiated purchase, exchange or 10b5-1 plan;
transaction-row footnotes (not the holdings column's) naming an ESPP, DRIP
or 401(k).

**Revised parser on the same 100 labels: 73 retained, 72 correct —
precision 98.6%, recall 94.7%.** The one retained false positive is the
ambiguous VRME filing (a price footnote describing RSU vesting). The four
true positives dropped are all 10%-owners buying through their own
vehicles (TRS, OPK, GSAT, ACUT), excluded by the indirect-10%-owner rule
on purpose: a mechanical rule cannot tell a personal holding company from
a fund, and the paper's mechanism is the individual insider.

**Verdict: the parser passes the 95% bar.** The rules were fixed before
`p2_insider_cluster_v1` was registered and are part of its definition; a
change to them after registration is a new hypothesis.

**Acceptance times.** The data sets carry the filing date only; the EDGAR
submissions API (`data.sec.gov/submissions/CIK##########.json`) gives
`acceptanceDateTime` per accession, read on 2026-09-15 (e.g. Labcorp,
0001127602-25-010627, accepted 2025-03-31 14:47:01 UTC). `published_at` is
that time; a filing without one is never visible to a signal.
