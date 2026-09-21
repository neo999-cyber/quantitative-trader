#!/bin/zsh
# Night of 16-17 September 2026, laptop side: data for E7, C2 (and C5's OI pull continues from night 1).
export QR_ROOT=$HOME/qr/lake
cd $HOME/quantitative-trader
PY=.venv/bin/python; LOG=$QR_ROOT/logs; STATUS=$LOG/overnight_status.txt
stage() { echo "$(date -u +%FT%TZ) [night3] $1" >> $STATUS; }
# wait for the short-data pull started earlier to finish
while pgrep -f short_data_pull >/dev/null; do sleep 60; done
stage "short data (ftd + regsho) done: $(ls $QR_ROOT/mirror/sec/ftd/*.zip | wc -l) ftd, $(ls $QR_ROOT/mirror/finra/regsho | wc -l) regsho"
$PY - > $LOG/night3_finra_si.log 2>&1 <<'PYEOF'
from pathlib import Path
from qr.config import paths
from qr.data.short_data import pull_finra_si, si_settlement_days
out = pull_finra_si(Path(paths().root) / "mirror" / "finra" / "shortinterest", si_settlement_days("2019-01-01"))
print(out.to_string()[:3000]); print("fetched", len(out), "errors", int(out["note"].notna().sum()) if "note" in out else 0)
PYEOF
stage "finra short interest exit=$? $(ls $QR_ROOT/mirror/finra/shortinterest/*.csv 2>/dev/null | wc -l) files"
$PY - > $LOG/night3_bybit.log 2>&1 <<'PYEOF'
from pathlib import Path
from qr.config import paths
from qr.data.bybit import pull_all
out = pull_all(Path(paths().root) / "mirror" / "bybit" / "funding")
print(out.to_string()[:3000]); print("symbols", len(out), "errors", int(out["note"].notna().sum()) if "note" in out else 0)
PYEOF
stage "bybit funding exit=$? $(ls $QR_ROOT/mirror/bybit/funding/*.parquet 2>/dev/null | wc -l) symbols"
$PY -m pytest -q > $LOG/night3_pytest.log 2>&1
stage "pytest exit=$? $(tail -1 $LOG/night3_pytest.log)"
stage "done"
