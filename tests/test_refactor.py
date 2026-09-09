"""Unit tests for recipe refactoring module and CLI command using table-driven patterns."""

from pathlib import Path
from unittest.mock import patch
import pytest

from meta_agent.cmd import Cmd, RefactorOpts
from meta_agent.refactor import (
    extract_toml_and_review,
    refactor_recipe,
    save_refactored_recipe,
    RefactorRequest,
)


@pytest.mark.parametrize(
    "case_name, raw_output, expected_review_snippet, expected_toml_snippet",
    [
        (
            "standard_with_delimiter",
            (
                "1. Added think to tools.\n"
                "2. Improved prompt.\n\n"
                "---TOML---\n"
                '[recipe]\nname = "test_bot"\nversion = "0.2.0"'
            ),
            "Added think",
            '[recipe]\nname = "test_bot"',
        ),
        (
            "wrapped_with_markdown_fences",
            'Review points:\n- Done\n\n---TOML---\n```toml\n[recipe]\nname = "fenced_bot"\n```',
            "Review points",
            '[recipe]\nname = "fenced_bot"',
        ),
        (
            "fallback_without_delimiter",
            'Explanation text here\n[recipe]\nname = "fallback_bot"\nversion = "0.1.0"',
            "Explanation text",
            '[recipe]\nname = "fallback_bot"',
        ),
    ],
)
def test_extract_toml_and_review_table(
    case_name: str,
    raw_output: str,
    expected_review_snippet: str,
    expected_toml_snippet: str,
) -> None:
    """Table-driven test for splitting review comments and TOML from LLM output."""
    review, toml_part = extract_toml_and_review(raw_output)
    assert expected_review_snippet in review
    assert expected_toml_snippet in toml_part


@pytest.mark.parametrize(
    "in_place, expected_filename_part, expected_name_in_content",
    [
        (True, "sample_bot.toml", "sample_bot"),
        (False, "sample_bot_v0-2-0", "sample_bot_v0-2-0"),
    ],
)
def test_refactor_recipe_and_save_modes(
    tmp_path: Path,
    in_place: bool,
    expected_filename_part: str,
    expected_name_in_content: str,
) -> None:
    """Table-driven test for refactor execution and save modes (in-place vs as-new)."""
    recipe_file = tmp_path / "sample_bot.toml"
    recipe_file.write_text(
        """[recipe]
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
""",
        encoding="utf-8",
    )

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

        ok, saved_path, msg = save_refactored_recipe(res, in_place=in_place, recipes_dir=str(tmp_path))
        assert ok
        assert expected_filename_part in saved_path
        content = Path(saved_path).read_text(encoding="utf-8")
        assert f'name = "{expected_name_in_content}"' in content
        assert 'version = "0.2.0"' in content


@pytest.mark.parametrize(
    "out_format, expect_in_stdout",
    [
        ("diff", "-tools = []"),
        ("toml", '[recipe]\nname = "dry_bot"'),
        ("json", '"recipe":"dry_bot"'),
    ],
)
def test_cmd_refactor_output_formats_table(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    out_format: str,
    expect_in_stdout: str,
) -> None:
    """Table-driven test for refactor CLI command with dry-run and different output formats."""
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
tools = ["file_read"]
system_prompt = "Updated test"
"""
    with patch("meta_agent.api.Script.run", return_value=mock_llm_output):
        opts = RefactorOpts(
            recipes=[str(recipe_file)],
            dry_run=True,
            out=out_format,
        )
        Cmd.refactor_cmd(opts)
        out = capsys.readouterr().out
        assert "Refactor Assessment for 'dry_bot'" in out
        assert "Dry-run mode: no changes saved" in out
        assert expect_in_stdout in out
        # Verify dry-run did not alter the file
        assert 'version = "0.1.0"' in recipe_file.read_text(encoding="utf-8")
