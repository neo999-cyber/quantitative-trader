#!/bin/sh
# Recorder and collector health on the Hetzner box, every 30 minutes from cron (14 October 2026; collectors added
# 15 October). Alert-only: a line goes to /root/pm/health.log every run, and a push through ntfy only when something
# is wrong — a recorder unit down, the Polymarket writer behind its socket, more than 8 reconnects in the last hour,
# a surface snapshot failed in the last two hours, less than 5 GB free, or a feed gone quiet: the Polymarket
# catalogue not refreshed for 2 hours, no surface file for the last two hours, the yield snapshot or the ETF
# workbooks missing after 07:00 UTC, the equities share-count file untouched for 3 days. Standard tools only;
# QR_NTFY_TOPIC from /root/stage1/env.
. /root/stage1/env 2>/dev/null
bad=""
now=$(date -u +%s)
today=$(date -u +%Y-%m-%d)
hour=$(date -u +%H)
age() { f="$1"; [ -e "$f" ] && echo $(( now - $(stat -c %Y "$f") )) || echo 999999; }
for u in qr-pm-polymarket qr-pm-deribit qr-surface.timer qr-yield.timer; do
  st=$(systemctl is-active "$u" 2>/dev/null)
  [ "$st" = "active" ] || bad="$bad $u:$st"
done
rc=$(journalctl -u qr-pm-polymarket --since "1 hour ago" --no-pager 2>/dev/null | grep -c "reconnect after error")
behind=$(journalctl -u qr-pm-polymarket --since "1 hour ago" --no-pager 2>/dev/null | grep -c "behind")
sf=$(journalctl -u qr-surface.service --since "2 hours ago" --no-pager 2>/dev/null | grep -c "FAILED")
avail_gb=$(( $(df --output=avail -k / | tail -1 | tr -d ' ') / 1024 / 1024 ))
mb_today=$(du -sm /root/pm/data/polymarket/$today 2>/dev/null | cut -f1)
[ "$rc" -gt 8 ] && bad="$bad reconnects/h:$rc"
[ "$behind" -gt 0 ] && bad="$bad writer-behind:$behind"
[ "$sf" -gt 0 ] && bad="$bad surface-failed:$sf"
[ "$avail_gb" -lt 5 ] && bad="$bad disk:${avail_gb}GB"
# feeds gone quiet
[ "$(age /root/pm/data/polymarket/catalogue.json)" -gt 7200 ] && bad="$bad catalogue-stale"
latest_surface=$(ls -t /root/surface/data/deribit/*/*.json.gz 2>/dev/null | head -1)
[ "$(age "$latest_surface")" -gt 7200 ] && bad="$bad surface-stale"
if [ "$hour" -ge 7 ]; then
  [ -s "/root/yield/data/yields/$today.jsonl" ] || bad="$bad yield-missing"
  [ -s "/root/flows/ishares/IBIT_$today.xls" ] || bad="$bad etf-workbook-missing"
fi
[ "$(age /root/flows/etf_shares_outstanding.jsonl)" -gt 259200 ] && bad="$bad equities-flows-quiet"
line="$(date -u +%Y-%m-%dT%H:%MZ) recorders: reconnects/h $rc, behind $behind, surface fails/2h $sf, disk ${avail_gb} GB, pm today ${mb_today:-0} MB${bad:+ — WRONG:$bad}"
echo "$line" >> /root/pm/health.log
if [ -n "$bad" ] && [ -n "$QR_NTFY_TOPIC" ]; then
  curl -s -m 20 -H "Title: recorder ALERT" -H "Priority: urgent" -d "$line" "https://ntfy.sh/$QR_NTFY_TOPIC" >/dev/null
fi
