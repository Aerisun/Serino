from .schemas import (
    AgentSkillMapRead,
    AgentUsageCapabilityRead,
    AgentUsageMcpRead,
    AgentUsageRead,
    McpAdminConfigRead,
    McpAdminConfigUpdate,
    McpCapabilityConfigRead,
    McpPresetRead,
)

__all__ = [
    "AgentSkillMapRead",
    "AgentUsageCapabilityRead",
    "AgentUsageMcpRead",
    "AgentUsageRead",
    "McpAdminConfigRead",
    "McpAdminConfigUpdate",
    "McpCapabilityConfigRead",
    "McpPresetRead",
    "build_agent_usage",
    "build_mcp_admin_config",
    "load_agent_skill_maps",
    "save_mcp_admin_config",
]


def __getattr__(name: str):
    if name in {"build_agent_usage", "build_mcp_admin_config", "load_agent_skill_maps", "save_mcp_admin_config"}:
        from .service import build_agent_usage, build_mcp_admin_config, load_agent_skill_maps, save_mcp_admin_config

        values = {
            "build_agent_usage": build_agent_usage,
            "build_mcp_admin_config": build_mcp_admin_config,
            "load_agent_skill_maps": load_agent_skill_maps,
            "save_mcp_admin_config": save_mcp_admin_config,
        }
        return values[name]
    raise AttributeError(name)
