#!/usr/bin/env bash
# DEPRECATED: This script is not part of the main development workflow.
# Use 'make dev' (which calls scripts/dev-start.sh) instead.
# This file is retained for reference and may be removed in a future cleanup.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=./process-env.sh
source "${SCRIPT_DIR}/process-env.sh"

WALINE_DIR="${AERISUN_WALINE_SOURCE_DIR:-${AERISUN_COMMON_ROOT}/temp/waline}"

if [[ ! -d "${WALINE_DIR}" ]]; then
  echo "Waline source not found: ${WALINE_DIR}" >&2
  exit 1
fi

if [[ ! -d "${WALINE_DIR}/packages/server/node_modules/thinkjs" ]]; then
  pnpm --dir "${WALINE_DIR}" --filter @waline/vercel install --frozen-lockfile --prefer-offline --prod
fi

if ! (cd "${WALINE_DIR}" && node -e "require('sqlite3')"); then
  npm_config_build_from_source=true pnpm --dir "${WALINE_DIR}" rebuild sqlite3
fi

cd "${WALINE_DIR}/packages/server"

exec env \
  JWT_TOKEN="${JWT_TOKEN}" \
  SECURE_DOMAINS="${SECURE_DOMAINS}" \
  AVATAR_PROXY="${AVATAR_PROXY}" \
  GRAVATAR_STR="${GRAVATAR_STR}" \
  SERVER_URL="${WALINE_SERVER_URL}" \
  SITE_URL="${SITE_URL}" \
  SITE_NAME="${SITE_NAME}" \
  SQLITE_PATH="${SQLITE_PATH}" \
  SQLITE_DB="${SQLITE_DB}" \
  node development.js "${WALINE_PORT}"
