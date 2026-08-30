from typing import TYPE_CHECKING


from meta_agent.api import Recipe
from meta_agent.asking import AskingOpts
from meta_agent.tui.app import MetaAgentTUI
from meta_agent.tui.screens.chat import ChatScreen
from meta_agent.tui.screens.help import HelpScreen

if TYPE_CHECKING:
    from pytest_textual_snapshot import SnapCompareType

FIXED_TEST_DIR = "/tmp/meta_agent_test_recipes"


def test_golden_main_recipes_tab(snap_compare: "SnapCompareType") -> None:
    """Golden test for main screen Recipes tab layout and styling (empty)."""
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
    )
    assert snap_compare(app, terminal_size=(100, 30))


def test_golden_main_recipes_with_item(snap_compare: "SnapCompareType") -> None:
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

    async def run_before(pilot) -> None:
        app._render_tab("recipes")
        await pilot.pause()
        list_view = app.query_one("#recipes-list")
        list_view.index = 0
        await pilot.pause()

    assert snap_compare(app, terminal_size=(100, 30), run_before=run_before)


def test_golden_generate_tab(snap_compare: "SnapCompareType") -> None:
    """Golden test for GenerateTab layout, log pane, and input bar."""
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
        initial_tab="tab-generate",
    )
    assert snap_compare(app, terminal_size=(100, 30))


def test_golden_logs_tab(snap_compare: "SnapCompareType") -> None:
    """Golden test for LogsTab toolbar, log container, and footer bindings."""
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
        initial_tab="tab-logs",
    )
    assert snap_compare(app, terminal_size=(100, 30))


def test_golden_help_screen(snap_compare: "SnapCompareType") -> None:
    """Golden test for HelpScreen modal layout and shortcuts table."""
    app = MetaAgentTUI(
        engine="ollama",
        model="llama3",
        recipes_dir=FIXED_TEST_DIR,
        export_dir=FIXED_TEST_DIR,
        auto_load=False,
    )

    async def run_before(pilot) -> None:
        app.push_screen(HelpScreen())
        await pilot.pause()

    assert snap_compare(app, terminal_size=(100, 30), run_before=run_before)


def test_golden_chat_screen(snap_compare: "SnapCompareType") -> None:
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

    async def run_before(pilot) -> None:
        chat = ChatScreen("sample_bot", opts, export_dir=FIXED_TEST_DIR)
        app.push_screen(chat)
        await pilot.pause()

    assert snap_compare(app, terminal_size=(100, 30), run_before=run_before)
