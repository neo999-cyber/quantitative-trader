# Amendment 1 to `p3_threshold_wedge_v3_daily` (and a data note for `p3_threshold_wedge_v2_intraday`) — the recorded book depth

*13 October 2026, 05:20 UTC, before any daily-ladder line was read for a
wedge. Registered as its own stamp so the memo (seq 951) is not edited.*

The daily ladders' full order books run to about a megabyte of JSON each
— thousands of one-tick levels of bot quotes — and the CLOB sends every
subscribed token's full book on every (re)connect: 673 books, 740 MB raw,
in one minute at 05:02 UTC, after which the venue closed the socket as a
"slow consumer" (close 1013) and the reconnect sent the dump again. Left
alone that is ~1 GB a day on a box with 26 GB free and a reconnect loop
waiting to happen.

**From 13 October 2026 05:2x UTC the recorder keeps the best 50 levels a
side of each `book` snapshot** (`--book-depth 50`; the message carries
`"book_depth": 50` when it was cut; smaller books are untouched). Nothing
else changes: `price_change` entries are compacted exactly as before,
`last_trade_price` and `tick_size_change` are never dropped.

What the registered rules read from a `book`: the best bid and the best
ask (`qr/execution/pm_replay.py`, `State.apply`). Fifty levels a side is
more depth than any rewards band or posted order in either memo touches.
The monthly markets v2 reads have books of a few hundred levels at most
and are cut the same way from the same moment; v2's window (21 September
→ 26 October) therefore has whole books until 05:2x UTC on 13 October and
50-level books after, which its rule cannot tell apart.
