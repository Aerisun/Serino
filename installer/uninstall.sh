#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/env.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/docker.sh"

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
- 数据目录：${AERISUN_DATA_DIR}
- 备份目录：${AERISUN_BACKUP_ROOT}
- 本机命令入口：/usr/local/bin/sercli

此操作不可恢复。
EOF

  local answer=""
  read -r -p "如确认彻底卸载，请输入 UNINSTALL: " answer </dev/tty
  [[ "${answer}" == "UNINSTALL" ]] || die "已取消卸载。"
}

stop_upgrade_units() {
  local unit=""
  for unit in aerisun-upgrade.timer aerisun-upgrade.service; do
    run_as_root systemctl disable --now "${unit}" >/dev/null 2>&1 || true
    if [[ -f "/etc/systemd/system/${unit}" ]]; then
      run_as_root rm -f "/etc/systemd/system/${unit}"
    fi
  done
  run_as_root systemctl daemon-reload >/dev/null 2>&1 || true
}

teardown_release_stack() {
  if command_exists docker && [[ -f "${AERISUN_COMPOSE_FILE}" ]]; then
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi

  if command_exists docker; then
    run_as_root docker volume rm -f \
      "${AERISUN_COMPOSE_PROJECT_NAME}_caddy_data" \
      "${AERISUN_COMPOSE_PROJECT_NAME}_caddy_config" >/dev/null 2>&1 || true
    run_as_root docker network rm "${AERISUN_COMPOSE_PROJECT_NAME}_default" >/dev/null 2>&1 || true
  fi
}

remove_local_images() {
  command_exists docker || return 0

  local image_ids=""
  image_ids="$(
    run_as_root docker images --format '{{.Repository}} {{.ID}}' \
      | awk '$1 ~ /(^|\/)(serino-api|serino-web|serino-waline)$/ { print $2 }' \
      | sort -u
  )"

  [[ -n "${image_ids}" ]] || return 0
  # shellcheck disable=SC2086
  run_as_root docker image rm -f ${image_ids} >/dev/null 2>&1 || true
}

remove_installation_paths() {
  cd /
  run_as_root rm -rf "${AERISUN_APP_ROOT}"

  if [[ "${AERISUN_BACKUP_ROOT}" != "${AERISUN_APP_ROOT}" && "${AERISUN_BACKUP_ROOT}" != "${AERISUN_APP_ROOT}/"* ]]; then
    run_as_root rm -rf "${AERISUN_BACKUP_ROOT}"
  fi

  if [[ "${AERISUN_DATA_DIR}" != "/" ]]; then
    run_as_root rm -rf "${AERISUN_DATA_DIR}"
  fi

  run_as_root rm -f /usr/local/bin/sercli
}

main() {
  require_supported_linux
  require_root_or_sudo
  load_env_file "${AERISUN_ENV_FILE}"
  confirm_uninstall "${1:-}"
  stop_upgrade_units
  teardown_release_stack
  remove_local_images
  remove_installation_paths
  log_info "Serino 已从当前机器彻底卸载。"
}

main "$@"
