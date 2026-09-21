#!/bin/zsh
# Night of 16-17 September 2026: C5 (OI-conditioned reversal) — data, mechanical check, registration, run.
export QR_ROOT=$HOME/qr/lake
cd $HOME/quantitative-trader
QR=.venv/bin/qr; PY=.venv/bin/python; LOG=$QR_ROOT/logs; STATUS=$LOG/overnight_status.txt
stage() { echo "$(date -u +%FT%TZ) [night4d] $1" >> $STATUS; }
stage "start (re-run after the VWAP-bar fix in Panel.tradable; nothing re-registered)"
$QR gates --family oi_reversal --hypothesis p2_oi_reversal_v1_unconditioned \
  --market futures/um --costs perp --n 150 --rank-min 31 --min-history 90 \
  --benchmark cash --risk-free fred --start 2021-12-01 --end 2025-08-31 \
  --param lookback=7 --param oi_lookback=7 --param oi_min=-1 --param n_side=5 \
  --param rebalance_on=W --all-gates --upto 8 > $LOG/night4_c5_control.log 2>&1
stage "c5 control exit=$?"
$QR gates --family oi_reversal --hypothesis p2_oi_reversal_v1 \
  --market futures/um --costs perp --n 150 --rank-min 31 --min-history 90 \
  --benchmark cash --risk-free fred --start 2021-12-01 --end 2025-08-31 \
  --grid 'lookback=[3,7,14]' --grid 'oi_min=[0.05,0.10,0.20]' --grid 'n_side=[5,10]' \
  --param oi_lookback=7 --param rebalance_on=W --all-gates --upto 8 > $LOG/night4_c5_family.log 2>&1
stage "c5 family exit=$?"
$QR trial verify > $LOG/night4_verify.log 2>&1
stage "verify $(head -1 $LOG/night4_verify.log)"
stage "done"
