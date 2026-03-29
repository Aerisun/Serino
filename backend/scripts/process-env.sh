#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKTREE_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"
COMMON_GIT_DIR="$(git -C "${WORKTREE_ROOT}" rev-parse --git-common-dir 2>/dev/null || true)"

load_env_file() {
  local env_file="$1"
  local line=""
  local key=""
  local value=""

  [[ -f "${env_file}" ]] || return 0

  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ -z "${line}" ]] && continue
    [[ "${line}" =~ ^[[:space:]]*# ]] && continue
    [[ "${line}" != *=* ]] && continue

    key="${line%%=*}"
    value="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value%$'\r'}"

    [[ -n "${key}" ]] || continue
    export "${key}=${value}"
  done < "${env_file}"
}

if [[ -n "${COMMON_GIT_DIR}" ]]; then
  AERISUN_COMMON_ROOT="$(cd "$(dirname "${COMMON_GIT_DIR}")" && pwd)"
else
  AERISUN_COMMON_ROOT="${WORKTREE_ROOT}"
fi

load_env_file "${WORKTREE_ROOT}/.env"
load_env_file "${BACKEND_DIR}/.env"

export AERISUN_API_BASE_PATH="${AERISUN_API_BASE_PATH:-/api}"
export AERISUN_ADMIN_BASE_PATH="${AERISUN_ADMIN_BASE_PATH:-/admin/}"
export AERISUN_WALINE_BASE_PATH="${AERISUN_WALINE_BASE_PATH:-/waline}"
export AERISUN_HEALTHCHECK_PATH="${AERISUN_HEALTHCHECK_PATH:-${AERISUN_API_BASE_PATH}/v1/site/healthz}"

AERISUN_PROCESS_FRONTEND_PORT="${AERISUN_PROCESS_FRONTEND_PORT:-8080}"
AERISUN_PROCESS_BACKEND_PORT="${AERISUN_PROCESS_BACKEND_PORT:-8001}"
AERISUN_PROCESS_WALINE_PORT="${AERISUN_PROCESS_WALINE_PORT:-8360}"
AERISUN_PROCESS_STORE_DIR="${AERISUN_PROCESS_STORE_DIR:-${AERISUN_COMMON_ROOT}/.store}"

export AERISUN_COMMON_ROOT
export AERISUN_HOST="127.0.0.1"
export AERISUN_PORT="${AERISUN_PROCESS_BACKEND_PORT}"
export AERISUN_STORE_DIR="${AERISUN_PROCESS_STORE_DIR}"
export AERISUN_DATA_DIR="${AERISUN_PROCESS_STORE_DIR}"
export AERISUN_DB_PATH="${AERISUN_PROCESS_DB_PATH:-${AERISUN_PROCESS_STORE_DIR}/aerisun.db}"
export AERISUN_WALINE_DB_PATH="${AERISUN_PROCESS_WALINE_DB_PATH:-${AERISUN_PROCESS_STORE_DIR}/waline.db}"
export AERISUN_MEDIA_DIR="${AERISUN_PROCESS_MEDIA_DIR:-${AERISUN_PROCESS_STORE_DIR}/media}"
export AERISUN_SECRETS_DIR="${AERISUN_PROCESS_SECRETS_DIR:-${AERISUN_PROCESS_STORE_DIR}/secrets}"
export AERISUN_SITE_URL="${AERISUN_PROCESS_SITE_URL:-http://localhost:${AERISUN_PROCESS_FRONTEND_PORT}}"
export AERISUN_WALINE_SERVER_URL="${AERISUN_PROCESS_BROWSER_WALINE_URL:-${AERISUN_WALINE_BASE_PATH}}"

export WALINE_PORT="${AERISUN_PROCESS_WALINE_PORT}"
export WALINE_SERVER_URL="${AERISUN_PROCESS_WALINE_SERVER_URL:-http://localhost:${AERISUN_PROCESS_FRONTEND_PORT}${AERISUN_WALINE_BASE_PATH}}"
export SITE_URL="${AERISUN_SITE_URL}"
export SITE_NAME="${SITE_NAME:-Aerisun}"
export JWT_TOKEN="${JWT_TOKEN:-${WALINE_JWT_TOKEN:-change-me}}"
export SECURE_DOMAINS="${SECURE_DOMAINS:-${WALINE_SECURE_DOMAINS:-localhost,127.0.0.1}}"
export AVATAR_PROXY="${AVATAR_PROXY:-${WALINE_AVATAR_PROXY:-}}"
export GRAVATAR_STR="${GRAVATAR_STR:-${WALINE_GRAVATAR_STR:-}}"
export SQLITE_PATH="$(dirname "${AERISUN_WALINE_DB_PATH}")"
export SQLITE_DB="$(basename "${AERISUN_WALINE_DB_PATH}" .db)"

mkdir -p "${AERISUN_STORE_DIR}" "${AERISUN_MEDIA_DIR}" "${AERISUN_SECRETS_DIR}"
