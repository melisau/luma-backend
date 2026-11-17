#!/bin/sh
# Enter the Backblaze B2 key for Luma Event's off-server backup.
# The key is typed here (hidden) and only written to /opt/lumaevent/.env.vds.
# Then the first backup runs at once and its result is shown.
#
# Usage (on the server): sh /opt/lumaevent/luma-backend/deploy/set-b2.sh
set -eu
ROOT=/opt/lumaevent
ENV_FILE="$ROOT/.env.vds"
COMPOSE="docker compose -f $ROOT/luma-backend/deploy/compose.vds.yaml --env-file $ENV_FILE"

[ -f "$ENV_FILE" ] || { echo "Bulunamadı: $ENV_FILE" >&2; exit 1; }

printf "B2 kova (bucket) adı [luma-event-backups]: "; read -r bucket; bucket="${bucket:-luma-event-backups}"
printf "B2 keyID: "; read -r key_id
printf "B2 applicationKey (ekranda görünmez): "; stty -echo; read -r app_key; stty echo; echo

for value in "$bucket" "$key_id" "$app_key"; do
  case "$value" in *"'"*|*" "*) echo "Değerlerde boşluk veya tek tırnak (') olamaz." >&2; exit 1;; esac
done
[ -n "$key_id" ] && [ -n "$app_key" ] || { echo "keyID ve applicationKey gerekli." >&2; exit 1; }

backup="$ENV_FILE.bak-$(date +%Y%m%d-%H%M%S)"
cp -p "$ENV_FILE" "$backup"

tmp="$(mktemp)"; chmod 600 "$tmp"
grep -vE '^(B2_BUCKET|B2_ACCOUNT_ID|B2_APPLICATION_KEY)=' "$ENV_FILE" > "$tmp" || true
cat >> "$tmp" <<EOF
B2_BUCKET=$bucket
B2_ACCOUNT_ID=$key_id
B2_APPLICATION_KEY=$app_key
EOF
mv "$tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"

echo "Yedek kapsayıcısı yeniden başlatılıyor..."
$COMPOSE up -d --force-recreate --no-deps offsite >/dev/null 2>&1
sleep 3

echo "İlk yedek çalışıyor..."
if docker exec lumaevent-offsite sh /offsite.sh once; then
  echo "Tamam: yedekler Backblaze B2'ye kopyalandı. Eski ayarların yedeği: $backup"
else
  echo "Yedek başarısız. keyID, applicationKey ve kova adını kontrol edin; betiği yeniden çalıştırabilirsiniz." >&2
  exit 1
fi
