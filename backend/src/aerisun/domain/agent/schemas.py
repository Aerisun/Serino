from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from aerisun.core.schemas import ModelBase


class AgentUsageCapabilityRead(ModelBase):
    id: str = Field(description="Stable capability identifier")
    name: str = Field(description="Capability name")
    kind: str = Field(description="Capability kind: tool or resource")
    description: str = Field(description="Human-readable capability description")
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required to access this capability")
    invocation: dict[str, Any] = Field(default_factory=dict, description="How to invoke this capability")
    examples: list[dict[str, Any]] = Field(default_factory=list, description="Optional few-shot examples")


class AgentUsageAuthRead(ModelBase):
    type: str = Field(description="Authentication type")
    header: str = Field(description="HTTP header used for authentication")
    format: str = Field(description="Expected header value format")
    example: str = Field(description="Authentication header example")
    notes: list[str] = Field(default_factory=list, description="Additional auth notes")


class AgentUsageEndpointRead(ModelBase):
    id: str = Field(description="Stable endpoint identifier")
    url: str = Field(description="Absolute endpoint URL")
    method: str = Field(default="GET", description="HTTP method")
    description: str = Field(description="What this endpoint is for")
    required_headers: list[str] = Field(default_factory=list, description="Required request headers")
    expected_status: list[int] = Field(default_factory=list, description="Expected success status codes")


class AgentUsageScopeGuideRead(ModelBase):
    required_for_connection: list[str] = Field(default_factory=list, description="Scopes required to establish MCP connection")
    available_on_current_key: list[str] = Field(default_factory=list, description="Scopes granted to current API key")
    recommended_for_full_management: list[str] = Field(default_factory=list, description="Recommended scopes for full capability coverage")
    missing_recommended_scopes: list[str] = Field(default_factory=list, description="Recommended scopes not present on current API key")


class AgentUsageQuickstartStepRead(ModelBase):
    order: int = Field(description="Step sequence number")
    title: str = Field(description="Short step title")
    goal: str = Field(description="What this step verifies")
    command: str = Field(description="Copy-pasteable command snippet")
    expected_result: str = Field(description="Expected success signal")


class AgentUsageQuickstartRead(ModelBase):
    summary: str = Field(description="What the quickstart achieves")
    environment: dict[str, str] = Field(default_factory=dict, description="Environment variables used by commands")
    steps: list[AgentUsageQuickstartStepRead] = Field(default_factory=list, description="Ordered quickstart steps")


class AgentUsagePlaybookStepRead(ModelBase):
    order: int = Field(description="Step sequence number")
    title: str = Field(description="Short step title")
    action_type: str = Field(description="Action category such as mcp_call or curl")
    payload: dict[str, Any] = Field(default_factory=dict, description="Machine-readable action payload")
    success_criteria: str = Field(description="How to determine the step succeeded")


class AgentUsagePlaybookRead(ModelBase):
    id: str = Field(description="Stable playbook identifier")
    title: str = Field(description="Playbook title")
    description: str = Field(description="Playbook purpose")
    available: bool = Field(description="Whether current API key can execute this playbook end-to-end")
    risk_level: str = Field(description="Operational risk level")
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required by this playbook")
    steps: list[AgentUsagePlaybookStepRead] = Field(default_factory=list, description="Ordered steps")
    verification: list[str] = Field(default_factory=list, description="Post-run checks")


class AgentUsageTroubleshootingRead(ModelBase):
    code: str = Field(description="HTTP status code or error tag")
    symptom: str = Field(description="Observed symptom")
    likely_causes: list[str] = Field(default_factory=list, description="Likely causes")
    fixes: list[str] = Field(default_factory=list, description="Recommended fixes")


class AgentUsageMcpTemplateRead(ModelBase):
    id: str = Field(description="Stable template identifier")
    description: str = Field(description="Template purpose")
    sequence: list[dict[str, Any]] = Field(default_factory=list, description="Ordered MCP request sequence")


class AgentUsageMcpRead(ModelBase):
    endpoint: str = Field(description="MCP endpoint URL")
    transport: str = Field(description="MCP transport")
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required to connect to MCP")
    available_scopes: list[str] = Field(default_factory=list, description="Scopes available on the current API key")
    tools: list[AgentUsageCapabilityRead] = Field(default_factory=list, description="Visible MCP tools")
    resources: list[AgentUsageCapabilityRead] = Field(default_factory=list, description="Visible MCP resources")
    call_templates: list[AgentUsageMcpTemplateRead] = Field(default_factory=list, description="High-signal MCP call sequences")
    usage_hints: list[str] = Field(default_factory=list, description="Practical usage hints for agents")


class AgentSkillMapRead(ModelBase):
    id: str = Field(description="Skill map identifier")
    name: str = Field(description="Skill map display name")
    description: str = Field(description="What this skill map is for")
    version: int = Field(description="Skill map version")
    when: dict[str, Any] = Field(default_factory=dict, description="Trigger conditions")
    where: dict[str, Any] = Field(default_factory=dict, description="Target MCP endpoint metadata")
    docs_url: str = Field(description="Usage docs URL the agent should read first")
    use_cases: list[str] = Field(default_factory=list, description="Suggested usage scenarios")
    workflow: dict[str, Any] = Field(default_factory=dict, description="Workflow metadata")


class AgentUsageRead(ModelBase):
    schema_version: str = Field(description="Usage schema version")
    generated_at: datetime = Field(description="Server generation timestamp")
    name: str = Field(description="Usage document name")
    objective: str = Field(description="Primary goal of this usage document")
    auth: AgentUsageAuthRead = Field(description="Authentication instructions")
    endpoints: list[AgentUsageEndpointRead] = Field(default_factory=list, description="Key endpoints agents should use")
    scope_guide: AgentUsageScopeGuideRead = Field(description="Scope guidance for current API key")
    quickstart: AgentUsageQuickstartRead = Field(description="Copy-pasteable first-run path")
    playbooks: list[AgentUsagePlaybookRead] = Field(default_factory=list, description="Task-oriented execution playbooks")
    mcp: AgentUsageMcpRead = Field(description="MCP capability summary")
    troubleshooting: list[AgentUsageTroubleshootingRead] = Field(default_factory=list, description="Common failures and recovery actions")
    skill_maps: list[AgentSkillMapRead] = Field(default_factory=list, description="Local agent skill maps")


class McpPresetRead(ModelBase):
    key: str = Field(description="Preset identifier")
    name: str = Field(description="Preset display name")
    description: str = Field(description="Preset description")
    capability_ids: list[str] = Field(default_factory=list, description="Capabilities enabled by this preset")


class McpCapabilityConfigRead(ModelBase):
    id: str = Field(description="Stable capability identifier")
    name: str = Field(description="Capability name")
    kind: str = Field(description="Capability kind: tool or resource")
    description: str = Field(description="Human-readable capability description")
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required to access this capability")
    enabled: bool = Field(description="Whether this capability is enabled for MCP exposure")


class McpAdminConfigRead(ModelBase):
    api_key_id: str | None = Field(default=None, description="Selected API key identifier")
    api_key_name: str | None = Field(default=None, description="Selected API key display name")
    api_key_scopes: list[str] = Field(default_factory=list, description="Scopes currently granted to the selected API key")
    public_access: bool = Field(description="Whether MCP public access is enabled")
    selected_preset: str = Field(description="Currently selected preset key")
    is_customized: bool = Field(default=False, description="Whether enabled capabilities were customized from the preset")
    enabled_capability_count: int = Field(default=0, description="How many capabilities are currently enabled")
    available_capability_count: int = Field(default=0, description="How many capabilities exist in the MCP catalog")
    usage_url: str = Field(description="Canonical MCP usage document URL")
    endpoint: str = Field(description="MCP endpoint URL")
    transport: str = Field(description="MCP transport")
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required to connect to MCP")
    recommended_scopes: list[str] = Field(
        default_factory=list,
        description="Suggested scopes based on enabled capabilities",
    )
    presets: list[McpPresetRead] = Field(default_factory=list, description="Recommended MCP exposure presets")
    capabilities: list[McpCapabilityConfigRead] = Field(
        default_factory=list,
        description="Full MCP capability catalog with enabled state for the selected API key",
    )


class McpAdminConfigUpdate(ModelBase):
    public_access: bool | None = Field(default=None, description="Whether MCP public access is enabled")
    selected_preset: str | None = Field(default=None, description="Selected preset key")
    enabled_capability_ids: list[str] | None = Field(
        default=None,
        description="Explicitly enabled capability identifiers",
    )
