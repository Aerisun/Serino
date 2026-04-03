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
  local primary="$1"
  local fallback="$2"
  local image_tag="$3"
  local selection="${AERISUN_INSTALL_REGISTRY}"

  case "${selection}" in
    auto)
      if try_pull_release_image "${primary}" "${image_tag}"; then
        printf '%s' "${primary}"
        return 0
      fi
      if try_pull_release_image "${fallback}" "${image_tag}"; then
        printf '%s' "${fallback}"
        return 0
      fi
      die "TCR 和 Docker Hub 都无法拉取镜像。"
      ;;
    tcr)
      try_pull_release_image "${primary}" "${image_tag}" || die "TCR 拉取失败。"
      printf '%s' "${primary}"
      ;;
    dockerhub)
      try_pull_release_image "${fallback}" "${image_tag}" || die "Docker Hub 拉取失败。"
      printf '%s' "${fallback}"
      ;;
    *)
      die "AERISUN_INSTALL_REGISTRY 只能是 auto、tcr 或 dockerhub。"
      ;;
  esac
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

wait_for_release_ready() {
  load_env_file "${AERISUN_ENV_FILE}"

  local backend_url="http://127.0.0.1:${AERISUN_PORT:-8000}${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"
  wait_for_url "${backend_url}" 180 || die "后端健康检查未通过：${backend_url}"

  if [[ "${AERISUN_DOMAIN}" == http://* ]]; then
    wait_for_url "${AERISUN_SITE_URL}/" 180 || die "前台未就绪：${AERISUN_SITE_URL}/"
    wait_for_url "${AERISUN_SITE_URL}${AERISUN_ADMIN_BASE_PATH:-/admin/}" 180 || die "后台未就绪。"
    wait_for_url "${AERISUN_WALINE_SERVER_URL}/" 180 || die "Waline 未就绪。"
  else
    wait_for_domain_url "${AERISUN_DOMAIN}" "/" 240 || die "前台未就绪：${AERISUN_DOMAIN}"
    wait_for_domain_url "${AERISUN_DOMAIN}" "${AERISUN_ADMIN_BASE_PATH:-/admin/}" 240 || die "后台未就绪。"
    wait_for_domain_url "${AERISUN_DOMAIN}" "${AERISUN_WALINE_BASE_PATH:-/waline}/" 240 || die "Waline 未就绪。"
  fi
}

verify_default_admin_login() {
  load_env_file "${AERISUN_ENV_FILE}"

  local response token me_response
  response="$(
    curl --fail --silent --show-error \
      -H 'content-type: application/json' \
      -d '{"username":"admin","password":"admin123"}' \
      "http://127.0.0.1:${AERISUN_PORT:-8000}/api/v1/admin/auth/login"
  )" || return 1

  token="$(printf '%s' "${response}" | tr -d '\n' | sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  [[ -n "${token}" ]] || return 1

  me_response="$(
    curl --fail --silent --show-error \
      -H "Authorization: Bearer ${token}" \
      "http://127.0.0.1:${AERISUN_PORT:-8000}/api/v1/admin/auth/me"
  )" || return 1

  grep -q '"password_change_required"[[:space:]]*:[[:space:]]*true' <<<"${me_response}"
}
