# Luma Backend

FastAPI tabanlı davetiye fotoğraf API'si. Frontend ayrı repoda barınır.

## Yapı

```text
backend/
├── app/
│   ├── main.py
│   ├── api/events.py, photos.py
│   ├── core/config.py, security.py
│   ├── db/database.py, models.py
│   ├── services/storage.py, photo_service.py, rate_limit.py
│   └── schemas/
├── tests/
├── requirements.txt
└── .env.example
```

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env içinde SECRET_KEY ve ADMIN_PASSWORD güncelleyin
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Sağlık kontrolü: http://127.0.0.1:8000/health
- API dokümantasyonu: http://127.0.0.1:8000/docs

## Frontend ile birlikte çalıştırma

1. Backend bu repoda `8000` portunda çalışsın.
2. Frontend reposunda `js/config.local.js` oluşturun:

```js
window.__LUMA_API_BASE__ = 'http://127.0.0.1:8000';
```

3. `.env` içinde `FRONTEND_ORIGINS` değerine frontend adresini ekleyin (ör. `http://127.0.0.1:5500`).

## API uç noktaları

| Method | Path | Açıklama |
|--------|------|----------|
| GET | `/health` | Sağlık kontrolü |
| GET | `/api/events/{event_token}` | Etkinlik bilgisi |
| POST | `/api/events/{event_token}/photos` | Fotoğraf yükleme |
| GET | `/api/photos/{photo_id}` | Korunan görsel |
| POST | `/api/admin/login` | Yönetici JWT |

Tam liste için kök workspace README'sine bakın.

## Testler

```bash
pytest tests/test_security.py -q
```

## Production

1. PostgreSQL + güçlü `SECRET_KEY`
2. Private S3/R2 bucket (`STORAGE_BACKEND=s3`)
3. `FRONTEND_ORIGINS` → production frontend URL
4. `PUBLIC_BASE_URL` → QR kodları için frontend domain
