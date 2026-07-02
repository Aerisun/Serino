#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"
export BACKEND_DIR

ensure_runtime_identity() {
  local current_uid current_gid group_name home_dir nss_dir passwd_file group_file nss_wrapper_lib

  current_uid="$(id -u)"
  current_gid="$(id -g)"
  if getent passwd "${current_uid}" >/dev/null 2>&1; then
    return
  fi

  nss_wrapper_lib="$(find /usr/lib -name libnss_wrapper.so -print -quit 2>/dev/null || true)"
  if [[ -z "${nss_wrapper_lib}" ]]; then
    echo "WARN: current UID ${current_uid} has no passwd entry and libnss_wrapper is unavailable." >&2
    return
  fi

  group_name="${AERISUN_RUNTIME_GROUP_NAME:-aerisun-runtime}"
  home_dir="${HOME:-/tmp}"
  nss_dir="${XDG_RUNTIME_DIR:-/tmp}/aerisun-nss-wrapper-${current_uid}"
  passwd_file="${nss_dir}/passwd"
  group_file="${nss_dir}/group"

  mkdir -p "${nss_dir}"
  chmod 700 "${nss_dir}"
  printf 'aerisun-runtime:x:%s:%s:Aerisun runtime:%s:/usr/sbin/nologin\n' \
    "${current_uid}" "${current_gid}" "${home_dir}" >"${passwd_file}"
  printf '%s:x:%s:\n' "${group_name}" "${current_gid}" >"${group_file}"

  export NSS_WRAPPER_PASSWD="${passwd_file}"
  export NSS_WRAPPER_GROUP="${group_file}"
  case ":${LD_PRELOAD:-}:" in
    *":${nss_wrapper_lib}:"*) ;;
    *) export LD_PRELOAD="${nss_wrapper_lib}${LD_PRELOAD:+:${LD_PRELOAD}}" ;;
  esac
}

prepare_backend_runtime() {
  ensure_runtime_identity
  cd "${BACKEND_DIR}"
  export PYTHONPATH="${BACKEND_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
}

run_backend_python() {
  if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
    "${BACKEND_DIR}/.venv/bin/python" "$@"
    return
  fi
  uv run python "$@"
}

run_backend_alembic() {
  if [[ -x "${BACKEND_DIR}/.venv/bin/alembic" ]]; then
    "${BACKEND_DIR}/.venv/bin/alembic" "$@"
    return
  fi
  uv run alembic "$@"
}

run_backend_uvicorn() {
  if [[ -x "${BACKEND_DIR}/.venv/bin/uvicorn" ]]; then
    exec "${BACKEND_DIR}/.venv/bin/uvicorn" "$@"
  fi
  exec uv run uvicorn "$@"
}

source_env_file() {
  if [[ -f "$1" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$1"
    set +a
  fi
}

source_runtime_env_chain() {
  local env_name="${AERISUN_ENVIRONMENT:-development}"
  source_env_file "${PROJECT_DIR}/.env"
  source_env_file "${PROJECT_DIR}/.env.${env_name}"
  source_env_file "${PROJECT_DIR}/.env.${env_name}.local"
}
