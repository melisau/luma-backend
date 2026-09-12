# Luma Backend

FastAPI REST API for digital invitations, guest RSVP records, moderated photo uploads, and admin authentication.

The frontend lives in a separate repository: [luma-frontend](https://github.com/melisau/luma-frontend).

## Table of contents

- [Project structure](#project-structure)
- [Setup](#setup)
- [Environment variables](#environment-variables)
- [API overview](#api-overview)
- [Database](#database)
- [Storage](#storage)
- [Docker](#docker)
- [Production checklist](#production-checklist)
- [Tests and CI](#tests-and-ci)

## Project structure

```text
backend/
├── app/
│   ├── api/              # FastAPI route modules
│   │   ├── event_data.py # RSVP, guests, invitation, messages, activity
│   │   ├── events.py     # Public event info, QR
│   │   └── photos.py     # Photos, admin auth, event CRUD
│   ├── core/             # Configuration, security
│   ├── db/               # SQLAlchemy models, session
│   ├── schemas/          # Pydantic request/response models
│   └── services/         # Business logic, storage, rate limits
├── alembic/              # Database migrations
├── tests/                # Pytest suite
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── .env.production.example
```

## Setup

### Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On first startup, a seed admin user and demo event are created (see `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env`).

| Endpoint | Description |
|----------|-------------|
| http://127.0.0.1:8000/docs | Swagger UI (interactive API) |
| http://127.0.0.1:8000/health | Database and storage status |

To serve the frontend from the same port in the monorepo workspace, keep `SERVE_FRONTEND=true` in `.env`.

### With a separate frontend

1. Run the backend on port `8000`.
2. Point the frontend `js/config.local.js` at the API base URL.
3. Add the frontend origin to `FRONTEND_ORIGINS` in `.env`.

## Environment variables

Full list: [`.env.example`](.env.example). Production template: [`.env.production.example`](.env.production.example).

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | `change-me-…` |
| `DATABASE_URL` | SQLite or PostgreSQL connection string | SQLite (`planner.db`) |
| `STORAGE_BACKEND` | `local` or `s3` | `local` |
| `LOCAL_STORAGE_PATH` | Local private upload directory | `private_uploads` |
| `STORAGE_*` | S3/R2 endpoint, bucket, credentials | — |
| `SERVE_FRONTEND` | Serve frontend static files | `true` (dev) |
| `FRONTEND_ORIGINS` | CORS allowed origins (comma-separated) | localhost |
| `PUBLIC_BASE_URL` | Public URL for QR and upload links | — |
| `ADMIN_EMAIL` | Seed admin email | `admin@example.com` |
| `ADMIN_PASSWORD` | Seed admin password | `change-me-admin` |
| `UPLOADS_PER_MINUTE` | Upload rate limit per IP/event | `10` |
| `LOGINS_PER_MINUTE` | Admin login attempt limit | `10` |
| `MESSAGES_PER_MINUTE` | Guestbook message rate limit | `20` |
| `MAX_PHOTO_SIZE_MB` | Max file size per photo | `15` |
| `MAX_PHOTOS_PER_EVENT` | Max photos per event | `500` |

## API overview

All routes are under the `/api` prefix. Full schema: `/docs`.

### Public (guest)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/events/{token}` | Event metadata |
| GET | `/events/{token}/invitation` | Invitation content |
| GET | `/events/{token}/cover` | Cover image |
| GET | `/events/{token}/music` | Background music |
| GET | `/events/{token}/photos` | Approved photos |
| POST | `/events/{token}/photos` | Photo upload |
| POST | `/events/{token}/rsvp` | RSVP submission |
| GET | `/events/{token}/messages` | Approved messages |
| POST | `/events/{token}/messages` | Leave a message (awaiting moderation) |

### Admin (JWT Bearer)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin/login` | Sign in |
| GET/PATCH | `/admin/me` | Profile and display name |
| POST | `/admin/change-password` | Change password |
| GET/POST/PATCH/DELETE | `/admin/events` | Event CRUD |
| GET/PATCH/DELETE | `/admin/events/{token}/guests` | Guest management |
| GET/PATCH/DELETE | `/admin/events/{token}/photos` | Photo moderation |
| GET/PATCH/DELETE | `/admin/events/{token}/messages` | Message moderation |
| PATCH | `/admin/events/{token}/invitation` | Invitation content |
| POST/DELETE | `/admin/events/{token}/invitation/cover` | Upload/remove cover |
| POST/DELETE | `/admin/events/{token}/invitation/music` | Upload/remove music |

### Photo access

Photo files are served at `/api/photos/{id}` and `/api/photos/{id}/thumbnail`. Access requires a valid event token (`?access=`) or admin JWT. No permanent public bucket URLs are generated.

## Database

`alembic upgrade head` runs automatically on application startup.

Manual migration:

```bash
PYTHONPATH=. alembic upgrade head
```

New schema change:

```bash
PYTHONPATH=. alembic revision -m "description"
PYTHONPATH=. alembic upgrade head
```

Supported databases: SQLite (development), PostgreSQL (production).

## Storage

| Mode | Use case | Notes |
|------|----------|-------|
| `local` | Local development | `private_uploads/` — not mounted as public static files |
| `s3` | Production | Cloudflare R2 or S3-compatible private bucket |

The `/health` endpoint also checks storage availability.

## Docker

SQLite (development):

```bash
cp .env.example .env
docker compose up --build
```

PostgreSQL:

```bash
cp .env.example .env
# DATABASE_URL=postgresql+psycopg2://luma:luma@db:5432/luma
docker compose --profile postgres up --build
```

The API service waits until the PostgreSQL healthcheck passes (`depends_on` + `condition: service_healthy`).

## Production checklist

- [ ] `SECRET_KEY` — generate with `openssl rand -hex 32`
- [ ] `ADMIN_PASSWORD` — change the default value
- [ ] `DATABASE_URL` — managed PostgreSQL
- [ ] `STORAGE_BACKEND=s3` — private bucket (R2/S3)
- [ ] `SERVE_FRONTEND=false` — frontend on a separate CDN/domain
- [ ] `FRONTEND_ORIGINS` — production frontend URL
- [ ] `PUBLIC_BASE_URL` — correct domain for QR and upload links
- [ ] HTTPS — all public traffic
- [ ] Tune rate limits for expected traffic

## Tests and CI

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest -q
```

GitHub Actions (`.github/workflows/ci.yml`):

- Full pytest suite on every push/PR
- Docker image build and container smoke test
- Verifies Alembic files are present in the image

## Features

- Event, invitation, RSVP, and guest CRUD
- Photo moderation: `uploaded` → `approved` → `hidden`
- Guestbook moderation: `pending` → `approved` → `hidden`
- HEIC/MPO image support with thumbnail generation
- Event-scoped QR code generation
- Activity feed (admin panel)
- Admin profile and display name (`display_name`)
- Login, upload, and message rate limiting

## RSVP and invitation reliability

- `RSVPS_PER_MINUTE` defaults to 20 per client IP and event. The limiter is in-memory; multiple workers require shared storage.
- Authenticated event owners can export `GET /api/admin/events/{token}/guests.csv`. UTF-8 BOM supports Turkish Excel imports; formula-like values are escaped.
- Invitation PATCH supports `address`, `transport_notes`, `contact_info`, and `schedule`; migration `0008` preserves existing event data.
- Event timestamps are normalized to UTC; the editor displays local time.
- Startup migrations use the application database connection and abort startup on migration failures.

## Private RSVP links and album exports

RSVP POST returns an `edit_token` on the first submission. Updates require that token in the request body. Pre-invited and legacy guests require a personal link issued by the event owner through `POST /api/admin/events/{event_token}/guests/{guest_id}/rsvp-link`. Issuing a link revokes its predecessor. Only SHA-256 token hashes are stored; guest lists and CSV exports contain no credentials. This is possession-based editing authorization, not email verification. The browser retains credentials locally and displays a private recovery link using a URL fragment.

Owners can download `GET /api/admin/events/{event_token}/album.zip`, including pending/approved/hidden photos, excluding deleted photos. Exports are limited to 200 MB and fail if any file is unavailable.

New photo uploads are oriented using EXIF, resized to `MAX_PHOTO_DIMENSION` (4096 by default), and compressed. The processed copy is retained, not the untouched original. Exact processed-content duplicates within an event are skipped and reported as `duplicates_skipped`. Legacy photos without a hash are not retroactively deduplicated. Deleted photos may be uploaded again. Duplicate checks do not detect visually similar photos with different encoding/content.

## Invitation access codes and album privacy

Event owners can PATCH `access_code` (6–64 characters, at most 72 UTF-8 bytes). Omit it to preserve the current code; an empty string removes it. Only its password hash is stored. `access_code_enabled` exposes the state to the owner without returning the code.

Public event data, covers, music, RSVP, messages, photo upload and photo reads require access after a code is enabled. POST `/api/events/{token}/unlock` verifies the code with a five-attempts-per-minute limit per event/IP and issues an HttpOnly, SameSite=Lax cookie for 12 hours. Changing the code revokes previously issued cookies. Use same-site frontend/API domains in production and HTTPS; cross-site cookie restrictions can otherwise block the flow. Owners obtain preview access through an authenticated event-scoped endpoint.

`album_public=false` hides approved photos from guests, including original and thumbnail endpoints. Upload permission remains independent; administrators retain album and ZIP access. Guest photo requests use the API proxy so every new read checks current privacy settings. Previously issued storage URLs remain valid until their original expiry; downloaded copies cannot be recalled.

Retention is a separate, opt-in policy; privacy switches alone never delete memories.

## Opt-in memory retention

An owner may PATCH `memory_delete_at` with `confirm_memory_deletion=true`. A new deadline must be at least 24 hours away. Omitting the date leaves it unchanged; null cancels it. Default is no automatic deletion. After the deadline, guest photo/message access and submissions close while invitation and RSVP remain available.

While the API runs, the background job checks hourly (`MEMORY_CLEANUP_ENABLED`, `MEMORY_CLEANUP_INTERVAL_SECONDS`, minimum interval 60 seconds). It deletes original/thumbnail objects and photo/message records only for explicitly scheduled events. Failed storage deletes preserve their records for retry. Completed policies are marked to avoid repeated work. PostgreSQL row locks coordinate workers and uploads; use one worker with SQLite. A stopped API does not run cleanup; it resumes on the next interval after startup.

RSVP guests, invitation content, invitation cover/music, and activity records remain. This is application memory cleanup, not complete personal-data erasure. Production S3 versioning, provider backups and lifecycle expiration require a separate storage policy.
