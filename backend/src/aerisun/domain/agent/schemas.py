from __future__ import annotations

from typing import Any

from pydantic import Field

from aerisun.core.schemas import ModelBase


class AgentUsageCapabilityRead(ModelBase):
    name: str = Field(description="Capability name")
    kind: str = Field(description="Capability kind: tool or resource")
    description: str = Field(description="Human-readable capability description")
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required to access this capability")
    invocation: dict[str, Any] = Field(default_factory=dict, description="How to invoke this capability")
    examples: list[dict[str, Any]] = Field(default_factory=list, description="Optional few-shot examples")


class AgentUsageMcpRead(ModelBase):
    endpoint: str = Field(description="MCP endpoint URL")
    transport: str = Field(description="MCP transport")
    required_scopes: list[str] = Field(default_factory=list, description="Scopes required to connect to MCP")
    available_scopes: list[str] = Field(default_factory=list, description="Scopes available on the current API key")
    tools: list[AgentUsageCapabilityRead] = Field(default_factory=list, description="Visible MCP tools")
    resources: list[AgentUsageCapabilityRead] = Field(default_factory=list, description="Visible MCP resources")


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
    name: str = Field(description="Usage document name")
    auth: dict[str, Any] = Field(default_factory=dict, description="Authentication instructions")
    endpoint_base: str = Field(description="Base site URL")
    docs_url: str = Field(description="Canonical usage document URL")
    recommended_scopes: list[str] = Field(default_factory=list, description="Suggested MCP-related scopes")
    mcp: AgentUsageMcpRead = Field(description="MCP capability summary")
    skill_maps: list[AgentSkillMapRead] = Field(default_factory=list, description="Local agent skill maps")
    workflows: list[dict[str, Any]] = Field(default_factory=list, description="Workflow templates or notes")
