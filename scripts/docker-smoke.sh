#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TMP_ENV_FILE="$(mktemp)"
TMP_STORE_DIR="$(mktemp -d)"
COMPOSE_PROJECT="serino-smoke-$(date +%s)"
SMOKE_TAG="${AERISUN_SMOKE_IMAGE_TAG:-smoke}"
LOCAL_API_IMAGE="${AERISUN_SMOKE_API_IMAGE:-serino-api-smoke}"
LOCAL_WEB_IMAGE="${AERISUN_SMOKE_WEB_IMAGE:-serino-web-smoke}"
LOCAL_WALINE_IMAGE="${AERISUN_SMOKE_WALINE_IMAGE:-serino-waline-smoke}"

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

compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT}" docker compose "$@"
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT}" docker-compose "$@"
    return
  fi

  echo "docker compose or docker-compose is required" >&2
  exit 1
}

ensure_trailing_slash() {
  local value="$1"
  if [[ "${value}" == */ ]]; then
    printf '%s' "${value}"
    return 0
  fi
  printf '%s/' "${value}"
}

strip_trailing_slash() {
  local value="$1"
  printf '%s' "${value%/}"
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local timeout_seconds="${3:-180}"
  local started_at
  started_at=$(date +%s)

  while true; do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "${label} is ready: ${url}"
      return 0
    fi
    if [[ $(( $(date +%s) - started_at )) -ge ${timeout_seconds} ]]; then
      echo "ERROR: timed out waiting for ${label}: ${url}" >&2
      return 1
    fi
    sleep 2
  done
}

assert_spa_response() {
  local url="$1"
  local label="$2"
  local body_file
  body_file="$(mktemp)"

  curl -fsS "${url}" -o "${body_file}"
  if ! grep -qi '<!doctype html' "${body_file}"; then
    echo "ERROR: ${label} did not return an SPA document: ${url}" >&2
    cat "${body_file}" >&2
    rm -f "${body_file}"
    return 1
  fi
  rm -f "${body_file}"
}

assert_not_404() {
  local url="$1"
  local label="$2"
  local status
  local response_file

  response_file="$(mktemp)"

  status="$(curl -sS -o "${response_file}" -w '%{http_code}' "${url}")"
  if [[ "${status}" == "404" ]]; then
    echo "ERROR: ${label} returned 404: ${url}" >&2
    cat "${response_file}" >&2
    rm -f "${response_file}"
    return 1
  fi
  rm -f "${response_file}"
}

build_local_images() {
  docker build -t "${LOCAL_API_IMAGE}:${SMOKE_TAG}" ./backend
  docker build -t "${LOCAL_WEB_IMAGE}:${SMOKE_TAG}" -f Dockerfile.caddy .
  docker build -t "${LOCAL_WALINE_IMAGE}:${SMOKE_TAG}" -f Dockerfile.waline .
}

cleanup() {
  local exit_code="$1"
  if [[ "${exit_code}" -ne 0 ]]; then
    echo "Docker smoke failed; dumping compose diagnostics..." >&2
    compose -f docker-compose.release.yml ps || true
    compose -f docker-compose.release.yml logs --tail 80 api waline caddy || true
  fi
  compose -f docker-compose.release.yml down -v --remove-orphans >/dev/null 2>&1 || true
  docker image rm \
    "${LOCAL_API_IMAGE}:${SMOKE_TAG}" \
    "${LOCAL_WEB_IMAGE}:${SMOKE_TAG}" \
    "${LOCAL_WALINE_IMAGE}:${SMOKE_TAG}" >/dev/null 2>&1 || true
  rm -f "${TMP_ENV_FILE}"
  rm -rf "${TMP_STORE_DIR}"
}

trap 'cleanup $?' EXIT INT TERM

HTTP_PORT="${AERISUN_HTTP_PORT:-18080}"
HTTPS_PORT="${AERISUN_HTTPS_PORT:-18443}"
BACKEND_PORT="${AERISUN_PORT:-18000}"
WALINE_PORT="${WALINE_PORT:-18360}"
SITE_HOST="${AERISUN_SMOKE_HOST:-127.0.0.1}"
SITE_URL="http://${SITE_HOST}:${HTTP_PORT}"
PUBLIC_ORIGIN="${AERISUN_SMOKE_PUBLIC_ORIGIN:-https://smoke.aerisun.test}"
HEALTHCHECK_PATH="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"
ADMIN_BASE_PATH="$(ensure_trailing_slash "${AERISUN_ADMIN_BASE_PATH:-/admin/}")"
WALINE_BASE_PATH="$(strip_trailing_slash "${AERISUN_WALINE_BASE_PATH:-/waline}")"

chmod 0777 "${TMP_STORE_DIR}"

cat >"${TMP_ENV_FILE}" <<EOF
AERISUN_DOMAIN=http://${SITE_HOST}
AERISUN_SITE_URL=${SITE_URL}
AERISUN_WALINE_SERVER_URL=${SITE_URL}${WALINE_BASE_PATH}
AERISUN_CORS_ORIGINS=["${PUBLIC_ORIGIN}"]
WALINE_SECURE_DOMAINS=${SITE_HOST},localhost,127.0.0.1
WALINE_JWT_TOKEN=smoke-0123456789abcdef0123456789abcdef
AERISUN_HTTP_PORT=${HTTP_PORT}
AERISUN_HTTPS_PORT=${HTTPS_PORT}
AERISUN_PORT=${BACKEND_PORT}
WALINE_PORT=${WALINE_PORT}
AERISUN_SENTRY_DSN=
VITE_SENTRY_DSN=
AERISUN_STORE_BIND_DIR=${TMP_STORE_DIR}
AERISUN_API_IMAGE=${LOCAL_API_IMAGE}
AERISUN_WEB_IMAGE=${LOCAL_WEB_IMAGE}
AERISUN_WALINE_IMAGE=${LOCAL_WALINE_IMAGE}
AERISUN_IMAGE_TAG=${SMOKE_TAG}
EOF

load_env_file "${PROJECT_DIR}/.env"
load_env_file "${PROJECT_DIR}/.env.production"
load_env_file "${TMP_ENV_FILE}"

build_local_images

compose -f docker-compose.release.yml up -d

wait_for_url "${SITE_URL}/" "frontend"
wait_for_url "${SITE_URL}${ADMIN_BASE_PATH}" "admin"
wait_for_url "${SITE_URL}${HEALTHCHECK_PATH}" "backend via caddy"
wait_for_url "${SITE_URL}${WALINE_BASE_PATH}/" "waline via caddy"
assert_not_404 "${SITE_URL}${WALINE_BASE_PATH}/api/comment?type=recent&pageSize=1" "waline API"

assert_spa_response "${SITE_URL}/posts" "frontend deep link"
assert_spa_response "${SITE_URL}${ADMIN_BASE_PATH}posts" "admin deep link"

echo "Docker smoke test passed for ${SITE_URL}"
