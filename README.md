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
3. Seeds the default site config, pages, and resume data.
4. Starts FastAPI with Uvicorn.

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
