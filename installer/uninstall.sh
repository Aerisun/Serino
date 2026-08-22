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

print_last_diagnostics() {
  if [[ -f "${AERISUN_INSTALLER_DEST}/doctor.sh" ]]; then
    log_info "卸载前状态摘要（仅供参考，不影响继续卸载）："
    if ! bash "${AERISUN_INSTALLER_DEST}/doctor.sh"; then
      log_warn "上面的诊断失败项不会阻止彻底卸载。"
    fi
  fi
}

print_caddy_route_uninstall_warning() {
  local route_path=""
  local upstream=""
  local routes=""
  local site_url="${AERISUN_SITE_URL:-}"

  routes="$(list_caddy_routes)"
  [[ -n "${routes}" ]] || return 0

  printf '检测到有其他服务正在使用 Serino 的 Caddy 进行转发：\n\n' >&2
  while IFS=$'\t' read -r route_path upstream; do
    [[ -n "${route_path}" ]] || continue
    printf -- '- %s%s → %s\n' "${site_url%/}" "${route_path}" "${upstream}" >&2
  done <<<"${routes}"
  printf '\n继续卸载将一并删除 Serino 的 Caddy，上述地址将立即停止访问。\n' >&2
  printf '请记录这些转发规则，并在卸载 Serino 后重新配置相关转发！\n' >&2
}

confirm_uninstall() {
  if [[ "${1:-}" == "--force" ]]; then
    return 0
  fi

  [[ -e /dev/tty ]] || die "非交互环境下执行彻底卸载需要追加 --force。"

  cat >&2 <<EOF
即将彻底卸载 Serino。

这会永久删除以下内容：
- 当前站点容器、网络和卷
- 安装目录：${AERISUN_APP_ROOT}
- 配置目录：${SERINO_CONFIG_ROOT}
- 数据目录：${AERISUN_DATA_DIR}
- 日志目录：${SERINO_LOG_ROOT}
- 备份目录：${AERISUN_BACKUP_ROOT}
- 本机命令入口：${SERINO_BIN_LINK}
- systemd 服务：${SERINO_SYSTEMD_UNIT} / ${SERINO_SYSTEMD_UPGRADE_SERVICE} / ${SERINO_SYSTEMD_UPGRADE_TIMER}
- 服务用户与用户组：${SERINO_SERVICE_USER}:${SERINO_SERVICE_GROUP}

此操作不可恢复。
EOF

  local answer=""
  read -r -p "如确认彻底卸载，请输入 UNINSTALL: " answer </dev/tty
  [[ "${answer}" == "UNINSTALL" ]] || die "已取消卸载。"
}

main() {
  require_supported_linux
  require_root_or_sudo

  if path_is_file "${AERISUN_ENV_FILE}"; then
    load_env_file "${AERISUN_ENV_FILE}"
  fi

  print_caddy_route_uninstall_warning
  confirm_uninstall "${1:-}"
  print_last_diagnostics
  if ! stop_and_remove_serino_units; then
    die "后台数据迁移仍在运行或无法确认已经停止，已取消卸载以保护数据。"
  fi
  if ! teardown_release_stack; then
    die "Serino 容器未能全部停止并移除，已取消卸载以保护数据。"
  fi
  remove_serino_local_images
  purge_service_account
  purge_installation_paths
  log_info "Serino 已从当前机器彻底卸载。"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
