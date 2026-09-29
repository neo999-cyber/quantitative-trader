# Pre-registration: `p2_unlock_fade_v1_long` — the mirror control of `p2_unlock_fade_v1`

*17 September 2026, before any run. The same names over the same window,
held **long** (`side=long`), at the family's best variant's parameters
fixed in advance: `lead=30`, `post=14`, `min_pct=0.01`, `n_max=10`.*

The mechanism says a scheduled insider seller pushes the price down into
the cliff; a long over the same window must therefore lose. If it does not
— if the long earns as much as the short or more — there is no pre-unlock
pressure and the family's result, whatever it is, is not the mechanism.
Same universe, costs and cash benchmark as the family. One variant.

    qr gates --family unlock_fade --hypothesis p2_unlock_fade_v1_long \
      --market futures/um --costs perp --n 300 --min-history 60 \
      --benchmark cash --risk-free fred --start 2022-01-01 --end 2025-08-31 \
      --param lead=30 --param post=14 --param min_pct=0.01 --param n_max=10 --param side=long \
      --engine ledger --all-gates --upto 8
