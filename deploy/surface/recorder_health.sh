#!/bin/sh
# Recorder and collector health on the Hetzner box, every 30 minutes from cron (14 October 2026; collectors added
# 15 October). A line goes to /root/pm/health.log every run, and a push through ntfy when something is wrong — a
# recorder unit down, the Polymarket writer behind its socket, more than 8 reconnects in the last hour, a surface
# snapshot failed in the last two hours, less than 5 GB free, or a feed gone quiet: the Polymarket catalogue not
# refreshed for 2 hours, no surface file for the last two hours, the yield snapshot or the ETF workbooks missing after
# 07:00 UTC, the equities share-count file untouched for 3 days. Standard tools only; QR_NTFY_TOPIC from
# /root/stage1/env.
#
# One push per failure (10 November 2026, on the owner's word, after four pushes for one Deribit 503 hour): a
# condition is pushed when it first appears and is quiet while it lasts; a condition still wrong a day after the last
# push is pushed again, once a day, so an outage cannot go silent; and one low-priority push says when a check finds
# nothing wrong again (for the two after-07:00 checks that can also mean "not checked before 07:00"). A push that
# fails to send is retried on the next run. The state is /root/pm/health.state: line 1 the epoch of the last push,
# then the names of the conditions wrong at the last run. The log line is unchanged and written on every run — the
# desk sheet reads its last line.
#
# For the test and the dry run only: QR_HEALTH_BAD replaces the computed list of conditions, QR_HEALTH_STATE,
# QR_HEALTH_LOG and QR_HEALTH_ENV move the three files, QR_HEALTH_NOW sets the clock (epoch seconds), and
# QR_HEALTH_DRYRUN prints the push instead of sending it.
ENV=${QR_HEALTH_ENV:-/root/stage1/env}
STATE=${QR_HEALTH_STATE:-/root/pm/health.state}
LOG=${QR_HEALTH_LOG:-/root/pm/health.log}
[ -r "$ENV" ] && . "$ENV"
bad=""
now=${QR_HEALTH_NOW:-$(date -u +%s)}
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
[ -n "${QR_HEALTH_BAD+x}" ] && bad="$QR_HEALTH_BAD"
line="$(date -u +%Y-%m-%dT%H:%MZ) recorders: reconnects/h $rc, behind $behind, surface fails/2h $sf, disk ${avail_gb} GB, pm today ${mb_today:-0} MB${bad:+ — WRONG:$bad}"
echo "$line" >> "$LOG"

# ---- one push per failure ----
set -f
names=$(for b in $bad; do echo "${b%%:*}"; done | sort -u)      # the conditions wrong now, without their counts
set +f
last=0; prev=""
if [ -s "$STATE" ]; then last=$(head -1 "$STATE"); prev=$(tail -n +2 "$STATE"); fi
case "$last" in ''|*[!0-9]*) last=0 ;; esac
new=""; old=""
for n in $names; do
  if echo "$prev" | grep -qxF -- "$n"; then old="$old $n"; else new="$new $n"; fi
done
push() {  # title, priority, body; succeeds only if the push was accepted
  if [ -n "$QR_HEALTH_DRYRUN" ]; then echo "PUSH [$2] $1: $3"; return 0; fi
  [ -n "$QR_NTFY_TOPIC" ] || return 1
  curl -s -f -m 20 -H "Title: $1" -H "Priority: $2" -d "$3" "https://ntfy.sh/$QR_NTFY_TOPIC" >/dev/null
}
if [ -z "$names" ]; then                                        # nothing wrong: say so once, then forget
  if [ -z "$prev" ] || push "recorder OK" low "$line — nothing wrong at this check (was: $(echo $prev))"; then
    rm -f "$STATE"
  fi
  exit 0
fi
keep="$names"
if [ -n "$new" ]; then                                          # something not yet pushed
  if push "recorder ALERT" urgent "$line"; then last=$now; else keep="$old"; fi
elif [ $(( now - last )) -ge 86400 ]; then                      # nothing new, still wrong a day after the last push
  push "recorder still WRONG" high "$line" && last=$now
fi
if [ -n "$keep" ]; then
  { echo "$last"; for n in $keep; do echo "$n"; done; } > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
else
  rm -f "$STATE"
fi
