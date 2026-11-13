#!/bin/sh
# Enter the SMTP details for Luma Event on the server and switch it to production.
# The password is typed here (hidden) and only written to /opt/lumaevent/.env.vds.
# If the app does not come back healthy, the previous settings are restored.
#
# Usage (on the server): sh /opt/lumaevent/luma-backend/deploy/set-smtp.sh
set -eu
ROOT=/opt/lumaevent
ENV_FILE="$ROOT/.env.vds"
COMPOSE="docker compose -f $ROOT/luma-backend/deploy/compose.vds.yaml --env-file $ENV_FILE"

[ -f "$ENV_FILE" ] || { echo "Bulunamadı: $ENV_FILE" >&2; exit 1; }

printf "SMTP sunucusu [smtp-relay.brevo.com]: "; read -r host; host="${host:-smtp-relay.brevo.com}"
printf "Port [587]: "; read -r port; port="${port:-587}"
printf "SMTP kullanıcı adı (Brevo'da 'Login'): "; read -r user
printf "SMTP parolası / anahtarı (ekranda görünmez): "; stty -echo; read -r pass; stty echo; echo
printf "Gönderen adres [Luma Event <noreply@melisauyar.com>]: "; read -r from
from="${from:-Luma Event <noreply@melisauyar.com>}"

for value in "$host" "$port" "$user" "$pass" "$from"; do
  case "$value" in *"'"*) echo "Değerlerde tek tırnak (') olamaz." >&2; exit 1;; esac
done
[ -n "$user" ] && [ -n "$pass" ] || { echo "Kullanıcı adı ve parola gerekli." >&2; exit 1; }

backup="$ENV_FILE.bak-$(date +%Y%m%d-%H%M%S)"
cp -p "$ENV_FILE" "$backup"

tmp="$(mktemp)"; chmod 600 "$tmp"
grep -vE '^(ENVIRONMENT|EMAIL_BACKEND|EMAIL_FROM|SMTP_HOST|SMTP_PORT|SMTP_USERNAME|SMTP_PASSWORD|SMTP_USE_TLS)=' "$ENV_FILE" \
  | grep -v '^# SMTP gelene kadar' > "$tmp" || true
cat >> "$tmp" <<EOF
ENVIRONMENT=production
EMAIL_BACKEND=smtp
EMAIL_FROM='$from'
SMTP_HOST='$host'
SMTP_PORT=$port
SMTP_USERNAME='$user'
SMTP_PASSWORD='$pass'
SMTP_USE_TLS=true
EOF
mv "$tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"

echo "Uygulama yeniden başlatılıyor..."
$COMPOSE up -d api >/dev/null 2>&1

i=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' lumaevent-api 2>/dev/null)" = healthy ]; do
  i=$((i + 1))
  if [ $i -gt 30 ]; then
    echo "Uygulama açılmadı, eski ayarlara dönülüyor. Son loglar:" >&2
    docker logs lumaevent-api --tail 15 2>&1 | grep -viE 'password|secret' >&2 || true
    cp -p "$backup" "$ENV_FILE"
    $COMPOSE up -d api >/dev/null 2>&1
    exit 1
  fi
  sleep 2
done
echo "Tamam: Luma Event üretim modunda ve e-posta ayarlı. Eski ayarların yedeği: $backup"
