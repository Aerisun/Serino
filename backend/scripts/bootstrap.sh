#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/runtime-lib.sh"

prepare_backend_runtime

# 没有明确说明，默认环境是 development
_env="${AERISUN_ENVIRONMENT:-development}"
source_runtime_env_chain

if [[ "$_env" == "development" || "$_env" == "test" ]]; then
  # 数据库预检：1、检测数据库结构有没有和迁移脚本不一致 2、检测种子数据的变化
  PREFLIGHT_JSON=$(run_backend_python -u - <<'PY'
import json, os
from pathlib import Path
from aerisun.core.settings import get_settings
from aerisun.core.db_preflight import run_preflight
from aerisun.core.seed_profile import normalize_seed_profile, resolve_seed_path

settings = get_settings()
settings.ensure_directories()
seed_profile = normalize_seed_profile(os.environ.get(
    "AERISUN_SEED_PROFILE",
    "dev-seed" if settings.environment == "development" and settings.seed_dev_data else "seed",
))

backend_dir = Path(os.environ["BACKEND_DIR"])
result = run_preflight(
    db_path=settings.db_path,
    alembic_dir=backend_dir / "alembic",
    seed_path=resolve_seed_path(backend_dir / "src" / "aerisun" / "core", seed_profile=seed_profile),
    seed_profile=seed_profile,
)
print(json.dumps(result))
PY
  )
  PREFLIGHT_JSON="$PREFLIGHT_JSON" run_backend_python -u - <<'PY'
import json
import os

result = json.loads(os.environ["PREFLIGHT_JSON"])
print(f"数据库预检结果: {result.get('reason')}", flush=True)
PY

  FORCE_RESEED=false
  if echo "$PREFLIGHT_JSON" | run_backend_python -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('reseed') else 1)"; then
    FORCE_RESEED=true
  fi
else
  run_backend_python -u - <<'PY'
from aerisun.core.settings import get_settings
get_settings().ensure_directories()
PY
fi

# 运行 Alembic 数据库迁移，自动升级到最新版本
run_backend_alembic upgrade head

if [[ "$_env" == "development" || "$_env" == "test" ]]; then
  FORCE_RESEED="${FORCE_RESEED:-false}" run_backend_python -u - <<'PY'
import os
from pathlib import Path
from importlib import import_module

from aerisun.core.db_preflight import compute_seed_fingerprint, store_seed_metadata
from aerisun.core.seed_profile import normalize_seed_profile, resolve_seed_module_name, resolve_seed_path
from aerisun.core.settings import get_settings


def log(message: str) -> None:
  print(message, flush=True)

settings = get_settings()
force_reseed = os.environ.get("FORCE_RESEED", "").lower() in {"true", "1"}
seed_profile = normalize_seed_profile(os.environ.get(
    "AERISUN_SEED_PROFILE",
    "dev-seed" if settings.seed_dev_data else "seed",
))
seed_module = import_module(resolve_seed_module_name(seed_profile))
seed_path = resolve_seed_path(Path(os.environ["BACKEND_DIR"]) / "src" / "aerisun" / "core", seed_profile=seed_profile)

if settings.seed_reference_data:
    seed_module.seed_reference_data(force=force_reseed)
    if seed_path.exists():
        store_seed_metadata(
            settings.db_path,
            fingerprint=compute_seed_fingerprint(seed_path, seed_profile=seed_profile),
        )
    log(
        "种子数据已准备完成"
        f"（profile={seed_profile}, module={seed_module.__name__}, force={force_reseed}）"
    )
else:
    log("已跳过种子数据初始化，因为未启用 AERISUN_SEED_REFERENCE_DATA。")
PY
else
  run_backend_python -u - <<'PY'
from aerisun.core.settings import get_settings

get_settings().ensure_directories()
print("生产运行时不会在应用启动阶段自动执行 baseline 或数据迁移。", flush=True)
PY
fi

exec "${SCRIPT_DIR}/serve.sh"
