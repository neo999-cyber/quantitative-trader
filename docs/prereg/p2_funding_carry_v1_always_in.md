# Control: `p2_funding_carry_v1_always_in` — hold every eligible carry unit

*Registered 15 September 2026. This is the first control named in
`docs/prereg/p2_funding_carry_v1.md` ("always-in carry"), run as its own
hypothesis so it has its own report and its own gate verdicts. The second
control, hold-T-bill, is the benchmark itself and needs no run.*

Same universe (`carry_top40`), same panel (`carry-um`), same cost model
(`carry_pair`), same benchmark (cash, FRED DTB3), same in-sample end
(`--end 2025-09-14`). One variant, no search:

    FundingCarry(entry=-1.0, exit=-2.0, ceiling=1.0, n_max=40, lookback=7)

which opens every eligible unit (no annualised funding is below −100%),
never closes one for its funding, never refuses one for its percentile, and
holds up to the whole universe at equal weight. The `lookback` is
immaterial when the floor is −1.0 and is fixed at 7 so the variant is
unambiguous.

What it answers: whether `p2_funding_carry_v1`'s entry rule adds anything
after its turnover. If the family does not beat this control net of costs,
the finding is "hold the carry, do not time it". Predicted: positive
against cash, lower gross Sharpe than the timed family, higher net
turnover-adjusted return only if the entry rule earns its trading.

Invocation:

    qr gates --family funding_carry --hypothesis p2_funding_carry_v1_always_in \
      --market carry-um --costs carry --n 40 --min-history 180 \
      --benchmark cash --risk-free fred --end 2025-09-14 \
      --param entry=-1.0 --param exit=-2.0 --param ceiling=1.0 \
      --param n_max=40 --param lookback=7 --all-gates --upto 8
