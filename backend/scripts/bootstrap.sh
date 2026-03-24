#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"
export BACKEND_DIR

# 进入后端目录，设置 PYTHONPATH 包含 src 以便导入 aerisun 包
cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

# 没有明确说明，默认环境是 development
_env="${AERISUN_ENVIRONMENT:-development}"

# Docker 里不是靠读文件，而是直接通过 docker-compose.yml 里的 environment: 把变量传进去
# 先读 .env，里面有通用配置
# 再读 .env.development，覆盖开发环境专用配置
# 再读 .env.local，覆盖本机个性化配置
# 再读 .env.development.local，优先级最高
_source_if_exists() { [[ -f "$1" ]] && { set -a; source "$1"; set +a; } || true; }
_source_if_exists "${PROJECT_DIR}/.env"
_source_if_exists "${PROJECT_DIR}/.env.${_env}"
_source_if_exists "${PROJECT_DIR}/.env.local"
_source_if_exists "${PROJECT_DIR}/.env.${_env}.local"

if [[ "$_env" == "development" ]]; then
  # 数据库预检：1、检测数据库结构有没有和迁移脚本不一致 2、检测种子数据的变化
  PREFLIGHT_JSON=$(uv run python -u - <<'PY'
import json, os
from pathlib import Path
from aerisun.core.settings import get_settings
from aerisun.core.db_preflight import run_preflight

settings = get_settings()
settings.ensure_directories()

backend_dir = Path(os.environ["BACKEND_DIR"])
result = run_preflight(
    db_path=settings.db_path,
    alembic_dir=backend_dir / "alembic",
    seed_path=backend_dir / "src" / "aerisun" / "core" / "seed.py",
)
print(json.dumps(result))
PY
  )
  PREFLIGHT_JSON="$PREFLIGHT_JSON" uv run python -u - <<'PY'
import json
import os

result = json.loads(os.environ["PREFLIGHT_JSON"])
print(f"数据库预检结果: {result.get('reason')}", flush=True)
PY

  FORCE_RESEED=false
  if echo "$PREFLIGHT_JSON" | uv run python -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('reseed') else 1)"; then
    FORCE_RESEED=true
  fi
# 生产环境不做预检
else
  uv run python -u - <<'PY'
from aerisun.core.settings import get_settings
get_settings().ensure_directories()
PY
fi

# 运行 Alembic 数据库迁移，自动升级到最新版本
uv run alembic upgrade head

FORCE_RESEED="${FORCE_RESEED:-false}" uv run python -u - <<'PY'
import os
from pathlib import Path

from aerisun.core.db_preflight import compute_seed_fingerprint, store_seed_fingerprint
from aerisun.core.seed import seed_reference_data
from aerisun.core.settings import get_settings


def log(message: str) -> None:
  print(message, flush=True)

settings = get_settings()
force_reseed = os.environ.get("FORCE_RESEED", "").lower() in {"true", "1"}

if settings.seed_reference_data:
    seed_reference_data(force=force_reseed)
    seed_path = Path(os.environ["BACKEND_DIR"]) / "src" / "aerisun" / "core" / "seed.py"
    if seed_path.exists():
        store_seed_fingerprint(settings.db_path, compute_seed_fingerprint(seed_path))
    log(f"种子数据已准备完成（force={force_reseed}）")
else:
    log("已跳过种子数据初始化，因为未启用 AERISUN_SEED_REFERENCE_DATA。")
PY

exec "${SCRIPT_DIR}/serve.sh"
