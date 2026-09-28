# Koyeb + Neon + Cloudflare R2 deployment

This repository is prepared for a free Koyeb web service backed by Neon PostgreSQL and private Cloudflare R2 storage. The public frontend is deployed separately with Cloudflare Pages.

## 1. Neon

1. Create a Neon project in a European region.
2. Copy the pooled PostgreSQL connection string.
3. Keep `sslmode=require` in the URL.
4. Convert the scheme to `postgresql+psycopg2://` if Neon shows `postgresql://`.
5. Save the result as the Koyeb secret `DATABASE_URL`.

Application startup runs `alembic upgrade head`, so the schema is created automatically. Before importing existing data, run the backup and restore rehearsal described in `OPERATIONS.md` against a separate Neon branch.

## 2. Cloudflare R2

1. Create a private R2 bucket, for example `luma-private`.
2. Create an R2 API token limited to that bucket with object read/write permission.
3. Record the S3 endpoint, access key ID, secret access key, bucket name, and region `auto`.
4. Do not enable a public bucket URL. Photos are served through authenticated Luma API routes.

## 3. Koyeb web service

Create a Web Service from this GitHub repository with these settings:

- Builder: `Dockerfile`
- Dockerfile path: `Dockerfile`
- Instance: `Free`
- Region: Frankfurt
- Exposed port: `8000` (HTTP)
- Route: `/`
- Health check: HTTP `GET /health`

Copy every variable from `.env.production.example` into the Koyeb environment. Store `SECRET_KEY`, `DATABASE_URL`, R2 credentials, SMTP password, and `ADMIN_PASSWORD` as secrets.

Set these URL values after Cloudflare Pages creates the frontend address:

```env
FRONTEND_ORIGINS=https://YOUR_PROJECT.pages.dev
PUBLIC_BASE_URL=https://YOUR_PROJECT.pages.dev
```

The free Koyeb instance sleeps after inactivity. Luma runs due reminder and retention work immediately whenever the service starts or wakes, then continues its normal interval while the process is active.

## 4. Cloudflare Pages

Use the `luma-frontend` repository and follow its README deployment settings. Set `LUMA_API_BASE` to the Koyeb service URL, without a trailing slash.

After both services are live, update Koyeb with the final Pages/custom-domain URL and redeploy.

## 5. Verification

1. Open the Koyeb `/health` endpoint and verify database and storage are `ok` or configured.
2. Register a fresh administrator instead of using the seed account.
3. Create an event and open its invitation from a private mobile browser.
4. Submit an RSVP, guestbook message, and phone photo.
5. Approve the photo and verify its thumbnail and full preview.
6. Download the guest CSV and album ZIP.
7. Test password reset and RSVP email delivery after SMTP is configured.
