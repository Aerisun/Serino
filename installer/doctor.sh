#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/env.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/docker.sh"

JSON_MODE=false
DOCTOR_TMP="$(mktemp)"
trap 'rm -f "${DOCTOR_TMP}"' EXIT

record_check() {
  local status="$1"
  local key="$2"
  local message="$3"
  local fix="$4"
  printf '%s\t%s\t%s\t%s\n' "${status}" "${key}" "${message}" "${fix}" >> "${DOCTOR_TMP}"
}

has_failures() {
  grep -q '^fail	' "${DOCTOR_TMP}" 2>/dev/null
}

emit_text_report() {
  local status=""
  local key=""
  local message=""
  local fix=""

  while IFS=$'\t' read -r status key message fix; do
    printf '[%s] %s: %s\n' "${status}" "${key}" "${message}"
    if [[ -n "${fix}" ]]; then
      printf '  修复建议：%s\n' "${fix}"
    fi
  done < "${DOCTOR_TMP}"
}

emit_json_report() {
  python3 - "${DOCTOR_TMP}" <<'PY'
import json
import sys
from pathlib import Path

rows = []
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    status, key, message, fix = (line.split("\t", 3) + ["", "", "", ""])[:4]
    rows.append(
        {
            "status": status,
            "key": key,
            "message": message,
            "fix": fix,
        }
    )

print(json.dumps(rows, ensure_ascii=False))
PY
}

parse_env_value() {
  local key="$1"
  awk -F= -v wanted="${key}" '$1 == wanted {sub(/^[^=]*=/, ""); print; exit}' "${AERISUN_ENV_FILE}"
}

check_legacy_layout() {
  local legacy_paths=""
  legacy_paths="$(legacy_installation_paths)"
  if [[ -n "${legacy_paths}" ]]; then
    record_check \
      "fail" \
      "layout.legacy" \
      "检测到旧版安装布局，不支持与新模型混用。" \
      "先清理这些旧路径后再重装：$(printf '%s' "${legacy_paths}" | paste -sd ', ' -)"
  else
    record_check "ok" "layout.legacy" "未检测到旧版安装布局残留。" ""
  fi
}

check_service_user() {
  if ! id -u "${SERINO_SERVICE_USER}" >/dev/null 2>&1; then
    record_check "fail" "service_user" "缺少 ${SERINO_SERVICE_USER} 服务用户。" "sudo useradd --system --home-dir ${AERISUN_DATA_DIR} --create-home --shell $(resolve_nologin_shell) ${SERINO_SERVICE_USER}"
    return
  fi

  local shell_path=""
  shell_path="$(getent passwd "${SERINO_SERVICE_USER}" | cut -d: -f7)"
  if [[ "${shell_path}" == */nologin || "${shell_path}" == "/bin/false" || "${shell_path}" == "/usr/bin/false" ]]; then
    record_check "ok" "service_user" "服务用户 ${SERINO_SERVICE_USER} 已存在，且为禁止登录用户。" ""
  else
    record_check "warn" "service_user" "服务用户 ${SERINO_SERVICE_USER} 存在，但 shell 不是 nologin/false。" "sudo usermod --shell $(resolve_nologin_shell) ${SERINO_SERVICE_USER}"
  fi
}

check_path_contract() {
  local path="$1"
  local owner="$2"
  local group="$3"
  local mode="$4"
  local key="$5"
  local fix="$6"
  local stat_value=""

  if [[ ! -e "${path}" ]]; then
    record_check "fail" "${key}" "缺少路径 ${path}" "${fix}"
    return
  fi

  stat_value="$(stat -c '%U:%G %a' "${path}")"
  if [[ "${stat_value}" == "${owner}:${group} ${mode}" ]]; then
    record_check "ok" "${key}" "${path} owner/mode 正确（${stat_value}）。" ""
  else
    record_check "fail" "${key}" "${path} owner/mode 不正确（当前 ${stat_value}，预期 ${owner}:${group} ${mode}）。" "${fix}"
  fi
}

check_directories() {
  check_path_contract "${AERISUN_APP_ROOT}" "root" "root" "755" "path.app_root" "sudo install -d -o root -g root -m 0755 ${AERISUN_APP_ROOT}"
  check_path_contract "${AERISUN_INSTALLER_DEST}" "root" "root" "755" "path.installer_root" "sudo install -d -o root -g root -m 0755 ${AERISUN_INSTALLER_DEST}"
  check_path_contract "${SERINO_CONFIG_ROOT}" "root" "${SERINO_SERVICE_GROUP}" "750" "path.config_root" "sudo install -d -o root -g ${SERINO_SERVICE_GROUP} -m 0750 ${SERINO_CONFIG_ROOT}"
  check_path_contract "${AERISUN_ENV_FILE}" "root" "${SERINO_SERVICE_GROUP}" "640" "path.env_file" "sudo cp ${AERISUN_ENV_EXAMPLE_FILE} ${AERISUN_ENV_FILE} && sudo chown root:${SERINO_SERVICE_GROUP} ${AERISUN_ENV_FILE} && sudo chmod 0640 ${AERISUN_ENV_FILE}"
  check_path_contract "${AERISUN_DATA_DIR}" "${SERINO_SERVICE_USER}" "${SERINO_SERVICE_GROUP}" "750" "path.data_root" "sudo install -d -o ${SERINO_SERVICE_USER} -g ${SERINO_SERVICE_GROUP} -m 0750 ${AERISUN_DATA_DIR}"
  check_path_contract "${SERINO_LOG_ROOT}" "root" "root" "755" "path.log_root" "sudo install -d -o root -g root -m 0755 ${SERINO_LOG_ROOT}"
  check_path_contract "${AERISUN_BACKUP_ROOT}" "root" "root" "700" "path.backup_root" "sudo install -d -o root -g root -m 0700 ${AERISUN_BACKUP_ROOT}"
}

check_symlink_and_units() {
  if [[ "$(readlink -f "${SERINO_BIN_LINK}" 2>/dev/null || true)" == "${AERISUN_INSTALLER_DEST}/bin/sercli" ]]; then
    record_check "ok" "sercli.link" "sercli 命令入口已指向当前安装目录。" ""
  else
    record_check "fail" "sercli.link" "sercli 命令入口不存在或未指向当前安装目录。" "sudo ln -sf ${AERISUN_INSTALLER_DEST}/bin/sercli ${SERINO_BIN_LINK}"
  fi

  local unit=""
  local source_name=""
  for unit in \
    "${SERINO_SYSTEMD_UNIT}" \
    "${SERINO_SYSTEMD_UPGRADE_SERVICE}" \
    "${SERINO_SYSTEMD_UPGRADE_TIMER}"; do
    source_name="${unit}"
    if [[ -f "/etc/systemd/system/${unit}" ]]; then
      record_check "ok" "systemd.${unit}" "${unit} 已安装。" ""
    else
      record_check "fail" "systemd.${unit}" "缺少 systemd unit：${unit}" "sudo install -m 0644 ${AERISUN_INSTALLER_DEST}/systemd/${source_name} /etc/systemd/system/${unit} && sudo systemctl daemon-reload"
    fi
  done
}

check_docker_stack() {
  if ! command_exists docker; then
    record_check "fail" "docker.binary" "缺少 docker 命令。" "安装 Docker 后重新执行 sercli doctor"
    return
  fi

  if ! run_as_root docker compose version >/dev/null 2>&1 && ! command_exists docker-compose; then
    record_check "fail" "docker.compose" "缺少 docker compose。" "安装 Docker Compose 后重新执行 sercli doctor"
  else
    record_check "ok" "docker.compose" "Docker Compose 可用。" ""
  fi

  if run_as_root systemctl is-enabled --quiet docker && run_as_root systemctl is-active --quiet docker; then
    record_check "ok" "docker.service" "Docker 服务已启用并正在运行。" ""
  else
    record_check "fail" "docker.service" "Docker 服务未启用或未运行。" "sudo systemctl enable --now docker"
  fi
}

check_serino_service_state() {
  if run_as_root systemctl is-enabled --quiet "${SERINO_SYSTEMD_UNIT}" && service_is_active; then
    record_check "ok" "serino.service" "${SERINO_SYSTEMD_UNIT} 已启用且正在运行。" ""
  elif run_as_root systemctl is-enabled --quiet "${SERINO_SYSTEMD_UNIT}"; then
    record_check "fail" "serino.service" "${SERINO_SYSTEMD_UNIT} 已启用但当前未运行。" "sudo systemctl restart ${SERINO_SYSTEMD_UNIT}"
  else
    record_check "fail" "serino.service" "${SERINO_SYSTEMD_UNIT} 未启用。" "sudo systemctl enable --now ${SERINO_SYSTEMD_UNIT}"
  fi
}

check_env_contract() {
  if ! path_is_file "${AERISUN_ENV_FILE}"; then
    record_check "fail" "env.missing" "缺少配置文件 ${AERISUN_ENV_FILE}" "重新执行安装器或从备份恢复 ${AERISUN_ENV_FILE}"
    return
  fi

  load_env_file "${AERISUN_ENV_FILE}"

  local key=""
  for key in \
    AERISUN_SITE_URL \
    AERISUN_WALINE_SERVER_URL \
    AERISUN_CORS_ORIGINS \
    WALINE_JWT_TOKEN \
    AERISUN_INSTALL_CHANNEL \
    AERISUN_IMAGE_REGISTRY \
    AERISUN_IMAGE_TAG \
    AERISUN_API_IMAGE_NAME \
    AERISUN_WEB_IMAGE_NAME \
    AERISUN_WALINE_IMAGE_NAME \
    AERISUN_RELEASE_VERSION \
    AERISUN_STORE_BIND_DIR \
    SERINO_RUNTIME_UID \
    SERINO_RUNTIME_GID; do
    if [[ -z "${!key:-}" ]]; then
      record_check "fail" "env.${key}" "${AERISUN_ENV_FILE} 缺少 ${key}" "sudo editor ${AERISUN_ENV_FILE}"
    else
      record_check "ok" "env.${key}" "${key} 已配置。" ""
    fi
  done

  if [[ "${AERISUN_STORE_BIND_DIR:-}" == "${AERISUN_DATA_DIR}" ]]; then
    record_check "ok" "env.store_bind" "AERISUN_STORE_BIND_DIR 已对齐到 ${AERISUN_DATA_DIR}。" ""
  else
    record_check "fail" "env.store_bind" "AERISUN_STORE_BIND_DIR 未指向 ${AERISUN_DATA_DIR}。" "sudo sed -i 's|^AERISUN_STORE_BIND_DIR=.*|AERISUN_STORE_BIND_DIR=${AERISUN_DATA_DIR}|' ${AERISUN_ENV_FILE}"
  fi

  if [[ -n "${SERINO_RUNTIME_UID:-}" && -n "${SERINO_RUNTIME_GID:-}" ]]; then
    local expected_uid=""
    local expected_gid=""
    expected_uid="$(id -u "${SERINO_SERVICE_USER}" 2>/dev/null || true)"
    expected_gid="$(id -g "${SERINO_SERVICE_USER}" 2>/dev/null || true)"
    if [[ "${SERINO_RUNTIME_UID}" == "${expected_uid}" && "${SERINO_RUNTIME_GID}" == "${expected_gid}" ]]; then
      record_check "ok" "env.runtime_ids" "SERINO_RUNTIME_UID/GID 已与服务用户对齐。" ""
    else
      record_check "fail" "env.runtime_ids" "SERINO_RUNTIME_UID/GID 与服务用户不一致。" "sudo editor ${AERISUN_ENV_FILE} && sudo systemctl restart ${SERINO_SYSTEMD_UNIT}"
    fi
  fi

  if [[ "${AERISUN_INSTALL_CHANNEL:-stable}" == "dev" ]]; then
    if [[ -n "${AERISUN_INSTALL_BASE_URL:-}" ]]; then
      record_check "ok" "env.channel_source" "dev 渠道已配置分发源 ${AERISUN_INSTALL_BASE_URL}。" ""
    else
      record_check "fail" "env.channel_source" "dev 渠道缺少 AERISUN_INSTALL_BASE_URL，后续无法按同渠道升级。" "sudo editor ${AERISUN_ENV_FILE}"
    fi
  fi

  if grep -q '^AERISUN_BOOTSTRAP_ADMIN_.*=' "${AERISUN_ENV_FILE}"; then
    record_check "fail" "env.bootstrap_cleanup" "检测到残留的 bootstrap 管理员凭据。" "sudo sed -i '/^AERISUN_BOOTSTRAP_ADMIN_/d' ${AERISUN_ENV_FILE}"
  else
    record_check "ok" "env.bootstrap_cleanup" "bootstrap 管理员凭据已清理。" ""
  fi
}

check_bind_mount_writeability() {
  if ! id -u "${SERINO_SERVICE_USER}" >/dev/null 2>&1; then
    return
  fi

  if command_exists runuser; then
    if run_as_root runuser -u "${SERINO_SERVICE_USER}" -- test -w "${AERISUN_DATA_DIR}"; then
      record_check "ok" "path.data_writable" "服务用户可写 ${AERISUN_DATA_DIR}。" ""
    else
      record_check "fail" "path.data_writable" "服务用户无法写入 ${AERISUN_DATA_DIR}。" "sudo chown -R ${SERINO_SERVICE_USER}:${SERINO_SERVICE_GROUP} ${AERISUN_DATA_DIR} && sudo chmod 0750 ${AERISUN_DATA_DIR}"
    fi
    return
  fi

  record_check "warn" "path.data_writable" "系统缺少 runuser，未执行服务用户写权限探测。" ""
}

check_health_and_data_status() {
  load_env_file "${AERISUN_ENV_FILE}"

  local backend_url="http://127.0.0.1:${AERISUN_PORT:-8000}${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"
  if curl --fail --silent --show-error "${backend_url}" >/dev/null 2>&1; then
    record_check "ok" "health.api" "API 健康检查通过。" ""
  else
    record_check "fail" "health.api" "API 健康检查未通过：${backend_url}" "sercli logs api"
  fi

  if [[ -n "${AERISUN_SITE_URL:-}" ]] && curl --fail --silent --show-error "${AERISUN_SITE_URL}/" >/dev/null 2>&1; then
    record_check "ok" "health.site" "站点首页可访问。" ""
  else
    record_check "fail" "health.site" "站点首页不可访问：${AERISUN_SITE_URL:-<unknown>}/" "sercli logs caddy"
  fi

  if [[ -n "${AERISUN_SITE_URL:-}" ]] && curl --fail --silent --show-error "${AERISUN_SITE_URL}${AERISUN_ADMIN_BASE_PATH:-/admin/}" >/dev/null 2>&1; then
    record_check "ok" "health.admin" "网站管理台可访问。" ""
  else
    record_check "fail" "health.admin" "网站管理台不可访问。" "sercli logs caddy api"
  fi

  if [[ -n "${AERISUN_WALINE_SERVER_URL:-}" ]] && curl --fail --silent --show-error "${AERISUN_WALINE_SERVER_URL}/" >/dev/null 2>&1; then
    record_check "ok" "health.waline" "Waline 可访问。" ""
  else
    record_check "fail" "health.waline" "Waline 不可访问。" "sercli logs waline caddy"
  fi

  local migration_report=""
  migration_report="$(compose exec -T api uv run python -u - <<'PY' 2>/dev/null || true
import json
from sqlalchemy import text
from alembic.config import Config
from alembic.script import ScriptDirectory
from aerisun.core.backfills.registry import REGISTERED_BACKFILLS
from aerisun.core.backfills.state import list_applied_data_migrations
from aerisun.core.db import get_session_factory

config = Config("/app/backend/alembic.ini")
script = ScriptDirectory.from_config(config)
heads = script.get_heads()

with get_session_factory()() as session:
    current = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    applied = list_applied_data_migrations(session, kind="backfill")

pending = [spec.migration_key for spec in REGISTERED_BACKFILLS if spec.migration_key not in applied]

print(json.dumps({
    "current_revision": current,
    "head_revisions": heads,
    "pending_backfills": pending,
}, ensure_ascii=False))
PY
)"

  if [[ -z "${migration_report}" ]]; then
    record_check "fail" "data.migrations" "无法获取 migration/backfill 状态。" "sercli logs api"
    return
  fi

  local migration_summary=""
  migration_summary="$(python3 - <<'PY' "${migration_report}"
import json
import sys
payload = json.loads(sys.argv[1])
heads = payload.get("head_revisions") or []
current = payload.get("current_revision")
pending = payload.get("pending_backfills") or []
if current not in heads:
    print(f"fail\t当前数据库 revision={current}，未对齐 head={','.join(heads)}\tsercli upgrade")
elif pending:
    print(f"fail\t仍有未执行的 backfill：{', '.join(pending)}\tsercli upgrade")
else:
    print("ok\t数据库 migration 和 backfill 已对齐。")
PY
)"

  local status=""
  local message=""
  local fix=""
  IFS=$'\t' read -r status message fix <<<"${migration_summary}"
  record_check "${status}" "data.migrations" "${message}" "${fix}"
}

main() {
  if [[ "${1:-}" == "--json" ]]; then
    JSON_MODE=true
    shift
  fi

  require_supported_linux
  require_root_or_sudo

  check_legacy_layout
  check_service_user
  check_directories
  check_symlink_and_units
  check_docker_stack
  check_serino_service_state
  check_env_contract
  check_bind_mount_writeability
  check_health_and_data_status

  if [[ "${JSON_MODE}" == "true" ]]; then
    emit_json_report
  else
    emit_text_report
  fi

  if has_failures; then
    exit 1
  fi
}

main "$@"
