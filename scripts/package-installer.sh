#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${AERISUN_INSTALL_DIST_DIR:-${PROJECT_DIR}/dist/installer}"
RELEASE_TAG="${AERISUN_RELEASE_TAG:?AERISUN_RELEASE_TAG is required}"
VERSION="${AERISUN_RELEASE_VERSION:?AERISUN_RELEASE_VERSION is required}"
INSTALL_CHANNEL="${AERISUN_INSTALL_CHANNEL:-stable}"
IMAGE_REGISTRY="${AERISUN_IMAGE_REGISTRY:-}"
API_IMAGE_NAME="serino-api"
WEB_IMAGE_NAME="serino-web"
WALINE_IMAGE_NAME="serino-waline"
INSTALL_BASE_URL="${AERISUN_INSTALL_BASE_URL:-}"
RELEASED_AT="${AERISUN_RELEASED_AT:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}"
RELEASE_NOTES_FILE="${AERISUN_RELEASE_NOTES_FILE:-}"
UPDATE_SIGNING_REQUIRED="${AERISUN_UPDATE_SIGNING_REQUIRED:-false}"
UPDATE_SIGNING_PRIVATE_KEY_B64="${AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64:-}"
UPDATE_SIGNATURE_KEY_ID="${AERISUN_UPDATE_SIGNATURE_KEY_ID:-serino-release}"
UPDATE_TRUSTED_PUBLIC_KEY_B64="${AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64:-}"
UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE=""

compute_sha256() {
  local file="$1"

  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${file}" | awk '{print $1}'
    return 0
  fi

  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${file}" | awk '{print $1}'
    return 0
  fi

  echo "sha256sum or shasum is required to package installer assets" >&2
  return 1
}

normalize_bool() {
  local name="$1"
  local value="$2"

  case "${value,,}" in
    1|true|yes|y|on)
      printf 'true'
      ;;
    0|false|no|n|off|"")
      printf 'false'
      ;;
    *)
      echo "${name} must be true or false, got '${value}'." >&2
      return 1
      ;;
  esac
}

resolve_update_signing_configuration() {
  local signing_required=""
  local private_key_present=""

  signing_required="$(normalize_bool "AERISUN_UPDATE_SIGNING_REQUIRED" "${UPDATE_SIGNING_REQUIRED}")"
  private_key_present="$(printf '%s' "${UPDATE_SIGNING_PRIVATE_KEY_B64}" | tr -d '[:space:]')"

  if [[ -z "${private_key_present}" ]]; then
    if [[ "${signing_required}" == "true" ]]; then
      echo "AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64 is required when AERISUN_UPDATE_SIGNING_REQUIRED=true." >&2
      exit 1
    fi
    return 0
  fi

  command -v openssl >/dev/null 2>&1 || {
    echo "openssl is required to sign release metadata." >&2
    exit 1
  }

  if ! UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE="$(
    AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64="${UPDATE_SIGNING_PRIVATE_KEY_B64}" \
    AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64="${UPDATE_TRUSTED_PUBLIC_KEY_B64}" \
    python3 - <<'PY'
from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def normalized_b64(name: str) -> str:
    return "".join(os.environ.get(name, "").split())


def decode_b64(name: str, value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:
        raise SystemExit(f"{name} must be valid base64.") from exc


private_key_b64 = normalized_b64("AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64")
trusted_public_key_b64 = normalized_b64("AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64")

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    private_key_path = tmp_path / "release-signing-key.pem"
    derived_public_key_path = tmp_path / "release-signing-key.public.pem"
    private_key_path.write_bytes(decode_b64("AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64", private_key_b64))
    try:
        subprocess.run(
            ["openssl", "pkey", "-in", str(private_key_path), "-pubout", "-out", str(derived_public_key_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr)
        raise SystemExit("AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64 is not a readable private key.") from exc

    derived_public_key = derived_public_key_path.read_bytes()

    if trusted_public_key_b64:
        provided_public_key_path = tmp_path / "provided-public-key.pem"
        normalized_public_key_path = tmp_path / "provided-public-key.normalized.pem"
        provided_public_key_path.write_bytes(
            decode_b64("AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64", trusted_public_key_b64)
        )
        try:
            subprocess.run(
                [
                    "openssl",
                    "pkey",
                    "-pubin",
                    "-in",
                    str(provided_public_key_path),
                    "-pubout",
                    "-out",
                    str(normalized_public_key_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(exc.stderr)
            raise SystemExit("AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64 is not a readable public key.") from exc

        if normalized_public_key_path.read_bytes() != derived_public_key:
            raise SystemExit(
                "AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64 does not match "
                "AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64."
            )

    print(base64.b64encode(derived_public_key).decode("ascii"))
PY
  )"; then
    exit 1
  fi

  export AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64="${UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE}"
}

render_release_metadata() {
  local bundle_sha256="$1"
  local notes_file="$2"

  python3 - \
    "${DIST_DIR}" \
    "${INSTALL_CHANNEL}" \
    "${RELEASE_TAG}" \
    "${VERSION}" \
    "${INSTALL_BASE_URL%/}" \
    "${IMAGE_REGISTRY}" \
    "${API_IMAGE_NAME}" \
    "${WEB_IMAGE_NAME}" \
    "${WALINE_IMAGE_NAME}" \
    "${bundle_sha256}" \
    "${RELEASED_AT}" \
    "${notes_file}" <<'PY'
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

dist = Path(sys.argv[1])
channel = sys.argv[2]
release_tag = sys.argv[3]
image_tag = sys.argv[4]
base_url = sys.argv[5].rstrip("/")
image_registry = sys.argv[6]
api_image = sys.argv[7]
web_image = sys.argv[8]
waline_image = sys.argv[9]
bundle_sha256 = sys.argv[10]
released_at = sys.argv[11]
notes_file = Path(sys.argv[12])

version_dir = dist / release_tag
version_dir.mkdir(parents=True, exist_ok=True)

notes = notes_file.read_text(encoding="utf-8")
(dist / "release-notes.md").write_text(notes, encoding="utf-8")
(version_dir / "release-notes.md").write_text(notes, encoding="utf-8")
notes_sha256 = __import__("hashlib").sha256(notes.encode("utf-8")).hexdigest()
trusted_public_key_b64 = "".join(os.environ.get("AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64", "").split())

release_json_url = f"{base_url}/{release_tag}/release.json"
release_notes_url = f"{base_url}/{release_tag}/release-notes.md"
manifest_url = f"{base_url}/{release_tag}/aerisun-installer-manifest.env"
bundle_url = f"{base_url}/{release_tag}/aerisun-installer-bundle.tar.gz"

signed = {
    "schema_version": 1,
    "channel": channel,
    "version": release_tag,
    "image_tag": image_tag,
    "image_registry": image_registry,
    "api_image_name": api_image,
    "web_image_name": web_image,
    "waline_image_name": waline_image,
    "released_at": released_at,
    "manifest_url": manifest_url,
    "bundle_url": bundle_url,
    "bundle_sha256": bundle_sha256,
    "release_notes_url": release_notes_url,
    "release_notes_sha256": notes_sha256,
    "trusted_public_key_b64": trusted_public_key_b64 or None,
}

signature = None
signing_required = os.environ.get("AERISUN_UPDATE_SIGNING_REQUIRED", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}
private_key_b64 = "".join(os.environ.get("AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64", "").split())
if signing_required and not private_key_b64:
    raise SystemExit("AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64 is required when AERISUN_UPDATE_SIGNING_REQUIRED=true.")
if private_key_b64:
    if not trusted_public_key_b64:
        raise SystemExit("AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64 is required when signing release metadata.")
    key_id = os.environ.get("AERISUN_UPDATE_SIGNATURE_KEY_ID", "serino-release").strip() or "serino-release"
    canonical = json.dumps(signed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        key_path = tmp_path / "release-signing-key.pem"
        public_key_path = tmp_path / "release-signing-key.public.pem"
        payload_path = tmp_path / "release-payload.json"
        sig_path = tmp_path / "release-payload.sig"
        try:
            key_path.write_bytes(base64.b64decode(private_key_b64, validate=True))
            public_key_path.write_bytes(base64.b64decode(trusted_public_key_b64, validate=True))
        except Exception as exc:
            raise SystemExit("release signing key values must be valid base64.") from exc
        payload_path.write_bytes(canonical)
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(key_path), "-out", str(sig_path), str(payload_path)],
            check=True,
        )
        subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(public_key_path),
                "-signature",
                str(sig_path),
                str(payload_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        signature = {
            "alg": "rsa-sha256",
            "key_id": key_id,
            "value": base64.b64encode(sig_path.read_bytes()).decode("ascii"),
        }

latest = {
    "schema_version": 1,
    "channel": channel,
    "version": release_tag,
    "released_at": released_at,
    "release_json_url": release_json_url,
    "release_notes_url": release_notes_url,
}
release = {
    "schema_version": 1,
    "channel": channel,
    "version": release_tag,
    "released_at": released_at,
    "bundle_sha256": bundle_sha256,
    "signed": signed,
    "signature": signature,
}

for path, payload in (
    (dist / "latest.json", latest),
    (dist / "release.json", release),
    (version_dir / "release.json", release),
):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

assert_install_script_bootstrap_header() {
  local install_script="${PROJECT_DIR}/installer/install.sh"
  local expected_header=""
  local actual_header=""

  expected_header="$(printf '%s\n%s\n\n' '#!/usr/bin/env bash' 'set -Eeuo pipefail')"
  actual_header="$(sed -n '1,3p' "${install_script}")"
  if [[ "${actual_header}" != "${expected_header}" ]]; then
    echo "installer/install.sh bootstrap header changed; update package-installer.sh before publishing." >&2
    exit 1
  fi
}

render_bootstrap_script() {
  local target_file="$1"
  local channel="$2"
  local base_url="$3"
  local install_version="${4:-}"

  assert_install_script_bootstrap_header

  {
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'set -euo pipefail'
    printf '\n'
    printf 'export AERISUN_INSTALL_CHANNEL="${AERISUN_INSTALL_CHANNEL:-%s}"\n' "${channel}"
    if [[ -n "${base_url}" ]]; then
      printf 'export AERISUN_INSTALL_BASE_URL="${AERISUN_INSTALL_BASE_URL:-%s}"\n' "${base_url}"
    fi
    if [[ -n "${UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE}" ]]; then
      printf 'export AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64="${AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64:-%s}"\n' \
        "${UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE}"
    fi
    if [[ -n "${install_version}" ]]; then
      printf 'export AERISUN_INSTALL_VERSION="${AERISUN_INSTALL_VERSION:-%s}"\n' "${install_version}"
    fi
    printf '\n'
    tail -n +4 "${PROJECT_DIR}/installer/install.sh"
  } > "${target_file}"

  chmod 0755 "${target_file}"
}

case "${INSTALL_CHANNEL}" in
  stable)
    IMAGE_REGISTRY="${IMAGE_REGISTRY:?AERISUN_IMAGE_REGISTRY is required for stable channel}"
    if [[ -z "${INSTALL_BASE_URL}" ]]; then
      INSTALL_BASE_URL="https://install.aerisun.top/serino"
    fi
    ;;
  dev)
    IMAGE_REGISTRY="${IMAGE_REGISTRY:?AERISUN_IMAGE_REGISTRY is required for dev channel}"
    API_IMAGE_NAME="serino-dev-api"
    WEB_IMAGE_NAME="serino-dev-web"
    WALINE_IMAGE_NAME="serino-dev-waline"
    if [[ -z "${INSTALL_BASE_URL}" ]]; then
      INSTALL_BASE_URL="https://install.aerisun.top/serino/dev"
    fi
    ;;
  *)
    echo "Unsupported AERISUN_INSTALL_CHANNEL=${INSTALL_CHANNEL}" >&2
    exit 1
    ;;
esac

resolve_update_signing_configuration

mkdir -p "${DIST_DIR}"
find "${DIST_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

render_bootstrap_script "${DIST_DIR}/install.latest.sh" "${INSTALL_CHANNEL}" "${INSTALL_BASE_URL}"
render_bootstrap_script "${DIST_DIR}/install.sh" "${INSTALL_CHANNEL}" "${INSTALL_BASE_URL}" "${RELEASE_TAG}"
cp "${PROJECT_DIR}/docker-compose.release.yml" "${DIST_DIR}/docker-compose.release.yml"
cp "${PROJECT_DIR}/.env.production.local.example" "${DIST_DIR}/.env.production.local.example"

tar -czf "${DIST_DIR}/aerisun-installer-bundle.tar.gz" \
  -C "${PROJECT_DIR}" \
  docker-compose.release.yml \
  .env.production.local.example \
  installer

BUNDLE_SHA256="$(compute_sha256 "${DIST_DIR}/aerisun-installer-bundle.tar.gz")"

RENDERED_RELEASE_NOTES="$(mktemp "${TMPDIR:-/tmp}/serino-release-notes.XXXXXX.md")"
if [[ -n "${RELEASE_NOTES_FILE}" ]]; then
  cp "${RELEASE_NOTES_FILE}" "${RENDERED_RELEASE_NOTES}"
else
  cat > "${RENDERED_RELEASE_NOTES}" <<EOF
# Serino ${RELEASE_TAG}

- 发布版本：${RELEASE_TAG}
- 镜像版本：${VERSION}

本版本未提供额外更新说明。
EOF
fi
render_release_metadata "${BUNDLE_SHA256}" "${RENDERED_RELEASE_NOTES}"
rm -f "${RENDERED_RELEASE_NOTES}"

if [[ -n "${UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE}" ]]; then
  mkdir -p "${DIST_DIR}/${RELEASE_TAG}"
  printf '%s\n' "${UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE}" > "${DIST_DIR}/update-trusted-public-key.b64"
  printf '%s\n' "${UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE}" > "${DIST_DIR}/${RELEASE_TAG}/update-trusted-public-key.b64"
fi

cat > "${DIST_DIR}/latest.env" <<EOF
AERISUN_INSTALL_VERSION=${RELEASE_TAG}
AERISUN_INSTALL_BUNDLE_SHA256=${BUNDLE_SHA256}
EOF

{
  cat <<EOF
AERISUN_INSTALL_CHANNEL=${INSTALL_CHANNEL}
AERISUN_INSTALL_VERSION=${RELEASE_TAG}
AERISUN_IMAGE_TAG=${VERSION}
AERISUN_IMAGE_REGISTRY=${IMAGE_REGISTRY}
AERISUN_API_IMAGE_NAME=${API_IMAGE_NAME}
AERISUN_WEB_IMAGE_NAME=${WEB_IMAGE_NAME}
AERISUN_WALINE_IMAGE_NAME=${WALINE_IMAGE_NAME}
AERISUN_INSTALL_BUNDLE_SHA256=${BUNDLE_SHA256}
EOF
  if [[ -n "${UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE}" ]]; then
    printf 'AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64=%s\n' "${UPDATE_TRUSTED_PUBLIC_KEY_B64_EFFECTIVE}"
  fi
} > "${DIST_DIR}/aerisun-installer-manifest.env"
