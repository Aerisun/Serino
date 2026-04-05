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

run_backend_python -u - <<'PY'
import os
import subprocess
import sys
from pathlib import Path

backend_dir = Path(os.environ["BACKEND_DIR"])
command = [sys.executable, "-m", "alembic", "upgrade", "head"]
process = subprocess.Popen(
    command,
    cwd=backend_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

assert process.stdout is not None

migration_steps = 0
captured_lines: list[str] = []

for raw_line in process.stdout:
    line = raw_line.rstrip("\n")
    captured_lines.append(line)
    if "Running upgrade" in line:
        migration_steps += 1
        print(".", end="", flush=True)

return_code = process.wait()
if migration_steps:
    print(f"     已完成 {migration_steps} 步迁移。", flush=True)
else:
    print("     数据库结构已是最新。", flush=True)

if return_code != 0:
    for line in captured_lines:
        print(line, file=sys.stderr)
    raise SystemExit(return_code)
PY

run_backend_python -u - <<'PY'
from aerisun.core.db import get_session_factory
from aerisun.domain.iam.service import repair_legacy_api_key_scopes

with get_session_factory()() as session:
    repaired = repair_legacy_api_key_scopes(session)

if repaired:
    print(f"已修复历史 API Key scope 存储：{repaired}", flush=True)
PY
