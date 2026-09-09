"""Unit tests for recipe refactoring module and CLI command."""

from pathlib import Path
from unittest.mock import patch
import pytest

from meta_agent.cmd import Cmd, RefactorOpts
from meta_agent.refactor import (
    SemVer,
    validate_recipe_components,
    extract_toml_and_review,
    refactor_recipe,
    save_refactored_recipe,
    RefactorRequest,
)


def test_semver_parse_and_bump() -> None:
    """Test SemVer parsing and incrementing."""
    s1 = SemVer.parse("0.1.0")
    assert s1.major == 0 and s1.minor == 1 and s1.patch == 0
    assert str(s1) == "0.1.0"
    assert s1.to_suffix() == "v0-1-0"

    p1 = s1.bump_patch()
    assert str(p1) == "0.1.1"

    m1 = s1.bump_minor()
    assert str(m1) == "0.2.0"

    s_empty = SemVer.parse("")
    assert str(s_empty) == "0.1.0"


def test_validate_recipe_components() -> None:
    """Test recipe component validation against mock registries."""
    sample_toml_data = {
        "recipe": {"name": "test_bot", "version": "0.1.0"},
        "agent": {"type": "non_existent_agent", "tools": ["non_existent_tool"]},
        "engine": {"key": "unknown_engine"},
    }

    report = validate_recipe_components(sample_toml_data)
    assert report.has_issues
    assert "non_existent_tool" in report.invalid_tools
    assert report.invalid_agent == "non_existent_agent"
    assert len(report.warnings) >= 2


def test_extract_toml_and_review() -> None:
    """Test splitting review comments and TOML from LLM output."""
    raw = """
1. Added think to tools.
2. Clarified and structured the system prompt.

---TOML---
[recipe]
name = "test_bot"
version = "0.2.0"

[agent]
type = "native_react"
tools = ["think"]
system_prompt = "Hello"
"""
    review, toml_part = extract_toml_and_review(raw)
    assert "Added think" in review
    assert '[recipe]\nname = "test_bot"' in toml_part


def test_refactor_recipe_and_save(tmp_path: Path) -> None:
    """Test complete refactor workflow with mock LLM."""
    recipe_file = tmp_path / "sample_bot.toml"
    recipe_content = """[recipe]
name = "sample_bot"
description = "Sample assistant"
version = "0.1.0"

[engine]
key = "ollama"

[intelligence]
model = "llama3"

[agent]
type = "native_react"
tools = []
system_prompt = "Old prompt"
"""
    recipe_file.write_text(recipe_content, encoding="utf-8")

    mock_llm_output = """
- Added file_read to tools
- Bumped version to 0.2.0

---TOML---
[recipe]
name = "sample_bot"
description = "Sample assistant"
version = "0.2.0"

[engine]
key = "ollama"

[intelligence]
model = "llama3"

[agent]
type = "native_react"
tools = ["file_read"]
system_prompt = "Improved prompt"
"""
    with patch("meta_agent.api.Script.run", return_value=mock_llm_output):
        req = RefactorRequest(
            recipe_name_or_path=str(recipe_file),
            query="Add file_read tool",
            recipes_dir=str(tmp_path),
        )
        res = refactor_recipe(req)

        assert res.success
        assert res.recipe_name == "sample_bot"
        assert res.old_version == "0.1.0"
        assert res.new_version == "0.2.0"
        assert 'tools = ["file_read"]' in res.refactored_content
        assert "-tools = []" in res.diff

        # 1. Test in-place save
        ok, path, msg = save_refactored_recipe(res, in_place=True)
        assert ok
        assert path == str(recipe_file)
        assert "0.2.0" in recipe_file.read_text(encoding="utf-8")

        # 2. Test save as new recipe
        ok_new, path_new, msg_new = save_refactored_recipe(res, in_place=False, recipes_dir=str(tmp_path))
        assert ok_new
        assert "sample_bot_v0-2-0" in path_new
        new_file_content = Path(path_new).read_text(encoding="utf-8")
        assert 'name = "sample_bot_v0-2-0"' in new_file_content


def test_cmd_refactor_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test refactor CLI command with dry-run."""
    recipe_file = tmp_path / "dry_bot.toml"
    recipe_file.write_text(
        """[recipe]
name = "dry_bot"
version = "0.1.0"
[agent]
type = "native_react"
tools = []
system_prompt = "Test"
""",
        encoding="utf-8",
    )

    mock_llm_output = """
- Refactoring completed

---TOML---
[recipe]
name = "dry_bot"
version = "0.2.0"
[agent]
type = "native_react"
tools = []
system_prompt = "Updated test"
"""
    with patch("meta_agent.api.Script.run", return_value=mock_llm_output):
        opts = RefactorOpts(
            recipes=[str(recipe_file)],
            dry_run=True,
            out="diff",
        )
        Cmd.refactor_cmd(opts)
        out = capsys.readouterr().out
        assert "Refactor Assessment for 'dry_bot'" in out
        assert "Dry-run mode: no changes saved" in out
        # Verify file was not modified
        assert 'version = "0.1.0"' in recipe_file.read_text(encoding="utf-8")
