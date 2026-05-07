#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TMP_ENV_FILE="$(mktemp)"
TMP_STORE_DIR="$(mktemp -d)"
COMPOSE_PROJECT="serino-smoke-$(date +%s)"
SMOKE_TAG="${AERISUN_SMOKE_IMAGE_TAG:-smoke}"
LOCAL_IMAGE_REGISTRY="${AERISUN_SMOKE_IMAGE_REGISTRY:-serino-smoke-local}"

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
    if curl --noproxy '*' -fsS "${url}" >/dev/null 2>&1; then
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

  curl --noproxy '*' -fsS "${url}" -o "${body_file}"
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

  status="$(curl --noproxy '*' -sS -o "${response_file}" -w '%{http_code}' "${url}")"
  if [[ "${status}" == "404" ]]; then
    echo "ERROR: ${label} returned 404: ${url}" >&2
    cat "${response_file}" >&2
    rm -f "${response_file}"
    return 1
  fi
  rm -f "${response_file}"
}

assert_cache_control() {
  local url="$1"
  local label="$2"
  local expected="$3"
  local headers_file

  headers_file="$(mktemp)"
  curl --noproxy '*' -fsS -D "${headers_file}" -o /dev/null "${url}"
  if ! grep -Eiq "^cache-control:[[:space:]]*${expected}" "${headers_file}"; then
    echo "ERROR: ${label} did not return expected Cache-Control (${expected}): ${url}" >&2
    cat "${headers_file}" >&2
    rm -f "${headers_file}"
    return 1
  fi
  rm -f "${headers_file}"
}

assert_body_not_contains() {
  local url="$1"
  local label="$2"
  local pattern="$3"
  local body_file

  body_file="$(mktemp)"
  curl --noproxy '*' -fsS "${url}" -o "${body_file}"
  if grep -Eiq "${pattern}" "${body_file}"; then
    echo "ERROR: ${label} matched forbidden pattern (${pattern}): ${url}" >&2
    rm -f "${body_file}"
    return 1
  fi
  rm -f "${body_file}"
}

assert_body_contains() {
  local url="$1"
  local label="$2"
  local pattern="$3"
  local body_file

  body_file="$(mktemp)"
  curl --noproxy '*' -fsS "${url}" -o "${body_file}"
  if ! grep -Eiq "${pattern}" "${body_file}"; then
    echo "ERROR: ${label} did not match required pattern (${pattern}): ${url}" >&2
    rm -f "${body_file}"
    return 1
  fi
  rm -f "${body_file}"
}

assert_runtime_css_contains() {
  local label="$1"
  local pattern="$2"
  local index_file
  local entry_file
  local css_file
  local entry_path
  local css_path

  index_file="$(mktemp)"
  entry_file="$(mktemp)"
  css_file="$(mktemp)"

  curl --noproxy '*' -fsS "${SITE_URL}/" -o "${index_file}"
  entry_path="$(grep -Eo 'src="/assets/index-[^"]+\.js"' "${index_file}" | head -n 1 | sed -E 's/^src="([^"]+)"/\1/' || true)"
  if [[ -z "${entry_path}" ]]; then
    echo "ERROR: frontend index entry script was not found" >&2
    rm -f "${index_file}" "${entry_file}" "${css_file}"
    return 1
  fi

  curl --noproxy '*' -fsS "${SITE_URL}${entry_path}" -o "${entry_file}"
  css_path="$(grep -Eo 'assets/AppRuntime-[A-Za-z0-9_-]+\.css' "${entry_file}" | head -n 1 || true)"
  if [[ -z "${css_path}" ]]; then
    echo "ERROR: frontend runtime CSS asset was not found" >&2
    rm -f "${index_file}" "${entry_file}" "${css_file}"
    return 1
  fi

  curl --noproxy '*' -fsS "${SITE_URL}/${css_path}" -o "${css_file}"
  if ! grep -Eiq "${pattern}" "${css_file}"; then
    echo "ERROR: ${label} did not match required pattern (${pattern}): ${SITE_URL}/${css_path}" >&2
    rm -f "${index_file}" "${entry_file}" "${css_file}"
    return 1
  fi

  rm -f "${index_file}" "${entry_file}" "${css_file}"
}

resolve_site_asset_url() {
  local asset_path="$1"

  if [[ "${asset_path}" =~ ^https?:// ]]; then
    printf '%s' "${asset_path}"
    return 0
  fi
  if [[ "${asset_path}" == /* ]]; then
    printf '%s%s' "${SITE_URL}" "${asset_path}"
    return 0
  fi
  printf '%s%s%s' "${SITE_URL}" "${ADMIN_BASE_PATH}" "${asset_path}"
}

assert_admin_css_contains() {
  local label="$1"
  local pattern="$2"
  local index_file
  local css_file
  local css_path
  local css_url

  index_file="$(mktemp)"
  css_file="$(mktemp)"

  curl --noproxy '*' -fsS "${SITE_URL}${ADMIN_BASE_PATH}" -o "${index_file}"
  css_path="$(grep -Eo 'href="[^"]*assets/index-[^"]+\.css"' "${index_file}" | head -n 1 | sed -E 's/^href="([^"]+)"/\1/' || true)"
  if [[ -z "${css_path}" ]]; then
    echo "ERROR: admin CSS asset was not found" >&2
    rm -f "${index_file}" "${css_file}"
    return 1
  fi

  css_url="$(resolve_site_asset_url "${css_path}")"
  curl --noproxy '*' -fsS "${css_url}" -o "${css_file}"
  if ! grep -Eiq "${pattern}" "${css_file}"; then
    echo "ERROR: ${label} did not match required pattern (${pattern}): ${css_url}" >&2
    rm -f "${index_file}" "${css_file}"
    return 1
  fi

  rm -f "${index_file}" "${css_file}"
}

build_local_images() {
  docker build -t "${LOCAL_IMAGE_REGISTRY}/serino-api:${SMOKE_TAG}" ./backend
  docker build -t "${LOCAL_IMAGE_REGISTRY}/serino-web:${SMOKE_TAG}" -f Dockerfile.caddy .
  docker build -t "${LOCAL_IMAGE_REGISTRY}/serino-waline:${SMOKE_TAG}" -f Dockerfile.waline .
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
    "${LOCAL_IMAGE_REGISTRY}/serino-api:${SMOKE_TAG}" \
    "${LOCAL_IMAGE_REGISTRY}/serino-web:${SMOKE_TAG}" \
    "${LOCAL_IMAGE_REGISTRY}/serino-waline:${SMOKE_TAG}" >/dev/null 2>&1 || true
  rm -f "${TMP_ENV_FILE}"
  if [[ -d "${TMP_STORE_DIR}" ]]; then
    docker run --rm -v "${TMP_STORE_DIR}:/target" alpine sh -c 'chmod -R 0777 /target >/dev/null 2>&1 || true' >/dev/null 2>&1 || true
  fi
  rm -rf "${TMP_STORE_DIR}" || true
}

trap 'cleanup $?' EXIT INT TERM

HTTP_PORT="${AERISUN_HTTP_PORT:-18080}"
HTTPS_PORT="${AERISUN_HTTPS_PORT:-18443}"
BACKEND_PORT="${AERISUN_PORT:-18000}"
WALINE_PORT="${WALINE_PORT:-18360}"
SITE_HOST="${AERISUN_SMOKE_HOST:-127.0.0.1}"
SITE_URL="http://${SITE_HOST}:${HTTP_PORT}"
PUBLIC_ORIGIN="${AERISUN_SMOKE_PUBLIC_ORIGIN:-https://smoke.aerisun.test}"
HEALTHCHECK_PATH="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/readyz}"
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
AERISUN_BOOTSTRAP_ADMIN_USERNAME=smoke-admin
AERISUN_BOOTSTRAP_ADMIN_PASSWORD=smoke-admin-pass
AERISUN_HTTP_PORT=${HTTP_PORT}
AERISUN_HTTPS_PORT=${HTTPS_PORT}
AERISUN_PORT=${BACKEND_PORT}
WALINE_PORT=${WALINE_PORT}
AERISUN_SENTRY_DSN=
VITE_SENTRY_DSN=
AERISUN_STORE_BIND_DIR=${TMP_STORE_DIR}
AERISUN_IMAGE_REGISTRY=${LOCAL_IMAGE_REGISTRY}
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
assert_cache_control "${SITE_URL}/posts" "frontend SPA fallback" "no-cache"
assert_cache_control "${SITE_URL}/sw.js" "frontend service worker" "no-cache"
assert_cache_control "${SITE_URL}/registerSW.js" "frontend service worker registration" "no-cache"
assert_body_not_contains "${SITE_URL}/sw.js" "service worker cache policy" "api-cache|bootstrap-cache|media-cache|asset-cache|precacheAndRoute|CacheFirst|createHandlerBoundToURL|workbox"
assert_body_contains "${SITE_URL}/sw.js" "service worker retirement" "registration\\.unregister\\("
assert_body_not_contains "${SITE_URL}/registerSW.js" "service worker registration shim" "serviceWorker\\.register|navigator\\.serviceWorker"
assert_runtime_css_contains "hero nav backdrop-filter" "\\.liquid-glass-nav-hero\\{[^}]*[;{]backdrop-filter:blur\\(24px\\)saturate\\(146%\\)"
assert_runtime_css_contains "hero nav prefixed backdrop-filter" "\\.liquid-glass-nav-hero\\{[^}]*-webkit-backdrop-filter:blur\\(24px\\)saturate\\(146%\\)"
assert_admin_css_contains "admin sidebar backdrop-filter" "\\.admin-glass-sidebar\\{[^}]*[;{]backdrop-filter:blur\\(var\\(--admin-blur-md\\)\\)[[:space:]]*saturate\\(var\\(--admin-saturate\\)\\)"
assert_admin_css_contains "admin sidebar prefixed backdrop-filter" "\\.admin-glass-sidebar\\{[^}]*-webkit-backdrop-filter:blur\\(var\\(--admin-blur-md\\)\\)[[:space:]]*saturate\\(var\\(--admin-saturate\\)\\)"

echo "Docker smoke test passed for ${SITE_URL}"
