#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

UVICORN_ARGS=(
  aerisun.main:app
  --host "${AERISUN_HOST:-0.0.0.0}"
  --port "${AERISUN_PORT:-8000}"
)

if [[ "${AERISUN_DEV_RELOAD:-0}" == "1" ]]; then
  UVICORN_ARGS+=(
    --reload
    --reload-dir "${BACKEND_DIR}/src"
  )
fi

exec uv run uvicorn "${UVICORN_ARGS[@]}"
