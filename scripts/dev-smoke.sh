#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/.env.local"
DEV_DIR="${PROJECT_DIR}/.dev"
LOG_FILE="${DEV_DIR}/dev-smoke.log"

PID_FILE="${DEV_DIR}/dev.pid"

backend_port="${BACKEND_PORT:-${AERISUN_PORT:-8000}}"
frontend_port="${FRONTEND_PORT:-${AERISUN_FRONTEND_PORT:-5173}}"
admin_port="${ADMIN_PORT:-${AERISUN_ADMIN_PORT:-5174}}"
healthcheck_path="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"
admin_base_path="${AERISUN_ADMIN_BASE_PATH:-/admin/}"

source_env_file() {
  local env_file="$1"
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a
  fi
}

ensure_trailing_slash() {
  local value="$1"
  if [[ "${value}" == */ ]]; then
    printf '%s' "${value}"
    return 0
  fi
  printf '%s/' "${value}"
}

load_env_ports() {
  local env_name="${AERISUN_ENVIRONMENT:-development}"
  source_env_file "${PROJECT_DIR}/.env"
  source_env_file "${PROJECT_DIR}/.env.${env_name}"
  source_env_file "${PROJECT_DIR}/.env.local"
  source_env_file "${PROJECT_DIR}/.env.${env_name}.local"
  backend_port="${BACKEND_PORT:-${AERISUN_PORT:-8000}}"
  frontend_port="${FRONTEND_PORT:-${AERISUN_FRONTEND_PORT:-5173}}"
  admin_port="${ADMIN_PORT:-${AERISUN_ADMIN_PORT:-5174}}"
  healthcheck_path="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"
  admin_base_path="$(ensure_trailing_slash "${AERISUN_ADMIN_BASE_PATH:-/admin/}")"
}

url_is_ready() {
  local url="$1"
  curl --noproxy '*' -fsS -o /dev/null "${url}"
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local timeout_seconds="${3:-90}"
  local start_seconds
  start_seconds=$(date +%s)

  while true; do
    if url_is_ready "${url}"; then
      echo "${label} is ready: ${url}"
      return 0
    fi
    if [[ $(( $(date +%s) - start_seconds )) -ge ${timeout_seconds} ]]; then
      echo "ERROR: timed out waiting for ${label}: ${url}" >&2
      return 1
    fi
    sleep 1
  done
}

wait_for_stack_ready() {
  wait_for_url "http://127.0.0.1:${backend_port}${healthcheck_path}" "backend"
  wait_for_url "http://127.0.0.1:${frontend_port}/" "frontend"
  wait_for_url "http://127.0.0.1:${admin_port}${admin_base_path}" "admin"
}

# ── 检测 make dev 是否已经在运行 ──────────────────────────
make_dev_is_running() {
  [[ -f "${PID_FILE}" ]] || return 1
  local launcher_pid=""
  # shellcheck disable=SC1090
  source "${PID_FILE}"
  [[ -n "${launcher_pid:-}" ]] && kill -0 "${launcher_pid}" >/dev/null 2>&1
}

# ── 主逻辑 ────────────────────────────────────────────────
mkdir -p "${DEV_DIR}"

managed_stack=0
managed_stack_launcher_pid=""

if make_dev_is_running; then
  # make dev 已在运行，直接复用，测试完后不清理
  echo "检测到 make dev 已在运行，复用现有开发栈进行冒烟测试。"
  load_env_ports
else
  # make dev 未运行，自己启动临时开发栈，测试完后清理
  managed_stack=1
  echo "未检测到 make dev，启动临时开发栈..."

  if [[ ! -f "${ENV_FILE}" ]]; then
    bash "${PROJECT_DIR}/scripts/setup-ports.sh"
  fi
  load_env_ports

  nohup bash -lc "cd '${PROJECT_DIR}' && bash ./scripts/dev-start.sh" >"${LOG_FILE}" 2>&1 &
  managed_stack_launcher_pid=$!
fi

cleanup() {
  # 仅在自己启动了开发栈时才清理；复用 make dev 时什么都不做
  if [[ "${managed_stack}" == "1" ]]; then
    bash "${SCRIPT_DIR}/dev-stop.sh" >/dev/null 2>&1 || true
    [[ -n "${managed_stack_launcher_pid:-}" ]] && wait "${managed_stack_launcher_pid}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM ERR

# 等待开发栈就绪
wait_for_stack_ready

# ========== 测试区 =============





# ===============================



echo "Development smoke test passed. Logs: ${LOG_FILE}"
