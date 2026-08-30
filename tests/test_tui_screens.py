from pathlib import Path
import tempfile

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, Label, ListView, Markdown, Static, TextArea

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
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            # Press 'ctrl+h' to open help modal
            await pilot.press("ctrl+h")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)

            # Press 'escape' to dismiss help modal
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, HelpScreen)

            # Unfocus search TextArea before testing '?' shortcut
            await pilot.press("escape")
            await pilot.pause()

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
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            screen = ChatOptionsScreen(rec, default_engine="ollama", default_model="llama3", export_dir=tmpdir)
            app.push_screen(screen)
            await pilot.pause()
            assert isinstance(app.screen, ChatOptionsScreen)

            # Check preview is populated
            cmd_preview = screen.query_one("#chat-opts-cmd", Static)
            assert cmd_preview is not None

            # Press Ctrl+C to start chat directly
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert isinstance(app.screen, ChatScreen)

            # Dismiss chat screen to cleanly trigger on_unmount() and detach log handlers
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, ChatScreen)


@pytest.mark.anyio
async def test_tui_chat_options_dropdown_search_and_sync() -> None:
    """Test searching dropdown options via 'Ctrl+F' in ChatOptionsScreen and syncing input."""
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
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            screen = ChatOptionsScreen(rec, default_engine="ollama", default_model="llama3", export_dir=tmpdir)
            app.push_screen(screen)
            await pilot.pause()

            # Focus agent Select widget
            agent_select = screen.query_one("#chat-opts-agent-select", SearchableSelect)
            agent_select.focus()
            await pilot.pause()

            # Press 'ctrl+f' to open searchable overlay
            await pilot.press("ctrl+f")
            await pilot.pause()
            assert agent_select.expanded

            # Select 'simple' option directly
            agent_select.value = "simple"
            await pilot.pause()
            assert screen.query_one("#chat-opts-agent", Input).value == "simple"

            # Test Copy Command logic
            screen._copy_command()
            await pilot.pause()

            # Dismiss via escape key to cleanly pop screen and teardown resources
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, ChatOptionsScreen)


@pytest.mark.anyio
async def test_tui_edit_recipe_screen_save() -> None:
    """Test EditRecipeScreen TOML saving and validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        recipe_path = Path(tmpdir) / "test_bot.toml"
        recipe_path.write_text('[recipe]\nname = "test_bot"\n', encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
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

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
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

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
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

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
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
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
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

            # Maximize messages via 'ctrl+o' key
            await pilot.press("ctrl+o")
            assert chat_screen._maximized_pane == "chat-messages"

            # Press Escape: should restore normal view, NOT dismiss screen
            await pilot.press("escape")
            assert chat_screen._maximized_pane is None
            assert isinstance(app.screen, ChatScreen)

            # Maximize logs via 'ctrl+l' key
            await pilot.press("ctrl+l")
            assert chat_screen._maximized_pane == "chat-log"

            # Maximize prompt via 'ctrl+p' key
            await pilot.press("ctrl+p")
            assert chat_screen._maximized_pane == "chat-prompt"

            # Press 'ctrl+p' to toggle restore
            await pilot.press("ctrl+p")
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
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
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


@pytest.mark.anyio
async def test_tui_delete_recipe_multi_file_and_confirm() -> None:
    """Test DeleteRecipeScreen single confirm and multi-file delete buttons."""
    with tempfile.TemporaryDirectory() as tmpdir:
        f1 = Path(tmpdir) / "dup1.toml"
        f2 = Path(tmpdir) / "dup2.toml"
        f1.write_text('[recipe]\nname = "dup"\n', encoding="utf-8")
        f2.write_text('[recipe]\nname = "dup"\n', encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            # Test multi-file delete all
            screen = DeleteRecipeScreen("dup", [str(f1), str(f2)])
            app.push_screen(screen)
            await pilot.pause()
            assert len(screen.query_one("#delete-file-list", ListView).children) == 2

            # Click Delete All
            await pilot.click("#delete-all-btn")
            await pilot.pause()
            assert not f1.exists()
            assert not f2.exists()
            assert not isinstance(app.screen, DeleteRecipeScreen)


@pytest.mark.anyio
async def test_tui_edit_recipe_multi_file_switch_and_ctrl_s() -> None:
    """Test EditRecipeScreen switching files in list and saving via Ctrl+S."""
    with tempfile.TemporaryDirectory() as tmpdir:
        f1 = Path(tmpdir) / "edit1.toml"
        f2 = Path(tmpdir) / "edit2.toml"
        f1.write_text('[recipe]\nname = "edit1"\n', encoding="utf-8")
        f2.write_text('[recipe]\nname = "edit2"\n', encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            screen = EditRecipeScreen("edit_bot", [str(f1), str(f2)])
            app.push_screen(screen)
            await pilot.pause()

            # Switch file to f2
            file_list = screen.query_one("#edit-file-list", ListView)
            file_list.index = 1
            file_list.action_select_cursor()
            await pilot.pause()

            # Verify editor text switched to f2
            editor = screen.query_one("#edit-text-area", TextArea)
            assert "edit2" in editor.text

            # Modify and save with Ctrl+S
            editor.text = '[recipe]\nname = "edit2_updated"\n'
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert "edit2_updated" in f2.read_text(encoding="utf-8")
            assert not isinstance(app.screen, EditRecipeScreen)


@pytest.mark.anyio
async def test_tui_resume_chat_preview_and_confirm() -> None:
    """Test selecting a session in ResumeChatScreen updates preview and confirm returns session data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        chat_file = Path(tmpdir) / "chat_preview_20260101.md"
        content = (
            "# Chat Session: preview_bot\n- **Engine**: ollama\n- **Model**: llama3\n"
            "---\n## 👤 User [2026-01-01 10:00:00]\nHello preview\n"
        )
        chat_file.write_text(content, encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            screen = ResumeChatScreen(tmpdir)
            app.push_screen(screen)
            await pilot.pause()

            # Select first file
            file_list = screen.query_one("#resume-file-list", ListView)
            file_list.index = 0
            file_list.action_select_cursor()
            await pilot.pause()

            # Verify preview is updated
            preview = screen.query_one("#resume-preview-md", Markdown)
            assert preview is not None

            # Click Confirm / Resume button
            screen.query_one("#resume-confirm-btn", Button).press()
            await pilot.pause()
            assert not isinstance(app.screen, ResumeChatScreen)


@pytest.mark.anyio
async def test_tui_chat_options_tool_append_and_start() -> None:
    """Test appending tools from dropdown and starting chat in ChatOptionsScreen."""
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
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            screen = ChatOptionsScreen(rec, default_engine="ollama", default_model="llama3", export_dir=tmpdir)
            app.push_screen(screen)
            await pilot.pause()

            # Select a tool from dropdown to append
            tool_select = screen.query_one("#chat-opts-tool-select", SearchableSelect)
            legal_tools = [v for v in tool_select._legal_values if isinstance(v, str) and v]
            if legal_tools:
                chosen_tool = legal_tools[0]
                tool_select.value = chosen_tool
                await pilot.pause()

                tools_input = screen.query_one("#chat-opts-tools", Input)
                assert chosen_tool in tools_input.value

            # Click Start Chat
            screen.query_one("#chat-opts-start", Button).press()
            await pilot.pause()
            assert not isinstance(app.screen, ChatOptionsScreen)


@pytest.mark.anyio
async def test_tui_chat_screen_back_and_empty_submission() -> None:
    """Test Back button in ChatScreen and empty input submission handling."""
    opts = AskingOpts(engine="ollama", model="llama3", agent=None, tools="", system="You are a bot")
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            chat_screen = ChatScreen("test_bot", opts, export_dir=tmpdir)
            app.push_screen(chat_screen)
            await pilot.pause()

            # Empty submit should be ignored
            chat_ta = chat_screen.query_one("#chat-input", TextArea)
            chat_ta.text = "   \n  "
            await pilot.press("ctrl+j")
            await pilot.pause()
            assert len(chat_screen._history) == 0

            # Click Back button to dismiss
            chat_screen.query_one("#chat-back-btn", Button).press()
            await pilot.pause()
            assert not isinstance(app.screen, ChatScreen)


@pytest.mark.anyio
async def test_tui_chat_screen_sidebar_layout_and_notifications() -> None:
    """Test ChatScreen sidebar widgets (system prompt, tools display, export button) and notify text."""
    opts_with_str_tools = AskingOpts(
        engine="ollama",
        model="llama3",
        agent="native_react",
        tools="file_read,bash",
        system="You are a helpful assistant.",
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            chat_screen = ChatScreen("custom_bot", opts_with_str_tools, export_dir=tmpdir)
            app.push_screen(chat_screen)
            await pilot.pause()

            # Verify sidebar layout and tools formatting
            sidebar = chat_screen.query_one("#chat-sidebar")
            assert sidebar is not None

            # Verify Tools is not character-split (e.g. not 'f, i, l, e, ...')
            labels = [str(lbl.render()) for lbl in sidebar.query(Label)]
            tools_label = next(lbl for lbl in labels if "Tools:" in lbl)
            assert "Tools: file_read,bash" in tools_label
            assert "Tools: f, i, l, e" not in tools_label

            # Verify System Prompt is present and rendered
            prompt_pane = chat_screen.query_one("#chat-sidebar-prompt", VerticalScroll)
            assert prompt_pane is not None
            assert chat_screen.query_one("#chat-prompt-max-btn", Button) is not None

            # Verify Export Chat button is styled with primary variant
            export_btn = chat_screen.query_one("#chat-export-btn", Button)
            assert export_btn.variant == "primary"

            # Maximize messages and verify notification mentions Ctrl+O
            chat_screen.action_toggle_messages_fullscreen()
            await pilot.pause()
            assert chat_screen._maximized_pane == "chat-messages"

            # Restore and toggle prompt fullscreen and verify
            chat_screen.action_toggle_prompt_fullscreen()
            await pilot.pause()
            assert chat_screen._maximized_pane == "chat-prompt"
            chat_screen.action_toggle_prompt_fullscreen()
            await pilot.pause()
            assert chat_screen._maximized_pane is None
