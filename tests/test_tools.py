"""Tests for custom OpenJarvis tools registered in meta_agent.tools."""

from unittest.mock import patch
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.tools._stubs import ToolSpec
import pytest

from meta_agent.api import Agent, Recipe, Tool, Engine, Model
from meta_agent.gen import GenResponse
from meta_agent.refactor import RefactorResult


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
        "inspect_engine",
        "list_engines",
        "inspect_model",
        "list_models",
        "refactor_recipe",
        "ask_recipe",
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
        ("inspect_engine", "meta_agent.tools.inspect_engine", None, "", False, ""),
        (
            "inspect_engine",
            "meta_agent.tools.inspect_engine",
            Engine(name="ollama", description="Ollama local engine"),
            "ollama",
            True,
            "ollama",
        ),
        ("inspect_model", "meta_agent.tools.inspect_model", None, "", False, ""),
        (
            "inspect_model",
            "meta_agent.tools.inspect_model",
            Model(name="llama3", engine="ollama"),
            "llama3",
            True,
            "llama3",
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
        (
            "list_engines",
            "meta_agent.tools.list_engines",
            [Engine(name="ollama"), Engine(name="anthropic")],
            "ollama",
        ),
        (
            "list_models",
            "meta_agent.tools.list_models",
            [Model(name="llama3", engine="ollama"), Model(name="mistral", engine="ollama")],
            "llama3",
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


@pytest.mark.parametrize(
    "recipe, query, target, refactor_res, expected_success, expected_snippet",
    [
        ("", "", "all", None, False, "No recipe specified"),
        (
            "my_recipe",
            "",
            "all",
            RefactorResult(
                recipe_name="my_recipe",
                original_path="/p.toml",
                original_content="a = 1",
                refactored_content="a = 2",
                diff="--- +++",
                review_comments="ok",
                old_version="1.0.0",
                new_version="1.0.1",
                success=True,
            ),
            True,
            "Refactored: my_recipe (1.0.0 -> 1.0.1)",
        ),
        (
            "my_recipe",
            "optimize",
            "tools",
            RefactorResult(
                recipe_name="my_recipe",
                original_path="/p.toml",
                original_content="",
                refactored_content="",
                diff="",
                review_comments="",
                old_version="",
                new_version="",
                success=False,
                error_message="Failed to refactor",
            ),
            False,
            "Failed to refactor",
        ),
    ],
)
def test_refactor_recipe_tool_execute_table(
    recipe: str,
    query: str,
    target: str,
    refactor_res: Any,
    expected_success: bool,
    expected_snippet: str,
) -> None:
    """Table-driven test for refactor_recipe execute method."""
    tool = ToolRegistry.get("refactor_recipe")()
    with patch("meta_agent.tools.refactor_recipe", return_value=refactor_res):
        res = tool.execute(recipe=recipe, query=query, target=target)
        assert res.success is expected_success
        assert expected_snippet in res.content


@pytest.mark.parametrize(
    "recipe, query, inspect_res, ask_res, ask_exc, expected_success, expected_snippet",
    [
        ("", "hi", None, "", None, False, "Both recipe and query are required"),
        ("rec", "", None, "", None, False, "Both recipe and query are required"),
        ("rec", "hi", None, "", None, False, "Recipe 'rec' not found"),
        (
            "rec",
            "hi",
            Recipe(name="rec", description="d", agent_type="a", tools=[], system_prompt="s"),
            "Answer 42",
            None,
            True,
            "Answer 42",
        ),
        (
            "rec",
            "hi",
            Recipe(name="rec", description="d", agent_type="a", tools=[], system_prompt="s"),
            "",
            RuntimeError("LLM error"),
            False,
            "Error executing agent",
        ),
    ],
)
def test_ask_recipe_tool_execute_table(
    recipe: str,
    query: str,
    inspect_res: Recipe | None,
    ask_res: str,
    ask_exc: Exception | None,
    expected_success: bool,
    expected_snippet: str,
) -> None:
    """Table-driven test for ask_recipe execute method."""
    tool = ToolRegistry.get("ask_recipe")()
    with (
        patch("meta_agent.tools.inspect_recipe", return_value=inspect_res),
        patch("meta_agent.tools.get_llm_client") as mock_client,
    ):
        if ask_exc:
            mock_client.return_value.ask.side_effect = ask_exc
        else:
            mock_client.return_value.ask.return_value = ask_res

        res = tool.execute(recipe=recipe, query=query, max_tokens=1024, temperature=0.2)
        assert res.success is expected_success
        assert expected_snippet in res.content
        if expected_success:
            mock_client.return_value.ask.assert_called_once()
            _, kwargs = mock_client.return_value.ask.call_args
            assert kwargs["max_tokens"] == 1024
            assert kwargs["temperature"] == 0.2
