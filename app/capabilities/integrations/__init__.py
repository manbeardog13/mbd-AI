"""Installed skill, MCP, and Codex-host integration providers.

The package keeps integration discovery separate from the agent loop. Every
callable capability still registers with :class:`Registry`, so the existing
security gate and metrics remain the only execution path.
"""
from .catalog import IntegrationCatalog, register_integration_capabilities
from .mcp import (
    MCPServerSpec,
    MCPToolCapability,
    StdioMCPClient,
    infer_mcp_risk,
    register_mcp_tools,
)

__all__ = [
    "IntegrationCatalog",
    "MCPServerSpec",
    "MCPToolCapability",
    "StdioMCPClient",
    "infer_mcp_risk",
    "register_integration_capabilities",
    "register_mcp_tools",
]
