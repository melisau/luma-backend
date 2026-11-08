# Luma'yı VDS'e kurma

Tek sunucu, tek alan adı. Caddy HTTPS'i yönetir, Luma API hem siteyi hem API'yi sunar, PostgreSQL ve fotoğraf depolaması (SeaweedFS) aynı sunucuda çalışır. Her gece veritabanı yedeği alınır.

```
İnternet ──443──> Caddy ──> api (FastAPI, tek süreç) ──> db (PostgreSQL 16)
                    └── /luma-private/* ──> seaweedfs (fotoğraflar, özel kova)
                                            backup (gece pg_dump)
```

## Hazırlanması gerekenler

| Ne | Not |
| --- | --- |
| VDS | Ubuntu 24.04, en az 2 vCPU, 4 GB RAM, 40 GB+ disk. Sunucuyu Türkiye'den seçersen KVKK yurt dışı aktarım yükü azalır. |
| Alan adı | Örnek: `luma.com.tr` |
| SMTP hesabı | Uygulama üretimde SMTP olmadan başlamaz. Host, port, kullanıcı ve parola gerekli. |
| SSH erişimi | Sunucuya `ssh root@SUNUCU_IP` ile bağlanabiliyor olmalısın. |

## 1. DNS

Alan adı panelinde iki kayıt ekle (birkaç dakika ile birkaç saat arasında yayılır):

| Tür | Ad | Değer |
| --- | --- | --- |
| A | `@` | sunucunun IP adresi |
| A | `www` | sunucunun IP adresi |

E-posta için SMTP sağlayıcısının verdiği SPF, DKIM ve DMARC kayıtlarını da ekle; yoksa e-postalar spam'e düşer.

## 2. Sunucuyu hazırla

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```

## 3. Kodu indir

İki depo yan yana olmalı (`docker-compose.yml` frontend'i `../../luma-frontend` yolundan okur):

```bash
mkdir -p /opt/luma && cd /opt/luma
git clone https://github.com/melisau/luma-backend.git
git clone https://github.com/melisau/luma-frontend.git
```

## 4. Ayarları doldur

```bash
cd /opt/luma/luma-backend/deploy
cp .env.example .env
nano .env
```

Doldurulacaklar: `DOMAIN`, `ACME_EMAIL`, `ADMIN_EMAIL`, SMTP alanları ve şu üç rastgele değer (her biri için ayrı ayrı `openssl rand -hex 32` çalıştır):

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `STORAGE_SECRET_ACCESS_KEY`

`.env` dosyası parolaları içerir; kimseyle paylaşma, git'e ekleme (zaten yok sayılıyor).

## 5. Başlat

```bash
docker compose up -d --build
docker compose ps
curl https://ALAN_ADIN/health
```

`/health` yanıtında `"database":"ok"` ve `"storage":"configured"` görmelisin. İlk açılışta Caddy sertifikayı birkaç saniyede alır. Hata varsa:

```bash
docker compose logs api --tail 50
docker compose logs caddy --tail 50
```

## 6. İlk yönetici hesabı

```bash
docker compose exec api python -m app.bootstrap_admin
```

E-posta adresini sorar ve tek seferlik bir parola yazdırır; parolayı hemen bir parola kasasına kaydet. Bu hesap doğrulanmış sayılır. Siteden kayıt olan diğer hesaplar e-postadaki bağlantıyla doğrulanır; doğrulanmamış hesapların davetiyesi misafirlere açılmaz.

## Güncelleme

```bash
cd /opt/luma/luma-backend && git pull
cd /opt/luma/luma-frontend && git pull
cd /opt/luma/luma-backend/deploy && docker compose up -d --build
```

Veritabanı migration'ları uygulama açılırken otomatik çalışır.

## Yedekler

- `backup` servisi her gün `deploy/backups/` klasörüne bir `luma-TARİH.dump` yazar ve 14 günden eskileri siler (`BACKUP_KEEP_DAYS`).
- Bu yedekler aynı diskte durur; disk bozulursa onlar da gider. Haftada bir başka yere kopyala, örneğin kendi bilgisayarına:

```bash
scp -r root@SUNUCU_IP:/opt/luma/luma-backend/deploy/backups ./luma-yedek
```

- Fotoğraflar `storagedata` Docker volume'ünde. Sağlayıcının sunucu yedeği (snapshot) özelliğini açmak en kolay korumadır.

Geri yükleme provası (boş veritabanına, canlıya değil):

```bash
docker compose exec -T db createdb -U luma luma_restore_test
docker compose exec -T db pg_restore -U luma -d luma_restore_test < backups/DOSYA.dump
docker compose exec -T db psql -U luma -d luma_restore_test -c "select count(*) from events;"
docker compose exec -T db dropdb -U luma luma_restore_test
```

## Fotoğrafları Cloudflare R2'de tutmak (isteğe bağlı)

`.env` içinde `COMPOSE_PROFILES=` satırını boşalt, R2 satırlarını aç ve doldur, sonra `docker compose up -d`. R2 yurt dışında olduğu için KVKK yurt dışı aktarım bildirimi gerekir.

## Ortak VDS'te (141.11.109.174) Luma Event

Bu sunucuda 80/443'ü ortak Caddy (`berkdev-proxy-caddy-1`) tutar, bu yüzden yukarıdaki `docker-compose.yml` değil `compose.vds.yaml` kullanılır: kendi Caddy'si yok, port yayınlamaz, `berkdev-proxy` ağına bağlanır. Konteyner adları `lumaevent-*`.

- Klasör: `/opt/lumaevent` (içinde `luma-backend`, `luma-frontend`, `.env.vds`, `backups/`)
- Sırlar: `/opt/lumaevent/.env.vds` (chmod 600): `DOMAIN`, `ENVIRONMENT`, `SECRET_KEY`, `POSTGRES_PASSWORD`, `STORAGE_SECRET_ACCESS_KEY`, SMTP alanları
- Güncelleme: `/opt/lumaevent/luma-backend/deploy/vds-deploy.sh [dal]`
- Ortak Caddyfile'daki blok `luma.melisauyar.com` için `/luma-private/*` isteklerini `lumaevent-storage:8333`'e, gerisini `lumaevent-api:8000`'e yollar. Caddyfile'ı değiştirmeden önce `/opt/CLAUDE.md` kurallarına uy.
- SMTP gelene kadar `ENVIRONMENT=development` ile açılabilir: e-posta gönderilmez (loglara yazılır), doğrulama zorunlu değildir. Gerçek kullanıcı almadan önce SMTP'yi ekleyip `ENVIRONMENT=production` yap.
