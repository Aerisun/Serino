#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/runtime-lib.sh"

prepare_backend_runtime
run_backend_python -u - <<'PY'
from aerisun.core.production_baseline import apply_production_baseline
from aerisun.core.settings import get_settings


def log(message: str) -> None:
    print(message, flush=True)


settings = get_settings()
settings.ensure_directories()

applied = apply_production_baseline()
if applied:
    log("生产 baseline 已完成。")
else:
    log("生产 baseline 已存在，跳过。")
PY
