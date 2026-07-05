from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_project_bash(script: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", script],
        cwd=PROJECT_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def write_minimal_bootstrap_bundle(bootstrap_root: Path) -> Path:
    installer_root = bootstrap_root / "bundle" / "installer"
    installer_root.mkdir(parents=True)

    (bootstrap_root / "v9.9.9").mkdir(parents=True)
    bundled_install = installer_root / "install.sh"
    bundled_install.write_text(
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        'if [[ "${1:-}" == "--bundled" ]]; then\n'
        "  shift\n"
        "fi\n"
        "printf 'bundled-ok\\n'\n",
        encoding="utf-8",
    )
    bundled_install.chmod(0o755)

    bundle_file = bootstrap_root / "v9.9.9" / "aerisun-installer-bundle.tar.gz"
    with tarfile.open(bundle_file, "w:gz") as archive:
        archive.add(installer_root, arcname="installer")

    return bundle_file


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def generate_rsa_signing_key_pair_b64(tmp_path: Path, name: str) -> tuple[str, str]:
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl is required for release signing tests")

    private_key = tmp_path / f"{name}.private.pem"
    public_key = tmp_path / f"{name}.public.pem"
    subprocess.run(
        [openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [openssl, "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True,
        capture_output=True,
        text=True,
    )
    return (
        base64.b64encode(private_key.read_bytes()).decode("ascii"),
        base64.b64encode(public_key.read_bytes()).decode("ascii"),
    )


def verify_release_signature(tmp_path: Path, release_payload: dict[str, object], public_key_b64: str) -> None:
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl is required for release signing tests")

    signed_payload = release_payload["signed"]
    signature = release_payload["signature"]
    assert isinstance(signed_payload, dict)
    assert isinstance(signature, dict)

    payload_file = tmp_path / "release-payload.json"
    signature_file = tmp_path / "release-payload.sig"
    public_key_file = tmp_path / "release-public.pem"
    payload_file.write_bytes(
        json.dumps(signed_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature_file.write_bytes(base64.b64decode(str(signature["value"])))
    public_key_file.write_bytes(base64.b64decode(public_key_b64))

    subprocess.run(
        [
            openssl,
            "dgst",
            "-sha256",
            "-verify",
            str(public_key_file),
            "-signature",
            str(signature_file),
            str(payload_file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_installer_scripts_are_source_safe() -> None:
    completed = run_project_bash(
        """
source installer/install.sh
source installer/upgrade.sh
source installer/uninstall.sh
source scripts/release-smoke-gate.sh
printf 'ok\\n'
"""
    )

    assert completed.stdout.strip() == "ok"


def test_install_script_supports_stdin_bootstrap_execution(tmp_path: Path) -> None:
    bootstrap_root = tmp_path / "bootstrap"
    bundle_file = write_minimal_bootstrap_bundle(bootstrap_root)
    bundle_sha256 = hashlib.sha256(bundle_file.read_bytes()).hexdigest()
    (bootstrap_root / "latest.env").write_text(
        f"AERISUN_INSTALL_VERSION=v9.9.9\nAERISUN_INSTALL_BUNDLE_SHA256={bundle_sha256}\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["AERISUN_INSTALL_BASE_URL"] = f"file://{bootstrap_root}"
    env["AERISUN_INSTALL_CHANNEL"] = "stable"
    env["AERISUN_INSTALL_BUNDLE_NAME"] = "aerisun-installer-bundle.tar.gz"

    install_script = (PROJECT_ROOT / "installer" / "install.sh").read_text(encoding="utf-8")
    completed = subprocess.run(
        ["bash"],
        cwd=PROJECT_ROOT,
        input=install_script,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.stdout.strip() == "bundled-ok"


def test_install_script_rejects_stdin_bootstrap_bundle_with_mismatched_sha256(tmp_path: Path) -> None:
    bootstrap_root = tmp_path / "bootstrap"
    write_minimal_bootstrap_bundle(bootstrap_root)
    (bootstrap_root / "latest.env").write_text(
        "AERISUN_INSTALL_VERSION=v9.9.9\nAERISUN_INSTALL_BUNDLE_SHA256=" + ("0" * 64) + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["AERISUN_INSTALL_BASE_URL"] = f"file://{bootstrap_root}"
    env["AERISUN_INSTALL_CHANNEL"] = "stable"
    env["AERISUN_INSTALL_BUNDLE_NAME"] = "aerisun-installer-bundle.tar.gz"

    install_script = (PROJECT_ROOT / "installer" / "install.sh").read_text(encoding="utf-8")
    completed = subprocess.run(
        ["bash"],
        cwd=PROJECT_ROOT,
        input=install_script,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode != 0
    assert completed.stdout.strip() == ""
    assert "sha256 校验失败" in completed.stderr


def test_package_installer_writes_bundle_sha256_to_manifest_and_latest(tmp_path: Path) -> None:
    dist_dir = tmp_path / "installer-dist"
    env = os.environ.copy()
    env.update(
        {
            "AERISUN_INSTALL_DIST_DIR": str(dist_dir),
            "AERISUN_RELEASE_TAG": "v9.9.9",
            "AERISUN_RELEASE_VERSION": "9.9.9",
            "AERISUN_INSTALL_CHANNEL": "stable",
            "AERISUN_IMAGE_REGISTRY": "registry.example.com/serino",
            "AERISUN_INSTALL_BASE_URL": "https://install.example.com/serino",
        }
    )

    subprocess.run(
        ["bash", "scripts/package-installer.sh"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    bundle_sha256 = hashlib.sha256((dist_dir / "aerisun-installer-bundle.tar.gz").read_bytes()).hexdigest()
    latest_values = parse_env_file(dist_dir / "latest.env")
    manifest_values = parse_env_file(dist_dir / "aerisun-installer-manifest.env")

    assert latest_values["AERISUN_INSTALL_BUNDLE_SHA256"] == bundle_sha256
    assert manifest_values["AERISUN_INSTALL_BUNDLE_SHA256"] == bundle_sha256
    latest_json = dist_dir / "latest.json"
    release_json = dist_dir / "release.json"
    release_notes = dist_dir / "release-notes.md"
    version_release_json = dist_dir / "v9.9.9" / "release.json"
    version_release_notes = dist_dir / "v9.9.9" / "release-notes.md"

    assert latest_json.is_file()
    assert release_json.is_file()
    assert release_notes.is_file()
    assert version_release_json.is_file()
    assert version_release_notes.is_file()

    latest_payload = json.loads(latest_json.read_text(encoding="utf-8"))
    release_payload = json.loads(release_json.read_text(encoding="utf-8"))
    assert latest_payload["version"] == "v9.9.9"
    assert latest_payload["release_json_url"] == "https://install.example.com/serino/v9.9.9/release.json"
    assert release_payload["version"] == "v9.9.9"
    assert release_payload["bundle_sha256"] == bundle_sha256
    assert release_payload["signature"] is None
    assert "v9.9.9" in release_notes.read_text(encoding="utf-8")


def test_package_installer_requires_release_signing_when_enabled(tmp_path: Path) -> None:
    dist_dir = tmp_path / "installer-dist"
    env = os.environ.copy()
    env.update(
        {
            "AERISUN_INSTALL_DIST_DIR": str(dist_dir),
            "AERISUN_RELEASE_TAG": "v9.9.9",
            "AERISUN_RELEASE_VERSION": "9.9.9",
            "AERISUN_INSTALL_CHANNEL": "stable",
            "AERISUN_IMAGE_REGISTRY": "registry.example.com/serino",
            "AERISUN_INSTALL_BASE_URL": "https://install.example.com/serino",
            "AERISUN_UPDATE_SIGNING_REQUIRED": "true",
        }
    )
    env.pop("AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64", None)

    completed = subprocess.run(
        ["bash", "scripts/package-installer.sh"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode != 0
    assert "AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64" in completed.stderr


def test_package_installer_signs_release_metadata_and_embeds_trusted_public_key(tmp_path: Path) -> None:
    private_key_b64, public_key_b64 = generate_rsa_signing_key_pair_b64(tmp_path, "release")
    dist_dir = tmp_path / "installer-dist"
    env = os.environ.copy()
    env.update(
        {
            "AERISUN_INSTALL_DIST_DIR": str(dist_dir),
            "AERISUN_RELEASE_TAG": "v9.9.9",
            "AERISUN_RELEASE_VERSION": "9.9.9",
            "AERISUN_INSTALL_CHANNEL": "stable",
            "AERISUN_IMAGE_REGISTRY": "registry.example.com/serino",
            "AERISUN_INSTALL_BASE_URL": "https://install.example.com/serino",
            "AERISUN_UPDATE_SIGNING_REQUIRED": "true",
            "AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64": private_key_b64,
            "AERISUN_UPDATE_SIGNATURE_KEY_ID": "serino-test-release",
        }
    )

    subprocess.run(
        ["bash", "scripts/package-installer.sh"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    release_payload = json.loads((dist_dir / "release.json").read_text(encoding="utf-8"))
    signature = release_payload["signature"]
    manifest_values = parse_env_file(dist_dir / "aerisun-installer-manifest.env")
    signed_payload = release_payload["signed"]
    assert signature["alg"] == "rsa-sha256"
    assert signature["key_id"] == "serino-test-release"
    assert signature["value"]
    assert signed_payload["channel"] == "stable"
    assert signed_payload["trusted_public_key_b64"] == public_key_b64
    assert (dist_dir / "update-trusted-public-key.b64").read_text(encoding="utf-8").strip() == public_key_b64
    assert manifest_values["AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64"] == public_key_b64
    assert public_key_b64 in (dist_dir / "install.sh").read_text(encoding="utf-8")
    assert public_key_b64 in (dist_dir / "install.latest.sh").read_text(encoding="utf-8")
    verify_release_signature(tmp_path, release_payload, public_key_b64)


def test_package_installer_signs_dev_channel_with_same_trust_contract(tmp_path: Path) -> None:
    private_key_b64, public_key_b64 = generate_rsa_signing_key_pair_b64(tmp_path, "dev-release")
    dist_dir = tmp_path / "installer-dist"
    env = os.environ.copy()
    env.update(
        {
            "AERISUN_INSTALL_DIST_DIR": str(dist_dir),
            "AERISUN_RELEASE_TAG": "v9.9.9",
            "AERISUN_RELEASE_VERSION": "9.9.9",
            "AERISUN_INSTALL_CHANNEL": "dev",
            "AERISUN_IMAGE_REGISTRY": "registry.example.com/serino",
            "AERISUN_INSTALL_BASE_URL": "https://install.example.com/serino/dev",
            "AERISUN_UPDATE_SIGNING_REQUIRED": "true",
            "AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64": private_key_b64,
            "AERISUN_UPDATE_SIGNATURE_KEY_ID": "serino-test-dev",
        }
    )

    subprocess.run(
        ["bash", "scripts/package-installer.sh"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    latest_payload = json.loads((dist_dir / "latest.json").read_text(encoding="utf-8"))
    release_payload = json.loads((dist_dir / "release.json").read_text(encoding="utf-8"))
    manifest_values = parse_env_file(dist_dir / "aerisun-installer-manifest.env")
    signed_payload = release_payload["signed"]
    signature = release_payload["signature"]

    assert latest_payload["channel"] == "dev"
    assert latest_payload["release_json_url"] == "https://install.example.com/serino/dev/v9.9.9/release.json"
    assert signed_payload["channel"] == "dev"
    assert signed_payload["api_image_name"] == "serino-dev-api"
    assert signed_payload["web_image_name"] == "serino-dev-web"
    assert signed_payload["waline_image_name"] == "serino-dev-waline"
    assert (
        signed_payload["manifest_url"] == "https://install.example.com/serino/dev/v9.9.9/aerisun-installer-manifest.env"
    )
    assert signed_payload["trusted_public_key_b64"] == public_key_b64
    assert signature["alg"] == "rsa-sha256"
    assert signature["key_id"] == "serino-test-dev"
    assert manifest_values["AERISUN_INSTALL_CHANNEL"] == "dev"
    assert manifest_values["AERISUN_API_IMAGE_NAME"] == "serino-dev-api"
    assert manifest_values["AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64"] == public_key_b64
    verify_release_signature(tmp_path, release_payload, public_key_b64)


def test_package_installer_rejects_mismatched_trusted_public_key(tmp_path: Path) -> None:
    private_key_b64, _ = generate_rsa_signing_key_pair_b64(tmp_path, "release")
    _, mismatched_public_key_b64 = generate_rsa_signing_key_pair_b64(tmp_path, "other")
    dist_dir = tmp_path / "installer-dist"
    env = os.environ.copy()
    env.update(
        {
            "AERISUN_INSTALL_DIST_DIR": str(dist_dir),
            "AERISUN_RELEASE_TAG": "v9.9.9",
            "AERISUN_RELEASE_VERSION": "9.9.9",
            "AERISUN_INSTALL_CHANNEL": "stable",
            "AERISUN_IMAGE_REGISTRY": "registry.example.com/serino",
            "AERISUN_INSTALL_BASE_URL": "https://install.example.com/serino",
            "AERISUN_UPDATE_SIGNING_REQUIRED": "true",
            "AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64": private_key_b64,
            "AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64": mismatched_public_key_b64,
        }
    )

    completed = subprocess.run(
        ["bash", "scripts/package-installer.sh"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode != 0
    assert "AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64" in completed.stderr
    assert "does not match" in completed.stderr


def test_load_release_manifest_safely_parses_whitelisted_values_and_sha256(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.env"
    manifest.write_text(
        "\n".join(
            [
                "AERISUN_INSTALL_CHANNEL=dev",
                "AERISUN_INSTALL_VERSION=v1.2.3",
                "AERISUN_IMAGE_TAG=1.2.3",
                "AERISUN_IMAGE_REGISTRY=registry.example.com:5000/serino",
                "AERISUN_API_IMAGE_NAME=serino-dev-api",
                "AERISUN_WEB_IMAGE_NAME=serino-dev-web",
                "AERISUN_WALINE_IMAGE_NAME=serino-dev-waline",
                "AERISUN_INSTALL_BUNDLE_SHA256=" + ("a" * 64),
                "AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64=QUJDRA==",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    destination = tmp_path / "downloaded.env"

    completed = run_project_bash(
        f"""
source installer/lib/common.sh
source installer/lib/download.sh

download_release_asset() {{ cp '{manifest}' "$3"; }}
load_release_manifest v1.2.3 '{destination}'
printf '%s\\n' "${{AERISUN_INSTALL_CHANNEL}}"
printf '%s\\n' "${{AERISUN_IMAGE_REGISTRY}}"
printf '%s\\n' "${{AERISUN_INSTALL_BUNDLE_SHA256}}"
printf '%s\\n' "${{AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64}}"
"""
    )

    assert completed.stdout.strip().splitlines() == [
        "dev",
        "registry.example.com:5000/serino",
        "a" * 64,
        "QUJDRA==",
    ]


def test_load_release_manifest_rejects_untrusted_shell_content(tmp_path: Path) -> None:
    marker = tmp_path / "manifest-was-sourced"
    manifest = tmp_path / "manifest.env"
    manifest.write_text(
        f"AERISUN_IMAGE_TAG=$(touch '{marker}')\nAERISUN_IMAGE_REGISTRY=registry.example.com/serino\n",
        encoding="utf-8",
    )
    destination = tmp_path / "downloaded.env"

    completed = run_project_bash(
        f"""
source installer/lib/common.sh
source installer/lib/download.sh

download_release_asset() {{ cp '{manifest}' "$3"; }}
load_release_manifest v1.2.3 '{destination}'
""",
        check=False,
    )

    assert completed.returncode == 1
    assert not marker.exists()
    assert "发布清单" in completed.stderr


def test_normalize_release_registry_strategy_forces_direct_docker_hub_for_dev_channel() -> None:
    completed = run_project_bash(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

AERISUN_INSTALL_CHANNEL='dev'
AERISUN_DOCKER_REGISTRY_MIRRORS='https://mirror.example.com'
normalize_release_registry_strategy
printf '<%s>\\n' "${AERISUN_DOCKER_REGISTRY_MIRRORS}"
"""
    )

    assert completed.stdout.strip() == "<>"


def test_normalize_release_registry_strategy_keeps_production_mirror_settings_unchanged() -> None:
    completed = run_project_bash(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

AERISUN_INSTALL_CHANNEL='stable'
AERISUN_DOCKER_REGISTRY_MIRRORS='https://mirror.example.com'
normalize_release_registry_strategy
printf '<%s>\\n' "${AERISUN_DOCKER_REGISTRY_MIRRORS}"
"""
    )

    assert completed.stdout.strip() == "<https://mirror.example.com>"


def test_configure_docker_registry_mirrors_removes_existing_daemon_mirror_for_dev_channel(tmp_path: Path) -> None:
    daemon_file = tmp_path / "daemon.json"
    daemon_file.write_text(
        '{\n  "registry-mirrors": ["https://mirror.example.com"],\n  "features": {"buildkit": true}\n}\n',
        encoding="utf-8",
    )

    completed = run_project_bash(
        f"""
source installer/lib/common.sh
source installer/lib/docker.sh

SERINO_DOCKER_DAEMON_FILE='{daemon_file}'
AERISUN_INSTALL_CHANNEL='dev'
AERISUN_DOCKER_REGISTRY_MIRRORS='https://ignored.example.com'

make_temp_file() {{ mktemp '{tmp_path}/tmp.XXXXXX'; }}
run_as_root() {{
  if [[ "$1" == install ]]; then
    shift
    if [[ " $* " == *" -d "* ]]; then
      mkdir -p "${{@: -1}}"
    else
      cp "${{@: -2:1}}" "${{@: -1}}"
    fi
    return 0
  fi
  "$@"
}}

state="$(configure_docker_registry_mirrors)"
printf 'state=%s\\n' "$state"
cat '{daemon_file}'
"""
    )

    assert "state=changed" in completed.stdout
    assert '"registry-mirrors"' not in completed.stdout
    assert '"features": {' in completed.stdout
    assert '"buildkit": true' in completed.stdout


def test_runtime_environment_value_stays_production_for_release_channels() -> None:
    completed = run_project_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh

AERISUN_INSTALL_CHANNEL='stable'
resolve_runtime_environment_value
printf '\\n'
AERISUN_INSTALL_CHANNEL='dev'
resolve_runtime_environment_value
printf '\\n'
unset AERISUN_INSTALL_CHANNEL
resolve_runtime_environment_value
printf '\\n'
"""
    )

    assert completed.stdout.strip().splitlines() == [
        "production",
        "production",
        "production",
    ]


def test_normalize_production_env_file_sets_environment_from_channel(tmp_path: Path) -> None:
    env_file = tmp_path / "serino.env"
    env_file.write_text(
        "\n".join(
            [
                "AERISUN_INSTALL_CHANNEL=dev",
                "AERISUN_ENVIRONMENT=production",
                "AERISUN_SITE_URL=https://example.test",
                "AERISUN_IMAGE_TAG=0.1.36",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = run_project_bash(
        f"""
source installer/lib/common.sh
source installer/lib/env.sh

make_temp_file() {{ mktemp '{tmp_path}/env.XXXXXX'; }}
install_managed_env_file() {{ cp "$1" "$2"; }}

normalize_production_env_file '{env_file}'
grep '^AERISUN_ENVIRONMENT=' '{env_file}'
"""
    )

    assert completed.stdout.strip() == "AERISUN_ENVIRONMENT=production"


def test_install_main_runs_schema_baseline_and_background_pipeline_in_order() -> None:
    completed = run_project_bash(
        """
source installer/install.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
prepare_install_target() { record prepare_install_target; }
ensure_port_available() { record "ensure_port_available:$1"; }
resolve_release_tag() { printf 'v1.2.3'; }
make_temp_file() { printf '/tmp/manifest'; }
load_release_manifest() {
  record "load_release_manifest:$1"
  AERISUN_IMAGE_REGISTRY='registry.example.com/serino'
  AERISUN_IMAGE_TAG='v1.2.3'
}
prompt_access_mode() { AERISUN_INSTALL_ACCESS_MODE='ip'; record prompt_access_mode; }
prompt_install_host() { AERISUN_INSTALL_HOST='127.0.0.1'; record prompt_install_host; }
prompt_bootstrap_admin_credentials() {
  AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE='admin'
  AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE='pass'
  record prompt_bootstrap_admin_credentials
}
confirm_install_settings() { record confirm_install_settings; }
ensure_docker_installed() { record ensure_docker_installed; }
configure_local_firewall() { record configure_local_firewall; }
ensure_service_user() { record ensure_service_user; }
resolve_active_registry() { printf '%s' "$1"; }
build_runtime_configuration() {
  record "build_runtime_configuration:$1:$2:$4"
  AERISUN_DOMAIN_VALUE='http://127.0.0.1'
  AERISUN_SITE_URL_VALUE='http://127.0.0.1'
  AERISUN_WALINE_SERVER_URL_VALUE='http://127.0.0.1/waline'
}
install_release_payload() { record install_release_payload; }
write_production_env() { record write_production_env; }
normalize_production_env_file() { record normalize_production_env_file; }
daemon_reload() { record daemon_reload; }
validate_release_compose_configuration() { record validate_release_compose_configuration; }
compose() { record "compose:$*"; }
run_release_migrations() { record run_release_migrations; }
run_release_baseline() { record run_release_baseline; }
run_release_data_migrations() { record "run_release_data_migrations:$1"; }
run_release_admin_bootstrap() { record run_release_admin_bootstrap; }
enable_serino_service() { record enable_serino_service; }
wait_for_release_ready() { record wait_for_release_ready; }
verify_default_admin_login() { record verify_default_admin_login; }
schedule_release_background_data_migrations() { record schedule_release_background_data_migrations; }
unset_env_value() { record "unset_env_value:$2"; }
verify_install_summary_endpoints() { record "verify_install_summary_endpoints:$1|$2"; }
print_install_summary() { record "print_install_summary:$1"; }

main
"""
    )

    assert completed.stdout.strip().splitlines() == [
        "prepare_install_target",
        "ensure_port_available:80",
        "ensure_port_available:443",
        "load_release_manifest:v1.2.3",
        "prompt_access_mode",
        "prompt_install_host",
        "prompt_bootstrap_admin_credentials",
        "confirm_install_settings",
        "ensure_docker_installed",
        "configure_local_firewall",
        "ensure_service_user",
        "build_runtime_configuration:ip:127.0.0.1:v1.2.3",
        "install_release_payload",
        "write_production_env",
        "normalize_production_env_file",
        "daemon_reload",
        "validate_release_compose_configuration",
        "compose:pull",
        "run_release_migrations",
        "run_release_baseline",
        "run_release_data_migrations:blocking",
        "run_release_admin_bootstrap",
        "enable_serino_service",
        "wait_for_release_ready",
        "verify_default_admin_login",
        "schedule_release_background_data_migrations",
        "unset_env_value:AERISUN_BOOTSTRAP_ADMIN_USERNAME_B64",
        "unset_env_value:AERISUN_BOOTSTRAP_ADMIN_PASSWORD_B64",
        "verify_install_summary_endpoints:http://127.0.0.1/|http://127.0.0.1/admin/",
        "print_install_summary:http://127.0.0.1/",
    ]


def test_install_main_clears_registry_mirrors_before_ensuring_docker_for_dev_channel() -> None:
    completed = run_project_bash(
        """
source installer/install.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
prepare_install_target() { :; }
ensure_port_available() { :; }
resolve_release_tag() { printf 'v1.2.3'; }
make_temp_file() { printf '/tmp/manifest'; }
load_release_manifest() {
  AERISUN_INSTALL_CHANNEL='dev'
  AERISUN_IMAGE_REGISTRY='docker.io/aerisun'
  AERISUN_IMAGE_TAG='v1.2.3'
  AERISUN_DOCKER_REGISTRY_MIRRORS='https://mirror.example.com'
}
prompt_access_mode() { AERISUN_INSTALL_ACCESS_MODE='ip'; }
prompt_install_host() { AERISUN_INSTALL_HOST='127.0.0.1'; }
prompt_bootstrap_admin_credentials() {
  AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE='admin'
  AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE='pass'
}
confirm_install_settings() { :; }
ensure_docker_installed() { record "ensure_docker_installed:${AERISUN_DOCKER_REGISTRY_MIRRORS}"; }
configure_local_firewall() { :; }
ensure_service_user() { :; }
resolve_active_registry() { printf '%s' "$1"; }
build_runtime_configuration() {
  AERISUN_DOMAIN_VALUE='http://127.0.0.1'
  AERISUN_SITE_URL_VALUE='http://127.0.0.1'
  AERISUN_WALINE_SERVER_URL_VALUE='http://127.0.0.1/waline'
}
install_release_payload() { :; }
write_production_env() { :; }
normalize_production_env_file() { :; }
daemon_reload() { :; }
validate_release_compose_configuration() { :; }
compose() { :; }
run_release_migrations() { :; }
run_release_baseline() { :; }
run_release_data_migrations() { :; }
run_release_admin_bootstrap() { :; }
enable_serino_service() { :; }
wait_for_release_ready() { :; }
verify_default_admin_login() { :; }
schedule_release_background_data_migrations() { :; }
unset_env_value() { :; }
verify_install_summary_endpoints() { :; }
print_install_summary() { :; }

main
"""
    )

    assert completed.stdout.strip() == "ensure_docker_installed:"


def test_install_main_cleans_up_when_blocking_data_migration_fails() -> None:
    completed = run_project_bash(
        """
source installer/install.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
prepare_install_target() { :; }
ensure_port_available() { :; }
resolve_release_tag() { printf 'v1.2.3'; }
make_temp_file() { printf '/tmp/manifest'; }
load_release_manifest() {
  AERISUN_IMAGE_REGISTRY='registry.example.com/serino'
  AERISUN_IMAGE_TAG='v1.2.3'
}
prompt_access_mode() { AERISUN_INSTALL_ACCESS_MODE='ip'; }
prompt_install_host() { AERISUN_INSTALL_HOST='127.0.0.1'; }
prompt_bootstrap_admin_credentials() {
  AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE='admin'
  AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE='pass'
}
confirm_install_settings() { :; }
ensure_docker_installed() { :; }
configure_local_firewall() { :; }
ensure_service_user() { :; }
resolve_active_registry() { printf '%s' "$1"; }
build_runtime_configuration() {
  AERISUN_DOMAIN_VALUE='http://127.0.0.1'
  AERISUN_SITE_URL_VALUE='http://127.0.0.1'
  AERISUN_WALINE_SERVER_URL_VALUE='http://127.0.0.1/waline'
}
install_release_payload() { :; }
write_production_env() { :; }
normalize_production_env_file() { :; }
daemon_reload() { :; }
validate_release_compose_configuration() { :; }
compose() { :; }
run_release_migrations() { record run_release_migrations; }
run_release_baseline() { record run_release_baseline; }
run_release_data_migrations() {
  record "run_release_data_migrations:$1"
  return 1
}
print_service_start_failure_diagnostics() { record print_service_start_failure_diagnostics; }
cleanup_failed_installation() { record cleanup_failed_installation; }
die() {
  record "die:$*"
  exit 1
}

main
""",
        check=False,
    )

    assert completed.returncode == 1
    lines = completed.stdout.strip().splitlines()
    assert lines[:6] == [
        "run_release_migrations",
        "run_release_baseline",
        "run_release_data_migrations:blocking",
        "print_service_start_failure_diagnostics",
        "cleanup_failed_installation",
        "die:阻塞式数据迁移失败，安装已中止。可根据上面的报错信息修复后重试。",
    ]
    assert lines[6:] in ([], ["cleanup_failed_installation"])


def test_install_main_cleans_up_when_final_summary_endpoint_verification_fails() -> None:
    completed = run_project_bash(
        """
source installer/install.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
prepare_install_target() { :; }
ensure_port_available() { :; }
resolve_release_tag() { printf 'v1.2.3'; }
make_temp_file() { printf '/tmp/manifest'; }
load_release_manifest() {
  AERISUN_IMAGE_REGISTRY='registry.example.com/serino'
  AERISUN_IMAGE_TAG='v1.2.3'
}
prompt_access_mode() { AERISUN_INSTALL_ACCESS_MODE='ip'; }
prompt_install_host() { AERISUN_INSTALL_HOST='127.0.0.1'; }
prompt_bootstrap_admin_credentials() {
  AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE='admin'
  AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE='pass'
}
confirm_install_settings() { :; }
ensure_docker_installed() { :; }
configure_local_firewall() { :; }
ensure_service_user() { :; }
resolve_active_registry() { printf '%s' "$1"; }
build_runtime_configuration() {
  AERISUN_DOMAIN_VALUE='http://127.0.0.1'
  AERISUN_SITE_URL_VALUE='http://127.0.0.1'
  AERISUN_WALINE_SERVER_URL_VALUE='http://127.0.0.1/waline'
}
install_release_payload() { :; }
write_production_env() { :; }
normalize_production_env_file() { :; }
daemon_reload() { :; }
validate_release_compose_configuration() { :; }
compose() { :; }
run_release_migrations() { record run_release_migrations; }
run_release_baseline() { record run_release_baseline; }
run_release_data_migrations() { record "run_release_data_migrations:$1"; }
run_release_admin_bootstrap() { record run_release_admin_bootstrap; }
enable_serino_service() { record enable_serino_service; }
wait_for_release_ready() { record wait_for_release_ready; }
verify_default_admin_login() { record verify_default_admin_login; }
schedule_release_background_data_migrations() { record schedule_release_background_data_migrations; }
unset_env_value() { record "unset_env_value:$2"; }
verify_install_summary_endpoints() {
  record "verify_install_summary_endpoints:$1|$2"
  return 1
}
print_service_start_failure_diagnostics() { record print_service_start_failure_diagnostics; }
cleanup_failed_installation() { record cleanup_failed_installation; }
die() {
  record "die:$*"
  exit 1
}

main
""",
        check=False,
    )

    assert completed.returncode == 1
    lines = completed.stdout.strip().splitlines()
    assert lines[:14] == [
        "run_release_migrations",
        "run_release_baseline",
        "run_release_data_migrations:blocking",
        "run_release_admin_bootstrap",
        "enable_serino_service",
        "wait_for_release_ready",
        "verify_default_admin_login",
        "schedule_release_background_data_migrations",
        "unset_env_value:AERISUN_BOOTSTRAP_ADMIN_USERNAME_B64",
        "unset_env_value:AERISUN_BOOTSTRAP_ADMIN_PASSWORD_B64",
        "verify_install_summary_endpoints:http://127.0.0.1/|http://127.0.0.1/admin/",
        "print_service_start_failure_diagnostics",
        "cleanup_failed_installation",
        "die:安装完成前的最终访问校验失败：当前填写的 IPv4 绑定有误，常见原因是把代理出口地址填成了服务器 IP。请改填这台服务器真实 IPv4（优先公网 IPv4，没有公网再用内网）后重新安装。",
    ]
    assert lines[14:] in ([], ["cleanup_failed_installation"])


def test_upgrade_check_only_runs_preflight_without_mutation() -> None:
    completed = run_project_bash(
        """
source installer/upgrade.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
ensure_supported_existing_installation() { :; }
ensure_service_user() { :; }
load_env_file() {
  AERISUN_IMAGE_REGISTRY='registry.example.com/current'
  AERISUN_IMAGE_TAG='v1.0.0'
}
run_upgrade_preflight() { record run_upgrade_preflight; }
resolve_release_tag() { printf '%s' "${AERISUN_INSTALL_VERSION:-v2.0.0}"; }
make_temp_file() { printf '/tmp/manifest'; }
load_release_manifest() {
  record "load_release_manifest:$1"
  AERISUN_IMAGE_REGISTRY='registry.example.com/next'
  AERISUN_IMAGE_TAG='v2.0.0'
}
download_release_asset() { record download_release_asset; }
stop_serino_service() { record stop_serino_service; }
backup_current_installation() { record backup_current_installation; }
install_release_payload() { record install_release_payload; }
reload_installer_libraries() { record reload_installer_libraries; }
set_env_value() { record "set_env_value:$2=$3"; }
normalize_production_env_file() { record normalize_production_env_file; }
validate_release_compose_configuration() { record validate_release_compose_configuration; }

main --check v2.0.0
"""
    )

    assert completed.stdout.strip().splitlines() == [
        "run_upgrade_preflight",
        "load_release_manifest:v2.0.0",
    ]


def test_upgrade_current_api_started_at_epoch_parses_docker_timestamp() -> None:
    completed = run_project_bash(
        """
source installer/upgrade.sh

compose() {
  if [[ "$*" == "ps -q api" ]]; then
    printf 'api-container\\n'
  fi
}

run_as_root() {
  if [[ "$1" == docker && "$2" == inspect ]]; then
    printf '1970-01-01T00:00:42.500000000Z\\n'
    return 0
  fi
  "$@"
}

current_api_started_at_epoch
"""
    )

    assert completed.stdout.strip() == "42.500000"


def test_upgrade_seed_persistent_uptime_marker_writes_current_api_start(tmp_path: Path) -> None:
    completed = run_project_bash(
        f"""
source installer/upgrade.sh

AERISUN_DATA_DIR='{tmp_path}/data'
SERINO_SERVICE_USER='serino'
SERINO_SERVICE_GROUP='serino'

current_api_started_at_epoch() {{
  printf '123456.500000\\n'
}}

run_as_root() {{
  if [[ "$1" == test ]]; then
    "$@"
    return $?
  fi
  if [[ "$1" == install ]]; then
    mkdir -p "${{@: -1}}"
    return 0
  fi
  if [[ "$1" == bash && "$2" == "-lc" ]]; then
    marker_path="$5"
    started_at_epoch="$6"
    printf '%s\\n' "${{started_at_epoch}}" > "${{marker_path}}"
    return 0
  fi
  "$@"
}}

seed_persistent_uptime_marker
cat "${{AERISUN_DATA_DIR}}/.serino-uptime-started-at"
"""
    )

    assert completed.stdout.strip() == "123456.500000"


def test_upgrade_main_rolls_back_and_restarts_previous_release_on_failure() -> None:
    completed = run_project_bash(
        """
source installer/upgrade.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
ensure_supported_existing_installation() { :; }
ensure_service_user() { :; }
load_env_file() {
  AERISUN_IMAGE_REGISTRY='registry.example.com/current'
  AERISUN_IMAGE_TAG='v1.0.0'
}
run_upgrade_preflight() { record run_upgrade_preflight; }
resolve_release_tag() { printf '%s' "${AERISUN_INSTALL_VERSION:-v2.0.0}"; }
make_temp_file() { printf '/tmp/manifest'; }
make_temp_dir() { printf '/tmp/bundle'; }
make_root_temp_dir_in_dir() { printf '/var/backups/serino/upgrade-20260408112233'; }
load_release_manifest() {
  record "load_release_manifest:$1"
  AERISUN_IMAGE_REGISTRY='registry.example.com/next'
  AERISUN_IMAGE_TAG='v2.0.0'
}
download_release_asset() { record "download_release_asset:$1"; }
tar() { record "tar:$*"; }
date() { printf '20260408112233'; }
seed_persistent_uptime_marker() { :; }
    stop_serino_service() { record stop_serino_service; }
    backup_current_installation() { record "backup_current_installation:$1"; }
    resolve_active_registry() {
      printf '%s' "$1"
    }
install_release_payload() { record install_release_payload; }
reload_installer_libraries() { record reload_installer_libraries; }
set_env_value() { record "set_env_value:$2=$3"; }
normalize_production_env_file() { record normalize_production_env_file; }
validate_release_compose_configuration() { record validate_release_compose_configuration; }
compose() {
  record "compose:$*"
}
run_release_migrations() { record run_release_migrations; }
run_release_data_migrations() {
  record "run_release_data_migrations:$1"
  return 1
}
enable_serino_service() { record enable_serino_service; }
wait_for_release_ready() { record wait_for_release_ready; }
print_service_start_failure_diagnostics() { record print_service_start_failure_diagnostics; }
restore_current_installation() { record "restore_current_installation:$1"; }
log_warn() { record "log_warn:$*"; }
die() {
  record "die:$*"
  exit 1
}

main v2.0.0
""",
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stdout.strip().splitlines() == [
        "run_upgrade_preflight",
        "load_release_manifest:v2.0.0",
        "download_release_asset:v2.0.0",
        "tar:-xzf /tmp/bundle/aerisun-installer-bundle.tar.gz -C /tmp/bundle",
        "stop_serino_service",
        "backup_current_installation:/var/backups/serino/upgrade-20260408112233",
        "install_release_payload",
        "reload_installer_libraries",
        "set_env_value:AERISUN_IMAGE_REGISTRY=registry.example.com/next",
        "set_env_value:AERISUN_IMAGE_TAG=v2.0.0",
        "set_env_value:AERISUN_RELEASE_VERSION=v2.0.0",
        "set_env_value:AERISUN_DOCKER_REGISTRY_MIRRORS=",
        "normalize_production_env_file",
        "validate_release_compose_configuration",
        "compose:pull",
        "run_release_migrations",
        "run_release_data_migrations:blocking",
        "log_warn:升级失败，正在回滚。",
        "print_service_start_failure_diagnostics",
        "stop_serino_service",
        "restore_current_installation:/var/backups/serino/upgrade-20260408112233",
        "compose:pull",
        "enable_serino_service",
        "wait_for_release_ready",
        "die:升级失败，已回滚到旧版本。可执行 sercli doctor 与 sercli logs api waline caddy 查看诊断信息。",
    ]


def test_upgrade_main_validates_compose_with_loaded_env_urls() -> None:
    completed = run_project_bash(
        """
source installer/upgrade.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
ensure_supported_existing_installation() { :; }
ensure_service_user() { :; }
load_env_file() {
  AERISUN_IMAGE_REGISTRY='registry.example.com/current'
  AERISUN_IMAGE_TAG='v1.0.0'
  AERISUN_SITE_URL='https://example.test'
  AERISUN_WALINE_SERVER_URL='https://example.test/waline'
}
run_upgrade_preflight() { record run_upgrade_preflight; }
resolve_release_tag() { printf '%s' "${AERISUN_INSTALL_VERSION:-v2.0.0}"; }
make_temp_file() { printf '/tmp/manifest'; }
make_temp_dir() { printf '/tmp/bundle'; }
make_root_temp_dir_in_dir() { printf '/var/backups/serino/upgrade-20260408112233'; }
load_release_manifest() {
  record "load_release_manifest:$1"
  AERISUN_IMAGE_REGISTRY='registry.example.com/next'
  AERISUN_IMAGE_TAG='v2.0.0'
}
download_release_asset() { record "download_release_asset:$1"; }
tar() { record "tar:$*"; }
date() { printf '20260408112233'; }
seed_persistent_uptime_marker() { :; }
stop_serino_service() { record stop_serino_service; }
backup_current_installation() { record "backup_current_installation:$1"; }
resolve_active_registry() {
  printf '%s' "$1"
}
install_release_payload() { record install_release_payload; }
reload_installer_libraries() { record reload_installer_libraries; }
set_env_value() { record "set_env_value:$2=$3"; }
normalize_production_env_file() { record normalize_production_env_file; }
validate_release_compose_configuration() {
  printf '%s|%s\\n' "${AERISUN_SITE_URL:-}" "${AERISUN_WALINE_SERVER_URL:-}"
  record validate_release_compose_configuration
}
compose() {
  record "compose:$*"
}
run_release_migrations() { record run_release_migrations; }
run_release_data_migrations() { record "run_release_data_migrations:$1"; }
enable_serino_service() { record enable_serino_service; }
wait_for_release_ready() { record wait_for_release_ready; }
schedule_release_background_data_migrations() { record schedule_release_background_data_migrations; }

main v2.0.0
"""
    )

    assert completed.stdout.strip().splitlines() == [
        "run_upgrade_preflight",
        "load_release_manifest:v2.0.0",
        "download_release_asset:v2.0.0",
        "tar:-xzf /tmp/bundle/aerisun-installer-bundle.tar.gz -C /tmp/bundle",
        "stop_serino_service",
        "backup_current_installation:/var/backups/serino/upgrade-20260408112233",
        "install_release_payload",
        "reload_installer_libraries",
        "set_env_value:AERISUN_IMAGE_REGISTRY=registry.example.com/next",
        "set_env_value:AERISUN_IMAGE_TAG=v2.0.0",
        "set_env_value:AERISUN_RELEASE_VERSION=v2.0.0",
        "set_env_value:AERISUN_DOCKER_REGISTRY_MIRRORS=",
        "normalize_production_env_file",
        "https://example.test|https://example.test/waline",
        "validate_release_compose_configuration",
        "compose:pull",
        "run_release_migrations",
        "run_release_data_migrations:blocking",
        "enable_serino_service",
        "wait_for_release_ready",
        "schedule_release_background_data_migrations",
    ]


def test_upgrade_main_clears_registry_mirrors_in_env_for_dev_channel() -> None:
    completed = run_project_bash(
        """
source installer/upgrade.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
ensure_supported_existing_installation() { :; }
ensure_service_user() { :; }
load_env_file() { :; }
run_upgrade_preflight() { :; }
resolve_release_tag() { printf '%s' "${AERISUN_INSTALL_VERSION:-v2.0.0}"; }
make_temp_file() { printf '/tmp/manifest'; }
make_temp_dir() { printf '/tmp/bundle'; }
make_root_temp_dir_in_dir() { printf '/var/backups/serino/upgrade-20260408112233'; }
load_release_manifest() {
  AERISUN_INSTALL_CHANNEL='dev'
  AERISUN_IMAGE_REGISTRY='docker.io/aerisun'
  AERISUN_IMAGE_TAG='v2.0.0'
  AERISUN_DOCKER_REGISTRY_MIRRORS='https://mirror.example.com'
}
download_release_asset() { record "download_release_asset:$1"; }
tar() { record "tar:$*"; }
date() { printf '20260408112233'; }
seed_persistent_uptime_marker() { :; }
stop_serino_service() { :; }
backup_current_installation() { :; }
resolve_active_registry() { printf '%s' "$1"; }
install_release_payload() { :; }
reload_installer_libraries() { :; }
set_env_value() { record "set_env_value:$2=$3"; }
normalize_production_env_file() { :; }
validate_release_compose_configuration() { :; }
compose() { :; }
run_release_migrations() { :; }
run_release_data_migrations() { :; }
enable_serino_service() { :; }
wait_for_release_ready() { :; }
schedule_release_background_data_migrations() { :; }

main v2.0.0
"""
    )

    assert "set_env_value:AERISUN_DOCKER_REGISTRY_MIRRORS=" in completed.stdout


def test_upgrade_rollback_does_not_mutate_var_lib_parent_ownership(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "data.tar.gz").write_bytes(b"not-a-real-archive")

    completed = run_project_bash(
        f"""
source installer/upgrade.sh

AERISUN_DATA_DIR='/var/lib/serino'
SERINO_SERVICE_USER='serino'
SERINO_SERVICE_GROUP='serino'

run_as_root() {{
  printf 'run_as_root'
  printf ' <%s>' "$@"
  printf '\\n'
  return 0
}}
tar() {{
  printf 'tar'
  printf ' <%s>' "$@"
  printf '\\n'
}}
daemon_reload() {{
  printf 'daemon_reload\\n'
}}

restore_current_installation '{backup_dir}'
"""
    )

    lines = completed.stdout.strip().splitlines()
    assert not any(line.startswith("run_as_root <install>") and line.endswith(" </var/lib>") for line in lines)
    assert not any(line.startswith("run_as_root <chown>") and line.endswith(" </var/lib>") for line in lines)
    assert any(line.startswith(("tar ", "run_as_root <tar>")) for line in lines)


def test_purge_installation_paths_rejects_dangerous_roots_before_rm() -> None:
    completed = run_project_bash(
        """
source installer/lib/common.sh

AERISUN_APP_ROOT='/'
SERINO_CONFIG_ROOT='/etc'
AERISUN_DATA_DIR='/var/lib'
SERINO_LOG_ROOT='/var/log'
AERISUN_BACKUP_ROOT='/var/backups'
SERINO_BIN_LINK='/usr/local/bin'

run_as_root() {
  printf 'run_as_root'
  printf ' <%s>' "$@"
  printf '\\n'
  return 0
}
die() {
  printf 'die:%s\\n' "$*"
  exit 64
}

set -e
purge_installation_paths
""",
        check=False,
    )

    assert completed.returncode != 0
    assert "unexpected-ok" not in completed.stdout
    assert "run_as_root" not in completed.stdout


def test_package_installer_outputs_verifiable_manifest_and_bundle(tmp_path: Path) -> None:
    package_root = tmp_path / "package-root"
    (package_root / "scripts").mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "scripts" / "package-installer.sh", package_root / "scripts" / "package-installer.sh")
    shutil.copytree(PROJECT_ROOT / "installer", package_root / "installer")
    shutil.copy2(PROJECT_ROOT / "docker-compose.release.yml", package_root / "docker-compose.release.yml")
    shutil.copy2(PROJECT_ROOT / ".env.production.local.example", package_root / ".env.production.local.example")

    env = os.environ.copy()
    env.update(
        {
            "AERISUN_RELEASE_TAG": "v9.8.7",
            "AERISUN_RELEASE_VERSION": "9.8.7",
            "AERISUN_INSTALL_CHANNEL": "dev",
            "AERISUN_IMAGE_REGISTRY": "registry.example.com/aerisun",
            "AERISUN_INSTALL_BASE_URL": "https://install.example.test/dev",
        }
    )

    subprocess.run(
        ["bash", "scripts/package-installer.sh"],
        cwd=package_root,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            """
set -euo pipefail
dist='dist/installer'
source "${dist}/aerisun-installer-manifest.env"
test "${AERISUN_INSTALL_CHANNEL}" = 'dev'
test "${AERISUN_INSTALL_VERSION}" = 'v9.8.7'
test "${AERISUN_IMAGE_TAG}" = '9.8.7'
test "${AERISUN_IMAGE_REGISTRY}" = 'registry.example.com/aerisun'
test "${AERISUN_API_IMAGE_NAME}" = 'serino-dev-api'
test "${AERISUN_WEB_IMAGE_NAME}" = 'serino-dev-web'
test "${AERISUN_WALINE_IMAGE_NAME}" = 'serino-dev-waline'
actual_sha="$(sha256sum "${dist}/aerisun-installer-bundle.tar.gz" | awk '{print $1}')"
test "${AERISUN_INSTALL_BUNDLE_SHA256}" = "${actual_sha}"
grep -qx 'AERISUN_INSTALL_VERSION=v9.8.7' "${dist}/latest.env"
grep -qx "AERISUN_INSTALL_BUNDLE_SHA256=${actual_sha}" "${dist}/latest.env"
grep -q 'AERISUN_INSTALL_VERSION="${AERISUN_INSTALL_VERSION:-v9.8.7}"' "${dist}/install.sh"
! grep -q 'AERISUN_INSTALL_VERSION="${AERISUN_INSTALL_VERSION:-v9.8.7}"' "${dist}/install.latest.sh"
bash -n "${dist}/install.sh" "${dist}/install.latest.sh"
tar -tzf "${dist}/aerisun-installer-bundle.tar.gz" | sort > "${dist}/bundle.files"
grep -qx 'docker-compose.release.yml' "${dist}/bundle.files"
grep -qx '.env.production.local.example' "${dist}/bundle.files"
grep -qx 'installer/install.sh' "${dist}/bundle.files"
grep -qx 'installer/upgrade.sh' "${dist}/bundle.files"
grep -qx 'installer/bin/sercli' "${dist}/bundle.files"
printf 'ok\\n'
""",
        ],
        cwd=package_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "ok"


def test_release_smoke_gate_runs_shell_backend_and_docker_steps_in_order() -> None:
    completed = run_project_bash(
        """
source scripts/release-smoke-gate.sh

run_shell_contract_checks() { printf 'shell\\n'; }
run_backend_ops_tests() { printf 'backend\\n'; }
run_docker_release_smoke() { printf 'docker\\n'; }

main
"""
    )

    assert completed.stdout.strip().splitlines() == ["shell", "backend", "docker"]
