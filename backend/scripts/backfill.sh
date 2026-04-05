#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/runtime-lib.sh"

prepare_backend_runtime
run_backend_python -u - <<'PY'
from aerisun.core.backfills.runner import run_pending_backfills
from aerisun.core.settings import get_settings


def log(message: str) -> None:
    print(message, flush=True)


settings = get_settings()
settings.ensure_directories()

if settings.data_backfill_enabled:
    applied = run_pending_backfills()
    if applied:
        log(f"已执行升级数据回填：{', '.join(applied)}")
    else:
        log("没有待执行的升级数据回填。")
else:
    log("已跳过升级数据回填，因为未启用 AERISUN_DATA_BACKFILL_ENABLED。")
PY
