"""Unit tests for meta_agent.utils package using table-driven tests."""

from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest import TestCase
import pytest

import meta_agent.utils as utils


class TestUtils(TestCase):
    def test_format_obj_into_text(self) -> None:
        """Table-driven tests for format_obj_into_text."""
        testcases = [
            (
                "nameonly",
                "name",
                {"name": "NAME"},
                """\
                # NAME
                ## name
                NAME""",
            ),
            (
                "attr-1",
                "name",
                {"name": "NAME", "attr1": "ATTR1"},
                """\
                # NAME
                ## attr1
                ATTR1

                ## name
                NAME""",
            ),
            (
                "codeblock",
                "name",
                {"name": "NAME", "code": "```\nCODE\n```\n"},
                """\
                # NAME
                ## code
                `````
                ```
                CODE
                ```
                `````


                ## name
                NAME""",
            ),
            (
                "markdown",
                "name",
                {"name": "NAME", "data": "# title\nTITLE\n"},
                """\
                # NAME
                ## data
                `````
                # title
                TITLE
                `````


                ## name
                NAME""",
            ),
        ]
        for title, key, x, want in testcases:
            with self.subTest(title):
                got = utils.format_obj_into_text(key, x)
                self.assertEqual(dedent(want), got)


@pytest.mark.parametrize(
    (
        "raw_version, expected_major, expected_minor, expected_patch, "
        "expected_str, expected_suffix, bumped_patch, bumped_minor"
    ),
    [
        ("0.1.0", 0, 1, 0, "0.1.0", "v0-1-0", "0.1.1", "0.2.0"),
        ("1.2.3", 1, 2, 3, "1.2.3", "v1-2-3", "1.2.4", "1.3.0"),
        ("2.0", 2, 0, 0, "2.0.0", "v2-0-0", "2.0.1", "2.1.0"),
        ("v1.5.9", 1, 5, 9, "1.5.9", "v1-5-9", "1.5.10", "1.6.0"),
        ("", 0, 1, 0, "0.1.0", "v0-1-0", "0.1.1", "0.2.0"),
        ("invalid", 0, 1, 0, "0.1.0", "v0-1-0", "0.1.1", "0.2.0"),
    ],
)
def test_semver_table(
    raw_version: str,
    expected_major: int,
    expected_minor: int,
    expected_patch: int,
    expected_str: str,
    expected_suffix: str,
    bumped_patch: str,
    bumped_minor: str,
) -> None:
    """Table-driven test for SemVer parsing, representations, and version increments."""
    s = utils.SemVer.parse(raw_version)
    assert s.major == expected_major
    assert s.minor == expected_minor
    assert s.patch == expected_patch
    assert str(s) == expected_str
    assert s.to_suffix() == expected_suffix
    assert str(s.bump_patch()) == bumped_patch
    assert str(s.bump_minor()) == bumped_minor


@pytest.mark.parametrize(
    "case_name, recipe_dict, expect_issues, expect_invalid_tools, expect_invalid_agent, expect_invalid_engine",
    [
        (
            "valid_components",
            {
                "recipe": {"name": "valid_bot", "version": "0.1.0"},
                "agent": {"type": "orchestrator", "tools": ["think"]},
                "engine": {"key": "ollama"},
            },
            False,
            [],
            None,
            None,
        ),
        (
            "invalid_tools_and_agent",
            {
                "recipe": {"name": "invalid_bot", "version": "0.1.0"},
                "agent": {"type": "non_existent_agent", "tools": ["non_existent_tool_1", "non_existent_tool_2"]},
                "engine": {"key": "unknown_engine"},
            },
            True,
            ["non_existent_tool_1", "non_existent_tool_2"],
            "non_existent_agent",
            "unknown_engine",
        ),
        (
            "empty_agent_and_tools",
            {
                "recipe": {"name": "minimal_bot", "version": "0.1.0"},
                "agent": {"tools": []},
            },
            False,
            [],
            None,
            None,
        ),
    ],
)
def test_validate_recipe_components_table(
    case_name: str,
    recipe_dict: dict[str, Any],
    expect_issues: bool,
    expect_invalid_tools: list[str],
    expect_invalid_agent: str | None,
    expect_invalid_engine: str | None,
) -> None:
    """Table-driven test for recipe component validation."""
    report = utils.validate_recipe_components(recipe_dict)
    assert report.has_issues == expect_issues
    assert report.invalid_tools == expect_invalid_tools
    assert report.invalid_agent == expect_invalid_agent
    if expect_invalid_engine:
        assert report.invalid_engine == expect_invalid_engine


@pytest.mark.parametrize(
    "input_val, is_file, file_content, expected_output",
    [
        ("literal string input", False, "", "literal string input"),
        ("@-", False, "", "@-"),  # stdin reading tested separately or non-mocked as literal without stdin patch
        ("@testfile.txt", True, "content from file", "content from file"),
    ],
)
def test_read_file_or_stdin_or_str_table(
    tmp_path: Path,
    input_val: str,
    is_file: bool,
    file_content: str,
    expected_output: str,
) -> None:
    """Table-driven test for reading file or string."""
    if is_file:
        target = tmp_path / "testfile.txt"
        target.write_text(file_content, encoding="utf-8")
        actual_input = f"@{target}"
    else:
        actual_input = input_val

    if actual_input == "@-":
        # Skip stdin in parameterized run to prevent blocking
        return

    result = utils.read_file_or_stdin_or_str(actual_input)
    assert result == expected_output


@pytest.mark.parametrize(
    "data, expected_json",
    [
        ({"a": 1, "b": "hello"}, '{"a":1,"b":"hello"}'),
        ([1, 2, 3], "[1,2,3]"),
        ({"nested": {"key": True}}, '{"nested":{"key":true}}'),
    ],
)
def test_json_dumps_table(data: Any, expected_json: str) -> None:
    """Table-driven test for json_dumps."""
    assert utils.json_dumps(data) == expected_json
