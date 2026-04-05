#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"
export BACKEND_DIR

prepare_backend_runtime() {
  cd "${BACKEND_DIR}"
  export PYTHONPATH="${BACKEND_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
}

run_backend_python() {
  if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
    "${BACKEND_DIR}/.venv/bin/python" "$@"
    return
  fi
  uv run python "$@"
}

run_backend_alembic() {
  if [[ -x "${BACKEND_DIR}/.venv/bin/alembic" ]]; then
    "${BACKEND_DIR}/.venv/bin/alembic" "$@"
    return
  fi
  uv run alembic "$@"
}

run_backend_uvicorn() {
  if [[ -x "${BACKEND_DIR}/.venv/bin/uvicorn" ]]; then
    exec "${BACKEND_DIR}/.venv/bin/uvicorn" "$@"
  fi
  exec uv run uvicorn "$@"
}

source_env_file() {
  if [[ -f "$1" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$1"
    set +a
  fi
}

source_runtime_env_chain() {
  local env_name="${AERISUN_ENVIRONMENT:-development}"
  source_env_file "${PROJECT_DIR}/.env"
  source_env_file "${PROJECT_DIR}/.env.${env_name}"
  source_env_file "${PROJECT_DIR}/.env.${env_name}.local"
}
