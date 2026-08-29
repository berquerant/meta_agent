from pathlib import Path
import tempfile

import pytest
from textual.widgets import Button, ListView, Static, TabbedContent, TextArea

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

            # Press '/' to focus search TextArea in agents tab
            await pilot.press("slash")
            await pilot.pause()
            assert app.query_one("#agents-search", TextArea).has_focus

            # Switch to Generate tab via action
            app.action_open_generate()
            await pilot.pause()
            assert tabs.active == "tab-generate"
            assert app.query_one("#gen-input", TextArea).has_focus


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


@pytest.mark.anyio
async def test_tui_fullscreen_toggle_resource_tabs() -> None:
    """Test toggling fullscreen for detail and log panes via m and l keys in resource tabs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            # Default state: not maximized
            assert app._maximized_pane is None

            # Toggle detail fullscreen via 'm' key on recipes tab
            await pilot.press("m")
            await pilot.pause()
            assert app._maximized_pane == "recipes-detail"

            # Press 'm' again to restore
            await pilot.press("m")
            await pilot.pause()
            assert app._maximized_pane is None

            # Toggle log fullscreen via 'l' key
            await pilot.press("l")
            await pilot.pause()
            assert app._maximized_pane == "recipes-log"

            # Restore via escape key
            await pilot.press("escape")
            await pilot.pause()
            assert app._maximized_pane is None

            # Click log maximize button
            await pilot.click("#recipes-log-max-btn")
            await pilot.pause()
            assert app._maximized_pane == "recipes-log"

            # Switch to detail via 'm' key directly
            await pilot.press("m")
            await pilot.pause()
            assert app._maximized_pane == "recipes-detail"

            # Switch to Generate tab
            app.action_open_generate()
            await pilot.pause()
            app.query_one("#gen-preview-max-btn", Button).press()
            await pilot.pause()
            assert app._maximized_pane == "gen-preview"

            # Switching active tab automatically resets fullscreen
            app.query_one(TabbedContent).active = "tab-recipes"
            await pilot.pause()
            assert app._maximized_pane is None


@pytest.mark.anyio
async def test_tui_chat_screen_fullscreen_toggle() -> None:
    """Test toggling fullscreen for chat messages, logs, and prompt in ChatScreen."""
    from meta_agent.asking import AskingOpts
    from meta_agent.tui.screens.chat import ChatScreen

    opts = AskingOpts(engine="ollama", model="llama3", agent=None, tools="", system="You are a bot")
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            chat_screen = ChatScreen("test_bot", opts, export_dir=tmpdir)
            app.push_screen(chat_screen)
            await pilot.pause()
            assert isinstance(app.screen, ChatScreen)
            assert chat_screen._maximized_pane is None

            # Clicking on chat markdown or messages should not crash
            await pilot.click("#chat-markdown")
            await pilot.pause()
            await pilot.click("#chat-messages")
            await pilot.pause()

            # Maximize messages via button or 'm' key
            chat_screen.query_one("#chat-messages-max-btn", Button).press()
            await pilot.pause()
            assert chat_screen._maximized_pane == "chat-messages"

            # Press Escape: should restore normal view, NOT dismiss screen
            await pilot.press("escape")
            await pilot.pause()
            assert chat_screen._maximized_pane is None
            assert isinstance(app.screen, ChatScreen)

            # Maximize logs via 'l' key
            await pilot.press("l")
            await pilot.pause()
            assert chat_screen._maximized_pane == "chat-log"

            # Maximize prompt via 'p' key
            await pilot.press("p")
            await pilot.pause()
            assert chat_screen._maximized_pane == "chat-prompt"

            # Press 'p' to toggle restore
            await pilot.press("p")
            await pilot.pause()
            assert chat_screen._maximized_pane is None

            # Press Escape when normal: should dismiss screen
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, ChatScreen)


@pytest.mark.anyio
async def test_tui_multiline_messages_and_submission() -> None:
    """Test sending multi-line messages in chat screen and generate tab via Ctrl+J."""
    from meta_agent.asking import AskingOpts
    from meta_agent.tui.screens.chat import ChatScreen

    opts = AskingOpts(engine="ollama", model="llama3", agent=None, tools="", system="You are a bot")
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            chat_screen = ChatScreen("test_bot", opts, export_dir=tmpdir)
            app.push_screen(chat_screen)
            await pilot.pause()

            # Type multi-line message in chat TextArea
            chat_ta = chat_screen.query_one("#chat-input", TextArea)
            chat_ta.text = "Hello world\nThis is line 2\nThis is line 3"
            await pilot.pause()

            # Submit using Ctrl+J
            await pilot.press("ctrl+j")
            await pilot.pause()

            # Input should be cleared and message added to history
            assert chat_ta.text == ""
            assert len(chat_screen._history) >= 1
            assert chat_screen._history[0][0] == "User"
            assert "This is line 2" in chat_screen._history[0][1]

            # Dismiss chat screen
            await pilot.press("escape")
            await pilot.pause()

            # Test multi-line submission in Generate tab
            app.action_open_generate()
            await pilot.pause()
            gen_ta = app.query_one("#gen-input", TextArea)
            gen_ta.text = "Create a pytest assistant\nWith coverage analysis"
            await pilot.pause()

            # Submit using Ctrl+J
            await pilot.press("ctrl+j")
            await pilot.pause()
            assert gen_ta.text == ""
            assert len(app._gen_input_history.entries) == 1
            assert "coverage analysis" in app._gen_input_history.entries[0]
