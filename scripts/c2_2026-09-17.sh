#!/bin/zsh
# C2 cross-venue funding spread: control then family, as pre-registered (seq recorded in the status file).
export QR_ROOT=$HOME/qr/lake
cd $HOME/quantitative-trader
QR=.venv/bin/qr; LOG=$QR_ROOT/logs; STATUS=$LOG/overnight_status.txt
stage() { echo "$(date -u +%FT%TZ) [c2] $1" >> $STATUS; }
stage "start"
$QR gates --family funding_carry --hypothesis p2_venue_spread_v1_always_in \
  --market xvenue-um --costs xvenue --n 80 --lookback 30 --min-history 90 --vol-lookback 90 \
  --benchmark cash --risk-free fred --start 2021-01-01 --end 2025-08-31 \
  --param lookback=7 --param entry=-1.0 --param exit=-2.0 --param ceiling=1.0 --param n_max=80 --param rebalance=1 \
  --all-gates --upto 8 > $LOG/c2_control.log 2>&1
stage "control exit=$?"
$QR gates --family funding_carry --hypothesis p2_venue_spread_v1 \
  --market xvenue-um --costs xvenue --n 80 --lookback 30 --min-history 90 --vol-lookback 90 \
  --benchmark cash --risk-free fred --start 2021-01-01 --end 2025-08-31 \
  --grid 'lookback=[3,7,14]' --grid 'entry=[0.05,0.10,0.20]' --grid 'n_max=[5,10]' \
  --param ceiling=1.0 --param rebalance=1 --all-gates --upto 8 > $LOG/c2_family.log 2>&1
stage "family exit=$?"
$QR trial verify > $LOG/c2_verify.log 2>&1; stage "verify $(head -1 $LOG/c2_verify.log)"; stage "done"
