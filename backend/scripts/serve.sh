#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/runtime-lib.sh"

prepare_backend_runtime

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

run_backend_uvicorn "${UVICORN_ARGS[@]}"
