"""Configuration management for meta_agent."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
from typing import Any


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class MetaAgentConfig:
    """Top-level configuration for meta_agent."""

    mcp_servers: dict[str, MCPServerConfig] = field(default_factory=dict)


def get_config_dir() -> Path:
    """Get the configuration directory respecting XDG_CONFIG_HOME."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home and xdg_config_home.strip():
        base_dir = Path(xdg_config_home)
    else:
        base_dir = Path.home() / ".config"
    return base_dir / "meta_agent"


def get_config_path() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.json"


def load_config(config_path: Path | str | None = None) -> MetaAgentConfig:
    """Load configuration from the specified path or the default location."""
    path = Path(config_path) if config_path else get_config_path()
    if not path.is_file():
        return MetaAgentConfig()

    try:
        content = path.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(content)
    except Exception as exc:
        logging.warning("Failed to load config from %s: %s", path, exc)
        return MetaAgentConfig()

    servers: dict[str, MCPServerConfig] = {}
    raw_servers = data.get("mcpServers", {})
    if isinstance(raw_servers, dict):
        for name, cfg in raw_servers.items():
            if isinstance(cfg, dict) and "command" in cfg:
                command = str(cfg["command"])
                args = [str(a) for a in cfg.get("args", [])] if isinstance(cfg.get("args"), list) else []
                env = (
                    {str(k): str(v) for k, v in cfg.get("env", {}).items()} if isinstance(cfg.get("env"), dict) else {}
                )
                servers[name] = MCPServerConfig(command=command, args=args, env=env)

    return MetaAgentConfig(mcp_servers=servers)
