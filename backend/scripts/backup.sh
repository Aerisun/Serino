#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi

  echo "docker compose or docker-compose is required" >&2
  exit 1
}

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

: "${AERISUN_DB_PATH:?AERISUN_DB_PATH is required}"
: "${AERISUN_BACKUP_RSYNC_URI:?AERISUN_BACKUP_RSYNC_URI is required}"
: "${AERISUN_BACKUP_SSH_PORT:=22}"

if [[ -z "${AERISUN_BACKUP_SSH_KEY:-}" ]]; then
  SSH_KEY_ARGS=()
else
  SSH_KEY_ARGS=(-i "${AERISUN_BACKUP_SSH_KEY}")
fi

REMOTE_HOST="${AERISUN_BACKUP_RSYNC_URI%%:*}"
REMOTE_PATH="${AERISUN_BACKUP_RSYNC_URI#*:}"
MANIFEST_TS="$(date -u +%Y%m%dT%H%M%SZ)"
MANIFEST_FILE="$(mktemp)"

cat > "${MANIFEST_FILE}" <<EOF
timestamp=${MANIFEST_TS}
db_path=${AERISUN_DB_PATH}
replica_url=${AERISUN_LITESTREAM_REPLICA_URL:-}
media_dir=${AERISUN_MEDIA_DIR:-/srv/aerisun/media}
secrets_dir=${AERISUN_SECRETS_DIR:-/srv/aerisun/secrets}
compose_project=${ROOT_DIR}
EOF

compose exec -T api sqlite3 "${AERISUN_DB_PATH}" "PRAGMA wal_checkpoint(FULL);"

ssh -p "${AERISUN_BACKUP_SSH_PORT}" "${SSH_KEY_ARGS[@]}" "${REMOTE_HOST}" \
  "mkdir -p '${REMOTE_PATH}/media' '${REMOTE_PATH}/secrets' '${REMOTE_PATH}/manifests'"

SSH_CMD=(ssh -p "${AERISUN_BACKUP_SSH_PORT}")
if [[ -n "${AERISUN_BACKUP_SSH_KEY:-}" ]]; then
  SSH_CMD+=(-i "${AERISUN_BACKUP_SSH_KEY}")
fi
SSH_CMD_STR="${SSH_CMD[*]}"

rsync -a --delete -e "${SSH_CMD_STR}" \
  "${AERISUN_MEDIA_DIR:-/srv/aerisun/media}/" \
  "${REMOTE_HOST}:${REMOTE_PATH}/media/"

rsync -a --delete -e "${SSH_CMD_STR}" \
  "${AERISUN_SECRETS_DIR:-/srv/aerisun/secrets}/" \
  "${REMOTE_HOST}:${REMOTE_PATH}/secrets/"

rsync -a -e "${SSH_CMD_STR}" \
  "${MANIFEST_FILE}" \
  "${REMOTE_HOST}:${REMOTE_PATH}/manifests/backup-${MANIFEST_TS}.txt"

rsync -a -e "${SSH_CMD_STR}" \
  docker-compose.yml .env.example README.md backend/Dockerfile backend/pyproject.toml backend/alembic.ini backend/README.md backend/.gitignore backend/litestream.yml.template backend/scripts/*.sh \
  "${REMOTE_HOST}:${REMOTE_PATH}/manifests/"

rm -f "${MANIFEST_FILE}"

echo "backup complete: ${MANIFEST_TS}"
