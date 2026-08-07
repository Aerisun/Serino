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
progress_mode="false"
defer_cleanup="false"

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
    --progress)
      progress_mode="true"
      shift
      ;;
    --defer-cleanup)
      defer_cleanup="true"
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
    MODE="${mode}" PROGRESS_MODE="${progress_mode}" DEFER_CLEANUP="${defer_cleanup}" run_backend_python -u - <<'PY'
import os

from aerisun.core.data_migrations.registry import DataMigrationSpec
from aerisun.core.data_migrations.runner import apply_pending_data_migrations
from aerisun.core.settings import get_settings


def log(message: str) -> None:
    print(message, flush=True)


settings = get_settings()
settings.ensure_directories()
mode = os.environ["MODE"]
progress_mode = os.environ["PROGRESS_MODE"] == "true"
defer_cleanup = os.environ["DEFER_CLEANUP"] == "true"


def mark_progress(_spec: DataMigrationSpec) -> None:
    print(".", end="", flush=True)


applied = apply_pending_data_migrations(
    mode=mode,
    on_applied=mark_progress if progress_mode else None,
    defer_cleanup=defer_cleanup,
)
if progress_mode:
    if applied:
        print("", flush=True)
elif applied:
    log(f"已执行版本化数据迁移（mode={mode}）：{', '.join(applied)}")
else:
    log(f"没有待执行的版本化数据迁移（mode={mode}）。")
PY
    ;;
  cleanup)
    MODE="${mode}" run_backend_python -u - <<'PY'
import os

from aerisun.core.data_migrations.runner import cleanup_applied_data_migrations
from aerisun.core.settings import get_settings

get_settings().ensure_directories()
cleaned = cleanup_applied_data_migrations(mode=os.environ["MODE"])
if cleaned:
    print(f"已清理版本化数据迁移旧副本：{', '.join(cleaned)}", flush=True)
else:
    print("没有待清理的版本化数据迁移旧副本。", flush=True)
PY
    ;;
  rollback-external)
    MODE="${mode}" run_backend_python -u - <<'PY'
import os

from aerisun.core.data_migrations.runner import rollback_external_data_migrations
from aerisun.core.settings import get_settings

get_settings().ensure_directories()
rolled_back = rollback_external_data_migrations(mode=os.environ["MODE"])
if rolled_back:
    print(f"已撤销版本化数据迁移创建的外部副本：{', '.join(rolled_back)}", flush=True)
else:
    print("没有待撤销的版本化数据迁移外部副本。", flush=True)
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
    print(f"blocking running: {', '.join(payload['blocking']['running']) or '<none>'}", flush=True)
    print(f"blocking failed: {', '.join(payload['blocking']['failed']) or '<none>'}", flush=True)
    print(f"blocking cleanup pending: {', '.join(payload['blocking']['cleanup_pending']) or '<none>'}", flush=True)
    print(f"background pending: {', '.join(payload['background']['pending']) or '<none>'}", flush=True)
    print(f"background scheduled: {', '.join(payload['background']['scheduled']) or '<none>'}", flush=True)
    print(f"background running: {', '.join(payload['background']['running']) or '<none>'}", flush=True)
    print(f"background failed: {', '.join(payload['background']['failed']) or '<none>'}", flush=True)
    print(f"background cleanup pending: {', '.join(payload['background']['cleanup_pending']) or '<none>'}", flush=True)
PY
    ;;
  *)
    echo "不支持的命令：${command}" >&2
    exit 1
    ;;
esac
