# Aerisun v1 Deploy Notes

Minimal deploy skeleton for `SQLite + Litestream + rsync`.

## Start

1. Copy `.env.example` to `.env` and fill in the backup host values.
2. Start the stack:

```bash
docker compose up --build -d
```

The API container runs `backend/scripts/bootstrap.sh`, which:

1. Ensures the data/media/secrets directories exist.
2. Runs `alembic upgrade head`.
3. Starts FastAPI with Uvicorn.

At app startup, the FastAPI lifespan hook runs the reference-data seeding step so
the default site config, pages, and resume data are only filled through the
active runtime chain.

The two frontend apps remain host-side Vite apps in this setup:

- Main site: `frontend` on `http://localhost:8080`
- Admin: `admin` on `http://localhost:3001/admin/`

`Caddy` now proxies:

- `/` to `${AERISUN_FRONTEND_UPSTREAM}`
- `/admin/*` to `${AERISUN_ADMIN_UPSTREAM}`
- `/api/*` to the FastAPI backend

## Backup

Run the host-side helper:

```bash
./backend/scripts/backup.sh
```

It checkpoints the local SQLite database, lets Litestream keep the replica current, then syncs media, secrets, and a backup manifest to your backup host with `rsync`.

## Restore

Run the host-side helper:

```bash
./backend/scripts/restore.sh
```

It stops the stack, restores the SQLite database from the Litestream replica, syncs media and secrets back from the backup host, and then brings the stack up again.

## Files

- Database: `${AERISUN_DB_PATH}`
- Media: `${AERISUN_MEDIA_DIR}`
- Secrets: `${AERISUN_SECRETS_DIR}`
