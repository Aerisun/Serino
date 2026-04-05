#!/usr/bin/env bash

generate_secret() {
  od -An -tx1 -N32 /dev/urandom | tr -d ' \n'
}

trim_env_input() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

encode_env_b64() {
  printf '%s' "$1" | base64 | tr -d '\n'
}

quote_env_literal() {
  local value="$1"
  value="${value//\'/\'\"\'\"\'}"
  printf "'%s'" "${value}"
}

install_managed_env_file() {
  local source_file="$1"
  local target_file="$2"
  run_as_root install -o root -g "${SERINO_SERVICE_GROUP}" -m 0640 "${source_file}" "${target_file}"
}

managed_file_exists() {
  local file="$1"
  path_is_file "${file}"
}

normalize_host_input() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value#http://}"
  value="${value#https://}"
  value="${value%%/*}"
  printf '%s' "${value}"
}

load_env_file() {
  local file="$1"
  local tmp_file=""
  managed_file_exists "${file}" || return 0

  if [[ ! -r "${file}" ]]; then
    tmp_file="$(make_temp_file)"
    run_as_root cat "${file}" > "${tmp_file}"
    file="${tmp_file}"
  fi

  set -a
  # shellcheck disable=SC1090
  source "${file}"
  set +a

  if [[ -n "${tmp_file}" ]]; then
    rm -f "${tmp_file}"
  fi
}

copy_env_file_for_read() {
  local file="$1"
  local tmp_file=""

  managed_file_exists "${file}" || return 1

  if [[ -r "${file}" ]]; then
    printf '%s' "${file}"
    return 0
  fi

  tmp_file="$(make_temp_file)"
  run_as_root cat "${file}" > "${tmp_file}"
  printf '%s' "${tmp_file}"
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp_file
  local source_file=""

  tmp_file="$(make_temp_file)"
  if managed_file_exists "${file}"; then
    source_file="$(copy_env_file_for_read "${file}")"
    awk -v key="${key}" -v value="${value}" '
      BEGIN { replaced = 0 }
      $0 ~ ("^" key "=") {
        print key "=" value
        replaced = 1
        next
      }
      { print }
      END {
        if (!replaced) {
          print key "=" value
        }
      }
    ' "${source_file}" > "${tmp_file}"
  else
    printf '%s=%s\n' "${key}" "${value}" > "${tmp_file}"
  fi

  install_managed_env_file "${tmp_file}" "${file}"
  rm -f "${tmp_file}"
  if [[ -n "${source_file}" && "${source_file}" != "${file}" ]]; then
    rm -f "${source_file}"
  fi
}

unset_env_value() {
  local file="$1"
  local key="$2"
  local tmp_file
  local source_file=""

  managed_file_exists "${file}" || return 0

  tmp_file="$(make_temp_file)"
  source_file="$(copy_env_file_for_read "${file}")"
  awk -v key="${key}" '$0 !~ ("^" key "=") { print }' "${source_file}" > "${tmp_file}"
  install_managed_env_file "${tmp_file}" "${file}"
  rm -f "${tmp_file}"
  if [[ -n "${source_file}" && "${source_file}" != "${file}" ]]; then
    rm -f "${source_file}"
  fi
}

build_runtime_configuration() {
  local access_mode="$1"
  local host="$2"
  local active_registry="$3"
  local image_tag="$4"
  local site_url=""

  if [[ "${access_mode}" == "domain" ]]; then
    AERISUN_DOMAIN_VALUE="${host}"
    site_url="https://${host}"
  else
    AERISUN_DOMAIN_VALUE="http://${host}"
    site_url="http://${host}"
  fi

  AERISUN_SITE_URL_VALUE="${site_url}"
  AERISUN_WALINE_SERVER_URL_VALUE="${site_url}/waline"
  AERISUN_CORS_ORIGINS_VALUE="$(build_cors_origins_json "${site_url}")"
  AERISUN_WALINE_SECURE_DOMAINS_VALUE="${host}"
  AERISUN_WALINE_JWT_TOKEN_VALUE="$(generate_secret)"
  AERISUN_IMAGE_REGISTRY_VALUE="${active_registry}"
  AERISUN_IMAGE_TAG_VALUE="${image_tag}"
}

write_production_env() {
  local output_file="$1"
  local tmp_file

  tmp_file="$(make_temp_file)"
  cat > "${tmp_file}" <<EOF
AERISUN_ENVIRONMENT=production
AERISUN_INSTALL_CHANNEL=${AERISUN_INSTALL_CHANNEL}
AERISUN_INSTALL_BASE_URL=${AERISUN_INSTALL_BASE_URL}
AERISUN_DOMAIN=${AERISUN_DOMAIN_VALUE}
AERISUN_SITE_URL=${AERISUN_SITE_URL_VALUE}
AERISUN_WALINE_SERVER_URL=${AERISUN_WALINE_SERVER_URL_VALUE}
AERISUN_CORS_ORIGINS=$(quote_env_literal "${AERISUN_CORS_ORIGINS_VALUE}")
WALINE_SECURE_DOMAINS=${AERISUN_WALINE_SECURE_DOMAINS_VALUE}
WALINE_JWT_TOKEN=${AERISUN_WALINE_JWT_TOKEN_VALUE}
WALINE_GRAVATAR_STR=
AERISUN_SEED_REFERENCE_DATA=true
AERISUN_DATA_BACKFILL_ENABLED=true
AERISUN_BOOTSTRAP_ADMIN_USERNAME_B64=$(encode_env_b64 "${AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE}")
AERISUN_BOOTSTRAP_ADMIN_PASSWORD_B64=$(encode_env_b64 "${AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE}")
AERISUN_STORE_BIND_DIR=${AERISUN_DATA_DIR}
AERISUN_IMAGE_REGISTRY=${AERISUN_IMAGE_REGISTRY_VALUE}
AERISUN_IMAGE_TAG=${AERISUN_IMAGE_TAG_VALUE}
AERISUN_API_IMAGE_NAME=${AERISUN_API_IMAGE_NAME}
AERISUN_WEB_IMAGE_NAME=${AERISUN_WEB_IMAGE_NAME}
AERISUN_WALINE_IMAGE_NAME=${AERISUN_WALINE_IMAGE_NAME}
AERISUN_RELEASE_VERSION=${AERISUN_IMAGE_TAG_VALUE}
SERINO_RUNTIME_UID=${SERINO_RUNTIME_UID}
SERINO_RUNTIME_GID=${SERINO_RUNTIME_GID}
EOF

  install_managed_env_file "${tmp_file}" "${output_file}"
  rm -f "${tmp_file}"
}

build_cors_origins_json() {
  local site_url="$1"
  site_url="$(trim_env_input "${site_url}")"
  [[ -n "${site_url}" ]] || return 1
  [[ "${site_url}" =~ ^https?://[^[:space:]]+$ ]] || return 1
  printf '["%s"]' "${site_url}"
}

extract_host_from_url() {
  local value="$1"
  value="$(trim_env_input "${value}")"
  value="${value#http://}"
  value="${value#https://}"
  value="${value%%/*}"
  printf '%s' "${value}"
}

derive_domain_value() {
  local domain=""
  local host=""

  domain="$(trim_env_input "${AERISUN_DOMAIN:-${AERISUN_DOMAIN_VALUE:-}}")"
  if [[ -n "${domain}" ]]; then
    printf '%s' "${domain}"
    return 0
  fi

  host="$(trim_env_input "${AERISUN_INSTALL_HOST:-}")"
  [[ -n "${host}" ]] || return 1

  if [[ "${AERISUN_INSTALL_ACCESS_MODE:-}" == "ip" ]]; then
    printf 'http://%s' "${host}"
  else
    printf '%s' "${host}"
  fi
}

derive_site_url_value() {
  local site_url=""
  local domain_value=""

  site_url="$(trim_env_input "${AERISUN_SITE_URL:-${AERISUN_SITE_URL_VALUE:-}}")"
  if [[ -n "${site_url}" ]]; then
    printf '%s' "${site_url}"
    return 0
  fi

  domain_value="$(derive_domain_value || true)"
  [[ -n "${domain_value}" ]] || return 1

  if [[ "${domain_value}" =~ ^https?:// ]]; then
    printf '%s' "${domain_value}"
  else
    printf 'https://%s' "${domain_value}"
  fi
}

normalize_production_env_file() {
  local file="$1"
  local site_url=""
  local normalized_cors=""
  local domain_value=""
  local waline_secure_domains=""
  local waline_server_url=""
  local release_version=""

  load_env_file "${file}"

  site_url="$(derive_site_url_value || true)"
  [[ -n "${site_url}" ]] || die "缺少 AERISUN_SITE_URL，无法重建生产环境配置。"
  normalized_cors="$(build_cors_origins_json "${site_url}")" || die "AERISUN_SITE_URL 格式无效：${site_url}"
  domain_value="$(derive_domain_value || true)"
  waline_secure_domains="$(extract_host_from_url "${site_url}")"
  waline_server_url="${site_url}${AERISUN_WALINE_BASE_PATH:-/waline}"

  set_env_value "${file}" "AERISUN_SITE_URL" "${site_url}"
  if [[ -n "${domain_value}" ]]; then
    set_env_value "${file}" "AERISUN_DOMAIN" "${domain_value}"
  fi
  if [[ -n "${waline_secure_domains}" ]]; then
    set_env_value "${file}" "WALINE_SECURE_DOMAINS" "${waline_secure_domains}"
  fi
  set_env_value "${file}" "AERISUN_WALINE_SERVER_URL" "${waline_server_url}"
  set_env_value "${file}" "AERISUN_CORS_ORIGINS" "$(quote_env_literal "${normalized_cors}")"

  release_version="${AERISUN_RELEASE_VERSION:-${AERISUN_IMAGE_TAG:-}}"
  if [[ -n "${release_version}" ]]; then
    set_env_value "${file}" "AERISUN_RELEASE_VERSION" "${release_version}"
  fi
}
