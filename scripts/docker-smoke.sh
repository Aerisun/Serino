#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TMP_ENV_FILE="$(mktemp)"
COMPOSE_PROJECT="aerisun-smoke-$(date +%s)"

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

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local label="$3"
  if [[ "${haystack}" != *"${needle}"* ]]; then
    echo "ERROR: ${label} missing expected content: ${needle}" >&2
    return 1
  fi
}

cleanup() {
  local exit_code="$1"
  if [[ "${exit_code}" -ne 0 ]]; then
    echo "Docker smoke failed; dumping compose diagnostics..." >&2
    compose ps || true
    compose logs --tail 80 api waline litestream caddy || true
  fi
  compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "${TMP_ENV_FILE}"
}

trap 'cleanup $?' EXIT INT TERM

HTTP_PORT="${AERISUN_HTTP_PORT:-18080}"
HTTPS_PORT="${AERISUN_HTTPS_PORT:-18443}"
BACKEND_PORT="${AERISUN_PORT:-18000}"
WALINE_PORT="${WALINE_PORT:-18360}"
SITE_HOST="${AERISUN_SMOKE_HOST:-127.0.0.1}"
SITE_URL="http://${SITE_HOST}:${HTTP_PORT}"
PUBLIC_ORIGIN="${AERISUN_SMOKE_PUBLIC_ORIGIN:-https://smoke.aerisun.test}"
CANONICAL_ORIGIN="${AERISUN_SMOKE_CANONICAL_ORIGIN:-https://runtime-smoke.aerisun.test}"
HEALTHCHECK_PATH="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"
ADMIN_BASE_PATH="$(ensure_trailing_slash "${AERISUN_ADMIN_BASE_PATH:-/admin/}")"
WALINE_BASE_PATH="$(strip_trailing_slash "${AERISUN_WALINE_BASE_PATH:-/waline}")"
ADMIN_BOOTSTRAP_USERNAME="${AERISUN_SMOKE_ADMIN_USERNAME:-admin}"
ADMIN_BOOTSTRAP_PASSWORD="${AERISUN_SMOKE_ADMIN_PASSWORD:-admin123}"

cat >"${TMP_ENV_FILE}" <<EOF
AERISUN_DOMAIN=http://${SITE_HOST}
AERISUN_SITE_URL=${SITE_URL}
AERISUN_WALINE_SERVER_URL=${SITE_URL}${WALINE_BASE_PATH}
AERISUN_CORS_ORIGINS=["${PUBLIC_ORIGIN}"]
WALINE_SECURE_DOMAINS=${SITE_HOST},localhost,127.0.0.1
AERISUN_HTTP_PORT=${HTTP_PORT}
AERISUN_HTTPS_PORT=${HTTPS_PORT}
AERISUN_PORT=${BACKEND_PORT}
WALINE_PORT=${WALINE_PORT}
EOF

load_env_file "${PROJECT_DIR}/.env"
load_env_file "${PROJECT_DIR}/.env.production"
load_env_file "${TMP_ENV_FILE}"

export AERISUN_SECRETS_DIR="${AERISUN_SECRETS_DIR:-${PROJECT_DIR}/.store/secrets}"
mkdir -p "${AERISUN_SECRETS_DIR}"
printf '%s' 'smoke-0123456789abcdef0123456789abcdef' > "${AERISUN_SECRETS_DIR}/waline_jwt_token.txt"
printf 'JWT_TOKEN=%s\n' 'smoke-0123456789abcdef0123456789abcdef' > "${AERISUN_SECRETS_DIR}/waline.env"

compose up --build -d

wait_for_url "${SITE_URL}/" "frontend"
wait_for_url "${SITE_URL}${ADMIN_BASE_PATH}" "admin"
wait_for_url "${SITE_URL}${HEALTHCHECK_PATH}" "backend via caddy"
wait_for_url "${SITE_URL}${WALINE_BASE_PATH}/" "waline via caddy"

assert_spa_response "${SITE_URL}/posts" "frontend deep link"
assert_spa_response "${SITE_URL}${ADMIN_BASE_PATH}posts" "admin deep link"

ADMIN_LOGIN_RESPONSE="$(curl -fsS -X POST "${SITE_URL}/api/v1/admin/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${ADMIN_BOOTSTRAP_USERNAME}\",\"password\":\"${ADMIN_BOOTSTRAP_PASSWORD}\"}")"
ADMIN_TOKEN="$(python3 - <<'PY' "${ADMIN_LOGIN_RESPONSE}"
import json, sys
print(json.loads(sys.argv[1])["token"])
PY
)"

curl -fsS -X PUT "${SITE_URL}/api/v1/admin/site-config/runtime" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"public_site_url\":\"${CANONICAL_ORIGIN}\",\"production_cors_origins\":[\"${PUBLIC_ORIGIN}\"],\"seo_default_title\":\"Smoke Runtime Title\",\"seo_default_description\":\"Smoke Runtime Description\",\"rss_title\":\"Smoke Feed\",\"rss_description\":\"Smoke Feed Description\",\"robots_indexing_enabled\":false,\"sitemap_static_pages\":[{\"path\":\"/smoke-runtime\",\"changefreq\":\"daily\",\"priority\":\"0.9\"}]}" >/dev/null

SITEMAP_BODY="$(curl -fsS "${SITE_URL}/sitemap.xml")"
ROBOTS_BODY="$(curl -fsS "${SITE_URL}/robots.txt")"
RSS_BODY="$(curl -fsS "${SITE_URL}/rss.xml")"

assert_contains "${SITEMAP_BODY}" "${CANONICAL_ORIGIN}/smoke-runtime" "sitemap.xml"
assert_contains "${ROBOTS_BODY}" "Disallow: /" "robots.txt"
assert_contains "${ROBOTS_BODY}" "Sitemap: ${CANONICAL_ORIGIN}/sitemap.xml" "robots.txt"
assert_contains "${RSS_BODY}" "<title>Smoke Feed</title>" "rss.xml"
assert_contains "${RSS_BODY}" "${CANONICAL_ORIGIN}/feeds/posts.xml" "rss.xml"

echo "Docker smoke test passed for ${SITE_URL}"
