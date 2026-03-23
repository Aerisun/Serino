#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

# Source env files in layered order (later overrides earlier).
# In Docker, PROJECT_DIR is /app and these files won't exist —
# env vars are injected via docker-compose environment: directives instead.
_source_if_exists() { [[ -f "$1" ]] && { set -a; source "$1"; set +a; } || true; }

_env="${AERISUN_ENVIRONMENT:-development}"
_source_if_exists "${PROJECT_DIR}/.env"
_source_if_exists "${PROJECT_DIR}/.env.${_env}"
_source_if_exists "${PROJECT_DIR}/.env.local"
_source_if_exists "${PROJECT_DIR}/.env.${_env}.local"

python - <<'PY'
from aerisun.core.settings import get_settings

get_settings().ensure_directories()
PY

uv run alembic upgrade head

exec "${SCRIPT_DIR}/serve.sh"
