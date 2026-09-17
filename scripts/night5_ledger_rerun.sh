#!/bin/zsh
# Review 22, step 8: the frozen Programme 2 grids re-run on the position/cash ledger.
#
# NOT TO BE STARTED WITHOUT THE OWNER'S YES. Every `qr gates` below is a counted
# trial (docs/26, rules); nothing is re-registered and no grid is changed —
# each command is the pre-registration's invocation with `--engine ledger`
# added. The three QuantConnect families (E4, E5, E7) ran on LEAN and are not
# re-run here. Programme 1's three `hold_between` families (docs/25, Q3) are
# the second block, off by default.
#
# Before: the weight-engine reports are copied to reports/weights_engine/.
# After: each ledger report is moved to reports/ledger_engine/ and the
# original restored, so `<hyp>.json` in reports/ stays the recorded verdict.
# Then: python scripts/ledger_before_after.py reports/weights_engine reports/ledger_engine
export QR_ROOT=$HOME/qr/lake
cd $HOME/quantitative-trader
QR=.venv/bin/qr; PY=.venv/bin/python; LOG=$QR_ROOT/logs; STATUS=$LOG/overnight_status.txt
REPORTS=$QR_ROOT/reports; BEFORE=$REPORTS/weights_engine; AFTER=$REPORTS/ledger_engine
mkdir -p $BEFORE $AFTER
stage() { echo "$(date -u +%FT%TZ) [night5] $1" >> $STATUS; }

# keep the recorded verdicts; run; file the ledger's report beside them
rerun() {
  local hyp=$1; shift
  for f in $REPORTS/$hyp.md $REPORTS/$hyp.json $REPORTS/${hyp}_variant_returns.parquet; do
    [[ -f $f ]] && cp $f $BEFORE/
  done
  $QR gates --hypothesis $hyp --engine ledger "$@" > $LOG/night5_$hyp.log 2>&1
  stage "$hyp exit=$?"
  for f in $REPORTS/$hyp.md $REPORTS/$hyp.json $REPORTS/${hyp}_variant_returns.parquet; do
    [[ -f $f ]] && mv $f $AFTER/
  done
  for f in $BEFORE/$hyp.md $BEFORE/$hyp.json $BEFORE/${hyp}_variant_returns.parquet; do
    [[ -f $f ]] && cp $f $REPORTS/
  done
}

stage "start (ledger re-run of the frozen grids; owner said yes on: ______)"

# C1 funding carry, daily unit and control (docs/prereg/p2_funding_carry_v1.md)
rerun p2_funding_carry_v1 --family funding_carry \
  --market carry-um --costs carry --n 40 --min-history 180 \
  --benchmark cash --risk-free fred --end 2025-09-14 \
  --grid 'lookback=[3,7,14,30]' --grid 'entry=[0.05,0.10,0.15,0.20]' \
  --grid 'ceiling=[0.95,1.0]' --grid 'n_max=[5,10]' --all-gates --upto 8
rerun p2_funding_carry_v1_always_in --family funding_carry \
  --market carry-um --costs carry --n 40 --min-history 180 \
  --benchmark cash --risk-free fred --end 2025-09-14 \
  --param entry=-1.0 --param exit=-2.0 --param ceiling=1.0 --param n_max=40 --param lookback=7 \
  --all-gates --upto 8

# C1 v2, hourly unit (docs/prereg/p2_funding_carry_v2.md) — the long one; last in the crypto block
# C5 OI-conditioned reversal and its control (docs/prereg/p2_oi_reversal_v1.md)
rerun p2_oi_reversal_v1_unconditioned --family oi_reversal \
  --market futures/um --costs perp --n 150 --rank-min 31 --min-history 90 \
  --benchmark cash --risk-free fred --start 2021-12-01 --end 2025-08-31 \
  --param lookback=7 --param oi_lookback=7 --param oi_min=-1 --param n_side=5 \
  --param rebalance_on=W --all-gates --upto 8
rerun p2_oi_reversal_v1 --family oi_reversal \
  --market futures/um --costs perp --n 150 --rank-min 31 --min-history 90 \
  --benchmark cash --risk-free fred --start 2021-12-01 --end 2025-08-31 \
  --grid 'lookback=[3,7,14]' --grid 'oi_min=[0.05,0.10,0.20]' --grid 'n_side=[5,10]' \
  --param oi_lookback=7 --param rebalance_on=W --all-gates --upto 8

# C2 cross-venue spread and its control (docs/prereg/p2_venue_spread_v1.md)
rerun p2_venue_spread_v1_always_in --family funding_carry \
  --market xvenue-um --costs xvenue --n 80 --lookback 30 --min-history 90 --vol-lookback 90 \
  --benchmark cash --risk-free fred --start 2021-01-01 --end 2025-08-31 \
  --param lookback=7 --param entry=-1.0 --param exit=-2.0 --param ceiling=1.0 --param n_max=80 --param rebalance=1 \
  --all-gates --upto 8
rerun p2_venue_spread_v1 --family funding_carry \
  --market xvenue-um --costs xvenue --n 80 --lookback 30 --min-history 90 --vol-lookback 90 \
  --benchmark cash --risk-free fred --start 2021-01-01 --end 2025-08-31 \
  --grid 'lookback=[3,7,14]' --grid 'entry=[0.05,0.10,0.20]' --grid 'n_max=[5,10]' \
  --param ceiling=1.0 --param rebalance=1 --all-gates --upto 8

# E1 auction fade, $1,000 and mirror (docs/prereg/p2_auction_imbalance_v1.md, _mirror.md)
rerun p2_auction_imbalance_v1 --family auction_fade \
  --market auction-xnas --costs alpaca --basket nasdaq31 --equity 1000 \
  --benchmark exposure --risk-free fred --end 2025-08-31 \
  --grid 'k=[0.10,0.20,0.30,0.50]' --grid 'snapshot=["15:50","15:55"]' \
  --grid 'n_max=[4,8]' --param side=sell --all-gates --upto 8
rerun p2_auction_imbalance_v1_mirror --family auction_fade \
  --market auction-xnas --costs alpaca --basket nasdaq31 --equity 1000 \
  --benchmark exposure --risk-free fred --end 2025-08-31 \
  --param k=0.20 --param snapshot=15:55 --param n_max=4 --param side=buy \
  --all-gates --upto 8

# E2 late-day momentum and its reverse (docs/prereg/p2_late_day_momentum_v1.md, _reverse.md)
rerun p2_late_day_momentum_v1 --family late_day_momentum \
  --market intraday-xnas --costs alpaca --basket qqq --equity 1000 \
  --benchmark cash --risk-free fred --end 2025-08-31 \
  --grid 'k=[0,0.0025,0.005,0.01]' --param side=long --all-gates --upto 8
rerun p2_late_day_momentum_v1_reverse --family late_day_momentum \
  --market intraday-xnas --costs alpaca --basket qqq --equity 1000 \
  --benchmark cash --risk-free fred --end 2025-08-31 \
  --param k=0.005 --param side=reverse --all-gates --upto 8

# C1 v2 hourly unit and control (docs/prereg/p2_funding_carry_v2.md): 64 variants on hourly bars
rerun p2_funding_carry_v2 --family funding_carry \
  --market carry-um --interval 1h --costs carry \
  --n 40 --lookback 720 --min-history 4320 --vol-lookback 2160 \
  --benchmark cash --risk-free fred --end 2025-09-14 \
  --grid 'lookback=[72,168,336,720]' --grid 'entry=[0.05,0.10,0.15,0.20]' \
  --grid 'ceiling=[0.95,1.0]' --grid 'n_max=[5,10]' \
  --param rebalance=24 --param percentile_window=365 --all-gates --upto 8

# Programme 1's hold_between families (docs/25 Q3) — off by default; set RERUN_P1=1
if [[ -n "$RERUN_P1" ]]; then
  stage "programme 1 block: commands to be taken from docs/prereg/etf_tsmom_v1.md, etf_buyhold_v1.md, ls_xsmom_v1.md"
fi

$QR trial verify > $LOG/night5_verify.log 2>&1
stage "verify $(head -1 $LOG/night5_verify.log)"
$PY scripts/ledger_before_after.py $BEFORE $AFTER > $LOG/night5_before_after.md 2>&1
stage "table -> $LOG/night5_before_after.md"
stage "done"
