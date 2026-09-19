#!/bin/zsh
# Night of 17-18 September 2026: C6 unlock fade (docs/prereg/p2_unlock_fade_v1.md, registered seq 679-681).
# Waits for night5 (the ledger re-run chain) to finish, then runs the two controls and the family
# on the ledger engine. Owner's yes: 17 September 2026, evening Dubai ("yes register c6 and after night").
export QR_ROOT=$HOME/qr/lake
cd $HOME/quantitative-trader
QR=.venv/bin/qr; LOG=$QR_ROOT/logs; STATUS=$LOG/overnight_status.txt
stage() { echo "$(date -u +%FT%TZ) [night6] $1" >> $STATUS; }
if [[ "$1" == "--now" ]]; then
  stage "started in parallel with night5's last run (C1 v2 hourly gate 6, 3-5x slower on the ledger; owner asked for parallel runs)"
else
  stage "queued behind night5"
  until grep -qF "[night5] done" $STATUS; do sleep 120; done
fi
stage "start (C6 on --engine ledger; calendar frozen 17 Sep, manifest in the log)"
COMMON=(--market futures/um --costs perp --n 300 --min-history 60
        --benchmark cash --risk-free fred --start 2022-01-01 --end 2025-08-31 --engine ledger --all-gates --upto 8)
$QR gates --family unlock_fade --hypothesis p2_unlock_fade_v1_long "${COMMON[@]}" \
  --param lead=30 --param post=14 --param min_pct=0.01 --param n_max=10 --param side=long > $LOG/night6_c6_long.log 2>&1
stage "c6 long mirror exit=$?"
$QR gates --family unlock_fade --hypothesis p2_unlock_fade_v1_eco "${COMMON[@]}" \
  --param lead=30 --param post=14 --param min_pct=0.01 --param n_max=10 --param category=eco > $LOG/night6_c6_eco.log 2>&1
stage "c6 eco control exit=$?"
$QR gates --family unlock_fade --hypothesis p2_unlock_fade_v1 "${COMMON[@]}" \
  --grid 'lead=[20,30]' --grid 'post=[7,14]' --grid 'min_pct=[0.01,0.02]' --param n_max=10 > $LOG/night6_c6_family.log 2>&1
stage "c6 family exit=$?"
$QR trial verify > $LOG/night6_verify.log 2>&1
stage "verify $(head -1 $LOG/night6_verify.log)"
stage "done"
