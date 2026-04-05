#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/runtime-lib.sh"

prepare_backend_runtime
run_backend_python -u - <<'PY'
from aerisun.core.settings import get_settings

get_settings().ensure_directories()
PY

run_backend_alembic upgrade head

run_backend_python -u - <<'PY'
from aerisun.core.db import get_session_factory
from aerisun.domain.iam.service import repair_legacy_api_key_scopes

with get_session_factory()() as session:
    repaired = repair_legacy_api_key_scopes(session)

if repaired:
    print(f"已修复历史 API Key scope 存储：{repaired}", flush=True)
PY
