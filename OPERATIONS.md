# Luma üretim işletimi

Önerilen kurulum tek bir VDS üzerinde Docker Compose ile çalışır: Caddy (HTTPS), Luma API (siteyi de sunar), PostgreSQL, SeaweedFS (fotoğraflar) ve gece yedeği. Adım adım kurulum `deploy/README.md` dosyasındadır. Eski Koyeb + Neon + Cloudflare planı `KOYEB_DEPLOYMENT.md` dosyasında duruyor. `ENVIRONMENT=production` eksik veya güvensiz yapılandırmada uygulamanın başlamasını durdurur.

Dağıtım öncesi geçiş:

```bash
alembic upgrade head
```

Yedek oluşturma:

```bash
python scripts/backup_postgres.py luma.dump
```

Boş bir deneme veritabanında geri yükleme provası:

```bash
python scripts/restore_postgres.py luma.dump --confirm
alembic current
```

Canlı veritabanına geri yükleme mevcut verileri değiştirebilir. Önce ayrı bir PostgreSQL veritabanında prova yapılmalıdır. `/health` veritabanı ve depolama yapılandırmasını denetler. Uygulama yanıtlarındaki `X-Request-ID` ile istek logları eşleştirilir; `SENTRY_DSN` verilirse sunucu hataları Sentry'ye aktarılır.

E-posta için `EMAIL_BACKEND=smtp` ve SMTP alanları kullanılır. Alan adının SPF, DKIM ve DMARC kayıtları sağlayıcı panelinden doğrulanmalıdır. Geliştirmede `EMAIL_BACKEND=console` gerçek e-posta göndermeden akışları loglar.

## İzleme

- **Hatalar:** Sentry projesi `melisa-uyar-6v/luma-event` (AB bölgesi). DSN sunucuda `/opt/lumaevent/.env.vds` içindeki `SENTRY_DSN`. Yüksek öncelikli yeni hatalar e-postayla bildirilir.
- **Site ayakta mı:** `.github/workflows/uptime.yml` her 5 dakikada `https://luma.melisauyar.com/health` adresini üç kez dener; üçü de başarısızsa iş kırmızı olur ve GitHub depo sahibine e-posta atar. Sentry'nin ücretsiz planındaki tek site kontrolü başka projede kullanıldığı için bu yol seçildi. GitHub, depoda 60 gün hareket olmazsa zamanlanmış işleri durdurur; Actions sekmesinden yeniden açılır.

## Sunucu dışı yedek (Backblaze B2)

- `lumaevent-offsite` kapsayıcısı günde bir kez `/opt/lumaevent/backups` içindeki veritabanı yedeklerini `b2:<B2_BUCKET>/db` altına kopyalar ve fotoğraf deposunu `b2:<B2_BUCKET>/photos` altına eşler.
- Saklama süresi gizlilik metniyle aynıdır (`BACKUP_KEEP_DAYS`, 14 gün): eski yedekler ve Luma'da silinen fotoğraflar B2'den de kalıcı silinir (`--b2-hard-delete`).
- Gereken ayarlar `.env.vds` içinde: `B2_ACCOUNT_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET`. Yoksa kapsayıcı bekler, diğerleri etkilenmez. Girmek için sunucuda: `sh /opt/lumaevent/luma-backend/deploy/set-b2.sh` (anahtar ekranda görünmez, ilk yedeği hemen çalıştırır).
- Son çalışmanın sonucu `/opt/lumaevent/backups/offsite-status.txt` dosyasında; başarısız olursa Sentry'ye hata düşer.
- Elle çalıştırma: `docker exec lumaevent-offsite sh /offsite.sh once`
- Geri yükleme provası (canlıya dokunmaz): `sh /opt/lumaevent/luma-backend/deploy/restore-drill.sh`. B2'deki en son yedeği ağsız, geçici bir PostgreSQL'e yükler, tablo sayılarını canlıyla yan yana yazar, sonra geçici kapsayıcıyı siler.
- **İndirme her zaman `b2s3:` üzerinden** (B2'nin S3 adresi, `B2_S3_ENDPOINT`). B2'nin kendi indirme adresleri (`f00N.backblazeb2.com`) Türkiye'den engelli; `b2:` ile yükleme ve silme çalışır ama indirme sessizce boş döner.
- Gerçek geri yükleme: önce prova, sonra bakım penceresinde `pg_restore --clean` ile; fotoğraflar `docker exec lumaevent-offsite rclone sync b2s3:<B2_BUCKET>/photos photos:luma-private` ile geri gelir.
- Kova şu an ABD Doğu bölgesinde (us-east-005). Backblaze bir ABD şirketi olduğu için bu bir yurt dışı aktarımdır; aydınlatma metninde ve avukat kontrolünde (A9 ile birlikte) belirtilmeli.
