# Pre-registration: `p2_perp_pairs_v1_random` — the random-pairs control of `p2_perp_pairs_v1`

*18 September 2026, registered with the family. The same rule, at the
family's grid centre fixed in advance — `lookback=90`, `entry=2.0`,
`exit_z=0.5`, `max_hold=10`, `n_max=10` — on **twenty pairs drawn at
random** (seed 20260918, `qr/strategies/pairs.py::random_pairs`) from the
eligible names, excluding the linked pairs.*

The mechanism says the reversion belongs to the economic link between the
two legs. If unrelated pairs revert as much under the same z-score rule,
the effect is a property of the construction — a half-life-filtered,
window-normalised spread reverts by selection — and the family is
re-scoped as that, not passed. Same universe, costs, cash benchmark and
engine as the family. One variant.

    qr gates --family perp_pairs --hypothesis p2_perp_pairs_v1_random \
      --market futures/um --costs perp --n 300 --min-history 120 \
      --benchmark cash --risk-free fred --start 2020-01-01 --end 2025-08-31 \
      --param lookback=90 --param entry=2.0 --param exit_z=0.5 --param max_hold=10 --param n_max=10 --param pairs=random \
      --engine ledger --all-gates --upto 8
