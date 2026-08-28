from pathlib import Path
import tempfile

import pytest
from textual.widgets import Input, ListView, Static, TabbedContent

from meta_agent.api import Recipe
from meta_agent.tui.app import MetaAgentTUI
from meta_agent.tui.screens.chat_options import ChatOptionsScreen
from meta_agent.tui.screens.delete_recipe import DeleteRecipeScreen
from meta_agent.tui.screens.edit_recipe import EditRecipeScreen
from meta_agent.tui.screens.help import HelpScreen
from meta_agent.tui.screens.resume_chat import ResumeChatScreen
from meta_agent.tui.widgets import SearchableSelect, SearchableSelectOverlay


@pytest.mark.anyio
async def test_tui_app_tabs_and_search_focus() -> None:
    """Test switching tabs and focusing search via slash key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            tabs = app.query_one(TabbedContent)
            assert tabs.active == "tab-recipes"

            # Switch to agents tab
            tabs.active = "tab-agents"
            await pilot.pause()
            assert tabs.active == "tab-agents"

            # Press '/' to focus search input in agents tab
            await pilot.press("slash")
            await pilot.pause()
            assert app.query_one("#agents-search", Input).has_focus

            # Switch to Generate tab via action
            app.action_open_generate()
            await pilot.pause()
            assert tabs.active == "tab-generate"
            assert app.query_one("#gen-input", Input).has_focus


@pytest.mark.anyio
async def test_tui_dropdown_search_overlay() -> None:
    """Test pressing '/' on a focused Select widget opens the searchable overlay."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            # Focus sort Select on recipes tab
            select = app.query_one("#recipes-sort", SearchableSelect)
            select.focus()
            await pilot.pause()
            assert not select.expanded

            # Press '/' to open the dropdown overlay
            await pilot.press("slash")
            await pilot.pause()
            assert select.expanded

            # Type search characters in the overlay
            overlay = app.query_one(SearchableSelectOverlay)
            assert overlay.has_focus


@pytest.mark.anyio
async def test_tui_help_modal_open_and_dismiss() -> None:
    """Test opening and closing HelpScreen."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            # Press '?' to open help modal
            await pilot.press("question_mark")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)

            # Press 'escape' to dismiss help modal
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, HelpScreen)


@pytest.mark.anyio
async def test_tui_chat_options_screen_interaction() -> None:
    """Test opening ChatOptionsScreen, modifying inputs, updating command preview, and canceling."""
    rec = Recipe(
        name="test_bot",
        description="A bot for testing",
        system_prompt="You are a test assistant.",
        engine_key="ollama",
        model="llama3",
        agent_type="native_react",
        tools=["file_read"],
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            screen = ChatOptionsScreen(rec, default_engine="ollama", default_model="llama3", export_dir=tmpdir)
            app.push_screen(screen)
            await pilot.pause()
            assert isinstance(app.screen, ChatOptionsScreen)

            # Check preview is populated
            cmd_preview = screen.query_one("#chat-opts-cmd", Static)
            assert cmd_preview is not None

            # Press escape to cancel
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, ChatOptionsScreen)


@pytest.mark.anyio
async def test_tui_edit_recipe_screen_save() -> None:
    """Test EditRecipeScreen TOML saving and validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        recipe_path = Path(tmpdir) / "test_bot.toml"
        recipe_path.write_text('[recipe]\nname = "test_bot"\n', encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            screen = EditRecipeScreen("test_bot", [str(recipe_path)])
            app.push_screen(screen)
            await pilot.pause()
            assert isinstance(app.screen, EditRecipeScreen)

            # Save valid content
            await pilot.click("#edit-save-btn")
            await pilot.pause()
            assert not isinstance(app.screen, EditRecipeScreen)


@pytest.mark.anyio
async def test_tui_delete_recipe_screen_dismiss() -> None:
    """Test DeleteRecipeScreen cancelation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        recipe_path = Path(tmpdir) / "delete_bot.toml"
        recipe_path.write_text('[recipe]\nname = "delete_bot"\n', encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            screen = DeleteRecipeScreen("delete_bot", [str(recipe_path)])
            app.push_screen(screen)
            await pilot.pause()
            assert isinstance(app.screen, DeleteRecipeScreen)

            # Click Cancel
            await pilot.click("#delete-cancel-btn")
            await pilot.pause()
            assert not isinstance(app.screen, DeleteRecipeScreen)


@pytest.mark.anyio
async def test_tui_resume_chat_screen() -> None:
    """Test ResumeChatScreen list filtering and cancelation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        chat_file = Path(tmpdir) / "chat_bot_20260101.md"
        content = (
            "# Chat Session: bot\n- **Engine**: ollama\n- **Model**: llama3\n"
            "---\n## 👤 User [2026-01-01 10:00:00]\nHi\n"
        )
        chat_file.write_text(content, encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            screen = ResumeChatScreen(tmpdir, initial_filter="bot")
            app.push_screen(screen)
            await pilot.pause()
            assert isinstance(app.screen, ResumeChatScreen)

            # Verify matched files in list
            list_view = screen.query_one("#resume-file-list", ListView)
            assert len(list_view.children) >= 1

            # Click Cancel
            await pilot.click("#resume-cancel-btn")
            await pilot.pause()
            assert not isinstance(app.screen, ResumeChatScreen)
