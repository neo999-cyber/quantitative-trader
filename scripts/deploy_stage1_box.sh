#!/bin/zsh
# Copy the stage-1 runner to the Hetzner box (standard library only: nothing is installed there) and
# install its systemd units — DISABLED. Enabling the timer is the owner's command, printed at the end;
# so are copying the keys and granting the standing mandate. Re-run after any change to the code.
set -euo pipefail
BOX=${1:-root@91.98.172.9}
cd "$(dirname "$0")/.."
ssh $BOX 'mkdir -p ~/stage1/qr/execution ~/stage1/scripts ~/stage1/study ~/stage1/lake/study/logs'
scp -q qr/__init__.py qr/config.py qr/secrets.py $BOX:~/stage1/qr/
scp -q qr/execution/__init__.py qr/execution/journal.py qr/execution/limits.py qr/execution/orders.py qr/execution/venues.py qr/execution/study.py $BOX:~/stage1/qr/execution/
scp -q scripts/study_stage1.py scripts/stage1_summary.py $BOX:~/stage1/scripts/
scp -q study/stage1.live.json $BOX:~/stage1/study/
scp -q deploy/stage1/*.service deploy/stage1/*.timer $BOX:/etc/systemd/system/
ssh $BOX 'systemctl daemon-reload && cd ~/stage1 && QR_ROOT=/root/stage1/lake python3 -c "import sys; sys.path.insert(0, \".\"); import qr.execution.study, qr.execution.venues; print(\"bundle imports with the box python:\", sys.version.split()[0])" && systemctl is-enabled qr-stage1.timer 2>/dev/null || echo "qr-stage1.timer: installed, not enabled"'
echo
echo "The owner's three commands, in order (see docs/20):"
echo "  1. keys:   scp ~/.qr/secrets.env $BOX:~/.qr/secrets.env"
echo "  2. grant:  ssh -t $BOX 'cd ~/stage1 && QR_ROOT=/root/stage1/lake python3 scripts/study_stage1.py grant --config study/stage1.live.json --through YYYY-MM-DD --i-have-the-owners-yes'"
echo "  3. switch: ssh $BOX 'systemctl enable --now qr-stage1.timer qr-stage1-summary.timer'"
