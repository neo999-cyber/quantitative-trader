# Pre-registration: `p2_unlock_fade_v1_eco` — the ecosystem-cliff control of `p2_unlock_fade_v1`

*17 September 2026, before any run. The family's rule run on the
**ecosystem / community / airdrop** unlocks (`category=eco`) instead of
the insider and private-sale cliffs, short, `min_pct=0.01`, `n_max=10`.*

Keyrock's study finds ecosystem unlocks are the exception — on average
slightly positive — because the recipients (grants, liquidity programmes)
do not dump. If shorting into *these* earns as much as shorting into
insider cliffs, the effect is "any unlock inflates supply", not "a seller
with a date", and the family is re-scoped as a supply-inflation claim
rather than passed. Same universe, costs and cash benchmark. One variant.

    qr gates --family unlock_fade --hypothesis p2_unlock_fade_v1_eco \
      --market futures/um --costs perp --n 300 --min-history 60 \
      --benchmark cash --risk-free fred --start 2022-01-01 --end 2025-08-31 \
      --param lead=30 --param post=14 --param min_pct=0.01 --param n_max=10 --param category=eco \
      --engine ledger --all-gates --upto 8
