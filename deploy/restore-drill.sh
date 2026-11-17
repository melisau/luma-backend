#!/bin/sh
# Restore drill: takes the newest database dump from Backblaze B2, restores it
# into a throwaway PostgreSQL container and compares row counts with the live
# database. Touches nothing live; the throwaway container and files are removed.
#
# Usage (on the VDS): sh /opt/lumaevent/luma-backend/deploy/restore-drill.sh
set -eu
ROOT=/opt/lumaevent
DRILL=lumaevent-restore-drill
WORK=$(mktemp -d /tmp/luma-restore-drill.XXXXXX)
trap 'docker rm -f "$DRILL" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

# Pull the newest dump from B2 with the offsite container's own credentials,
# over the S3 API (B2's native download hosts are blocked from Turkey).
newest=$(docker exec lumaevent-offsite sh -c 'rclone lsf "b2s3:$B2_BUCKET/db" --include "luma-*.dump" 2>/dev/null' | sort | tail -1)
[ -n "$newest" ] || { echo "No dump found in B2" >&2; exit 1; }
echo "Newest dump in B2: $newest"
docker exec lumaevent-offsite sh -c "rclone cat \"b2s3:\$B2_BUCKET/db/$newest\" 2>/dev/null" > "$WORK/drill.dump"
[ "$(head -c 5 "$WORK/drill.dump")" = "PGDMP" ] || { echo "Downloaded file is not a PostgreSQL dump" >&2; exit 1; }
echo "Downloaded $(wc -c < "$WORK/drill.dump") bytes."
chmod 644 "$WORK/drill.dump"; chmod 755 "$WORK"

# Empty database, no network: nothing can reach it and it reaches nothing.
docker run -d --name "$DRILL" --network none -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=luma \
  -v "$WORK:/drill:ro" postgres:16-alpine >/dev/null
until docker exec "$DRILL" pg_isready -q -U postgres; do sleep 1; done
sleep 2
docker exec "$DRILL" pg_restore -U postgres -d luma --no-owner --no-privileges --exit-on-error /drill/drill.dump
echo "Restored into empty database."

COUNTS="SELECT 'admin_users', count(*) FROM admin_users UNION ALL
SELECT 'events', count(*) FROM events UNION ALL
SELECT 'guests', count(*) FROM guests UNION ALL
SELECT 'guestbook_messages', count(*) FROM guestbook_messages UNION ALL
SELECT 'photos', count(*) FROM photos UNION ALL
SELECT 'alembic', count(*) FROM alembic_version ORDER BY 1;"

restored=$(docker exec "$DRILL" psql -U postgres -d luma -tA -F' ' -c "$COUNTS")
live=$(docker exec lumaevent-db psql -U luma -d luma -tA -F' ' -c "$COUNTS")
echo "table restored live"
echo "$restored" | while read -r table count; do
  echo "$table $count $(echo "$live" | awk -v t="$table" '$1==t{print $2}')"
done
# The dump is up to a day old, so live counts may be higher; the restore must
# have every table and a schema version.
echo "$restored" | grep -q '^alembic 1$' || { echo "DRILL FAILED: no schema version" >&2; exit 1; }
echo "DRILL OK: $newest restores into an empty database."
