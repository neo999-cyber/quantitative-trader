#!/bin/zsh
# Overnight chain, 15-16 September 2026. Sequential, unattended, $0, no orders,
# no autopilot. Every stage logs to $QR_ROOT/logs/overnight_<stage>.log and
# appends one line to $QR_ROOT/logs/overnight_status.txt.
export QR_ROOT=$HOME/qr/lake
cd $HOME/quantitative-trader
QR=.venv/bin/qr
PY=.venv/bin/python
LOG=$QR_ROOT/logs
STATUS=$LOG/overnight_status.txt
stage() { echo "$(date -u +%FT%TZ) $1" >> $STATUS; }

stage "start"
# 1. wait for the C1 in-sample run
while pgrep -f "qr gates --family funding_carry --hypothesis p2_funding_carry_v1 " >/dev/null; do sleep 60; done
stage "c1 in-sample finished"

# 2. always-in control on the committed engine
$QR gates --family funding_carry --hypothesis p2_funding_carry_v1_always_in \
  --market carry-um --costs carry --n 40 --min-history 180 \
  --benchmark cash --risk-free fred --end 2025-09-14 \
  --param entry=-1.0 --param exit=-2.0 --param ceiling=1.0 --param n_max=40 --param lookback=7 \
  --all-gates --upto 8 > $LOG/overnight_control.log 2>&1
stage "control rerun exit=$?"

# 3. hourly perp bars, all USDT perps, then ingest
$QR data pull --market futures/um --interval 1h --workers 8 > $LOG/overnight_pull_um_1h.log 2>&1
stage "perp 1h pull exit=$?"
$QR data ingest --market futures/um --interval 1h > $LOG/overnight_ingest_um_1h.log 2>&1
stage "perp 1h ingest exit=$?"

# 4. hourly spot bars for the 471 both-leg symbols, then ingest
comm -12 <(ls $QR_ROOT/mirror/binance/data/spot/monthly/klines | sort) \
        <(ls $QR_ROOT/mirror/binance/data/futures/um/monthly/klines | sort) > $LOG/both_syms.txt
$QR data pull --market spot --interval 1h --workers 8 --symbols $(cat $LOG/both_syms.txt) > $LOG/overnight_pull_spot_1h.log 2>&1
stage "spot 1h pull exit=$?"
$QR data ingest --market spot --interval 1h --symbols $(cat $LOG/both_syms.txt) > $LOG/overnight_ingest_spot_1h.log 2>&1
stage "spot 1h ingest exit=$?"

# 5. Form 4, every quarter, with acceptance times
$PY scripts/form4_mirror.py --from 2006q1 --to 2026q2 > $LOG/overnight_form4.log 2>&1
stage "form4 mirror exit=$?"

# 6. open-interest metrics for the 471 both-leg symbols, then ingest
$QR data funding-pull --metrics --symbols $(cat $LOG/both_syms.txt) > $LOG/overnight_metrics_pull.log 2>&1
stage "metrics pull exit=$?"
$QR data funding-ingest --metrics --symbols $(cat $LOG/both_syms.txt) > $LOG/overnight_metrics_ingest.log 2>&1
stage "metrics ingest exit=$?"

# 7. checks
$PY -m pytest -q > $LOG/overnight_pytest.log 2>&1
stage "pytest exit=$? $(tail -1 $LOG/overnight_pytest.log)"
$QR trial verify > $LOG/overnight_verify.log 2>&1
stage "verify exit=$? $(head -1 $LOG/overnight_verify.log)"
$QR doctor > $LOG/overnight_doctor.log 2>&1
stage "done"
