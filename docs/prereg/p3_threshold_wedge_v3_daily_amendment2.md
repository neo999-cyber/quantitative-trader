# Amendment 2 to `p3_threshold_wedge_v3_daily` (and a data note for v2) — amendment 1's diagnosis corrected; price changes kept at the top of book only

*13 October 2026, 05:45 UTC, before any daily-ladder line was read for a
wedge. Registered as its own stamp; amendment 1 (seq 975) is left as
written, because the log is not edited.*

**Amendment 1 was wrong about the cause.** The megabyte frame at each
(re)connect is all 659 subscribed books in one message, about 1.7 KB a
book, 30 bid and up to 100 ask levels each — not megabyte books. The
50-level cap it introduced trims only asks beyond the fiftieth level and
is harmless; it stays. The venue's "slow consumer" closes came from the
steady stream, not the dump: after the daily ladders were admitted the
recorder kept ~270 `price_change` lines a second (83 MB of JSON in a
quarter of an hour, ~1 GB gzipped a day on a box with 26 GB free), 86% of
them entries kept only because they sat within 2¢ of the mid, and the
standard-library JSON parser fell behind in bursts.

**From 13 October 2026 05:4x UTC the recorder keeps a `price_change`
entry only when it moves that token's best bid or best ask** (`--near 0`;
the 2¢ band is no longer kept), parses with `orjson`, and still never
drops `book`, `last_trade_price` or `tick_size_change`. Nothing the
registered rules read changes: v2 and v3 take the best bid and ask from
`book` and `price_change` and fills from `last_trade_price` prints. The
2¢-band entries existed for the rewards sizing (P3-B, `docs/31` §11),
which was completed on 11 October from the earlier recording; the hourly
full-book snapshots keep the depth picture for anything later.

For v2 (seq 934) the monthly markets' recording therefore has band
entries until 05:4x UTC on 13 October and top-of-book moves only after;
its rule cannot tell the two apart.
