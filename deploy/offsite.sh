#!/bin/sh
# Runs inside the "offsite" container (rclone image): once a day copies the
# database dumps and the photo store to Backblaze B2, off this server.
#
# Remotes come from environment variables (see compose.vds.yaml):
#   b2:    Backblaze B2, credentials B2_ACCOUNT_ID / B2_APPLICATION_KEY
#   photos: the local SeaweedFS S3 store
#
# Retention matches the privacy policy: deleted data leaves backups within
# BACKUP_KEEP_DAYS (default 14). Photos are mirrored (a photo deleted in Luma
# is deleted here too, hard delete, no hidden versions); dumps older than
# BACKUP_KEEP_DAYS are removed from B2.
#
# A failed run is reported to Sentry when SENTRY_DSN is set.
set -u
KEEP="${BACKUP_KEEP_DAYS:-14}"
BUCKET="${B2_BUCKET:-luma-event-backups}"
# First run waits for the nightly dump (backup container runs at deploy time + every 24 h).
FIRST_DELAY="${OFFSITE_FIRST_DELAY_SECONDS:-1800}"
STATUS="${OFFSITE_STATUS_FILE:-/backups/offsite-status.txt}"

report_failure() {
  message="Luma Event: sunucu dışı yedek başarısız ($1)"
  echo "$(date -u) $message" >&2
  [ -n "${SENTRY_DSN:-}" ] || return 0
  # DSN: https://<key>@<host>/<project>
  key=$(echo "$SENTRY_DSN" | sed -E 's#^https://([^@]+)@.*#\1#')
  host=$(echo "$SENTRY_DSN" | sed -E 's#^https://[^@]+@([^/]+)/.*#\1#')
  project=$(echo "$SENTRY_DSN" | sed -E 's#.*/([0-9]+)$#\1#')
  wget -q -O /dev/null \
    --header "Content-Type: application/json" \
    --header "X-Sentry-Auth: Sentry sentry_version=7, sentry_key=$key, sentry_client=luma-offsite/1" \
    --post-data "{\"message\":\"$message\",\"level\":\"error\",\"logger\":\"offsite\",\"environment\":\"production\",\"tags\":{\"component\":\"offsite-backup\"}}" \
    "https://$host/api/$project/store/" || echo "$(date -u) Sentry report failed" >&2
}

run_once() {
  failed=""
  rclone copy /backups "b2:$BUCKET/db" --include 'luma-*.dump' --b2-hard-delete --stats-one-line -v \
    || failed="veritabanı yedeği kopyalanamadı"
  rclone delete "b2:$BUCKET/db" --min-age "${KEEP}d" --b2-hard-delete -v \
    || failed="${failed:+$failed; }eski veritabanı yedekleri silinemedi"
  rclone sync photos:luma-private "b2:$BUCKET/photos" --b2-hard-delete --fast-list --stats-one-line -v \
    || failed="${failed:+$failed; }fotoğraflar kopyalanamadı"
  if [ -n "$failed" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FAILED $failed" > "$STATUS"
    report_failure "$failed"
    return 1
  else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ok" > "$STATUS"
    echo "$(date -u) offsite ok"
  fi
}

if [ -z "${RCLONE_CONFIG_B2_ACCOUNT:-}" ] || [ -z "${RCLONE_CONFIG_B2_KEY:-}" ]; then
  echo "$(date -u) B2_ACCOUNT_ID / B2_APPLICATION_KEY not set in .env.vds; offsite backup is idle." >&2
  [ "${1:-}" = "once" ] && exit 1
  exec sleep 2147483647
fi

if [ "${1:-}" = "once" ]; then
  run_once
  exit $?
fi

sleep "$FIRST_DELAY"
while true; do
  run_once
  sleep 86400
done
