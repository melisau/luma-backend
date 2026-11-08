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
