from __future__ import annotations

from aerisun.domain.agent.capabilities.registry import list_capability_models
from aerisun.domain.agent.schemas import AgentUsageCapabilityRead


def list_registered_mcp_capabilities() -> list[AgentUsageCapabilityRead]:
    return list_capability_models()
