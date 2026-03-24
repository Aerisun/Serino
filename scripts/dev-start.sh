#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEV_DIR="${PROJECT_DIR}/.dev"
PID_FILE="${DEV_STACK_PID_FILE:-${DEV_DIR}/dev.pid}"

source_env_file() {
  if [[ -f "$1" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$1"
    set +a
  fi
}

log() {
  echo "$*"
}

wait_for_backend_ready() {
  local health_url="$1"
  local backend_pid="$2"


  while true; do
    if curl -fsS "${health_url}" >/dev/null 2>&1; then
      log "✅ 后端健康检查已通过"
      return 0
    fi

    if ! kill -0 "${backend_pid}" >/dev/null 2>&1; then
      echo "ERROR: backend process ${backend_pid} exited before becoming ready." >&2
      return 1
    fi

    sleep 1
  done
}

if [[ ! -f "${PROJECT_DIR}/.env.local" ]]; then
  echo "ERROR: .env.local is missing. Run 'make setup-ports' first." >&2
  exit 1
fi

source_env_file "${PROJECT_DIR}/.env.local"

mkdir -p "${DEV_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  existing_launcher_pid=""
  # shellcheck disable=SC1090
  source "${PID_FILE}"
  if [[ -n "${launcher_pid:-}" ]] && kill -0 "${launcher_pid}" >/dev/null 2>&1; then
    backend_port="${BACKEND_PORT:-8000}"
    frontend_port="${FRONTEND_PORT:-5173}"
    admin_port="${ADMIN_PORT:-5174}"
    printf '%s\n' \
      "🧐 当前工作树已有开发栈在运行: ${PID_FILE}" \
      "👉 运行端口：backend:${backend_port} frontend:${frontend_port} admin:${admin_port}" >&2
    exit 1
  fi
  rm -f "${PID_FILE}"
fi

cleanup() {
  DEV_STOP_SKIP_LAUNCHER=1 bash "${SCRIPT_DIR}/dev-stop.sh" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

echo "==> 开发环境下：正在启动后端，并在就绪后并行启动前台和管理后台..."

bash "${PROJECT_DIR}/backend/scripts/bootstrap.sh" &
backend_pid=$!


cat >"${PID_FILE}" <<EOF
launcher_pid=$$
backend_pid=$backend_pid
frontend_pid=
admin_pid=
project_dir=${PROJECT_DIR}
EOF

backend_health_url="http://127.0.0.1:${AERISUN_PORT:-8000}/api/v1/public/healthz"
# 后端检查到位后才启动前台和管理后台
wait_for_backend_ready "${backend_health_url}" "${backend_pid}"

( cd "${PROJECT_DIR}/frontend" && npx vite --mode development ) &
frontend_pid=$!

( cd "${PROJECT_DIR}/admin" && npx vite --mode development ) &
admin_pid=$!

cat >"${PID_FILE}" <<EOF
launcher_pid=$$
backend_pid=$backend_pid
frontend_pid=$frontend_pid
admin_pid=$admin_pid
project_dir=${PROJECT_DIR}
EOF

echo "🎊 后端开发栈已启动。PID 已写入 ${PID_FILE}"

pids=("$backend_pid" "$frontend_pid" "$admin_pid")
while true; do
  wait -n "${pids[@]}" || true

  for pid in "${pids[@]}"; do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      echo "ERROR: 后端开发进程 ${pid} 意外退出。正在停止整个开发栈..." >&2
      cleanup
      exit 1
    fi
  done

  sleep 1
done