# Amendment to `p2_short_squeeze_v1` — what "credible" means for a publication stamp

*Written 17 September 2026, after registration and before any run, while
building the event file (`scripts/e7_events.py`); no price series read.*

The parent's availability rule uses a file's HTTP `Last-Modified` "where
credible, else the 20-day rule, whichever is later". Building the file
showed FINRA's whole 2019 → mid-2023 archive stamped 2023-07-27 (a site
regeneration) and the SEC's pre-December-2020 files stamped 2020-12-19;
taking those literally would make five years of events enter in 2023.
**Credible** is defined as: the stamp falls **0 to 60 days after** the
settlement (or half-end) date. Otherwise the 20-day rule alone applies.
Where the stamp is credible the later of the two still applies, so no
event enters earlier than either reading allows. The random control's
seed is 7; ten names a mode a date.
