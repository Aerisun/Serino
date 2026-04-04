#!/usr/bin/env bash

validate_release_tag() {
  [[ "$1" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "版本号必须是 v1.2.3 这种格式。"
}

current_channel_base_url() {
  if [[ -n "${AERISUN_INSTALL_BASE_URL:-}" ]]; then
    printf '%s' "${AERISUN_INSTALL_BASE_URL}"
    return 0
  fi

  if [[ "${AERISUN_INSTALL_CHANNEL}" == "dev" ]]; then
    printf '%s' "${AERISUN_INSTALL_DEFAULT_DEV_BASE_URL}"
    return 0
  fi

  printf '%s' "${AERISUN_INSTALL_DEFAULT_BASE_URL}"
}

extract_release_tag_from_env_payload() {
  sed -n "s/^[[:space:]]*AERISUN_INSTALL_VERSION[[:space:]]*=[[:space:]]*['\"]\\{0,1\\}\\(v[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" \
    | head -n 1
}

release_download_base_urls() {
  local version="$1"
  local base_url=""
  base_url="$(current_channel_base_url)"
  if [[ -n "${base_url}" ]]; then
    printf '%s\n' "${base_url%/}/${version}"
  fi
  if [[ "${AERISUN_INSTALL_CHANNEL}" == "stable" ]]; then
    printf '%s\n' "https://github.com/${AERISUN_INSTALL_GITHUB_REPO}/releases/download/${version}"
  fi
}

download_release_asset() {
  local version="$1"
  local asset_name="$2"
  local destination="$3"
  local url=""

  while IFS= read -r base_url; do
    url="${base_url%/}/${asset_name}"
    if curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${url}" -o "${destination}"; then
      return 0
    fi
  done < <(release_download_base_urls "${version}")

  die "无法下载 ${asset_name}（version=${version}）。"
}

fetch_latest_release_tag() {
  local api_url="https://api.github.com/repos/${AERISUN_INSTALL_GITHUB_REPO}/releases/latest"
  local tag
  local base_url=""

  base_url="$(current_channel_base_url)"
  if [[ -n "${base_url}" ]]; then
    tag="$(
      curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 \
        "${base_url%/}/latest.env" 2>/dev/null \
        | extract_release_tag_from_env_payload \
        || true
    )"
    if [[ -n "${tag}" ]]; then
      validate_release_tag "${tag}"
      printf '%s' "${tag}"
      return 0
    fi
  fi

  if [[ "${AERISUN_INSTALL_CHANNEL}" != "stable" ]]; then
    die "渠道 ${AERISUN_INSTALL_CHANNEL} 缺少 latest.env，无法解析当前版本。"
  fi

  tag="$(
    curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${api_url}" \
      | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\(v[^"]*\)".*/\1/p' \
      | head -n 1
  )"

  [[ -n "${tag}" ]] || die "无法解析最新版本号。"
  validate_release_tag "${tag}"
  printf '%s' "${tag}"
}

resolve_release_tag() {
  if [[ -n "${AERISUN_INSTALL_VERSION}" ]]; then
    validate_release_tag "${AERISUN_INSTALL_VERSION}"
    printf '%s' "${AERISUN_INSTALL_VERSION}"
    return 0
  fi

  fetch_latest_release_tag
}

load_release_manifest() {
  local version="$1"
  local manifest_file="$2"

  download_release_asset "${version}" "${AERISUN_INSTALL_MANIFEST_NAME}" "${manifest_file}"
  # shellcheck disable=SC1090
  source "${manifest_file}"

  [[ -n "${AERISUN_IMAGE_TAG:-}" ]] || die "安装清单缺少 AERISUN_IMAGE_TAG。"
  [[ -n "${AERISUN_IMAGE_REGISTRY:-}" ]] || die "安装清单缺少 AERISUN_IMAGE_REGISTRY。"
  AERISUN_INSTALL_CHANNEL="${AERISUN_INSTALL_CHANNEL:-stable}"
  AERISUN_API_IMAGE_NAME="${AERISUN_API_IMAGE_NAME:-serino-api}"
  AERISUN_WEB_IMAGE_NAME="${AERISUN_WEB_IMAGE_NAME:-serino-web}"
  AERISUN_WALINE_IMAGE_NAME="${AERISUN_WALINE_IMAGE_NAME:-serino-waline}"
}
