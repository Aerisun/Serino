#!/usr/bin/env bash

generate_secret() {
  od -An -tx1 -N32 /dev/urandom | tr -d ' \n'
}

encode_env_b64() {
  printf '%s' "$1" | base64 | tr -d '\n'
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
  [[ -f "${file}" ]] || return 0
  set -a
  # shellcheck disable=SC1090
  source "${file}"
  set +a
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp_file

  tmp_file="$(mktemp)"
  if [[ -f "${file}" ]]; then
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
    ' "${file}" > "${tmp_file}"
  else
    printf '%s=%s\n' "${key}" "${value}" > "${tmp_file}"
  fi

  run_as_root install -m 0600 "${tmp_file}" "${file}"
  rm -f "${tmp_file}"
}

unset_env_value() {
  local file="$1"
  local key="$2"
  local tmp_file

  [[ -f "${file}" ]] || return 0

  tmp_file="$(mktemp)"
  awk -v key="${key}" '$0 !~ ("^" key "=") { print }' "${file}" > "${tmp_file}"
  run_as_root install -m 0600 "${tmp_file}" "${file}"
  rm -f "${tmp_file}"
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
  AERISUN_CORS_ORIGINS_VALUE="[\"${site_url}\"]"
  AERISUN_WALINE_SECURE_DOMAINS_VALUE="${host}"
  AERISUN_WALINE_JWT_TOKEN_VALUE="$(generate_secret)"
  AERISUN_IMAGE_REGISTRY_VALUE="${active_registry}"
  AERISUN_IMAGE_TAG_VALUE="${image_tag}"
}

write_production_env() {
  local output_file="$1"
  local tmp_file

  tmp_file="$(mktemp)"
  cat > "${tmp_file}" <<EOF
AERISUN_ENVIRONMENT=production
AERISUN_DOMAIN=${AERISUN_DOMAIN_VALUE}
AERISUN_SITE_URL=${AERISUN_SITE_URL_VALUE}
AERISUN_WALINE_SERVER_URL=${AERISUN_WALINE_SERVER_URL_VALUE}
AERISUN_CORS_ORIGINS=${AERISUN_CORS_ORIGINS_VALUE}
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
EOF

  run_as_root install -m 0600 "${tmp_file}" "${output_file}"
  rm -f "${tmp_file}"
}
