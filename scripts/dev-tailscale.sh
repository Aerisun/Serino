#!/usr/bin/env bash
# shellcheck shell=bash

DEV_TAILSCALE_BEGIN_MARKER="# ── AUTO:dev-tailscale ──"
DEV_TAILSCALE_END_MARKER="# ── /AUTO:dev-tailscale ──"
DEV_TAILSCALE_SUDO_READY=0
DEV_TAILSCALE_SUDO_KEEPALIVE_PID=""

dev_tailscale_is_truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

dev_tailscale_validate_port() {
  local name="$1"
  local port="$2"

  if [[ ! "${port}" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
    echo "ERROR: invalid ${name} port for Tailscale Serve: ${port}" >&2
    return 1
  fi
}

dev_tailscale_require_cli() {
  if ! command -v tailscale >/dev/null 2>&1; then
    echo "ERROR: tailscale CLI is not installed or not in PATH." >&2
    return 1
  fi
}

dev_tailscale_run() {
  local output=""

  if output="$("$@" 2>&1)"; then
    return 0
  fi

  if [[ "${output}" == *"handler does not exist"* ]]; then
    printf '%s\n' "${output}" >&2
    return 2
  fi

  if (( EUID != 0 )) && command -v sudo >/dev/null 2>&1; then
    if [[ "${DEV_TAILSCALE_SUDO_READY}" != "1" ]]; then
      echo "==> 需要 sudo 权限更新 Tailscale Serve 配置；如有提示请输入 sudo 密码。"
      sudo -v || return 1
      DEV_TAILSCALE_SUDO_READY=1
    fi

    if output="$(sudo "$@" 2>&1)"; then
      return 0
    fi
  fi

  [[ -z "${output}" ]] || printf '%s\n' "${output}" >&2
  echo "ERROR: Tailscale Serve requires permission to update serve config." >&2
  echo "Run 'sudo -v' before 'make dev-ts', or run 'sudo tailscale set --operator=\$USER' once." >&2
  return 1
}

dev_tailscale_ensure_sudo() {
  if (( EUID == 0 )); then
    DEV_TAILSCALE_SUDO_READY=1
    return 0
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    echo "ERROR: sudo is required to manage Tailscale Serve." >&2
    return 1
  fi

  if sudo -n -v >/dev/null 2>&1; then
    DEV_TAILSCALE_SUDO_READY=1
    return 0
  fi

  echo "==> dev-ts 需要 sudo 权限更新 Tailscale Serve 配置；请输入 sudo 密码。"
  sudo -v
  DEV_TAILSCALE_SUDO_READY=1
}

dev_tailscale_start_sudo_keepalive() {
  dev_tailscale_ensure_sudo

  if (( EUID == 0 )) || [[ -n "${DEV_TAILSCALE_SUDO_KEEPALIVE_PID}" ]]; then
    return 0
  fi

  (
    while true; do
      sudo -n -v >/dev/null 2>&1 || exit 0
      sleep 60
    done
  ) &
  DEV_TAILSCALE_SUDO_KEEPALIVE_PID=$!
}

dev_tailscale_stop_sudo_keepalive() {
  if [[ -n "${DEV_TAILSCALE_SUDO_KEEPALIVE_PID}" ]] \
    && kill -0 "${DEV_TAILSCALE_SUDO_KEEPALIVE_PID}" >/dev/null 2>&1; then
    kill "${DEV_TAILSCALE_SUDO_KEEPALIVE_PID}" >/dev/null 2>&1 || true
  fi
  DEV_TAILSCALE_SUDO_KEEPALIVE_PID=""
}

dev_tailscale_host() {
  local host=""

  host="$(
    tailscale status --json --peers=false 2>/dev/null \
      | sed -n 's/.*"DNSName"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
      | head -n 1
  )"
  host="${host%.}"

  if [[ -z "${host}" ]]; then
    host="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
  fi

  printf '%s' "${host}"
}

dev_tailscale_ip() {
  tailscale ip -4 2>/dev/null | head -n 1 || true
}

dev_tailscale_print_urls() {
  local frontend_port="$1"
  local admin_port="$2"
  local host
  local tailnet_ip

  host="$(dev_tailscale_host)"
  tailnet_ip="$(dev_tailscale_ip)"
  if [[ -z "${host}" ]]; then
    printf '\n%s\n\n' "👉  Tailscale Serve 已开启   frontend:${frontend_port}  admin:${admin_port}"
    return 0
  fi

  printf '\n%s\n%s\n%s\n' \
    "👉  Tailscale Serve 已开启，其他设备可通过 Tailnet 访问：" \
    "    前台：    http://${host}:${frontend_port}/" \
    "    管理后台：http://${host}:${admin_port}/admin/"

  if [[ -n "${tailnet_ip}" ]]; then
    printf '%s\n%s\n' \
      "    备用前台：http://${tailnet_ip}:${frontend_port}/" \
      "    备用后台：http://${tailnet_ip}:${admin_port}/admin/"
  fi

  printf '\n'
}

dev_tailscale_upsert_env_block() {
  local env_file="$1"
  local frontend_port="$2"
  local admin_port="$3"
  local block

  block="${DEV_TAILSCALE_BEGIN_MARKER}
AERISUN_DEV_TAILSCALE_SERVE_ENABLED=true
AERISUN_DEV_TAILSCALE_FRONTEND_PORT=${frontend_port}
AERISUN_DEV_TAILSCALE_ADMIN_PORT=${admin_port}
${DEV_TAILSCALE_END_MARKER}"

  if [[ -f "${env_file}" ]] && grep -qF "${DEV_TAILSCALE_BEGIN_MARKER}" "${env_file}"; then
    local tmp
    tmp="$(mktemp)"
    awk -v begin="${DEV_TAILSCALE_BEGIN_MARKER}" -v end="${DEV_TAILSCALE_END_MARKER}" -v block="${block}" '
      $0 == begin { skip=1; if (!printed) { print block; printed=1 } next }
      $0 == end   { skip=0; next }
      !skip
    ' "${env_file}" > "${tmp}"
    mv "${tmp}" "${env_file}"
  else
    [[ -f "${env_file}" ]] && printf '\n' >> "${env_file}"
    printf '%s\n' "${block}" >> "${env_file}"
  fi
}

dev_tailscale_remove_env_block() {
  local env_file="$1"

  [[ -f "${env_file}" ]] || return 0
  grep -qF "${DEV_TAILSCALE_BEGIN_MARKER}" "${env_file}" || return 0

  local tmp
  tmp="$(mktemp)"
  awk -v begin="${DEV_TAILSCALE_BEGIN_MARKER}" -v end="${DEV_TAILSCALE_END_MARKER}" '
    $0 == begin { skip=1; next }
    $0 == end   { skip=0; next }
    !skip
  ' "${env_file}" > "${tmp}"
  mv "${tmp}" "${env_file}"
}

dev_tailscale_disable_ports() {
  local frontend_port="$1"
  local admin_port="$2"
  local port=""
  local seen=" "
  local failed=0
  local released=0
  local absent=0
  local output=""

  dev_tailscale_require_cli || return 1

  for port in "${frontend_port}" "${admin_port}"; do
    [[ -n "${port:-}" ]] || continue
    if ! dev_tailscale_validate_port "recorded" "${port}"; then
      failed=1
      continue
    fi
    [[ "${seen}" == *" ${port} "* ]] && continue
    seen="${seen}${port} "

    if output="$(dev_tailscale_run tailscale serve --http="${port}" off 2>&1)"; then
      released=1
    elif [[ "${output}" == *"handler does not exist"* ]]; then
      absent=1
    else
      failed=1
      echo "WARN: failed to release Tailscale Serve forwarding on http:${port}." >&2
      [[ -z "${output}" ]] || printf '%s\n' "${output}" >&2
    fi
  done

  if (( released == 1 )); then
    echo "Released Tailscale Serve forwarding for frontend:${frontend_port:-?} admin:${admin_port:-?}."
  elif (( absent == 1 )); then
    echo "Tailscale Serve forwarding was already absent for frontend:${frontend_port:-?} admin:${admin_port:-?}."
  fi

  return "${failed}"
}

dev_tailscale_disable_recorded() {
  local env_file="$1"
  local AERISUN_DEV_TAILSCALE_SERVE_ENABLED=""
  local AERISUN_DEV_TAILSCALE_FRONTEND_PORT=""
  local AERISUN_DEV_TAILSCALE_ADMIN_PORT=""

  if [[ -f "${env_file}" ]]; then
    # shellcheck disable=SC1090
    source "${env_file}"
  fi

  local enabled="${AERISUN_DEV_TAILSCALE_SERVE_ENABLED:-}"
  local frontend_port="${AERISUN_DEV_TAILSCALE_FRONTEND_PORT:-}"
  local admin_port="${AERISUN_DEV_TAILSCALE_ADMIN_PORT:-}"

  if dev_tailscale_is_truthy "${enabled}"; then
    dev_tailscale_disable_ports "${frontend_port}" "${admin_port}" || return 1
  fi

  dev_tailscale_remove_env_block "${env_file}"
}

dev_tailscale_enable() {
  local env_file="$1"
  local frontend_port="$2"
  local admin_port="$3"

  dev_tailscale_validate_port "frontend" "${frontend_port}"
  dev_tailscale_validate_port "admin" "${admin_port}"
  dev_tailscale_require_cli

  dev_tailscale_disable_recorded "${env_file}"

  if ! dev_tailscale_run tailscale serve --bg --http="${frontend_port}" "http://127.0.0.1:${frontend_port}"; then
    return 1
  fi
  if ! dev_tailscale_run tailscale serve --bg --http="${admin_port}" "http://127.0.0.1:${admin_port}"; then
    dev_tailscale_run tailscale serve --http="${frontend_port}" off >/dev/null 2>&1 || true
    return 1
  fi
  dev_tailscale_upsert_env_block "${env_file}" "${frontend_port}" "${admin_port}"
  dev_tailscale_print_urls "${frontend_port}" "${admin_port}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  case "${1:-}" in
    authorize)
      if [[ $# -ne 2 ]]; then
        echo "Usage: $0 authorize <env-file>" >&2
        exit 2
      fi
      dev_tailscale_require_cli
      dev_tailscale_ensure_sudo
      dev_tailscale_disable_recorded "$2"
      ;;
    release-recorded)
      if [[ $# -ne 2 ]]; then
        echo "Usage: $0 release-recorded <env-file>" >&2
        exit 2
      fi
      dev_tailscale_disable_recorded "$2"
      ;;
    *)
      echo "Usage: $0 authorize <env-file> | release-recorded <env-file>" >&2
      exit 2
      ;;
  esac
fi
