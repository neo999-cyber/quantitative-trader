# Control: `p2_auction_imbalance_v1_mirror` — buy into a buy imbalance

*Registered 16 September 2026, before any run. The mirror control of
`p2_auction_imbalance_v1`: the same class, sizing, universe, costs, benchmark
and in-sample end, with `side=buy` — buy at the close into a **buy**
imbalance of at least `k`, sell at the next open. The mechanism predicts this
earns nothing or loses (the push is against the buyer). If it earns as much
as the family, the family is overnight drift, not the auction. One
variant, the family's central setting:*

    qr gates --family auction_fade --hypothesis p2_auction_imbalance_v1_mirror \
      --market auction-xnas --costs alpaca --basket nasdaq31 --equity 1000 \
      --benchmark exposure --risk-free fred --end 2025-08-31 \
      --param k=0.20 --param snapshot=15:55 --param n_max=4 --param side=buy \
      --all-gates --upto 8
