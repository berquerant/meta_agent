"""Script to generate and update golden SVG snapshots for TUI screens."""

import asyncio
from pathlib import Path
import re

from meta_agent.api import Recipe
from meta_agent.asking import AskingOpts
from meta_agent.tui.app import MetaAgentTUI
from meta_agent.tui.screens.chat import ChatScreen
from meta_agent.tui.screens.help import HelpScreen

GOLDEN_DIR = Path(__file__).parent.parent / "tests" / "golden"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
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


async def generate_all_golden() -> None:
    """Generate all golden SVG files."""
    # 1. Main Recipes Tab (Empty)
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        (GOLDEN_DIR / "main_recipes.svg").write_text(
            normalize_svg(app.export_screenshot(title="MainScreen")),
            encoding="utf-8",
        )

    # 2. Main Recipes Tab (With only sample_bot recipe loaded and selected)
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
        (GOLDEN_DIR / "main_recipes_with_item.svg").write_text(
            normalize_svg(app.export_screenshot(title="MainScreen")),
            encoding="utf-8",
        )

    # 3. Generate Tab
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
        (GOLDEN_DIR / "generate_tab.svg").write_text(
            normalize_svg(app.export_screenshot(title="GenerateTab")),
            encoding="utf-8",
        )

    # 4. Logs Tab
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
        (GOLDEN_DIR / "logs_tab.svg").write_text(
            normalize_svg(app.export_screenshot(title="LogTab")),
            encoding="utf-8",
        )

    # 5. Help Screen
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
        (GOLDEN_DIR / "help_screen.svg").write_text(
            normalize_svg(app.export_screenshot(title="HelpScreen")),
            encoding="utf-8",
        )

    # 6. Chat Screen
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
        (GOLDEN_DIR / "chat_screen.svg").write_text(
            normalize_svg(app.export_screenshot(title="ChatScreen")),
            encoding="utf-8",
        )


if __name__ == "__main__":
    asyncio.run(generate_all_golden())
    print("Successfully updated all golden SVGs in tests/golden/")
