from pathlib import Path
import tempfile

import pytest
from textual.widgets import Button, Input, ListView, Static, TextArea

from meta_agent.api import Recipe
from meta_agent.asking import AskingOpts
from meta_agent.tui.app import MetaAgentTUI
from meta_agent.tui.screens.chat import ChatScreen
from meta_agent.tui.screens.chat_options import ChatOptionsScreen
from meta_agent.tui.screens.delete_recipe import DeleteRecipeScreen
from meta_agent.tui.screens.edit_recipe import EditRecipeScreen
from meta_agent.tui.screens.help import HelpScreen
from meta_agent.tui.screens.resume_chat import ResumeChatScreen
from meta_agent.tui.widgets import SearchableSelect


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
async def test_tui_chat_options_dropdown_search_and_sync() -> None:
    """Test searching dropdown options via '/' in ChatOptionsScreen and syncing input."""
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

            # Focus agent Select widget
            agent_select = screen.query_one("#chat-opts-agent-select", SearchableSelect)
            agent_select.focus()
            await pilot.pause()

            # Press '/' to open searchable overlay
            await pilot.press("slash")
            await pilot.pause()
            assert agent_select.expanded

            # Select 'simple' option directly
            agent_select.value = "simple"
            await pilot.pause()
            assert screen.query_one("#chat-opts-agent", Input).value == "simple"

            # Test Copy Command button
            screen.query_one("#chat-opts-copy", Button).press()
            await pilot.pause()

            # Dismiss via cancel button
            screen.query_one("#chat-opts-cancel", Button).press()
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
async def test_tui_edit_recipe_validation_error() -> None:
    """Test EditRecipeScreen rejects invalid TOML and displays syntax error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        recipe_path = Path(tmpdir) / "invalid_bot.toml"
        recipe_path.write_text('[recipe]\nname = "invalid_bot"\n', encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            screen = EditRecipeScreen("invalid_bot", [str(recipe_path)])
            app.push_screen(screen)
            await pilot.pause()

            # Input invalid TOML syntax
            editor = screen.query_one("#edit-text-area", TextArea)
            editor.text = "invalid = [ unclosed array"
            await pilot.pause()

            # Click Save: should NOT dismiss and show error
            await pilot.click("#edit-save-btn")
            await pilot.pause()
            assert isinstance(app.screen, EditRecipeScreen)
            status_label = screen.query_one("#edit-status-bar", Static)
            assert "❌" in str(status_label.render()) or "error" in str(status_label.render()).lower()

            # Click Cancel: dismisses screen
            await pilot.click("#edit-cancel-btn")
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
async def test_tui_chat_screen_fullscreen_toggle() -> None:
    """Test toggling fullscreen for chat messages, logs, and prompt in ChatScreen."""
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
async def test_tui_chat_screen_export_and_history_navigation() -> None:
    """Test ChatScreen chat/log export buttons and Up/Down history navigation."""
    opts = AskingOpts(engine="ollama", model="llama3", agent=None, tools="", system="You are a bot")
    initial_history = [
        ("User", "First question", "2026-01-01 10:00:00"),
        ("Assistant", "First answer", "2026-01-01 10:00:01"),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            chat_screen = ChatScreen("test_bot", opts, export_dir=tmpdir, initial_history=initial_history)
            app.push_screen(chat_screen)
            await pilot.pause()

            # Export chat via button
            await pilot.click("#chat-export-btn")
            await pilot.pause()
            exported_chats = list(Path(tmpdir).glob("chat_test_bot_*.md"))
            assert len(exported_chats) >= 1

            # Export logs via action
            chat_screen.action_export_logs()
            await pilot.pause()
            exported_logs = list(Path(tmpdir).glob("logs_test_bot_*.log"))
            assert len(exported_logs) >= 1

            # Test history navigation with Up/Down arrows
            chat_ta = chat_screen.query_one("#chat-input", TextArea)
            chat_ta.focus()
            chat_ta.text = "Draft in progress"
            chat_ta.move_cursor((0, 0))
            await pilot.pause()

            # Press Up: loads historical prompt
            await pilot.press("up")
            await pilot.pause()
            assert chat_ta.text == "First question"

            # Press Down: restores draft
            await pilot.press("down")
            await pilot.pause()
            assert chat_ta.text == "Draft in progress"

            # Dismiss
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, ChatScreen)
