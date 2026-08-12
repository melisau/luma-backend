# Luma Backend

FastAPI tabanlı davetiye fotoğraf API'si. Frontend ayrı repoda barınır.

## Yapı

```text
backend/
├── app/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Kurulum (yerel)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Monorepo workspace'te frontend'i birlikte servis etmek için `.env` içinde `SERVE_FRONTEND=true` bırakın.

- Sağlık: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

## Veritabanı migration (Alembic)

Uygulama açılışında otomatik `alembic upgrade head` çalışır. Elle çalıştırmak için:

```bash
cd backend
PYTHONPATH=. alembic upgrade head
```

Yeni model/sütun ekledikten sonra:

```bash
PYTHONPATH=. alembic revision -m "açıklama"
# ardından upgrade
PYTHONPATH=. alembic upgrade head
```

## Docker

SQLite (geliştirme):

```bash
cp .env.example .env
docker compose up --build
```

PostgreSQL:

```bash
cp .env.example .env
# .env → DATABASE_URL=postgresql+psycopg2://luma:luma@db:5432/luma
docker compose --profile postgres up --build
```

API servisi PostgreSQL hazır olana kadar bekler (`depends_on` + healthcheck).

Production şablonu: `.env.production.example`

## Frontend ile birlikte (ayrı repolar)

1. Backend `8000` portunda.
2. Frontend `js/config.local.js`:

```js
window.__LUMA_API_BASE__ = 'http://127.0.0.1:8000';
```

3. `.env` → `FRONTEND_ORIGINS` içine frontend adresini ekleyin.

## Production checklist

| Ayar | Açıklama |
|------|----------|
| `SECRET_KEY` | Güçlü rastgele değer |
| `DATABASE_URL` | PostgreSQL (`postgresql+psycopg2://...`) |
| `STORAGE_BACKEND=s3` | Cloudflare R2 veya S3 private bucket |
| `SERVE_FRONTEND=false` | Frontend ayrı CDN'de |
| `FRONTEND_ORIGINS` | Production frontend URL |
| `PUBLIC_BASE_URL` | QR / upload linkleri için frontend domain |
| `ADMIN_PASSWORD` | Varsayılan şifreyi değiştirin |

## Testler

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest -q
```

CI: GitHub Actions — push/PR'da testler ve Docker smoke test (`.github/workflows/ci.yml`).
