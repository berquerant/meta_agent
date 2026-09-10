"""Tests for CLI arguments parsing and sub-command handlers in meta_agent.cli."""

from unittest.mock import MagicMock, patch
import pytest

from meta_agent.cli import main, get_resources, refactor_cmd


@pytest.mark.parametrize(
    "resource_type, resource_name, target_cmd_method",
    [
        ("recipe", None, "list_recipes_cmd"),
        ("recipe", "sample", "inspect_recipe_cmd"),
        ("agent", None, "list_agents_cmd"),
        ("agent", "ag", "inspect_agent_cmd"),
        ("tool", None, "list_tools_cmd"),
        ("tool", "tl", "inspect_tool_cmd"),
        ("engine", None, "list_engines_cmd"),
        ("engine", "ollama", "inspect_engine_cmd"),
        ("model", None, "list_models_cmd"),
        ("model", "llama3", "inspect_model_cmd"),
    ],
)
def test_cli_get_resources_dispatch_table(
    resource_type: str,
    resource_name: str | None,
    target_cmd_method: str,
) -> None:
    """Table-driven test for get_resources dispatching to Cmd methods."""
    args = MagicMock()
    args.out = "name"
    args.engine = "ollama"
    args.resource_type = resource_type
    args.resource_name = resource_name

    with patch(f"meta_agent.cli.Cmd.{target_cmd_method}") as mock_cmd:
        get_resources(args)
        mock_cmd.assert_called_once()


def test_cli_get_resources_unknown_type() -> None:
    """Test get_resources raises on unknown resource type."""
    args = MagicMock()
    args.out = "name"
    args.engine = "ollama"
    args.resource_type = "unknown_type"
    args.resource_name = None
    with pytest.raises(Exception, match="Unknown resource type"):
        get_resources(args)


@pytest.mark.parametrize(
    "recipes, query, target, in_place, as_new, expected_as_new",
    [
        (["r1"], "improve prompt", "prompt", False, True, True),
        (["r1", "r2"], "clean tools", "tools", True, False, False),
        (["r3"], "", "all", False, False, False),
    ],
)
def test_cli_refactor_cmd_dispatch_table(
    recipes: list[str],
    query: str,
    target: str,
    in_place: bool,
    as_new: bool,
    expected_as_new: bool,
) -> None:
    """Table-driven test for refactor_cmd options construction and dispatch."""
    args = MagicMock()
    args.recipe = recipes
    args.query = query
    args.engine = "ollama"
    args.model = "llama3"
    args.recipes = "/path/to/recipes"
    args.target = target
    args.in_place = in_place
    args.new = as_new
    args.yes = True
    args.dry_run = False
    args.out = "diff"
    args.color = True

    with patch("meta_agent.cli.Cmd.refactor_cmd") as mock_refactor:
        refactor_cmd(args)
        mock_refactor.assert_called_once()
        opts = mock_refactor.call_args[0][0]
        assert opts.recipes == recipes
        assert opts.query == query
        assert opts.target == target
        assert opts.as_new is expected_as_new


@pytest.mark.parametrize(
    "cli_args, patch_target",
    [
        (["meta_agent", "get", "recipe"], "meta_agent.cli.get_resources"),
        (["meta_agent", "gen", "Create a bot"], "meta_agent.cli.Cmd.gen_cmd"),
        (["meta_agent", "tui"], "meta_agent.cli.run_tui"),
    ],
)
def test_cli_main_subcommand_routing_table(cli_args: list[str], patch_target: str) -> None:
    """Table-driven test for CLI main subcommand routing."""
    with patch("sys.argv", cli_args), patch(patch_target) as mock_func:
        exit_code = main()
        assert exit_code == 0
        mock_func.assert_called_once()


def test_cli_main_help() -> None:
    """Test -h exits with 0."""
    with patch("sys.argv", ["meta_agent", "-h"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
