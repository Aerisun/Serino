from __future__ import annotations

import json
import os
import pty
import select
import subprocess
import time
from pathlib import Path

import pytest

from aerisun.core.settings import get_settings
from aerisun.domain.agent.install import _credential_bootstrap_shell, build_mcp_install_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "aerisun-mcp"
CODEX_MARKETPLACE_PATH = PROJECT_ROOT / ".agents" / "plugins" / "marketplace.json"
CADDYFILE_PATH = PROJECT_ROOT / "Caddyfile"
TEST_API_KEY = "aerisun_test_key_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_-"
REPLACEMENT_API_KEY = "aerisun_replacement_key_ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"


def test_domain_install_manifest_exposes_both_supported_clients(client) -> None:
    response = client.get("/mcp/install")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    payload = response.json()
    base_url = get_settings().site_url.rstrip("/")
    assert payload["schema_version"] == "2026-08-09-install-v4"
    assert payload["plugin_version"] == "0.1.0"
    assert payload["protocol_version"] == "2026-07-28"
    assert payload["mcp_endpoint"] == f"{base_url}/api/mcp/"
    assert "required_environment" not in payload
    assert payload["credential_input"] == {
        "mode": "interactive_hidden_prompt",
        "storage": "client_private",
        "automation_environment": "AERISUN_MCP_API_KEY",
        "update_command": "~/.local/bin/serino-mcp-key",
    }
    assert payload["clients"]["codex"]["install_url"].endswith("/mcp/install/codex.sh")
    assert payload["clients"]["claude_code"]["marketplace_url"].endswith("/mcp/install/claude-marketplace.json")
    assert "<API_KEY>" not in response.text


def test_claude_marketplace_bakes_in_the_current_site_domain(client) -> None:
    response = client.get("/mcp/install/claude-marketplace.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "aerisun"
    plugin = payload["plugins"][0]
    assert plugin["name"] == "aerisun-mcp"
    assert "version" not in plugin
    assert plugin["source"] == {
        "source": "git-subdir",
        "url": "https://github.com/Aerisun/Serino.git",
        "path": "plugins/aerisun-mcp",
        "ref": "main",
    }
    assert "mcpServers" not in plugin
    assert "<API_KEY>" not in response.text


@pytest.mark.parametrize("client_name", ["codex", "claude"])
def test_domain_install_scripts_are_valid_secret_free_shell(client, client_name: str) -> None:
    response = client.get(f"/mcp/install/{client_name}.sh")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/x-shellscript")
    assert response.text.startswith("#!/bin/sh\nset -eu\n")
    assert "AERISUN_MCP_API_KEY" in response.text
    assert "/dev/tty" in response.text
    assert "stty -echo" in response.text
    assert "umask 077" in response.text
    assert 'aerisun_local_bin="$HOME/.local/bin"' in response.text
    assert 'aerisun_key_updater="$aerisun_local_bin/serino-mcp-key"' in response.text
    assert "<API_KEY>" not in response.text
    assert get_settings().site_url.rstrip("/") in response.text
    syntax = subprocess.run(
        ["sh", "-n"],
        input=response.text,
        text=True,
        capture_output=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_installed_key_updater_rotates_credentials_without_network_or_reinstall(
    client,
    tmp_path: Path,
) -> None:
    install_result, _ = _run_installer_with_fake_client(
        client,
        tmp_path,
        "codex",
        existing=False,
    )
    home_dir = tmp_path / "home"
    config_home = tmp_path / "config"
    codex_home = tmp_path / "codex"
    updater = home_dir / ".local" / "bin" / "serino-mcp-key"
    codex_env = codex_home / ".env"
    assert install_result.returncode == 0, install_result.stderr
    assert updater.is_file()
    updater_text = updater.read_text(encoding="utf-8")

    result = subprocess.run(
        [str(updater)],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "HOME": str(home_dir),
            "XDG_CONFIG_HOME": str(config_home),
            "CODEX_HOME": str(codex_home),
            "AERISUN_MCP_API_KEY": REPLACEMENT_API_KEY,
        },
    )

    assert updater.stat().st_mode & 0o777 == 0o700
    assert updater_text.startswith("#!/bin/sh\nset -eu\n")
    assert "Serino MCP API Key: " in updater_text
    assert "curl" not in updater_text
    assert "http://" not in updater_text
    assert "https://" not in updater_text
    assert "command -v codex" not in updater_text
    assert "command -v claude" not in updater_text
    assert result.returncode == 0, result.stderr
    assert REPLACEMENT_API_KEY not in result.stdout
    assert REPLACEMENT_API_KEY not in result.stderr
    assert "Serino MCP API Key updated." in result.stdout

    credential_file = config_home / "aerisun" / "mcp-api-key"
    assert credential_file.read_text(encoding="utf-8") == f"{REPLACEMENT_API_KEY}\n"
    assert credential_file.stat().st_mode & 0o777 == 0o600
    codex_env_text = codex_env.read_text(encoding="utf-8")
    assert "KEEP_ME=preserved" in codex_env_text
    assert f"AERISUN_MCP_API_KEY={REPLACEMENT_API_KEY}" in codex_env_text
    assert "old_key" not in codex_env_text
    assert codex_env_text.count("AERISUN_MCP_API_KEY=") == 1
    assert codex_env.stat().st_mode & 0o777 == 0o600

    syntax = subprocess.run(
        ["sh", "-n"],
        input=updater_text,
        text=True,
        capture_output=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_key_update_rejects_an_unsafe_codex_target_before_writing_the_new_key(
    client,
    tmp_path: Path,
) -> None:
    install_result, _ = _run_installer_with_fake_client(
        client,
        tmp_path,
        "codex",
        existing=False,
    )
    home_dir = tmp_path / "home"
    config_home = tmp_path / "config"
    codex_home = tmp_path / "codex"
    external_env = tmp_path / "external.env"
    updater = home_dir / ".local" / "bin" / "serino-mcp-key"
    codex_env = codex_home / ".env"
    assert install_result.returncode == 0, install_result.stderr
    assert updater.is_file()
    codex_env.unlink()
    external_env.write_text("AERISUN_MCP_API_KEY=keep_me\n", encoding="utf-8")
    codex_env.symlink_to(external_env)

    result = subprocess.run(
        [str(updater)],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "HOME": str(home_dir),
            "XDG_CONFIG_HOME": str(config_home),
            "CODEX_HOME": str(codex_home),
            "AERISUN_MCP_API_KEY": REPLACEMENT_API_KEY,
        },
    )

    assert result.returncode != 0
    assert "Refusing unsafe Codex environment file" in result.stderr
    assert (config_home / "aerisun" / "mcp-api-key").read_text(encoding="utf-8") == f"{TEST_API_KEY}\n"
    assert external_env.read_text(encoding="utf-8") == "AERISUN_MCP_API_KEY=keep_me\n"


def test_key_updates_have_no_remote_script(client) -> None:
    assert client.get("/mcp/install/key.sh").status_code == 404


def test_install_manifest_rejects_non_http_site_urls() -> None:
    with pytest.raises(ValueError, match="http or https"):
        build_mcp_install_manifest("javascript:alert(1)")


@pytest.mark.parametrize(
    "site_url",
    [
        "https://example.test/base",
        "https://user:secret@example.test",
        "https://example.test/path?token=secret",
        "https://example.test/#fragment",
        "https://example.test\\evil",
        "https://example.test:invalid",
    ],
)
def test_install_manifest_rejects_non_origin_site_urls(site_url: str) -> None:
    with pytest.raises(ValueError, match="origin"):
        build_mcp_install_manifest(site_url)


def test_shared_plugin_is_packaged_for_codex_and_claude_code() -> None:
    codex_manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text())
    claude_manifest = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    marketplace = json.loads(CODEX_MARKETPLACE_PATH.read_text())

    assert codex_manifest["name"] == "aerisun-mcp"
    assert codex_manifest["skills"] == "./skills/"
    assert claude_manifest["name"] == "aerisun-mcp"
    assert marketplace["name"] == "aerisun"
    assert marketplace["plugins"][0]["source"]["path"] == "./plugins/aerisun-mcp"
    assert {path.parent.name for path in (PLUGIN_ROOT / "skills").glob("*/SKILL.md")} == {
        "aerisun-mcp-bootstrap",
        "aerisun-mcp-readonly",
        "aerisun-mcp-guarded-write",
    }


def test_production_proxy_exposes_the_domain_install_entry() -> None:
    caddyfile = CADDYFILE_PATH.read_text(encoding="utf-8")

    assert "path /mcp/install /mcp/install/*" in caddyfile
    assert caddyfile.index("@mcpInstallRoutes") < caddyfile.index("@frontendSpa")


def test_install_assets_do_not_bloat_the_application_openapi(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert all(not path.startswith("/mcp/install") for path in paths)


def test_credential_prompt_reads_hidden_key_from_the_controlling_terminal(tmp_path: Path) -> None:
    script_path = tmp_path / "credential-prompt.sh"
    script_path.write_text(
        "#!/bin/sh\nset -eu\n"
        f"{_credential_bootstrap_shell()}\n"
        "unset AERISUN_MCP_API_KEY aerisun_api_key\n"
        "printf '%s\\n' 'credential-stored'\n",
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }
    environment.pop("AERISUN_MCP_API_KEY", None)
    (tmp_path / "home").mkdir()

    child_pid, terminal_fd = pty.fork()
    if child_pid == 0:
        os.execve("/bin/sh", ["sh", str(script_path)], environment)

    output = bytearray()
    sent_key = False
    child_status: int | None = None
    deadline = time.monotonic() + 5
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([terminal_fd], [], [], 0.1)
            if readable:
                try:
                    chunk = os.read(terminal_fd, 4096)
                except OSError:
                    chunk = b""
                output.extend(chunk)
            if not sent_key and b"Serino MCP API Key:" in output:
                os.write(terminal_fd, f"{TEST_API_KEY}\n".encode())
                sent_key = True
            ended_pid, status = os.waitpid(child_pid, os.WNOHANG)
            if ended_pid == child_pid:
                child_status = status
                break
        if child_status is None:
            os.kill(child_pid, 9)
            _, child_status = os.waitpid(child_pid, 0)
            pytest.fail("interactive credential prompt timed out")
    finally:
        os.close(terminal_fd)

    terminal_output = output.decode(errors="replace")
    assert os.waitstatus_to_exitcode(child_status) == 0
    assert sent_key
    assert "credential-stored" in terminal_output
    assert TEST_API_KEY not in terminal_output
    credential_file = tmp_path / "config" / "aerisun" / "mcp-api-key"
    assert credential_file.read_text(encoding="utf-8") == f"{TEST_API_KEY}\n"


def _run_installer_with_fake_client(
    client,
    tmp_path: Path,
    client_name: str,
    *,
    existing: bool,
    marketplace_url: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], str]:
    response = client.get(f"/mcp/install/{client_name}.sh")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    command_log = tmp_path / "commands.log"
    fake_client = fake_bin / client_name
    fake_client.write_text(
        """#!/bin/sh
if [ -n "${AERISUN_MCP_API_KEY:-}" ]; then
  printf '%s\\n' 'credential-environment-leaked' >> "$AERISUN_INSTALL_TEST_LOG"
fi
printf '%s\\n' "$*" >> "$AERISUN_INSTALL_TEST_LOG"
case "$*" in
  'plugin marketplace list --json') printf '%s\\n' "$AERISUN_INSTALL_TEST_MARKETPLACES" ;;
  'plugin list --json') printf '%s\\n' "$AERISUN_INSTALL_TEST_PLUGINS" ;;
  'mcp add --help') printf '%s\\n' '--bearer-token-env-var' ;;
  'mcp get aerisun-mcp') test "$AERISUN_INSTALL_TEST_EXISTING" = '1' ;;
esac
""",
        encoding="utf-8",
    )
    fake_client.chmod(0o755)
    home_dir = tmp_path / "home"
    xdg_config_home = tmp_path / "config"
    codex_home = tmp_path / "codex"
    home_dir.mkdir()
    codex_home.mkdir()
    codex_env = codex_home / ".env"
    codex_env.write_text(
        "KEEP_ME=preserved\nAERISUN_MCP_API_KEY=old_key\n",
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(home_dir),
        "XDG_CONFIG_HOME": str(xdg_config_home),
        "CODEX_HOME": str(codex_home),
        "AERISUN_MCP_API_KEY": TEST_API_KEY,
        "AERISUN_INSTALL_TEST_LOG": str(command_log),
        "AERISUN_INSTALL_TEST_EXISTING": "1" if existing else "0",
        "AERISUN_INSTALL_TEST_MARKETPLACES": (
            json.dumps(
                {
                    "marketplaces": [
                        {
                            "name": "aerisun",
                            "marketplaceSource": {"source": marketplace_url or "https://github.com/Aerisun/Serino.git"},
                        }
                    ]
                }
                if client_name == "codex" and existing
                else (
                    [
                        {
                            "name": "aerisun",
                            "source": "url",
                            "url": marketplace_url
                            or f"{get_settings().site_url.rstrip('/')}/mcp/install/claude-marketplace.json",
                        }
                    ]
                    if existing
                    else []
                )
            )
        ),
        "AERISUN_INSTALL_TEST_PLUGINS": json.dumps(
            {"installed": [{"pluginId": "aerisun-mcp@aerisun"}]} if existing else {"installed": []}
        ),
    }

    result = subprocess.run(
        ["sh"],
        input=response.text,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )

    commands = command_log.read_text(encoding="utf-8")
    return result, commands


@pytest.mark.parametrize("client_name", ["codex", "claude"])
def test_fresh_install_scripts_use_only_official_client_commands(client, tmp_path: Path, client_name: str) -> None:
    result, commands = _run_installer_with_fake_client(
        client,
        tmp_path,
        client_name,
        existing=False,
    )

    assert result.returncode == 0, result.stderr
    assert TEST_API_KEY not in commands
    assert "credential-environment-leaked" not in commands
    assert TEST_API_KEY not in result.stdout
    assert TEST_API_KEY not in result.stderr

    credential_file = tmp_path / "config" / "aerisun" / "mcp-api-key"
    assert credential_file.read_text(encoding="utf-8") == f"{TEST_API_KEY}\n"
    assert credential_file.stat().st_mode & 0o777 == 0o600
    assert credential_file.parent.stat().st_mode & 0o777 == 0o700

    if client_name == "codex":
        assert "plugin marketplace add https://github.com/Aerisun/Serino.git" in commands
        assert "plugin add aerisun-mcp@aerisun" in commands
        assert "mcp add aerisun-mcp --url" in commands
        assert "--bearer-token-env-var AERISUN_MCP_API_KEY" in commands
        codex_env = tmp_path / "codex" / ".env"
        codex_env_text = codex_env.read_text(encoding="utf-8")
        assert "KEEP_ME=preserved" in codex_env_text
        assert f"AERISUN_MCP_API_KEY={TEST_API_KEY}" in codex_env_text
        assert codex_env_text.count("AERISUN_MCP_API_KEY=") == 1
        assert codex_env.stat().st_mode & 0o777 == 0o600
    else:
        assert "plugin marketplace add" in commands
        assert "/mcp/install/claude-marketplace.json" in commands
        assert "plugin install aerisun-mcp@aerisun --scope user" in commands
        assert "mcp add-json --scope user aerisun-mcp" in commands
        assert '"headersHelper"' in commands
        assert '"headers"' not in commands
        helper = tmp_path / "config" / "aerisun" / "mcp-headers"
        assert helper.stat().st_mode & 0o777 == 0o700
        assert TEST_API_KEY not in helper.read_text(encoding="utf-8")
        helper_result = subprocess.run(
            [str(helper)],
            text=True,
            capture_output=True,
            check=False,
            env={
                **os.environ,
                "HOME": str(tmp_path / "home"),
                "XDG_CONFIG_HOME": str(tmp_path / "config"),
            },
        )
        assert helper_result.returncode == 0, helper_result.stderr
        assert json.loads(helper_result.stdout) == {
            "Authorization": f"Bearer {TEST_API_KEY}",
        }


@pytest.mark.parametrize("client_name", ["codex", "claude"])
def test_repeat_install_scripts_refresh_only_the_aerisun_integration(client, tmp_path: Path, client_name: str) -> None:
    result, commands = _run_installer_with_fake_client(
        client,
        tmp_path,
        client_name,
        existing=True,
    )

    assert result.returncode == 0, result.stderr
    if client_name == "codex":
        assert "plugin marketplace upgrade aerisun" in commands
        assert "plugin add aerisun-mcp@aerisun" in commands
        assert "mcp remove aerisun-mcp" in commands
        assert "mcp add aerisun-mcp --url" in commands
    else:
        assert "plugin marketplace update aerisun" in commands
        assert "plugin update aerisun-mcp@aerisun --scope user" in commands
        assert "plugin marketplace remove" not in commands
        assert "mcp remove aerisun-mcp --scope user" in commands
        assert "mcp add-json --scope user aerisun-mcp" in commands


def test_claude_installer_rebinds_an_old_site_domain(client, tmp_path: Path) -> None:
    result, commands = _run_installer_with_fake_client(
        client,
        tmp_path,
        "claude",
        existing=True,
        marketplace_url="https://old.example/mcp/install/claude-marketplace.json",
    )

    assert result.returncode == 0, result.stderr
    assert "plugin marketplace remove aerisun --scope user" in commands
    assert "plugin marketplace add" in commands
    assert get_settings().site_url.rstrip("/") in commands
    assert "plugin install aerisun-mcp@aerisun --scope user" in commands
