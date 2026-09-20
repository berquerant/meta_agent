"""Tests for XDG config and MCP server integration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import ToolSpec

from meta_agent.config import (
    MCPServerConfig,
    MetaAgentConfig,
    get_config_path,
    load_config,
)
from meta_agent.mcp import MCPManager, MCPProxyTool


def test_get_config_path_default(monkeypatch) -> None:
    """Test get_config_path fallback to ~/.config."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    expected = Path.home() / ".config" / "meta_agent" / "config.json"
    assert get_config_path() == expected


def test_get_config_path_custom_xdg(monkeypatch, tmp_path: Path) -> None:
    """Test get_config_path respecting custom XDG_CONFIG_HOME."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    expected = tmp_path / "meta_agent" / "config.json"
    assert get_config_path() == expected


def test_load_config_non_existent(tmp_path: Path) -> None:
    """Test load_config when file does not exist."""
    cfg = load_config(tmp_path / "non_existent.json")
    assert isinstance(cfg, MetaAgentConfig)
    assert len(cfg.mcp_servers) == 0


def test_load_config_invalid_json(tmp_path: Path) -> None:
    """Test load_config with malformed JSON."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{invalid json", encoding="utf-8")
    cfg = load_config(bad_file)
    assert isinstance(cfg, MetaAgentConfig)
    assert len(cfg.mcp_servers) == 0


def test_load_config_valid(tmp_path: Path) -> None:
    """Test load_config parsing valid mcpServers config."""
    config_file = tmp_path / "config.json"
    data = {
        "mcpServers": {
            "test_server": {
                "command": "python",
                "args": ["-m", "test_mcp"],
                "env": {"TEST_VAR": "1"},
            }
        }
    }
    config_file.write_text(json.dumps(data), encoding="utf-8")

    cfg = load_config(config_file)
    assert "test_server" in cfg.mcp_servers
    server = cfg.mcp_servers["test_server"]
    assert server.command == "python"
    assert server.args == ["-m", "test_mcp"]
    assert server.env == {"TEST_VAR": "1"}


def test_mcp_proxy_tool_execute() -> None:
    """Test MCPProxyTool execution and formatting."""
    mock_client = MagicMock()
    mock_client.call_tool.return_value = {
        "content": [{"type": "text", "text": "Result from MCP tool"}],
        "isError": False,
    }
    spec = ToolSpec(name="mcp_echo", description="Echo tool", parameters={"type": "object"})
    proxy = MCPProxyTool(spec, mock_client, "server1")

    res = proxy.execute(message="hello")
    assert isinstance(res, ToolResult)
    assert res.tool_name == "mcp_echo"
    assert res.success is True
    assert "Result from MCP tool" in res.content
    mock_client.call_tool.assert_called_once_with("mcp_echo", {"message": "hello"})


def test_mcp_manager_register_and_collision() -> None:
    """Test MCPManager registering tools and handling collisions."""
    mock_client = MagicMock()
    mock_client.list_tools.return_value = [
        ToolSpec(name="mcp_custom_tool", description="Custom tool", parameters={}),
        ToolSpec(name="think", description="Collision tool", parameters={}),  # already exists in OpenJarvis
    ]

    manager = MCPManager()
    config = MetaAgentConfig(mcp_servers={"mock_srv": MCPServerConfig(command="dummy", args=[])})

    with (
        patch("meta_agent.mcp.StdioTransport"),
        patch("meta_agent.mcp.MCPClient", return_value=mock_client),
    ):
        registered = manager.register_servers(config)

        assert "mcp_custom_tool" in registered
        # "think" is a built-in OpenJarvis tool, so it should be skipped due to collision
        assert "think" not in registered
        assert ToolRegistry.contains("mcp_custom_tool")

        # Clean up
        manager.close_all()


def test_create_meta_agent_mcp_server() -> None:
    """Test create_meta_agent_mcp_server collects custom meta_agent tools."""
    from meta_agent.mcp import create_meta_agent_mcp_server

    server = create_meta_agent_mcp_server()
    assert server.SERVER_NAME == "meta_agent"
    tool_names = list(server._tools.keys())
    # Should include meta_agent custom tools
    assert "inspect_recipe" in tool_names
    assert "list_tools" in tool_names
    assert "list_agents" in tool_names
    assert "list_recipes" in tool_names


def test_serve_mcp_stdio_flow() -> None:
    """Test serve_mcp_stdio handling initialize, tools/list, and tools/call JSON-RPC messages."""
    import io
    from meta_agent.mcp import create_meta_agent_mcp_server, serve_mcp_stdio

    server = create_meta_agent_mcp_server()

    # Prepare inputs: initialize -> initialized notification -> tools/list -> tools/call
    requests = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_tools", "arguments": {}},
            }
        ),
    ]
    input_data = "\n".join(requests) + "\n"
    reader = io.StringIO(input_data)
    writer = io.StringIO()

    serve_mcp_stdio(server=server, reader=reader, writer=writer)

    output_lines = [line for line in writer.getvalue().splitlines() if line.strip()]
    # 3 responses expected (notification has no response)
    assert len(output_lines) == 3

    resp1 = json.loads(output_lines[0])
    assert resp1["id"] == 1
    assert "serverInfo" in resp1["result"]

    resp2 = json.loads(output_lines[1])
    assert resp2["id"] == 2
    tools = resp2["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "list_tools" in tool_names

    resp3 = json.loads(output_lines[2])
    assert resp3["id"] == 3
    assert resp3["result"]["isError"] is False
    assert len(resp3["result"]["content"]) > 0


def test_create_meta_agent_mcp_server_with_custom_recipes_dir() -> None:
    """Test create_meta_agent_mcp_server propagates recipes_dir to refactor_recipe tool."""
    from meta_agent.mcp import create_meta_agent_mcp_server

    server = create_meta_agent_mcp_server(recipes_dir="/custom/recipes/dir")
    refactor_tool = server._tools.get("refactor_recipe")
    assert refactor_tool is not None
    assert getattr(refactor_tool, "recipes_dir", None) == "/custom/recipes/dir"
