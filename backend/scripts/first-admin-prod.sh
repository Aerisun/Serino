#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/runtime-lib.sh"

prepare_backend_runtime
run_backend_python -u - <<'PY'
from aerisun.core.bootstrap_admin import ensure_first_boot_default_admin
from aerisun.core.settings import get_settings


def log(message: str) -> None:
    print(message, flush=True)


settings = get_settings()
settings.ensure_directories()

created = ensure_first_boot_default_admin(is_first_boot=True)
if created:
    log("已创建生产环境首次管理员账号。")
else:
    log("首次管理员已存在，跳过创建。")
PY
