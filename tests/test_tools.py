"""Tests for custom OpenJarvis tools registered in meta_agent.tools."""

from unittest.mock import patch
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.tools._stubs import ToolSpec
import pytest

from meta_agent.api import Agent, Recipe, Tool
from meta_agent.gen import GenResponse


@pytest.mark.parametrize(
    "tool_name",
    [
        "generate_assistant",
        "inspect_recipe",
        "inspect_agent",
        "inspect_tool",
        "list_tools",
        "list_agents",
        "list_recipes",
    ],
)
def test_tool_registry_contains_custom_tools_table(tool_name: str) -> None:
    """Table-driven test to verify all custom tools exist in registry."""
    tool_cls = ToolRegistry.get(tool_name)
    assert tool_cls is not None
    tool = tool_cls()
    assert tool.spec.name == tool_name


@pytest.mark.parametrize(
    "query, engine, model, gen_response, expected_success, expected_snippet",
    [
        ("", "ollama", "llama3", None, False, "No query"),
        (
            "Build a helper",
            "ollama",
            "llama3",
            GenResponse(name="new_agent", path="/p.toml", success=True, message="ok"),
            True,
            "new_agent",
        ),
        (
            "Build a failing helper",
            "ollama",
            "llama3",
            GenResponse(name="", path="", success=False, message="generation failed"),
            False,
            "generation failed",
        ),
    ],
)
def test_generate_assistant_tool_execute_table(
    query: str,
    engine: str,
    model: str,
    gen_response: GenResponse | None,
    expected_success: bool,
    expected_snippet: str,
) -> None:
    """Table-driven test for GenerateAssistant execute method."""
    tool = ToolRegistry.get("generate_assistant")()
    with patch("meta_agent.tools.generate_assistant", return_value=gen_response):
        res = tool.execute(query=query, engine=engine, model=model)
        assert res.success is expected_success
        assert expected_snippet in res.content


@pytest.mark.parametrize(
    "tool_name, mock_target, mock_val, name_arg, expected_success, expected_snippet",
    [
        ("inspect_recipe", "meta_agent.tools.inspect_recipe", None, "", False, ""),
        (
            "inspect_recipe",
            "meta_agent.tools.inspect_recipe",
            Recipe(name="rec1", description="desc", agent_type="ag", tools=[], system_prompt="sys"),
            "rec1",
            True,
            "rec1",
        ),
        ("inspect_agent", "meta_agent.tools.inspect_agent", None, "", False, ""),
        (
            "inspect_agent",
            "meta_agent.tools.inspect_agent",
            Agent(name="ag1", description="desc"),
            "ag1",
            True,
            "ag1",
        ),
        ("inspect_tool", "meta_agent.tools.inspect_tool", None, "", False, ""),
        (
            "inspect_tool",
            "meta_agent.tools.inspect_tool",
            ToolSpec(name="tl1", description="desc", parameters={}),
            "tl1",
            True,
            "tl1",
        ),
    ],
)
def test_inspect_tools_execute_table(
    tool_name: str,
    mock_target: str,
    mock_val: Any,
    name_arg: str,
    expected_success: bool,
    expected_snippet: str,
) -> None:
    """Table-driven test for inspect tool execute methods."""
    tool = ToolRegistry.get(tool_name)()
    with patch(mock_target, return_value=mock_val):
        res = tool.execute(name=name_arg, out="json")
        assert res.success is expected_success
        if expected_snippet:
            assert expected_snippet in res.content


@pytest.mark.parametrize(
    "tool_name, mock_target, mock_list, expected_snippet",
    [
        (
            "list_tools",
            "meta_agent.tools.list_tools",
            [Tool(name="t1", description="d1", category="custom")],
            "t1",
        ),
        (
            "list_agents",
            "meta_agent.tools.list_agents",
            [Agent(name="a1", description="d1")],
            "a1",
        ),
        (
            "list_recipes",
            "meta_agent.tools.list_recipes",
            [Recipe(name="r1", description="d1", agent_type="a", tools=[], system_prompt="s")],
            "r1",
        ),
    ],
)
def test_list_tools_execute_table(
    tool_name: str,
    mock_target: str,
    mock_list: list[Any],
    expected_snippet: str,
) -> None:
    """Table-driven test for list tools execute methods."""
    tool = ToolRegistry.get(tool_name)()
    with patch(mock_target, return_value=mock_list):
        res = tool.execute(out="name")
        assert res.success
        assert expected_snippet in res.content
