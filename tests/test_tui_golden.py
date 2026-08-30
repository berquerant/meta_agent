from pathlib import Path
import re

import pytest

from meta_agent.api import Recipe
from meta_agent.asking import AskingOpts
from meta_agent.tui.app import MetaAgentTUI
from meta_agent.tui.screens.chat import ChatScreen
from meta_agent.tui.screens.help import HelpScreen

GOLDEN_DIR = Path(__file__).parent / "golden"
FIXED_TEST_DIR = "/tmp/meta_agent_test_recipes"


def normalize_svg(svg: str) -> str:
    """Normalize dynamic attributes, timestamps, and strip OS window decoration."""
    # 1. Normalize terminal IDs
    s = re.sub(r"terminal-\d+", "terminal-STATIC", svg)
    # 2. Normalize timestamps (e.g. 13:11:07)
    s = re.sub(r"\d{2}:\d{2}:\d{2}", "HH:MM:SS", s)
    # 3. Strip outer window frame rect and terminal window buttons
    window_pattern = (
        r'<rect fill="#292929"[^>]*/><text class="terminal-STATIC-title"[^>]*>.*?</text>'
        r'\s*<g transform="translate\(26,22\)">.*?</g>'
    )
    s = re.sub(window_pattern, "", s, flags=re.DOTALL)
    return s


def assert_matches_golden(svg_content: str, golden_filename: str) -> None:
    """Compare generated SVG screenshot with stored golden snapshot."""
    golden_path = GOLDEN_DIR / golden_filename
    assert golden_path.exists(), f"Golden file '{golden_filename}' does not exist."
    expected_svg = golden_path.read_text(encoding="utf-8")
    normalized_actual = normalize_svg(svg_content)
    assert (
        normalized_actual == expected_svg
    ), f"Snapshot mismatch with '{golden_filename}'. Layout or styling has changed."


@pytest.mark.anyio
async def test_golden_main_recipes_tab() -> None:
    """Golden test for main screen Recipes tab layout and styling (empty)."""
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
    )
    async with app.run_test(size=(100, 30)):
        svg = app.export_screenshot(title="MainScreen")
        assert_matches_golden(svg, "main_recipes.svg")


@pytest.mark.anyio
async def test_golden_main_recipes_with_item() -> None:
    """Golden test for main screen Recipes tab with only sample_bot loaded and selected."""
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
    )
    rec = Recipe(
        name="sample_bot",
        description="A helpful sample bot",
        system_prompt="You are a test sample assistant.",
        engine_key="ollama",
        model="llama3",
        agent_type="native_react",
        tools=["file_read", "bash"],
    )
    app._recipes = [rec]
    async with app.run_test(size=(100, 30)) as pilot:
        app._render_tab("recipes")
        await pilot.pause()
        list_view = app.query_one("#recipes-list")
        list_view.index = 0
        await pilot.pause()
        svg = app.export_screenshot(title="MainScreen")
        assert_matches_golden(svg, "main_recipes_with_item.svg")


@pytest.mark.anyio
async def test_golden_generate_tab() -> None:
    """Golden test for GenerateTab layout, log pane, and input bar."""
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        app.action_open_generate()
        await pilot.pause()
        svg = app.export_screenshot(title="GenerateTab")
        assert_matches_golden(svg, "generate_tab.svg")


@pytest.mark.anyio
async def test_golden_logs_tab() -> None:
    """Golden test for LogsTab toolbar, log container, and footer bindings."""
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        app.query_one("TabbedContent").active = "tab-logs"
        await pilot.pause()
        svg = app.export_screenshot(title="LogTab")
        assert_matches_golden(svg, "logs_tab.svg")


@pytest.mark.anyio
async def test_golden_help_screen() -> None:
    """Golden test for HelpScreen modal layout and shortcuts table."""
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        svg = app.export_screenshot(title="HelpScreen")
        assert_matches_golden(svg, "help_screen.svg")


@pytest.mark.anyio
async def test_golden_chat_screen() -> None:
    """Golden test for ChatScreen layout (sidebar width, system prompt, messages, log pane, and input bar)."""
    opts = AskingOpts(
        engine="ollama",
        model="llama3",
        agent="native_react",
        tools="file_read,bash",
        system="You are a helpful assistant.",
    )
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        chat = ChatScreen("sample_bot", opts, export_dir=FIXED_TEST_DIR)
        app.push_screen(chat)
        await pilot.pause()
        svg = app.export_screenshot(title="ChatScreen")
        assert_matches_golden(svg, "chat_screen.svg")
