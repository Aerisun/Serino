#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/env.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/docker.sh"

print_last_diagnostics() {
  if [[ -f "${AERISUN_INSTALLER_DEST}/doctor.sh" ]]; then
    log_info "卸载前状态摘要（仅供参考，不影响继续卸载）："
    if ! bash "${AERISUN_INSTALLER_DEST}/doctor.sh"; then
      log_warn "上面的诊断失败项不会阻止彻底卸载。"
    fi
  fi
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
  confirm_uninstall "${1:-}"

  if path_is_file "${AERISUN_ENV_FILE}"; then
    load_env_file "${AERISUN_ENV_FILE}"
  fi

  print_last_diagnostics
  stop_and_remove_serino_units
  teardown_release_stack
  remove_serino_local_images
  purge_installation_paths
  purge_service_account
  log_info "Serino 已从当前机器彻底卸载。"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
