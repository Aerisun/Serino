from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from mcp import types

from aerisun.domain.agent.service import (
    _build_mcp_templates,
    _build_quickstart,
    build_agent_usage,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPANION_ROOT = PROJECT_ROOT / "companions" / "aerisun-mcp"
PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "aerisun-mcp"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
PREPARE_BUNDLE_PATH = COMPANION_ROOT / "scripts" / "prepare_ai_bundle.py"
SMOKE_PATH = PROJECT_ROOT / "scripts" / "mcp-smoke.py"


def _load_prepare_bundle() -> ModuleType:
    spec = importlib.util.spec_from_file_location("aerisun_prepare_ai_bundle", PREPARE_BUNDLE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_smoke() -> ModuleType:
    module_name = "aerisun_mcp_smoke_test_module"
    spec = importlib.util.spec_from_file_location(module_name, SMOKE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _AsyncContext:
    def __init__(self, value: object) -> None:
        self.value = value

    async def __aenter__(self) -> object:
        return self.value

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeMcpSession:
    def __init__(
        self,
        supported_versions: list[str],
        *,
        tool_names: list[str] | None = None,
        resource_names: list[str] | None = None,
        call_tool_result: types.CallToolResult | None = None,
    ) -> None:
        self.supported_versions = supported_versions
        self.tool_names = ["list_posts"] if tool_names is None else tool_names
        self.resource_names = ["aerisun://posts"] if resource_names is None else resource_names
        self.call_tool_result = call_tool_result or types.CallToolResult(content=[])
        self.calls: list[str] = []
        self.read_uris: list[str] = []
        self.called_tools: list[str] = []

    async def __aenter__(self) -> _FakeMcpSession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def discover(self) -> SimpleNamespace:
        self.calls.append("discover")
        return SimpleNamespace(supported_versions=self.supported_versions)

    async def list_tools(self) -> SimpleNamespace:
        self.calls.append("list_tools")
        return SimpleNamespace(tools=[SimpleNamespace(name=name) for name in self.tool_names])

    async def list_resources(self) -> SimpleNamespace:
        self.calls.append("list_resources")
        return SimpleNamespace(resources=[SimpleNamespace(uri=name) for name in self.resource_names])

    async def read_resource(self, uri: str) -> SimpleNamespace:
        self.calls.append("read_resource")
        self.read_uris.append(uri)
        return SimpleNamespace(contents=[])

    async def call_tool(self, name: str, _arguments: dict[str, object]) -> types.CallToolResult:
        self.calls.append("call_tool")
        self.called_tools.append(name)
        return self.call_tool_result


def _install_fake_smoke_transport(
    monkeypatch: pytest.MonkeyPatch, module: ModuleType, session: _FakeMcpSession
) -> dict[str, object]:
    captured: dict[str, object] = {}

    def create_http_client(*, headers: dict[str, str]) -> _AsyncContext:
        captured["headers"] = headers
        return _AsyncContext(object())

    monkeypatch.setattr(module, "create_mcp_http_client", create_http_client, raising=False)
    if hasattr(module, "httpx2"):
        monkeypatch.setattr(module.httpx2, "AsyncClient", lambda **_kwargs: _AsyncContext(object()))
    monkeypatch.setattr(
        module,
        "streamable_http_client",
        lambda *_args, **_kwargs: _AsyncContext((object(), object())),
    )
    monkeypatch.setattr(module, "ClientSession", lambda *_args, **_kwargs: session)
    return captured


def _usage_with_intents() -> dict[str, object]:
    return {
        "mcp": {
            "tools": [
                {
                    "name": "get_but_actually_writes",
                    "intent": "write",
                    "required_scopes": ["content:write"],
                },
                {
                    "name": "perform_safe_snapshot",
                    "intent": "read",
                    "required_scopes": ["content:read"],
                },
                {
                    "name": "read_with_write_scope",
                    "intent": "read",
                    "required_scopes": ["content:write"],
                },
                {
                    "name": "legacy_without_intent",
                    "required_scopes": ["content:read"],
                },
            ],
            "resources": [],
            "prompts": [],
        },
        "scope_guide": {"available_on_current_key": ["agent:connect", "content:read"]},
    }


def _settings(**overrides: object) -> dict[str, object]:
    settings: dict[str, object] = {
        "base_url": "https://example.test",
        "endpoint": "https://example.test/api/mcp/",
        "usage_url": "https://example.test/api/agent/usage",
        "meta_url": "https://example.test/api/mcp-meta",
        "api_key": "secret-not-written",
        "require_readonly": False,
        "allowed_write_tools": ["get_but_actually_writes", "unknown_write"],
    }
    settings.update(overrides)
    return settings


def test_bundle_classifies_read_tools_from_usage_intent_not_name_prefix() -> None:
    module = _load_prepare_bundle()

    templates = module.build_openai_tool_templates(_settings(), _usage_with_intents())

    assert templates["readonly"]["allowed_tools"] == ["perform_safe_snapshot"]
    assert templates["guarded_write"]["allowed_tools"] == [
        "get_but_actually_writes",
        "perform_safe_snapshot",
    ]


def test_bundle_fails_closed_for_missing_or_conflicting_intent_metadata() -> None:
    module = _load_prepare_bundle()

    templates = module.build_openai_tool_templates(_settings(), _usage_with_intents())

    assert "legacy_without_intent" not in templates["readonly"]["allowed_tools"]
    assert "read_with_write_scope" not in templates["readonly"]["allowed_tools"]
    assert "unknown_write" not in templates["guarded_write"]["allowed_tools"]


@pytest.mark.parametrize(
    "required_scopes",
    [
        None,
        "content:read",
        [],
        [""],
        [" content:read"],
        ["Content:read"],
        ["content"],
        ["content:unknown"],
        [1],
    ],
)
def test_read_capability_scope_metadata_fails_closed(required_scopes: object) -> None:
    capability = {
        "name": "read_candidate",
        "intent": "read",
        "required_scopes": required_scopes,
    }

    assert _load_prepare_bundle().is_read_only_capability(capability) is False
    assert _load_smoke()._is_read_capability(capability) is False


def test_read_capability_accepts_only_canonical_read_and_connect_scopes() -> None:
    capability = {
        "name": "read_candidate",
        "intent": "read",
        "required_scopes": ["agent:connect", "content:read"],
    }

    assert _load_prepare_bundle().is_read_only_capability(capability) is True
    assert _load_smoke()._is_read_capability(capability) is True


def test_bundle_readonly_mode_cannot_enable_allowlisted_write_tools() -> None:
    module = _load_prepare_bundle()

    templates = module.build_openai_tool_templates(
        _settings(require_readonly=True),
        _usage_with_intents(),
    )

    assert templates["guarded_write"]["allowed_tools"] == ["perform_safe_snapshot"]


def test_bundle_has_no_second_confirmation_policy() -> None:
    module = _load_prepare_bundle()
    env_values = {
        "AERISUN_MCP_BASE_URL": "https://example.test",
        "AERISUN_MCP_API_KEY": "secret-not-written",
        "AERISUN_MCP_CONFIRM_BEFORE_WRITE": "true",
    }

    settings = module.resolve_settings(env_values)
    templates = module.build_openai_tool_templates(settings, _usage_with_intents())
    manifest = module.build_companion_manifest(settings, _usage_with_intents(), {})
    briefing = module.build_briefing(settings, _usage_with_intents(), {})

    assert "confirm_before_write" not in settings
    assert "confirm_before_write" not in manifest["safety"]
    assert templates["guarded_write"]["require_approval"] == "never"
    assert "Confirm before write" not in briefing


def test_companion_removes_dead_write_resource_configuration() -> None:
    module = _load_prepare_bundle()
    env_values = {
        "AERISUN_MCP_BASE_URL": "https://example.test",
        "AERISUN_MCP_API_KEY": "secret-not-written",
        "AERISUN_MCP_ALLOWED_WRITE_RESOURCES": "aerisun://posts",
    }
    settings = module.resolve_settings(env_values)
    manifest = module.build_companion_manifest(settings, _usage_with_intents(), {})
    briefing = module.build_briefing(settings, _usage_with_intents(), {})
    paths = [
        COMPANION_ROOT / ".env.example",
        COMPANION_ROOT / "README.md",
        COMPANION_ROOT / "scripts" / "prepare_ai_bundle.py",
        SKILLS_ROOT / "aerisun-mcp-guarded-write" / "SKILL.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()

    assert "allowed_write_resources" not in settings
    assert "allowed_write_resources" not in manifest["safety"]
    assert "write resources" not in briefing.lower()
    assert "aerisun_mcp_allowed_write_resources" not in combined


def test_companion_docs_and_write_skill_do_not_request_reconfirmation() -> None:
    paths = [
        COMPANION_ROOT / ".env.example",
        COMPANION_ROOT / "README.md",
        SKILLS_ROOT / "aerisun-mcp-bootstrap" / "SKILL.md",
        SKILLS_ROOT / "aerisun-mcp-guarded-write" / "SKILL.md",
        SKILLS_ROOT / "aerisun-mcp-guarded-write" / "agents" / "openai.yaml",
    ]

    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()

    assert "aerisun_mcp_confirm_before_write" not in combined
    assert "confirm_before_write" not in combined
    assert "require_approval: always" not in combined
    assert "before executing" not in combined


def test_companion_keeps_the_raw_env_file_out_of_ai_context() -> None:
    readme = (COMPANION_ROOT / "README.md").read_text(encoding="utf-8")

    assert "- 本地 `.env` 文件" not in readme
    assert "不要把 `.env` 文件作为上下文交给 AI" in readme


def test_companion_manifest_reuses_the_installable_plugin_skills() -> None:
    skills = _load_prepare_bundle().build_skill_manifest()

    assert {item["name"] for item in skills} == {
        "aerisun-mcp-bootstrap",
        "aerisun-mcp-readonly",
        "aerisun-mcp-guarded-write",
    }
    assert all(str(item["skill_path"]).startswith("plugins/aerisun-mcp/skills/") for item in skills)
    assert not list((COMPANION_ROOT / "skills").glob("*/SKILL.md"))


def test_bootstrap_skill_delegates_protocol_negotiation_to_the_installed_client() -> None:
    source = (SKILLS_ROOT / "aerisun-mcp-bootstrap" / "SKILL.md").read_text(encoding="utf-8")

    assert "negotiate the MCP protocol automatically" in source
    assert "Prefer MCP `2026-07-28`" in source
    assert "Do not fall back to legacy `initialize`" not in source


def test_bundle_rejects_non_modern_usage_documents() -> None:
    module = _load_prepare_bundle()

    with pytest.raises(SystemExit, match="2026-07-28-usage-v3"):
        module.validate_usage_document(
            {
                "schema_version": "2026-03-usage-v2",
                "mcp": {"tools": [], "resources": []},
            }
        )


def test_usage_guidance_targets_only_mcp_2026_07_28_discovery() -> None:
    quickstart = _build_quickstart("https://example.test").model_dump(mode="json")
    templates = [item.model_dump(mode="json") for item in _build_mcp_templates()]
    usage = build_agent_usage(None, "https://example.test", None)
    rendered = repr({"quickstart": quickstart, "templates": templates, "hints": usage.mcp.usage_hints}).lower()

    assert usage.schema_version == "2026-07-28-usage-v3"
    assert "2026-07-28" in rendered
    assert "server/discover" in rendered
    assert "initialize" not in rendered


def test_smoke_has_no_legacy_or_direct_http_client_usage() -> None:
    source = SMOKE_PATH.read_text(encoding="utf-8")

    assert "import httpx2" not in source
    assert "mcp.shared._httpx_utils" not in source
    assert "await session.discover()" in source
    assert "streamablehttp_client" not in source
    assert "session.initialize" not in source


def test_smoke_rejects_write_execution_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_smoke()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mcp-smoke.py",
            "--url",
            "https://example.test/api/mcp/",
            "--api-key",
            "test-key",
            "--mode",
            "all-examples",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 2


def test_smoke_stops_immediately_when_discovery_excludes_required_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_smoke()
    session = _FakeMcpSession(["2025-11-25"])
    captured = _install_fake_smoke_transport(monkeypatch, module, session)

    outcomes = asyncio.run(
        module._run_mcp_checks(
            mcp_url="https://example.test/api/mcp/",
            api_key="test-key",
            usage=None,
            mode="readonly-examples",
            max_tool_calls=25,
        )
    )

    assert [(item.name, item.status) for item in outcomes] == [("server/discover", "FAIL")]
    assert session.calls == ["discover"]
    assert captured["headers"] == {"Authorization": "Bearer test-key"}


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {
            "mcp": {
                "tools": [
                    {
                        "name": "list_posts",
                        "required_scopes": ["content:read"],
                        "examples": [{"arguments": {"limit": 1, "offset": 0}}],
                    }
                ],
                "resources": [],
            }
        },
    ],
)
def test_smoke_without_trusted_intent_only_lists_protocol_catalog(
    monkeypatch: pytest.MonkeyPatch,
    usage: dict[str, object] | None,
) -> None:
    module = _load_smoke()
    session = _FakeMcpSession(["2026-07-28"])
    _install_fake_smoke_transport(monkeypatch, module, session)

    outcomes = asyncio.run(
        module._run_mcp_checks(
            mcp_url="https://example.test/api/mcp/",
            api_key="test-key",
            usage=usage,
            mode="readonly-examples",
            max_tool_calls=25,
        )
    )

    assert [item.name for item in outcomes[:3]] == ["server/discover", "tools/list", "resources/list"]
    assert session.calls == ["discover", "list_tools", "list_resources"]


def test_smoke_stops_on_bidirectional_catalog_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_smoke()
    session = _FakeMcpSession(
        ["2026-07-28"],
        tool_names=["list_posts", "extra_tool"],
        resource_names=["aerisun://posts", "aerisun://extra"],
    )
    usage = {
        "mcp": {
            "tools": [
                {"name": "list_posts", "intent": "read", "required_scopes": ["content:read"]},
                {"name": "missing_tool", "intent": "read", "required_scopes": ["content:read"]},
            ],
            "resources": [
                {"name": "aerisun://posts", "intent": "read", "required_scopes": ["content:read"]},
                {"name": "aerisun://missing", "intent": "read", "required_scopes": ["content:read"]},
            ],
        }
    }
    _install_fake_smoke_transport(monkeypatch, module, session)

    outcomes = asyncio.run(
        module._run_mcp_checks(
            mcp_url="https://example.test/api/mcp/",
            api_key="test-key",
            usage=usage,
            mode="readonly-examples",
            max_tool_calls=25,
        )
    )

    comparison = next(item for item in outcomes if item.name == "usage-vs-mcp")
    assert comparison.status == "FAIL"
    assert "missing_tools=['missing_tool']" in comparison.detail
    assert "extra_tools=['extra_tool']" in comparison.detail
    assert "missing_resources=['aerisun://missing']" in comparison.detail
    assert "extra_resources=['aerisun://extra']" in comparison.detail
    assert session.calls == ["discover", "list_tools", "list_resources"]


def test_smoke_reads_only_trusted_usage_resources_in_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_smoke()
    session = _FakeMcpSession(
        ["2026-07-28"],
        resource_names=["aerisun://safe", "aerisun://malformed"],
    )
    usage = {
        "mcp": {
            "tools": [
                {
                    "name": "list_posts",
                    "intent": "read",
                    "required_scopes": ["content:read"],
                    "examples": [{"arguments": {"limit": 1, "offset": 0}}],
                }
            ],
            "resources": [
                {"name": "aerisun://safe", "intent": "read", "required_scopes": ["content:read"]},
                {"name": "aerisun://malformed", "intent": "read", "required_scopes": [1]},
            ],
        }
    }
    _install_fake_smoke_transport(monkeypatch, module, session)

    asyncio.run(
        module._run_mcp_checks(
            mcp_url="https://example.test/api/mcp/",
            api_key="test-key",
            usage=usage,
            mode="readonly-examples",
            max_tool_calls=25,
        )
    )

    assert session.read_uris == ["aerisun://safe"]


def test_smoke_marks_real_mcp_call_tool_error_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_smoke()
    session = _FakeMcpSession(
        ["2026-07-28"],
        resource_names=[],
        call_tool_result=types.CallToolResult(isError=True, content=[]),
    )
    usage = {
        "mcp": {
            "tools": [
                {
                    "name": "list_posts",
                    "intent": "read",
                    "required_scopes": ["content:read"],
                    "examples": [{"arguments": {"limit": 1, "offset": 0}}],
                }
            ],
            "resources": [],
        }
    }
    _install_fake_smoke_transport(monkeypatch, module, session)

    outcomes = asyncio.run(
        module._run_mcp_checks(
            mcp_url="https://example.test/api/mcp/",
            api_key="test-key",
            usage=usage,
            mode="readonly-examples",
            max_tool_calls=25,
        )
    )

    tool_outcome = next(item for item in outcomes if item.name == "tool:list_posts")
    assert tool_outcome.status == "FAIL"
