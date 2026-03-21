#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

if [[ -f "${BACKEND_DIR}/.env" ]]; then
  set -a
  source "${BACKEND_DIR}/.env"
  set +a
fi

python - <<'PY'
from aerisun.settings import get_settings

get_settings().ensure_directories()
PY

uv run alembic upgrade head
uv run python -m aerisun.seed

exec "${SCRIPT_DIR}/serve.sh"
