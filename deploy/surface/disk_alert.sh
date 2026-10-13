#!/bin/sh
# Daily disk check for the Hetzner box (cron, 06:00 UTC): a push through ntfy when less than 5 GB is free.
# The recorders write ~200 MB a day; from 13 October 2026 the daily Polymarket ladders are recorded too.
# Standard tools only. QR_NTFY_TOPIC comes from /root/stage1/env (the owner's topic, never printed).
. /root/stage1/env 2>/dev/null
avail_kb=$(df --output=avail -k / | tail -1 | tr -d ' ')
avail_gb=$((avail_kb / 1024 / 1024))
line="box disk: ${avail_gb} GB free on / ($(date -u +%Y-%m-%d)); pm $(du -sh /root/pm/data 2>/dev/null | cut -f1), surface $(du -sh /root/surface/data 2>/dev/null | cut -f1)"
echo "$line" >> /root/pm/disk.log
if [ "$avail_gb" -lt 5 ] && [ -n "$QR_NTFY_TOPIC" ]; then
  curl -s -m 20 -H "Title: box disk ALERT" -H "Priority: urgent" -d "$line" "https://ntfy.sh/$QR_NTFY_TOPIC" >/dev/null
fi
