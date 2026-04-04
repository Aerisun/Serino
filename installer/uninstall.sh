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
    log_info "卸载前诊断摘要："
    bash "${AERISUN_INSTALLER_DEST}/doctor.sh" || true
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
- 本机命令入口：/usr/local/bin/sercli
- systemd 服务：${SERINO_SYSTEMD_UNIT} / ${SERINO_SYSTEMD_UPGRADE_SERVICE} / ${SERINO_SYSTEMD_UPGRADE_TIMER}
- 服务用户与用户组：${SERINO_SERVICE_USER}:${SERINO_SERVICE_GROUP}

此操作不可恢复。
EOF

  local answer=""
  read -r -p "如确认彻底卸载，请输入 UNINSTALL: " answer </dev/tty
  [[ "${answer}" == "UNINSTALL" ]] || die "已取消卸载。"
}

remove_local_images() {
  command_exists docker || return 0

  local image_ids=""
  image_ids="$(
    run_as_root docker images --format '{{.Repository}} {{.ID}}' \
      | awk '$1 ~ /(^|\/)(serino-api|serino-web|serino-waline|serino-dev-api|serino-dev-web|serino-dev-waline)$/ { print $2 }' \
      | sort -u
  )"

  [[ -n "${image_ids}" ]] || return 0
  # shellcheck disable=SC2086
  run_as_root docker image rm -f ${image_ids} >/dev/null 2>&1 || true
}

remove_installation_paths() {
  cd /
  run_as_root rm -rf \
    "${AERISUN_APP_ROOT}" \
    "${SERINO_CONFIG_ROOT}" \
    "${AERISUN_DATA_DIR}" \
    "${SERINO_LOG_ROOT}" \
    "${AERISUN_BACKUP_ROOT}" \
    /opt/aerisun \
    /var/lib/aerisun \
    /var/backups/aerisun
  run_as_root rm -f /usr/local/bin/sercli
  run_as_root rm -f /usr/local/bin/aerisunctl
}

remove_service_account() {
  if id -u "${SERINO_SERVICE_USER}" >/dev/null 2>&1; then
    run_as_root userdel "${SERINO_SERVICE_USER}" >/dev/null 2>&1 || true
  fi
  if getent group "${SERINO_SERVICE_GROUP}" >/dev/null 2>&1; then
    run_as_root groupdel "${SERINO_SERVICE_GROUP}" >/dev/null 2>&1 || true
  fi
}

main() {
  require_supported_linux
  require_root_or_sudo
  confirm_uninstall "${1:-}"

  if [[ -f "${AERISUN_ENV_FILE}" ]]; then
    load_env_file "${AERISUN_ENV_FILE}"
  fi

  print_last_diagnostics
  stop_and_remove_serino_units
  teardown_release_stack
  remove_local_images
  remove_installation_paths
  remove_service_account
  log_info "Serino 已从当前机器彻底卸载。"
}

main "$@"
