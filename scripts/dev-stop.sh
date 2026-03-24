#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEV_DIR="${PROJECT_DIR}/.dev"
PID_FILE="${DEV_STACK_PID_FILE:-${DEV_DIR}/dev.pid}"

terminate_pid() {
  local pid="$1"
  if [[ -n "${pid:-}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    kill "${pid}" >/dev/null 2>&1 || true
  fi
}

terminate_process_tree() {
  local pid="$1"
  [[ -n "${pid:-}" ]] || return 0
  kill -0 "${pid}" >/dev/null 2>&1 || return 0

  local child=""
  while read -r child; do
    [[ -n "${child}" ]] || continue
    terminate_process_tree "${child}"
  done < <(pgrep -P "${pid}" || true)

  terminate_pid "${pid}"
}

main() {
  local launcher_pid=""
  local backend_pid=""
  local frontend_pid=""
  local admin_pid=""
  local skip_launcher="${DEV_STOP_SKIP_LAUNCHER:-0}"

  if [[ ! -f "${PID_FILE}" ]]; then
    echo "No dev stack running (${PID_FILE} not found)."
    return 0
  fi

  # shellcheck disable=SC1090
  source "${PID_FILE}"

  terminate_process_tree "${backend_pid:-}"
  terminate_process_tree "${frontend_pid:-}"
  terminate_process_tree "${admin_pid:-}"
  if [[ "${skip_launcher}" != "1" ]]; then
    terminate_process_tree "${launcher_pid:-}"
  fi

  sleep 2

  # SIGKILL 兜底
  for pid in "${backend_pid:-}" "${frontend_pid:-}" "${admin_pid:-}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
      kill -KILL "${pid}" >/dev/null 2>&1 || true
    fi
  done
  if [[ "${skip_launcher}" != "1" ]] && [[ -n "${launcher_pid:-}" ]] && kill -0 "${launcher_pid}" >/dev/null 2>&1; then
    kill -KILL "${launcher_pid}" >/dev/null 2>&1 || true
  fi

  rm -f "${PID_FILE}"
  echo "Stopped dev stack for this worktree."
}

main "$@"
