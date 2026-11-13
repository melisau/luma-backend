#!/bin/sh
# Runs inside the "backup" container: one pg_dump a day, old dumps pruned.
set -eu
KEEP="${BACKUP_KEEP_DAYS:-14}"

until pg_isready -q; do sleep 2; done

while true; do
  file="/backups/luma-$(date -u +%Y%m%d-%H%M%S).dump"
  if pg_dump --format=custom --file "$file.part"; then
    mv "$file.part" "$file"
    echo "$(date -u) backup ok: $file ($(du -h "$file" | cut -f1))"
  else
    rm -f "$file.part"
    echo "$(date -u) backup FAILED" >&2
  fi
  find /backups -name 'luma-*.dump' -mtime +"$KEEP" -delete
  sleep 86400
done
