"""MCP server integration and tool registration for meta_agent."""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
import json
import logging
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.mcp.client import MCPClient
from openjarvis.mcp.transport import StdioTransport
from openjarvis.tools._stubs import BaseTool, ToolSpec

from .config import MetaAgentConfig, load_config


class MCPProxyTool(BaseTool):  # type: ignore[misc]
    """Bridge tool that executes via an active MCPClient."""

    def __init__(self, tool_spec: ToolSpec, client: MCPClient, server_name: str) -> None:
        self._spec = tool_spec
        self._client = client
        self._server_name = server_name
        self.tool_id = tool_spec.name

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def execute(self, **params: Any) -> ToolResult:
        try:
            res = self._client.call_tool(self._spec.name, params)
            is_error = bool(res.get("isError", False))
            content = res.get("content", "")
            if isinstance(content, list):
                # MCP standard returns content array of objects, e.g. [{"type": "text", "text": "..."}]
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    else:
                        text_parts.append(str(item))
                content_str = "\n".join(text_parts)
            elif isinstance(content, dict):
                content_str = json.dumps(content, ensure_ascii=False)
            else:
                content_str = str(content)

            return ToolResult(
                tool_name=self._spec.name,
                content=content_str,
                success=not is_error,
            )
        except Exception as exc:
            logging.error("MCP tool '%s' on server '%s' failed: %s", self._spec.name, self._server_name, exc)
            return ToolResult(
                tool_name=self._spec.name,
                content=f"MCP tool error: {exc}",
                success=False,
            )


@dataclass
class MCPManager:
    """Manages active MCP client instances and tool registration."""

    _clients: dict[str, MCPClient] = field(default_factory=dict)
    _registered_tools: set[str] = field(default_factory=set)

    def register_servers(self, config: MetaAgentConfig | None = None) -> list[str]:
        """Start configured MCP servers, discover tools, and register them into ToolRegistry."""
        if config is None:
            config = load_config()

        registered: list[str] = []
        for server_name, server_cfg in config.mcp_servers.items():
            if server_name in self._clients:
                continue

            try:
                cmd = [server_cfg.command] + server_cfg.args
                transport = StdioTransport(cmd)
                client = MCPClient(transport)
                client.initialize()
                self._clients[server_name] = client

                tools = client.list_tools()
                for t in tools:
                    tool_name = t.name
                    if ToolRegistry.contains(tool_name):
                        logging.warning(
                            "MCP tool '%s' from server '%s' collides with already registered tool. Skipping.",
                            tool_name,
                            server_name,
                        )
                        continue

                    # Create tool wrapper
                    proxy = MCPProxyTool(t, client, server_name)
                    ToolRegistry.register_value(tool_name, proxy)
                    self._registered_tools.add(tool_name)
                    registered.append(tool_name)
                    logging.info("Registered MCP tool '%s' from server '%s'", tool_name, server_name)

            except Exception as exc:
                logging.warning("Failed to start or connect to MCP server '%s': %s", server_name, exc)

        return registered

    def close_all(self) -> None:
        """Close all active MCP clients and transport subprocesses."""
        for name, client in self._clients.items():
            try:
                client.close()
            except Exception as exc:
                logging.debug("Error closing MCP server '%s': %s", name, exc)
        self._clients.clear()


_GLOBAL_MCP_MANAGER = MCPManager()
atexit.register(_GLOBAL_MCP_MANAGER.close_all)


def init_mcp_servers(config: MetaAgentConfig | None = None) -> list[str]:
    """Initialize MCP servers from configuration and register tools."""
    return _GLOBAL_MCP_MANAGER.register_servers(config)


def get_mcp_manager() -> MCPManager:
    """Get the global MCP manager singleton."""
    return _GLOBAL_MCP_MANAGER
