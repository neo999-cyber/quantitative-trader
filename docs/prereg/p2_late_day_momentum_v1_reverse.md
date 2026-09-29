# Control: `p2_late_day_momentum_v1_reverse` — buy the down days

*Registered 16 September 2026, before any run. The mirror control of
`p2_late_day_momentum_v1`: the same instrument, book, costs and benchmark,
with `side=reverse` — buy at the decision when the day is down by at least
`k`, sell at the close. The mechanism says this loses.*

    qr gates --family late_day_momentum --hypothesis p2_late_day_momentum_v1_reverse \
      --market intraday-xnas --costs alpaca --basket qqq --equity 1000 \
      --benchmark cash --risk-free fred --end 2025-08-31 \
      --param k=0.005 --param side=reverse --all-gates --upto 8
