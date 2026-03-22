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
: "${AERISUN_WALINE_DB_PATH:=${AERISUN_DATA_DIR:-/srv/aerisun/store}/waline.db}"
: "${AERISUN_LITESTREAM_REPLICA_URL:?AERISUN_LITESTREAM_REPLICA_URL is required}"
: "${AERISUN_WALINE_LITESTREAM_REPLICA_URL:?AERISUN_WALINE_LITESTREAM_REPLICA_URL is required}"

STOPPED_BACKUP="${AERISUN_DB_PATH}.pre-restore.$(date -u +%Y%m%dT%H%M%SZ)"
WALINE_STOPPED_BACKUP="${AERISUN_WALINE_DB_PATH}.pre-restore.$(date -u +%Y%m%dT%H%M%SZ)"
RESTORE_TMP="${AERISUN_DB_PATH}.restoring"
WALINE_RESTORE_TMP="${AERISUN_WALINE_DB_PATH}.restoring"

compose stop api waline litestream || true

if [[ -f "${AERISUN_DB_PATH}" ]]; then
  mv "${AERISUN_DB_PATH}" "${STOPPED_BACKUP}"
fi

if [[ -f "${AERISUN_WALINE_DB_PATH}" ]]; then
  mv "${AERISUN_WALINE_DB_PATH}" "${WALINE_STOPPED_BACKUP}"
fi

rm -f "${RESTORE_TMP}"
rm -f "${WALINE_RESTORE_TMP}"

compose run --rm --no-deps --entrypoint litestream litestream \
  restore -o "${RESTORE_TMP}" "${AERISUN_LITESTREAM_REPLICA_URL}"

mv "${RESTORE_TMP}" "${AERISUN_DB_PATH}"

compose run --rm --no-deps --entrypoint litestream litestream \
  restore -o "${WALINE_RESTORE_TMP}" "${AERISUN_WALINE_LITESTREAM_REPLICA_URL}"

mv "${WALINE_RESTORE_TMP}" "${AERISUN_WALINE_DB_PATH}"

if [[ -n "${AERISUN_BACKUP_RSYNC_URI:-}" ]]; then
  REMOTE_HOST="${AERISUN_BACKUP_RSYNC_URI%%:*}"
  REMOTE_PATH="${AERISUN_BACKUP_RSYNC_URI#*:}"
  SSH_CMD=(ssh -p "${AERISUN_BACKUP_SSH_PORT:-22}")
  if [[ -n "${AERISUN_BACKUP_SSH_KEY:-}" ]]; then
    SSH_CMD+=(-i "${AERISUN_BACKUP_SSH_KEY}")
  fi
  SSH_CMD_STR="${SSH_CMD[*]}"

  rsync -a -e "${SSH_CMD_STR}" \
    "${REMOTE_HOST}:${REMOTE_PATH}/store/" \
    "${AERISUN_STORE_DIR:-/srv/aerisun/store}/"
fi

compose up -d api waline litestream

echo "restore complete from ${AERISUN_LITESTREAM_REPLICA_URL}"
