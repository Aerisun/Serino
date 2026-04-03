#!/usr/bin/env bash

validate_release_tag() {
  [[ "$1" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "版本号必须是 v1.2.3 这种格式。"
}

release_download_base_urls() {
  local version="$1"
  printf '%s\n' \
    "${AERISUN_INSTALL_BASE_URL%/}/${version}" \
    "https://github.com/${AERISUN_INSTALL_GITHUB_REPO}/releases/download/${version}"
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

  [[ "${AERISUN_INSTALL_CHANNEL}" == "stable" ]] || die "目前只支持 stable 渠道。"
  fetch_latest_release_tag
}

load_release_manifest() {
  local version="$1"
  local manifest_file="$2"

  download_release_asset "${version}" "${AERISUN_INSTALL_MANIFEST_NAME}" "${manifest_file}"
  # shellcheck disable=SC1090
  source "${manifest_file}"

  [[ -n "${AERISUN_IMAGE_TAG:-}" ]] || die "安装清单缺少 AERISUN_IMAGE_TAG。"
  [[ -n "${AERISUN_IMAGE_FALLBACK_REGISTRY:-}" ]] || die "安装清单缺少 AERISUN_IMAGE_FALLBACK_REGISTRY。"
}
