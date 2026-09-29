# Companion: `p2_auction_imbalance_v1_100k` — the same rule in a $100,000 book

*Registered 16 September 2026 after the $1,000 family's run, as its own
hypothesis so that gate 0 is clean. It is the companion the family's
pre-registration promised: the same rule, universe, costs and benchmark
with `--equity 100000` and up to 20 positions, so that diversification
available only at scale does not flatter — or hide — the $1,000 result. It
is not a second chance for the family: the family's verdict stands (FAIL
at gate 2 on 16 September); this reports what the mechanism is worth to a
larger account, which is the question `docs/11` asks of every finding.*

    qr gates --family auction_fade --hypothesis p2_auction_imbalance_v1_100k \
      --market auction-xnas --costs alpaca --basket nasdaq31 --equity 100000 \
      --benchmark exposure --risk-free fred --end 2025-08-31 \
      --grid 'k=[0.10,0.20,0.30,0.50]' --grid 'snapshot=["15:50","15:55"]' \
      --param n_max=20 --param side=sell --all-gates --upto 8

8 variants. Predicted: the same ~9 bps gross per event; more events held
per night, so lower volatility; costs still half of gross; not a pass.
