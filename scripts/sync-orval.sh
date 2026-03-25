#!/usr/bin/env bash
# 启动前的 Orval 同步流程：
# 1. 先用后端当前环境导出最新 OpenAPI 规范。
# 2. 再分别比较 admin / frontend 的生成输入有没有变化。
#    输入包括 openapi.json、orval 配置、package.json 和 mutator。
# 3. 只有检测到变化时才运行 Orval 重新生成接口代码。
# 4. 如果没有变化就直接跳过，避免每次 make dev 都全量重生成。
# 5. 最后由 dev-start.sh 继续启动 backend、frontend、admin。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEV_DIR="${PROJECT_DIR}/.dev"
STATE_FILE="${DEV_DIR}/orval-state.env"

log() {
  echo "$*"
}

resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi

  echo "ERROR: python3/python 未安装，无法导出 OpenAPI 规范。" >&2
  exit 1
}

run_export_openapi() {
  if command -v uv >/dev/null 2>&1; then
    ( cd "${PROJECT_DIR}/backend" && uv run python "${SCRIPT_DIR}/export-openapi.py" )
    return 0
  fi

  if [[ -x "${PROJECT_DIR}/backend/.venv/bin/python" ]]; then
    ( cd "${PROJECT_DIR}/backend" && "${PROJECT_DIR}/backend/.venv/bin/python" "${SCRIPT_DIR}/export-openapi.py" )
    return 0
  fi

  local python_cmd
  python_cmd="$(resolve_python)"
  ( cd "${PROJECT_DIR}/backend" && "${python_cmd}" "${SCRIPT_DIR}/export-openapi.py" )
}

fingerprint_files() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$@" | sha256sum | awk '{print $1}'
    return 0
  fi

  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$@" | shasum -a 256 | awk '{print $1}'
    return 0
  fi

  echo "ERROR: sha256sum/shasum 未安装，无法比对 Orval 输入变更。" >&2
  exit 1
}

run_orval_if_needed() {
  local label="$1"
  local package_dir="$2"
  local output_file="$3"
  local state_key="$4"
  shift 4

  local fingerprint
  fingerprint="$(fingerprint_files "$@")"
  local previous="${!state_key:-}"

  if [[ ! -f "${PROJECT_DIR}/${output_file}" ]]; then
    log "==> ${label} 生成产物缺失，正在运行 Orval..."
    ( cd "${PROJECT_DIR}/${package_dir}" && npx orval )
  elif [[ "${fingerprint}" != "${previous}" ]]; then
    log "==> 检测到 ${label} API 变更，正在运行 Orval..."
    ( cd "${PROJECT_DIR}/${package_dir}" && npx orval )
  else
    log "==> ${label} API 未变化，跳过 Orval"
  fi

  printf -v "${state_key}" "%s" "${fingerprint}"
}

mkdir -p "${DEV_DIR}"

if [[ -f "${STATE_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${STATE_FILE}"
fi

log "==> 正在导出 OpenAPI 规范..."
run_export_openapi

run_orval_if_needed \
  "admin" \
  "admin" \
  "admin/src/api/generated/admin/admin.ts" \
  "admin_codegen_fingerprint" \
  "${PROJECT_DIR}/packages/api-client/openapi.json" \
  "${PROJECT_DIR}/admin/orval.config.ts" \
  "${PROJECT_DIR}/admin/package.json" \
  "${PROJECT_DIR}/admin/src/api/mutator/custom-instance.ts"

run_orval_if_needed \
  "frontend" \
  "frontend" \
  "frontend/src/lib/api/generated/public/public.ts" \
  "frontend_codegen_fingerprint" \
  "${PROJECT_DIR}/packages/api-client/openapi.json" \
  "${PROJECT_DIR}/frontend/orval.config.ts" \
  "${PROJECT_DIR}/frontend/package.json" \
  "${PROJECT_DIR}/frontend/src/lib/api/mutator/custom-fetch.ts"

run_orval_if_needed \
  "contract-schemas" \
  "packages/api-client" \
  "packages/api-client/src/generated/schemas.zod.ts" \
  "contract_codegen_fingerprint" \
  "${PROJECT_DIR}/packages/api-client/openapi.json" \
  "${PROJECT_DIR}/packages/api-client/orval.config.ts" \
  "${PROJECT_DIR}/packages/api-client/package.json"

cat >"${STATE_FILE}" <<EOF
admin_codegen_fingerprint=${admin_codegen_fingerprint}
frontend_codegen_fingerprint=${frontend_codegen_fingerprint}
contract_codegen_fingerprint=${contract_codegen_fingerprint}
EOF
