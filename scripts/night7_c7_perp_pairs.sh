#!/bin/zsh
# Night of 18-19 September 2026: C7 perp pairs (docs/prereg/p2_perp_pairs_v1.md), the tenth candidate.
# Owner's yes: 18 September 2026 ("do this"). Control first, then the 8-variant family, on the ledger.
export QR_ROOT=$HOME/qr/lake
cd $HOME/quantitative-trader
QR=.venv/bin/qr; LOG=$QR_ROOT/logs; STATUS=$LOG/overnight_status.txt
stage() { echo "$(date -u +%FT%TZ) [night7] $1" >> $STATUS; }
stage "start (C7 on --engine ledger)"
COMMON=(--market futures/um --costs perp --n 300 --min-history 120
        --benchmark cash --risk-free fred --start 2020-01-01 --end 2025-08-31 --engine ledger --all-gates --upto 8)
$QR gates --family perp_pairs --hypothesis p2_perp_pairs_v1_random "${COMMON[@]}" \
  --param lookback=90 --param entry=2.0 --param exit_z=0.5 --param max_hold=10 --param n_max=10 --param pairs=random > $LOG/night7_c7_random.log 2>&1
stage "c7 random control exit=$?"
$QR gates --family perp_pairs --hypothesis p2_perp_pairs_v1 "${COMMON[@]}" \
  --grid 'lookback=[60,120]' --grid 'entry=[2.0,2.5]' --grid 'max_hold=[5,10]' --param exit_z=0.5 --param n_max=10 > $LOG/night7_c7_family.log 2>&1
stage "c7 family exit=$?"
$QR trial verify > $LOG/night7_verify.log 2>&1
stage "verify $(head -1 $LOG/night7_verify.log)"
stage "done"
