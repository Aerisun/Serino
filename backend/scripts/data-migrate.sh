#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/runtime-lib.sh"

prepare_backend_runtime

command="${1:-apply}"
if [[ "$#" -gt 0 ]]; then
  shift
fi

mode="blocking"
json_mode="false"

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ "$#" -ge 2 ]] || {
        echo "缺少 --mode 的参数值。" >&2
        exit 1
      }
      mode="$2"
      shift 2
      ;;
    --json)
      json_mode="true"
      shift
      ;;
    *)
      echo "不支持的参数：$1" >&2
      exit 1
      ;;
  esac
done

case "${command}" in
  apply)
    MODE="${mode}" run_backend_python -u - <<'PY'
import os

from aerisun.core.data_migrations.runner import apply_pending_data_migrations
from aerisun.core.settings import get_settings


def log(message: str) -> None:
    print(message, flush=True)


settings = get_settings()
settings.ensure_directories()
mode = os.environ["MODE"]
applied = apply_pending_data_migrations(mode=mode)
if applied:
    log(f"已执行版本化数据迁移（mode={mode}）：{', '.join(applied)}")
else:
    log(f"没有待执行的版本化数据迁移（mode={mode}）。")
PY
    ;;
  schedule)
    MODE="${mode}" run_backend_python -u - <<'PY'
import os

from aerisun.core.data_migrations.runner import schedule_pending_background_data_migrations
from aerisun.core.settings import get_settings


def log(message: str) -> None:
    print(message, flush=True)


settings = get_settings()
settings.ensure_directories()
mode = os.environ["MODE"]
if mode != "background":
    raise SystemExit("schedule 仅支持 --mode background")
scheduled = schedule_pending_background_data_migrations()
if scheduled:
    log(f"已调度后台数据迁移：{', '.join(scheduled)}")
else:
    log("没有待调度的后台数据迁移。")
PY
    ;;
  status)
    JSON_MODE="${json_mode}" run_backend_python -u - <<'PY'
import json
import os

from aerisun.core.data_migrations.runner import collect_migration_status

payload = collect_migration_status()
if os.environ["JSON_MODE"] == "true":
    print(json.dumps(payload, ensure_ascii=False), flush=True)
else:
    baseline = payload.get("baseline") or {}
    print(f"schema revision: {payload.get('current_revision') or '<missing>'}", flush=True)
    print(f"schema heads: {', '.join(payload.get('head_revisions') or []) or '<none>'}", flush=True)
    print(f"baseline: {baseline.get('migration_key') or '<missing>'}", flush=True)
    print(f"blocking pending: {', '.join(payload['blocking']['pending']) or '<none>'}", flush=True)
    print(f"blocking failed: {', '.join(payload['blocking']['failed']) or '<none>'}", flush=True)
    print(f"background pending: {', '.join(payload['background']['pending']) or '<none>'}", flush=True)
    print(f"background scheduled: {', '.join(payload['background']['scheduled']) or '<none>'}", flush=True)
    print(f"background running: {', '.join(payload['background']['running']) or '<none>'}", flush=True)
    print(f"background failed: {', '.join(payload['background']['failed']) or '<none>'}", flush=True)
PY
    ;;
  *)
    echo "不支持的命令：${command}" >&2
    exit 1
    ;;
esac
