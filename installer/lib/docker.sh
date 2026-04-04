#!/usr/bin/env bash

compose() {
  if run_as_root docker compose version >/dev/null 2>&1; then
    run_as_root env COMPOSE_PROJECT_NAME="${AERISUN_COMPOSE_PROJECT_NAME}" \
      docker compose --env-file "${AERISUN_ENV_FILE}" -f "${AERISUN_COMPOSE_FILE}" "$@"
    return 0
  fi

  if command_exists docker-compose; then
    run_as_root env COMPOSE_PROJECT_NAME="${AERISUN_COMPOSE_PROJECT_NAME}" \
      docker-compose --env-file "${AERISUN_ENV_FILE}" -f "${AERISUN_COMPOSE_FILE}" "$@"
    return 0
  fi

  die "当前机器缺少 docker compose。"
}

ensure_docker_installed() {
  if command_exists docker && (docker compose version >/dev/null 2>&1 || command_exists docker-compose); then
    run_as_root systemctl enable --now docker >/dev/null
    return 0
  fi

  log_info "正在自动安装 Docker。"
  local tmp_dir
  tmp_dir="$(make_temp_dir)"
  curl --fail --location --silent --show-error https://get.docker.com -o "${tmp_dir}/get-docker.sh"
  run_as_root sh "${tmp_dir}/get-docker.sh"
  cleanup_temp_dir "${tmp_dir}"
  run_as_root systemctl enable --now docker >/dev/null

  if ! (run_as_root docker compose version >/dev/null 2>&1 || command_exists docker-compose); then
    die "Docker 已安装，但缺少 docker compose。"
  fi
}

try_pull_release_image() {
  local registry="$1"
  local image_tag="$2"
  [[ -n "${registry}" ]] || return 1
  run_as_root docker pull "${registry}/serino-api:${image_tag}" >/dev/null 2>&1
}

resolve_active_registry() {
  local registry="$1"
  local image_tag="$2"
  [[ -n "${registry}" ]] || die "安装清单缺少 Docker Hub 镜像前缀。"
  try_pull_release_image "${registry}" "${image_tag}" || die "Docker Hub 拉取失败。"
  printf '%s' "${registry}"
}

compose_up_release() {
  compose pull
  compose up -d
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

detect_public_ip_candidate() {
  curl --silent --show-error --max-time 5 https://api64.ipify.org 2>/dev/null || true
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

print_domain_https_failure_details() {
  local host="$1"
  local label="$2"
  local path="$3"
  local resolved_ips=""
  local resolved_summary=""
  local local_ips=""
  local local_ip_summary=""
  local public_ip=""
  local caddy_logs=""
  local -a dns_reasons=()
  local -a firewall_reasons=()
  local -a cert_reasons=()
  local -a backend_reasons=()

  resolved_ips="$(resolve_host_ips "${host}" 2>/dev/null || true)"
  resolved_summary="$(printf '%s\n' "${resolved_ips}" | awk 'NF' | join_lines 2>/dev/null || true)"
  local_ips="$(list_local_ip_candidates)"
  local_ip_summary="$(printf '%s\n' "${local_ips}" | awk 'NF' | join_lines 2>/dev/null || true)"
  public_ip="$(detect_public_ip_candidate)"

  if [[ -z "${resolved_summary}" ]]; then
    dns_reasons+=("域名 ${host} 当前无法解析，请确认 A/AAAA 记录已经生效。")
  else
    if [[ -n "${public_ip}" ]] && ! domain_points_to_candidate_ip "${resolved_ips}" "${public_ip}"; then
      dns_reasons+=("域名 ${host} 当前解析到 ${resolved_summary}，没有命中本机公网 IP ${public_ip}。")
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

  log_error "${label} 未通过 HTTPS 就绪检查：https://${host}${path}"

  if [[ ${#dns_reasons[@]} -eq 0 && ${#firewall_reasons[@]} -eq 0 && ${#cert_reasons[@]} -eq 0 && ${#backend_reasons[@]} -eq 0 ]]; then
    log_error "未能自动定位具体原因，请重点检查 DNS、生效中的 80/443、安全组和 Caddy 日志。"
  else
    local reason=""
    if [[ ${#dns_reasons[@]} -gt 0 ]]; then
      printf '[ERROR] DNS 问题：\n' >&2
      for reason in "${dns_reasons[@]}"; do
        printf '[ERROR] - %s\n' "${reason}" >&2
      done
    fi
    if [[ ${#firewall_reasons[@]} -gt 0 ]]; then
      printf '[ERROR] 安全组问题：\n' >&2
      for reason in "${firewall_reasons[@]}"; do
        printf '[ERROR] - %s\n' "${reason}" >&2
      done
      printf '[ERROR] - 请同时确认云服务器安全组与本机防火墙都已放行 80/443。\n' >&2
    fi
    if [[ ${#cert_reasons[@]} -gt 0 ]]; then
      printf '[ERROR] 证书问题：\n' >&2
      for reason in "${cert_reasons[@]}"; do
        printf '[ERROR] - %s\n' "${reason}" >&2
      done
    fi
    if [[ ${#backend_reasons[@]} -gt 0 ]]; then
      printf '[ERROR] 后端容器问题：\n' >&2
      for reason in "${backend_reasons[@]}"; do
        printf '[ERROR] - %s\n' "${reason}" >&2
      done
      printf '[ERROR] - 可执行 aerisunctl logs api waline caddy 查看详细日志。\n' >&2
    fi
  fi

  if [[ -n "${resolved_summary}" ]]; then
    printf '[ERROR] 当前 DNS 解析：%s -> %s\n' "${host}" "${resolved_summary}" >&2
  fi
  if [[ -n "${public_ip}" ]]; then
    printf '[ERROR] 当前探测到的本机公网 IP：%s\n' "${public_ip}" >&2
  fi
  if [[ -n "${local_ip_summary}" ]]; then
    printf '[ERROR] 当前探测到的本机地址：%s\n' "${local_ip_summary}" >&2
  fi

  if [[ -n "${caddy_logs}" ]]; then
    printf '[ERROR] 最近 Caddy 日志：\n%s\n' "${caddy_logs}" >&2
  fi
}

die_domain_https_not_ready() {
  local host="$1"
  local label="$2"
  local path="$3"

  print_domain_https_failure_details "${host}" "${label}" "${path}"
  exit 1
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
