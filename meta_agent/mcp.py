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
from openjarvis.mcp.server import MCPServer
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


def create_meta_agent_mcp_server(recipes_dir: str | None = None) -> MCPServer:
    """Create an MCPServer instance exposing all tools registered in ToolRegistry."""
    import openjarvis.tools  # noqa: F401
    from . import tools as _tools  # noqa: F401

    tools: list[BaseTool] = []
    for key in ToolRegistry.keys():
        try:
            tool_entry = ToolRegistry.get(key)
            if isinstance(tool_entry, BaseTool):
                tools.append(tool_entry)
            elif callable(tool_entry):
                if key == "refactor_recipe" and recipes_dir is not None:
                    inst = tool_entry(recipes_dir=recipes_dir)
                else:
                    inst = tool_entry()
                if isinstance(inst, BaseTool):
                    tools.append(inst)
        except Exception as exc:
            logging.debug("Could not instantiate tool '%s' for MCP server: %s", key, exc)

    server = MCPServer(tools=tools)
    server.SERVER_NAME = "meta_agent"
    return server


def serve_mcp_stdio(
    server: MCPServer | None = None,
    reader: Any = None,
    writer: Any = None,
    recipes_dir: str | None = None,
) -> None:
    """Run an MCP JSON-RPC server over stdio."""
    import sys
    from openjarvis.mcp.protocol import (
        INTERNAL_ERROR,
        PARSE_ERROR,
        MCPRequest,
        MCPResponse,
    )

    if server is None:
        server = create_meta_agent_mcp_server(recipes_dir=recipes_dir)
    if reader is None:
        reader = sys.stdin
    if writer is None:
        writer = sys.stdout

    for line in reader:
        line_str = line.strip()
        if not line_str:
            continue

        try:
            parsed = json.loads(line_str)
            req = MCPRequest(
                method=parsed["method"],
                params=parsed.get("params", {}),
                id=parsed.get("id"),
                jsonrpc=parsed.get("jsonrpc", "2.0"),
            )
        except Exception as exc:
            err_resp = MCPResponse.error_response(0, PARSE_ERROR, f"Parse error: {exc}")
            writer.write(err_resp.to_json() + "\n")
            writer.flush()
            continue

        # JSON-RPC Notification: id is omitted or None -> do not send response
        if req.id is None or req.method.startswith("notifications/"):
            continue

        try:
            resp = server.handle(req)
        except Exception as exc:
            resp = MCPResponse.error_response(req.id, INTERNAL_ERROR, f"Server error: {exc}")

        writer.write(resp.to_json() + "\n")
        writer.flush()
