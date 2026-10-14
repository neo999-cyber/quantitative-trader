#!/bin/sh
# Recorder health on the Hetzner box, every 30 minutes from cron (14 October 2026). Alert-only: a line goes to
# /root/pm/health.log every run, and a push through ntfy only when something is wrong — a recorder unit down,
# the Polymarket writer behind its socket, more than 8 reconnects in the last hour, a surface snapshot failed
# in the last two hours, or less than 5 GB free. Standard tools only; QR_NTFY_TOPIC from /root/stage1/env.
. /root/stage1/env 2>/dev/null
bad=""
for u in qr-pm-polymarket qr-pm-deribit qr-surface.timer qr-yield.timer; do
  st=$(systemctl is-active "$u" 2>/dev/null)
  [ "$st" = "active" ] || bad="$bad $u:$st"
done
rc=$(journalctl -u qr-pm-polymarket --since "1 hour ago" --no-pager 2>/dev/null | grep -c "reconnect after error")
behind=$(journalctl -u qr-pm-polymarket --since "1 hour ago" --no-pager 2>/dev/null | grep -c "behind")
sf=$(journalctl -u qr-surface.service --since "2 hours ago" --no-pager 2>/dev/null | grep -c "FAILED")
avail_gb=$(( $(df --output=avail -k / | tail -1 | tr -d ' ') / 1024 / 1024 ))
today=$(date -u +%Y-%m-%d)
mb_today=$(du -sm /root/pm/data/polymarket/$today 2>/dev/null | cut -f1)
[ "$rc" -gt 8 ] && bad="$bad reconnects/h:$rc"
[ "$behind" -gt 0 ] && bad="$bad writer-behind:$behind"
[ "$sf" -gt 0 ] && bad="$bad surface-failed:$sf"
[ "$avail_gb" -lt 5 ] && bad="$bad disk:${avail_gb}GB"
line="$(date -u +%Y-%m-%dT%H:%MZ) recorders: reconnects/h $rc, behind $behind, surface fails/2h $sf, disk ${avail_gb} GB, pm today ${mb_today:-0} MB${bad:+ — WRONG:$bad}"
echo "$line" >> /root/pm/health.log
if [ -n "$bad" ] && [ -n "$QR_NTFY_TOPIC" ]; then
  curl -s -m 20 -H "Title: recorder ALERT" -H "Priority: urgent" -d "$line" "https://ntfy.sh/$QR_NTFY_TOPIC" >/dev/null
fi
