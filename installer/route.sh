#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/env.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/docker.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/routes.sh"

restore_caddy_route_file() {
  local backup_file="$1"
  local route_file="$2"
  run_as_root install -o root -g root -m 0644 "${backup_file}" "${route_file}"
}

cmd_route_add() {
  [[ "$#" -eq 2 ]] || die "用法：sercli route add <path> <upstream>"

  local route_path=""
  local upstream=""
  local route_file=""
  local temp_file=""

  route_path="$(normalize_caddy_route_path "$1")" || die "转发路径无效：$1"
  upstream="$(normalize_caddy_route_upstream "$2")" || die "转发目标无效：$2"
  if caddy_route_conflicts_with_serino "${route_path}"; then
    die "无法添加路由 ${route_path}：该路径由 Serino 保留。"
  fi

  ensure_caddy_routes_dir
  route_file="$(caddy_route_file_for_path "${route_path}")"
  path_is_file "${route_file}" && die "路由 ${route_path} 已经注册。"
  if caddy_route_conflicts_with_registered "${route_path}"; then
    die "无法添加路由 ${route_path}：该路径与已有的用户转发重叠。"
  fi

  temp_file="$(make_temp_file)"
  render_caddy_route_config "${route_path}" "${upstream}" >"${temp_file}"
  run_as_root install -o root -g root -m 0644 "${temp_file}" "${route_file}"
  rm -f "${temp_file}"

  if ! validate_caddy_route_configuration; then
    run_as_root rm -f "${route_file}"
    die "Caddy 配置校验失败，未添加路由 ${route_path}。"
  fi
  if ! reload_caddy_route_configuration_if_running; then
    run_as_root rm -f "${route_file}"
    die "Caddy 重新加载失败，未添加路由 ${route_path}。"
  fi

  log_info "已添加转发：${AERISUN_SITE_URL%/}${route_path} → ${upstream}"
}

cmd_route_list() {
  [[ "$#" -eq 0 ]] || die "用法：sercli route list"

  local route_path=""
  local upstream=""
  local found="false"
  local site_url="${AERISUN_SITE_URL%/}"

  while IFS=$'\t' read -r route_path upstream; do
    [[ -n "${route_path}" ]] || continue
    found="true"
    printf -- '- %s%s → %s\n' "${site_url}" "${route_path}" "${upstream}"
  done < <(list_caddy_routes)

  if [[ "${found}" == "false" ]]; then
    printf '未配置其他服务转发。\n'
  fi
}

cmd_route_remove() {
  [[ "$#" -eq 1 ]] || die "用法：sercli route remove <path>"

  local route_path=""
  local route_file=""
  local backup_file=""

  route_path="$(normalize_caddy_route_path "$1")" || die "转发路径无效：$1"
  route_file="$(caddy_route_file_for_path "${route_path}")"
  path_is_file "${route_file}" || die "路由 ${route_path} 尚未注册。"

  backup_file="$(make_temp_file)"
  run_as_root cp -a "${route_file}" "${backup_file}"
  run_as_root rm -f "${route_file}"

  if ! validate_caddy_route_configuration; then
    restore_caddy_route_file "${backup_file}" "${route_file}"
    rm -f "${backup_file}"
    die "Caddy 配置校验失败，未删除路由 ${route_path}。"
  fi
  if ! reload_caddy_route_configuration_if_running; then
    restore_caddy_route_file "${backup_file}" "${route_file}"
    rm -f "${backup_file}"
    die "Caddy 重新加载失败，未删除路由 ${route_path}。"
  fi

  rm -f "${backup_file}"
  log_info "已删除转发：${route_path}"
}

main() {
  local subcommand="${1:-list}"
  shift || true

  ensure_supported_existing_installation
  load_env_file "${AERISUN_ENV_FILE}"

  case "${subcommand}" in
    add)
      cmd_route_add "$@"
      ;;
    list)
      cmd_route_list "$@"
      ;;
    remove)
      cmd_route_remove "$@"
      ;;
    *)
      die "未知的 route 子命令：${subcommand}"
      ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
