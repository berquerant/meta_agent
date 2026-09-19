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
