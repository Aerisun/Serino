#!/usr/bin/env bash

compose_with_env() {
  local compose_runner="$1"
  local compose_file="$2"
  shift
  shift

  run_as_root bash -lc '
    env_file="$1"
    compose_file="$2"
    project_name="$3"
    compose_runner="$4"
    shift 4

    set -euo pipefail
    [[ -f "${env_file}" ]] || {
      echo "missing env file: ${env_file}" >&2
      exit 1
    }

    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a
    export COMPOSE_PROJECT_NAME="${project_name}"

    if [[ "${compose_runner}" == "docker-compose" ]]; then
      exec docker-compose -f "${compose_file}" "$@"
    fi

    exec docker compose -f "${compose_file}" "$@"
  ' bash "${AERISUN_ENV_FILE}" "${compose_file}" "${AERISUN_COMPOSE_PROJECT_NAME}" "${compose_runner}" "$@"
}

resolve_compose_runner() {
  if run_as_root docker compose version >/dev/null 2>&1; then
    printf '%s' "docker"
    return 0
  fi

  if command_exists docker-compose; then
    printf '%s' "docker-compose"
    return 0
  fi

  die "当前机器缺少 docker compose。"
}

runtime_compose_file() {
  if [[ -f "${AERISUN_RENDERED_COMPOSE_FILE}" ]]; then
    printf '%s' "${AERISUN_RENDERED_COMPOSE_FILE}"
    return 0
  fi

  printf '%s' "${AERISUN_COMPOSE_FILE}"
}

render_release_compose_configuration() {
  local output_file="$1"

  run_as_root bash -lc '
    env_file="$1"
    template_file="$2"
    output_file="$3"

    set -euo pipefail
    [[ -f "${env_file}" ]] || {
      echo "missing env file: ${env_file}" >&2
      exit 1
    }
    [[ -f "${template_file}" ]] || {
      echo "missing compose template: ${template_file}" >&2
      exit 1
    }

    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a

    python3 - "${template_file}" "${output_file}" <<'"'"'PY'"'"'
import os
import re
import sys
from pathlib import Path

import yaml

template_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:-([^}]*))?\}")


def substitute_string(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        default = match.group(3)
        if key in os.environ:
            return os.environ[key]
        if default is not None:
            return default
        return ""

    return pattern.sub(repl, value)


def render(node):
    if isinstance(node, dict):
        return {key: render(value) for key, value in node.items()}
    if isinstance(node, list):
        return [render(item) for item in node]
    if isinstance(node, str):
        return substitute_string(node)
    return node


template = yaml.safe_load(template_path.read_text()) or {}
rendered = render(template)
rendered_text = yaml.safe_dump(
    rendered,
    allow_unicode=True,
    default_flow_style=False,
    sort_keys=False,
)

if "${" in rendered_text:
    print("unresolved placeholders remain in rendered compose output", file=sys.stderr)
    sys.exit(1)

output_path.write_text(rendered_text)
PY
  ' bash "${AERISUN_ENV_FILE}" "${AERISUN_COMPOSE_FILE}" "${output_file}"
}

compose() {
  local compose_runner=""
  compose_runner="$(resolve_compose_runner)"
  compose_with_env "${compose_runner}" "$(runtime_compose_file)" "$@"
}

compose_api_task() {
  local task="$1"
  shift

  compose run --rm --no-deps -T api /bin/bash "/app/backend/scripts/${task}" "$@"
}

daemon_reload() {
  run_as_root systemctl daemon-reload
}

enable_serino_service() {
  run_as_root systemctl enable "${SERINO_SYSTEMD_UNIT}" >/dev/null
  run_as_root systemctl start "${SERINO_SYSTEMD_UNIT}" >/dev/null
  run_as_root systemctl is-active --quiet "${SERINO_SYSTEMD_UNIT}"
}

start_serino_service() {
  run_as_root systemctl start "${SERINO_SYSTEMD_UNIT}" >/dev/null
}

stop_serino_service() {
  run_as_root systemctl stop "${SERINO_SYSTEMD_UNIT}" >/dev/null 2>&1 || true
}

restart_serino_service() {
  run_as_root systemctl restart "${SERINO_SYSTEMD_UNIT}" >/dev/null
}

service_is_active() {
  run_as_root systemctl is-active --quiet "${SERINO_SYSTEMD_UNIT}"
}

stop_and_remove_serino_units() {
  local unit=""
  for unit in \
    "${SERINO_SYSTEMD_UNIT}" \
    "${SERINO_SYSTEMD_UPGRADE_TIMER}" \
    "${SERINO_SYSTEMD_UPGRADE_SERVICE}" \
    aerisun.service \
    aerisun-upgrade.timer \
    aerisun-upgrade.service; do
    run_as_root systemctl disable --now "${unit}" >/dev/null 2>&1 || true
    if [[ -f "/etc/systemd/system/${unit}" ]]; then
      run_as_root rm -f "/etc/systemd/system/${unit}"
    fi
    if [[ -d "/etc/systemd/system/${unit}.d" ]]; then
      run_as_root rm -rf "/etc/systemd/system/${unit}.d"
    fi
  done
  daemon_reload >/dev/null 2>&1 || true
}

teardown_release_stack() {
  if command_exists docker && path_is_file "${AERISUN_COMPOSE_FILE}" && path_is_file "${AERISUN_ENV_FILE}"; then
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi

  if command_exists docker; then
    run_as_root docker rm -f \
      serino-api-1 \
      serino-waline-1 \
      serino-caddy-1 \
      aerisun-api-1 \
      aerisun-waline-1 \
      aerisun-caddy-1 >/dev/null 2>&1 || true
    run_as_root docker volume rm -f \
      "${AERISUN_COMPOSE_PROJECT_NAME}_caddy_data" \
      "${AERISUN_COMPOSE_PROJECT_NAME}_caddy_config" >/dev/null 2>&1 || true
    run_as_root docker network rm "${AERISUN_COMPOSE_PROJECT_NAME}_default" >/dev/null 2>&1 || true
    run_as_root docker volume rm -f \
      "aerisun_caddy_data" \
      "aerisun_caddy_config" >/dev/null 2>&1 || true
    run_as_root docker network rm "aerisun_default" >/dev/null 2>&1 || true
  fi
}

remove_serino_local_images() {
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

print_service_start_failure_diagnostics() {
  log_error "服务启动失败，以下是最近的诊断信息。"
  run_as_root systemctl --no-pager --full status "${SERINO_SYSTEMD_UNIT}" >&2 || true
  if command_exists docker && path_is_file "$(runtime_compose_file)"; then
    compose ps >&2 || true
    compose logs --tail 120 api waline caddy >&2 || true
  fi
}

ensure_docker_installed() {
  if command_exists docker && (run_as_root docker compose version >/dev/null 2>&1 || command_exists docker-compose); then
    run_as_root systemctl enable --now docker >/dev/null
    return 0
  fi

  log_info "正在自动安装 Docker。"
  curl --fail --location --silent --show-error https://get.docker.com \
    | run_as_root bash -s docker --mirror Aliyun
  run_as_root systemctl enable --now docker >/dev/null

  if ! (run_as_root docker compose version >/dev/null 2>&1 || command_exists docker-compose); then
    die "Docker 已安装，但缺少 docker compose。"
  fi
}

resolve_active_registry() {
  local registry="$1"
  local image_tag="$2"
  [[ -n "${registry}" ]] || die "安装清单缺少镜像仓库前缀。"
  [[ -n "${image_tag}" ]] || die "安装清单缺少镜像版本号。"
  printf '%s' "${registry}"
}

validate_release_compose_configuration() {
  local rendered_file=""

  rendered_file="$(make_root_temp_file_in_dir "${AERISUN_APP_ROOT}" ".docker-compose.rendered.XXXXXX.yml")"
  if ! render_release_compose_configuration "${rendered_file}"; then
    run_as_root rm -f "${rendered_file}"
    die "安装配置校验失败，无法渲染最终 docker compose 配置。"
  fi

  run_as_root python3 - "${rendered_file}" \
    "${AERISUN_IMAGE_REGISTRY}/${AERISUN_API_IMAGE_NAME}:${AERISUN_IMAGE_TAG}" \
    "${AERISUN_IMAGE_REGISTRY}/${AERISUN_WEB_IMAGE_NAME}:${AERISUN_IMAGE_TAG}" \
    "${AERISUN_IMAGE_REGISTRY}/${AERISUN_WALINE_IMAGE_NAME}:${AERISUN_IMAGE_TAG}" \
    "${AERISUN_SITE_URL_VALUE}" \
    "${AERISUN_WALINE_SERVER_URL_VALUE}" <<'PY' || {
import sys
from pathlib import Path

import yaml

rendered_path = Path(sys.argv[1])
expected_api = sys.argv[2]
expected_web = sys.argv[3]
expected_waline = sys.argv[4]
expected_site_url = sys.argv[5]
expected_waline_url = sys.argv[6]

data = yaml.safe_load(rendered_path.read_text()) or {}
services = data.get("services") or {}
errors: list[str] = []

def env_value(service_name: str, key: str) -> str | None:
    service = services.get(service_name) or {}
    environment = service.get("environment") or {}
    return environment.get(key)

def image_value(service_name: str) -> str | None:
    service = services.get(service_name) or {}
    return service.get("image")

checks = [
    ("API 镜像", image_value("api"), expected_api),
    ("Web 镜像", image_value("caddy"), expected_web),
    ("Waline 镜像", image_value("waline"), expected_waline),
    ("AERISUN_SITE_URL", env_value("api", "AERISUN_SITE_URL"), expected_site_url),
    ("AERISUN_WALINE_SERVER_URL", env_value("api", "AERISUN_WALINE_SERVER_URL"), expected_waline_url),
    ("Waline SITE_URL", env_value("waline", "SITE_URL"), expected_site_url),
    ("Waline SERVER_URL", env_value("waline", "SERVER_URL"), expected_waline_url),
]

for label, actual, expected in checks:
    if actual != expected:
        errors.append(f"{label} 不匹配：期望 {expected}，实际 {actual or '<missing>'}")

if errors:
    for line in errors:
        print(line, file=sys.stderr)
    sys.exit(1)
PY
    if install_debug_enabled; then
      log_error "docker compose 渲染文件：${rendered_file}"
      run_as_root sed -n '1,220p' "${rendered_file}" >&2 || true
    fi
    run_as_root rm -f "${rendered_file}"
    die "安装配置校验失败，最终运行配置没有正确展开到目标版本。"
  }

  run_as_root install -m 0644 "${rendered_file}" "${AERISUN_RENDERED_COMPOSE_FILE}"
  run_as_root rm -f "${rendered_file}"
}

compose_up_release() {
  compose pull || return $?
  enable_serino_service || return $?
}

run_release_migrations() {
  log_info "🧱 正在执行数据库迁移..."
  compose_api_task "migrate.sh"
}

run_release_bootstrap() {
  log_info "🌱 正在执行首装初始化..."
  compose_api_task "bootstrap-prod.sh"
}

run_release_backfills() {
  log_info "🛠️ 正在执行升级数据回填..."
  compose_api_task "backfill.sh"
}

wait_for_url() {
  local url="$1"
  local timeout_seconds="${2:-180}"
  local started_at

  started_at="$(date +%s)"
  while true; do
    if curl --fail --silent --show-error "${url}" >/dev/null 2>&1; then
      return 0
    fi

    if [[ $(( $(date +%s) - started_at )) -ge "${timeout_seconds}" ]]; then
      return 1
    fi
    sleep 2
  done
}

wait_for_domain_url() {
  local host="$1"
  local path="$2"
  local timeout_seconds="${3:-240}"
  local started_at

  started_at="$(date +%s)"
  while true; do
    if curl --fail --silent --show-error --insecure \
      --resolve "${host}:443:127.0.0.1" \
      "https://${host}${path}" >/dev/null 2>&1; then
      return 0
    fi

    if [[ $(( $(date +%s) - started_at )) -ge "${timeout_seconds}" ]]; then
      return 1
    fi
    sleep 3
  done
}

resolve_host_ips() {
  local host="$1"

  if command_exists getent; then
    getent ahosts "${host}" 2>/dev/null | awk '{print $1}' | sort -u
    return 0
  fi

  if command_exists host; then
    host "${host}" 2>/dev/null | awk '/has address/ {print $4} /has IPv6 address/ {print $5}' | sort -u
    return 0
  fi

  if command_exists nslookup; then
    nslookup "${host}" 2>/dev/null | awk '/^Address: / {print $2}' | grep -v '^#' | sort -u
    return 0
  fi

  return 1
}

list_local_ip_candidates() {
  {
    if command_exists hostname; then
      hostname -I 2>/dev/null || true
    fi
    if command_exists ip; then
      ip -o addr show scope global up 2>/dev/null | awk '{print $4}' | cut -d/ -f1
    fi
  } | tr ' ' '\n' | awk 'NF' | sort -u
}

detect_public_ip_candidates() {
  local url=""
  local candidate=""

  for url in https://api.ipify.org https://api6.ipify.org https://api64.ipify.org; do
    candidate="$(curl --noproxy '*' --silent --show-error --max-time 5 "${url}" 2>/dev/null || true)"
    [[ -n "${candidate}" ]] && printf '%s\n' "${candidate}"
  done

  for url in https://api.ipify.org https://api6.ipify.org https://api64.ipify.org; do
    candidate="$(curl --silent --show-error --max-time 5 "${url}" 2>/dev/null || true)"
    [[ -n "${candidate}" ]] && printf '%s\n' "${candidate}"
  done
}

detect_public_ip_candidate() {
  detect_public_ip_candidates | awk 'NF' | sort -u | head -n 1
}

join_lines() {
  awk 'NF { printf "%s%s", sep, $0; sep = ", " } END { if (NR > 0) printf "\n" }'
}

domain_points_to_candidate_ip() {
  local resolved_ips="$1"
  local candidate_ip="$2"
  [[ -n "${candidate_ip}" ]] || return 1
  grep -Fxq "${candidate_ip}" <<<"${resolved_ips}"
}

domain_points_to_any_candidate_ip() {
  local resolved_ips="$1"
  local candidate_ips="$2"
  [[ -n "${candidate_ips}" ]] || return 1

  while IFS= read -r candidate_ip; do
    [[ -n "${candidate_ip}" ]] || continue
    if domain_points_to_candidate_ip "${resolved_ips}" "${candidate_ip}"; then
      return 0
    fi
  done <<<"${candidate_ips}"

  return 1
}

print_domain_https_failure_details() {
  local host="$1"
  local label="$2"
  local path="$3"
  local resolved_ips=""
  local resolved_summary=""
  local local_ips=""
  local local_ip_summary=""
  local public_ips=""
  local public_ip_summary=""
  local caddy_logs=""
  local -a dns_reasons=()
  local -a firewall_reasons=()
  local -a cert_reasons=()
  local -a backend_reasons=()

  resolved_ips="$(resolve_host_ips "${host}" 2>/dev/null || true)"
  resolved_summary="$(printf '%s\n' "${resolved_ips}" | awk 'NF' | join_lines 2>/dev/null || true)"
  local_ips="$(list_local_ip_candidates)"
  local_ip_summary="$(printf '%s\n' "${local_ips}" | awk 'NF' | join_lines 2>/dev/null || true)"
  public_ips="$(detect_public_ip_candidates | awk 'NF' | sort -u)"
  public_ip_summary="$(printf '%s\n' "${public_ips}" | awk 'NF' | join_lines 2>/dev/null || true)"

  if [[ -z "${resolved_summary}" ]]; then
    dns_reasons+=("域名 ${host} 当前无法解析，请确认 A/AAAA 记录已经生效。")
  else
    if [[ -n "${public_ips}" ]] && ! domain_points_to_any_candidate_ip "${resolved_ips}" "${public_ips}"; then
      dns_reasons+=("域名 ${host} 当前解析到 ${resolved_summary}，没有命中本机公网 IP 候选 ${public_ip_summary}。")
    elif [[ -n "${local_ips}" ]] && ! grep -Fxf <(printf '%s\n' "${resolved_ips}") <(printf '%s\n' "${local_ips}") >/dev/null 2>&1; then
      dns_reasons+=("域名 ${host} 当前解析到 ${resolved_summary}，没有命中本机已知地址 ${local_ip_summary:-未知}。")
    fi
  fi

  if ! port_in_use 80; then
    firewall_reasons+=("本机 80 端口没有监听，外部 HTTP 校验无法完成。")
  fi
  if ! port_in_use 443; then
    firewall_reasons+=("本机 443 端口没有监听，HTTPS 服务没有成功接管。")
  fi

  if ! curl --fail --silent --show-error --insecure --resolve "${host}:443:127.0.0.1" "https://${host}${path}" >/dev/null 2>&1; then
    cert_reasons+=("本机通过 HTTPS 访问 ${label} 仍未就绪，说明证书签发或 Caddy HTTPS 站点仍有异常。")
  fi

  caddy_logs="$(compose logs --tail 80 caddy 2>/dev/null || true)"
  if grep -Eiq 'challenge.*failed|authorization failed|acme.*error|tls.obtain' <<<"${caddy_logs}"; then
    cert_reasons+=("Caddy 证书签发失败，常见原因是域名未指向本机，或公网 80/443 未放行。")
  fi
  if grep -Eiq 'no such host|NXDOMAIN|SERVFAIL' <<<"${caddy_logs}"; then
    dns_reasons+=("Caddy 解析域名失败，请确认 DNS 记录与本机解析器可用。")
  fi
  if grep -Eiq 'too many certificates|rate limit' <<<"${caddy_logs}"; then
    cert_reasons+=("证书签发触发了 CA 限流，请稍后重试。")
  fi
  if grep -Eiq 'connection refused|dial tcp .*:8000|dial tcp .*:8360' <<<"${caddy_logs}"; then
    backend_reasons+=("Caddy 无法连接 API 或 Waline 容器，请检查后端容器是否已经健康启动。")
  fi

  log_error "${label} 还没有通过 HTTPS 就绪检查。"

  if [[ ${#dns_reasons[@]} -eq 0 && ${#firewall_reasons[@]} -eq 0 && ${#cert_reasons[@]} -eq 0 && ${#backend_reasons[@]} -eq 0 ]]; then
    log_error "还没能自动确认具体原因，请检查域名解析、80/443 放行情况，以及证书签发状态。"
  else
    local reason=""
    if [[ ${#dns_reasons[@]} -gt 0 ]]; then
      printf '[ERROR] 可能是域名解析还没完全生效。\n' >&2
      for reason in "${dns_reasons[@]}"; do
        install_debug_enabled && printf '[ERROR] - %s\n' "${reason}" >&2
      done
    fi
    if [[ ${#firewall_reasons[@]} -gt 0 ]]; then
      printf '[ERROR] 可能是 80/443 端口还没有完全放通。\n' >&2
      for reason in "${firewall_reasons[@]}"; do
        install_debug_enabled && printf '[ERROR] - %s\n' "${reason}" >&2
      done
      printf '[ERROR] 请同时确认云服务器安全组与本机防火墙都已放行 80/443。\n' >&2
    fi
    if [[ ${#cert_reasons[@]} -gt 0 ]]; then
      printf '[ERROR] 可能是证书签发或 HTTPS 站点初始化还没有完成。\n' >&2
      for reason in "${cert_reasons[@]}"; do
        install_debug_enabled && printf '[ERROR] - %s\n' "${reason}" >&2
      done
    fi
    if [[ ${#backend_reasons[@]} -gt 0 ]]; then
      printf '[ERROR] 可能是后端容器还没有完全启动。\n' >&2
      for reason in "${backend_reasons[@]}"; do
        install_debug_enabled && printf '[ERROR] - %s\n' "${reason}" >&2
      done
      printf '[ERROR] 如需详细排查，可执行 sercli logs api waline caddy。\n' >&2
    fi
  fi

  if install_debug_enabled; then
    if [[ -n "${resolved_summary}" ]]; then
      printf '[ERROR] 当前 DNS 解析：%s -> %s\n' "${host}" "${resolved_summary}" >&2
    fi
    if [[ -n "${public_ip_summary}" ]]; then
      printf '[ERROR] 当前探测到的本机公网 IP 候选：%s\n' "${public_ip_summary}" >&2
    fi
    if [[ -n "${local_ip_summary}" ]]; then
      printf '[ERROR] 当前探测到的本机地址：%s\n' "${local_ip_summary}" >&2
    fi
    if [[ -n "${caddy_logs}" ]]; then
      printf '[ERROR] 最近 Caddy 日志：\n%s\n' "${caddy_logs}" >&2
    fi
  fi
}

die_domain_https_not_ready() {
  local host="$1"
  local label="$2"
  local path="$3"

  print_domain_https_failure_details "${host}" "${label}" "${path}"
  exit 1
}

preflight_domain_installation() {
  local host="$1"
  local resolved_ips=""
  local resolved_summary=""
  local local_ips=""
  local local_ip_summary=""
  local public_ips=""
  local public_ip_summary=""
  local port_80_usage=""
  local port_443_usage=""
  local -a reasons=()
  local -a debug_lines=()

  AERISUN_DOMAIN_PREFLIGHT_SUMMARY=""
  AERISUN_DOMAIN_PREFLIGHT_DEBUG_DETAILS=""

  if [[ "${host}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ || "${host}" == *:* ]]; then
    reasons+=("域名模式要求填写可公网访问的域名，当前输入看起来是 IP 地址：${host}")
  fi

  resolved_ips="$(resolve_host_ips "${host}" 2>/dev/null || true)"
  resolved_summary="$(printf '%s\n' "${resolved_ips}" | awk 'NF' | join_lines 2>/dev/null || true)"
  local_ips="$(list_local_ip_candidates)"
  local_ip_summary="$(printf '%s\n' "${local_ips}" | awk 'NF' | join_lines 2>/dev/null || true)"
  public_ips="$(detect_public_ip_candidates | awk 'NF' | sort -u)"
  public_ip_summary="$(printf '%s\n' "${public_ips}" | awk 'NF' | join_lines 2>/dev/null || true)"

  if [[ -z "${resolved_summary}" ]]; then
    reasons+=("域名 ${host} 当前无法解析，请确认 A/AAAA 记录已经生效。")
  elif [[ -n "${public_ips}" ]] && ! domain_points_to_any_candidate_ip "${resolved_ips}" "${public_ips}"; then
    reasons+=("域名 ${host} 当前解析到 ${resolved_summary}，没有命中本机公网 IP 候选 ${public_ip_summary}。")
  elif [[ -n "${local_ips}" ]] && ! grep -Fxf <(printf '%s\n' "${resolved_ips}") <(printf '%s\n' "${local_ips}") >/dev/null 2>&1; then
    reasons+=("域名 ${host} 当前解析到 ${resolved_summary}，没有命中本机已知地址 ${local_ip_summary:-未知}。")
  fi

  if port_in_use 80; then
    port_80_usage="$(describe_port_usage 80 || true)"
    reasons+=("本机 80 端口已被占用，外部 HTTP 校验无法完成。")
  fi
  if port_in_use 443; then
    port_443_usage="$(describe_port_usage 443 || true)"
    reasons+=("本机 443 端口已被占用，HTTPS 服务无法接管。")
  fi

  if [[ ${#reasons[@]} -eq 0 ]]; then
    AERISUN_DOMAIN_PREFLIGHT_SUMMARY=""
    AERISUN_DOMAIN_PREFLIGHT_DEBUG_DETAILS=""
    return 0
  fi

  AERISUN_DOMAIN_PREFLIGHT_SUMMARY="$(cat <<EOF
域名 ${host} 似乎没有解析到本机器 IP，也许您的域名输入有误，或当前网络/代理影响了检测🤔
EOF
)"

  if install_debug_enabled; then
    for reason in "${reasons[@]}"; do
      debug_lines+=("- ${reason}")
    done
    if [[ -n "${resolved_summary}" ]]; then
      debug_lines+=("当前 DNS 解析：${host} -> ${resolved_summary}")
    fi
    if [[ -n "${public_ip_summary}" ]]; then
      debug_lines+=("当前探测到的本机公网 IP 候选：${public_ip_summary}")
    fi
    if [[ -n "${local_ip_summary}" ]]; then
      debug_lines+=("当前探测到的本机地址：${local_ip_summary}")
    fi
    if [[ -n "${port_80_usage}" ]]; then
      debug_lines+=("80 端口监听详情：")
      debug_lines+=("${port_80_usage}")
    fi
    if [[ -n "${port_443_usage}" ]]; then
      debug_lines+=("443 端口监听详情：")
      debug_lines+=("${port_443_usage}")
    fi
    AERISUN_DOMAIN_PREFLIGHT_DEBUG_DETAILS="$(printf '%s\n' "${debug_lines[@]}" | awk 'NF')"
  else
    AERISUN_DOMAIN_PREFLIGHT_DEBUG_DETAILS=""
  fi

  if !(command_exists whiptail && [[ -e /dev/tty ]]); then
    printf '[WARN] %s\n' "${AERISUN_DOMAIN_PREFLIGHT_SUMMARY}" >&2
    if [[ -n "${AERISUN_DOMAIN_PREFLIGHT_DEBUG_DETAILS}" ]]; then
      printf '[ERROR] %s\n' "${AERISUN_DOMAIN_PREFLIGHT_DEBUG_DETAILS}" >&2
    fi
  fi

  return 1
}

wait_for_release_ready() {
  load_env_file "${AERISUN_ENV_FILE}"

  local backend_url="http://127.0.0.1:${AERISUN_PORT:-8000}${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"
  wait_for_url "${backend_url}" 180 || die "后端健康检查未通过：${backend_url}"

  if [[ "${AERISUN_DOMAIN}" == http://* ]]; then
    wait_for_url "${AERISUN_SITE_URL}/" 180 || die "前台未就绪：${AERISUN_SITE_URL}/"
    wait_for_url "${AERISUN_SITE_URL}${AERISUN_ADMIN_BASE_PATH:-/admin/}" 180 || die "后台未就绪。"
    wait_for_url "${AERISUN_WALINE_SERVER_URL}/" 180 || die "Waline 未就绪。"
  else
    wait_for_domain_url "${AERISUN_DOMAIN}" "/" 240 \
      || die_domain_https_not_ready "${AERISUN_DOMAIN}" "前台" "/"
    wait_for_domain_url "${AERISUN_DOMAIN}" "${AERISUN_ADMIN_BASE_PATH:-/admin/}" 240 \
      || die_domain_https_not_ready "${AERISUN_DOMAIN}" "后台" "${AERISUN_ADMIN_BASE_PATH:-/admin/}"
    wait_for_domain_url "${AERISUN_DOMAIN}" "${AERISUN_WALINE_BASE_PATH:-/waline}/" 240 \
      || die_domain_https_not_ready "${AERISUN_DOMAIN}" "Waline" "${AERISUN_WALINE_BASE_PATH:-/waline}/"
  fi
}

verify_default_admin_login() {
  load_env_file "${AERISUN_ENV_FILE}"

  local username="${AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE:-${AERISUN_BOOTSTRAP_ADMIN_USERNAME:-}}"
  local password="${AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE:-${AERISUN_BOOTSTRAP_ADMIN_PASSWORD:-}}"
  local payload=""
  [[ -n "${username}" && -n "${password}" ]] || return 1

  payload="$(printf '{"username":"%s","password":"%s"}' "$(json_escape "${username}")" "$(json_escape "${password}")")"
  curl --fail --silent --show-error \
    -H 'content-type: application/json' \
    -d "${payload}" \
    "http://127.0.0.1:${AERISUN_PORT:-8000}/api/v1/admin/auth/login" >/dev/null
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "${value}"
}
