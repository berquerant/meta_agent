"""Top-level package for meta-agent."""

from . import tools as _tools
from .mcp import init_mcp_servers as _init_mcp_servers

# Auto-discover and register MCP servers configured in XDG_CONFIG_HOME
_init_mcp_servers()

__all__ = ["_tools", "_init_mcp_servers"]
