from dataclasses import dataclass

import pytest

from meta_agent.api import Recipe
from meta_agent.tui.helpers import (
    build_chat_command_parts,
    build_chat_prompt,
    build_recipe_action_prompt,
    build_semantic_search_prompt,
    filter_items,
    find_matching_recipe,
    format_command_preview,
    InputHistory,
    parse_exported_chat_file,
    parse_recipe_action_intent,
    sort_items,
)


@dataclass
class DummyItem:
    name: str


@pytest.mark.parametrize(
    ("sort_key", "expected_names"),
    [
        ("alpha_asc", ["Apple", "banana", "cherry"]),
        ("alpha_desc", ["cherry", "banana", "Apple"]),
    ],
)
def test_sort_items(sort_key: str, expected_names: list[str]) -> None:
    items = [DummyItem("banana"), DummyItem("Apple"), DummyItem("cherry")]
    sorted_res = sort_items(items, sort_key)
    assert [x.name for x in sorted_res] == expected_names


@pytest.mark.parametrize(
    ("query", "expected_names"),
    [
        ("alpha", ["alpha_bot", "alpha_tool"]),
        ("bot", ["alpha_bot", "beta_bot"]),
        ("", ["alpha_bot", "beta_bot", "alpha_tool"]),
        ("unknown", []),
    ],
)
def test_filter_items(query: str, expected_names: list[str]) -> None:
    items = [DummyItem("alpha_bot"), DummyItem("beta_bot"), DummyItem("alpha_tool")]
    filtered = filter_items(items, query)
    assert [x.name for x in filtered] == expected_names


@pytest.mark.parametrize(
    ("target", "expected_name"),
    [
        ("pytest", "pytest"),  # Exact match priority over substring
        ("bot", "pytest_bot"),  # Substring match
        ("DOC", "doc_writer"),  # Case-insensitive substring
        ("unknown", None),  # Not found
        ("", None),  # Empty target
    ],
)
def test_find_matching_recipe(target: str, expected_name: str | None) -> None:
    recipes = [
        Recipe(
            name="pytest_bot", description="", engine_key="e", model="m", agent_type="a", tools=[], system_prompt=""
        ),
        Recipe(name="pytest", description="", engine_key="e", model="m", agent_type="a", tools=[], system_prompt=""),
        Recipe(
            name="doc_writer", description="", engine_key="e", model="m", agent_type="a", tools=[], system_prompt=""
        ),
    ]
    matched = find_matching_recipe(recipes, target)
    if expected_name is None:
        assert matched is None
    else:
        assert matched is not None
        assert matched.name == expected_name


@pytest.mark.parametrize(
    ("engine", "model", "agent", "tools", "system", "expected_flags"),
    [
        # Recipe defaults -> no override flags
        ("ollama", "llama3", "native_react", "file_read, bash", "You are helpful.", []),
        # Partial overrides
        ("cloud", "llama3", "native_react", "file_read, bash", "You are helpful.", ["--engine", "cloud"]),
        (
            "ollama",
            "gpt-4o",
            "orchestrator",
            "file_read, bash",
            "You are helpful.",
            ["--model", "gpt-4o", "--agent", "orchestrator"],
        ),
    ],
)
def test_build_chat_command_parts(
    engine: str, model: str, agent: str, tools: str, system: str, expected_flags: list[str]
) -> None:
    rec = Recipe(
        name="test_recipe",
        description="Test recipe description",
        engine_key="ollama",
        model="llama3",
        agent_type="native_react",
        tools=["file_read", "bash"],
        system_prompt="You are helpful.",
    )
    parts = build_chat_command_parts(
        recipe=rec,
        engine=engine,
        model=model,
        agent=agent,
        tools=tools,
        system=system,
        default_engine="ollama",
        default_model="llama3",
    )
    assert parts[:4] == ["meta_agent", "chat", "--recipe", "test_recipe"]
    for flag in expected_flags:
        assert flag in parts


def test_format_command_preview() -> None:
    parts = ["meta_agent", "chat", "--recipe", "my_bot", "--engine", "cloud", "--model", "gpt-4o"]
    formatted = format_command_preview(parts)
    assert "meta_agent chat --recipe my_bot \\\n" in formatted
    assert "--engine cloud" in formatted
    assert "--model gpt-4o" in formatted


def test_build_chat_prompt() -> None:
    # First turn with system prompt
    p1 = build_chat_prompt("You are a bot.", [], "Hello")
    assert "# System Prompt\nYou are a bot." in p1
    assert "# User Query\nHello" in p1

    # Multi-turn prompt
    history = [
        ("User", "Hi", "2026-01-01 10:00:00"),
        ("Assistant", "Hello there!", "2026-01-01 10:00:05"),
        ("User", "What can you do?", "2026-01-01 10:01:00"),
    ]
    p2 = build_chat_prompt("You are a bot.", history, "What can you do?")
    assert "# Conversation History" in p2
    assert "<User>\nHi\n</User>" in p2
    assert "<Assistant>\nHello there!\n</Assistant>" in p2
    assert "# Current User Query\nWhat can you do?" in p2


def test_prompt_builders() -> None:
    rec_prompt = build_recipe_action_prompt(
        query="find recipe",
        catalogue="- bot: A bot",
        chat_catalogue="- File 'chat_1.md': Test session",
    )
    assert "User request: find recipe" in rec_prompt
    assert "- bot: A bot" in rec_prompt
    assert "chat_1.md" in rec_prompt
    assert '"action": "generate"' in rec_prompt

    search_prompt = build_semantic_search_prompt(
        query="find tool",
        catalogue="- tool1: Description",
    )
    assert "Query: find tool" in search_prompt
    assert "- tool1: Description" in search_prompt


@pytest.mark.parametrize(
    ("raw_input", "expected_action", "expected_attr", "expected_val"),
    [
        (
            '{"action": "generate", "query": "Build a python pytest bot"}',
            "generate",
            "generate_query",
            "Build a python pytest bot",
        ),
        (
            '{"action": "resume", "chat_file": "chat_pytest_20260101.md", "recipe": "pytest_bot"}',
            "resume",
            "chat_file",
            "chat_pytest_20260101.md",
        ),
        ('{"action": "delete", "target": "old_bot"}', "delete", "target", "old_bot"),
        ('{"action": "edit", "target": "custom_bot", "instruction": "change tools"}', "edit", "target", "custom_bot"),
        ("bot_alpha\nbot_beta\nbot_gamma", "search", "ranked_names", ["bot_alpha", "bot_beta", "bot_gamma"]),
    ],
)
def test_parse_recipe_action_intent(
    raw_input: str, expected_action: str, expected_attr: str, expected_val: object
) -> None:
    intent = parse_recipe_action_intent(raw_input)
    assert intent.action == expected_action
    assert getattr(intent, expected_attr) == expected_val


def test_parse_exported_chat_file() -> None:
    content = (
        "# Chat Session: my_test_recipe\n"
        "- **Engine**: ollama\n"
        "- **Model**: gemma4:12b\n"
        "- **Agent**: orchestrator\n"
        "- **Tools**: file_read, bash\n"
        "- **System**: You are a helpful test assistant.\n"
        "---\n\n"
        "## 👤 User [2026-08-28 10:00:00]\n"
        "Can you run tests?\n\n"
        "## 🤖 Assistant [2026-08-28 10:00:05]\n"
        "Yes, I can execute pytest for you.\n"
    )
    parsed = parse_exported_chat_file(content)
    assert parsed is not None
    assert parsed.recipe_name == "my_test_recipe"
    assert parsed.engine == "ollama"
    assert parsed.model == "gemma4:12b"
    assert parsed.agent == "orchestrator"
    assert parsed.tools == "file_read, bash"
    assert parsed.system == "You are a helpful test assistant."
    assert len(parsed.history) == 2
    assert parsed.history[0] == ("User", "Can you run tests?", "2026-08-28 10:00:00")
    assert parsed.history[1] == ("Assistant", "Yes, I can execute pytest for you.", "2026-08-28 10:00:05")


def test_input_history() -> None:
    history = InputHistory(max_size=3)
    assert history.entries == []
    assert history.previous("current draft") is None
    assert history.next() is None

    # Add entries
    history.append("prompt 1")
    history.append("prompt 2")
    assert history.entries == ["prompt 1", "prompt 2"]

    # Navigate backwards (up)
    assert history.previous("working draft") == "prompt 2"
    assert history.previous("working draft") == "prompt 1"
    # At oldest, stays at oldest
    assert history.previous("working draft") == "prompt 1"

    # Navigate forwards (down)
    assert history.next() == "prompt 2"
    assert history.next() == "working draft"
    assert history.next() is None

    # Append new entry resets navigation state
    history.append("prompt 3")
    history.append("prompt 4")  # Exceeds max_size=3, prompt 1 should be dropped
    assert history.entries == ["prompt 2", "prompt 3", "prompt 4"]
    assert history.previous("new draft") == "prompt 4"

    # Clear
    history.clear()
    assert history.entries == []
    assert history.previous("draft") is None
