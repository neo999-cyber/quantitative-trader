#!/bin/zsh
# Night of 16-17 September 2026. Sequential, unattended, $0, no orders.
export QR_ROOT=$HOME/qr/lake
cd $HOME/quantitative-trader
QR=.venv/bin/qr; PY=.venv/bin/python; LOG=$QR_ROOT/logs; STATUS=$LOG/overnight_status.txt
stage() { echo "$(date -u +%FT%TZ) [night2] $1" >> $STATUS; }
stage "start"
# 1. E1 companion book at $100,000 (registered seq 522)
$QR gates --family auction_fade --hypothesis p2_auction_imbalance_v1_100k \
  --market auction-xnas --costs alpaca --basket nasdaq31 --equity 100000 \
  --benchmark exposure --risk-free fred --end 2025-08-31 \
  --grid 'k=[0.10,0.20,0.30,0.50]' --grid 'snapshot=["15:50","15:55"]' \
  --param n_max=20 --param side=sell --all-gates --upto 8 > $LOG/night2_e1_100k.log 2>&1
stage "e1 100k exit=$?"
# 2. Databento bars into the lake (minute and daily), for E2
$PY scripts/databento_bars_ingest.py ohlcv-1d > $LOG/night2_ingest_1d.log 2>&1
stage "xnas 1d ingest exit=$?"
$PY scripts/databento_bars_ingest.py ohlcv-1m > $LOG/night2_ingest_1m.log 2>&1
stage "xnas 1m ingest exit=$?"
# 3. checks
$PY -m pytest -q > $LOG/night2_pytest.log 2>&1
stage "pytest exit=$? $(tail -1 $LOG/night2_pytest.log)"
$QR trial verify > $LOG/night2_verify.log 2>&1
stage "verify $(head -1 $LOG/night2_verify.log)"
stage "done"
