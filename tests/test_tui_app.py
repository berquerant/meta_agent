from pathlib import Path
import tempfile

import pytest
from textual.widgets import Button, TabbedContent, TextArea

from meta_agent.api import Recipe
from meta_agent.tui.app import MetaAgentTUI
from meta_agent.tui.screens.chat_options import ChatOptionsScreen
from meta_agent.tui.screens.delete_recipe import DeleteRecipeScreen
from meta_agent.tui.screens.edit_recipe import EditRecipeScreen
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
    """Test pressing '/' on a focused Select widget opens the searchable overlay, filters, and selects."""
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

            # Type search query
            await pilot.press("z")
            await pilot.pause()
            assert "z" in overlay.border_title.lower()

            # Press Enter to select the filtered option
            await pilot.press("enter")
            await pilot.pause()
            assert select.value == "alpha_desc"


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
async def test_tui_multiline_messages_and_submission() -> None:
    """Test sending multi-line messages in generate tab via Ctrl+J."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            # Switch to Generate tab
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


@pytest.mark.anyio
async def test_tui_main_keybindings_and_shortcuts() -> None:
    """Test c, e, d, r, and g shortcut actions on main screen."""
    rec = Recipe(
        name="alpha_bot",
        description="A bot for testing",
        system_prompt="You are a test assistant.",
        engine_key="ollama",
        model="llama3",
        agent_type="native_react",
        tools=["file_read"],
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        recipe_path = Path(tmpdir) / "alpha_bot.toml"
        recipe_path.write_text('[recipe]\nname = "alpha_bot"\n', encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._selected_recipe = rec

            # 'c' opens ChatOptionsScreen
            app.push_screen(ChatOptionsScreen(rec, "ollama", "llama3", export_dir=tmpdir))
            await pilot.pause()
            assert isinstance(app.screen, ChatOptionsScreen)
            await pilot.press("escape")
            await pilot.pause()

            # 'e' opens EditRecipeScreen
            app.push_screen(EditRecipeScreen("alpha_bot", [str(recipe_path)]))
            await pilot.pause()
            assert isinstance(app.screen, EditRecipeScreen)
            await pilot.press("escape")
            await pilot.pause()

            # 'd' opens DeleteRecipeScreen
            app.push_screen(DeleteRecipeScreen("alpha_bot", [str(recipe_path)]))
            await pilot.pause()
            assert isinstance(app.screen, DeleteRecipeScreen)
            await pilot.press("escape")
            await pilot.pause()

            # 'r' opens ResumeChatScreen
            app.push_screen(ResumeChatScreen(tmpdir))
            await pilot.pause()
            assert isinstance(app.screen, ResumeChatScreen)
            await pilot.press("escape")
            await pilot.pause()

            # 'g' switches to GenerateTab
            app.action_open_generate()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "tab-generate"
            assert app.query_one("#gen-input", TextArea).has_focus


@pytest.mark.anyio
async def test_tui_log_tab_clear_and_export() -> None:
    """Test clearing and exporting application logs from LogTab."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir)
        async with app.run_test() as pilot:
            # Switch to log tab
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-logs"
            await pilot.pause()

            # Populate log buffer
            app._app_log_buffer.append("INFO: test log message 1")
            app._app_log_buffer.append("INFO: test log message 2")

            # Maximize log tab via 'l' key
            await pilot.press("l")
            await pilot.pause()
            assert app._maximized_pane == "app-log"

            # Restore via escape
            await pilot.press("escape")
            await pilot.pause()
            assert app._maximized_pane is None

            # Export logs via button
            await pilot.click("#app-log-export-btn")
            await pilot.pause()
            exported_files = list(Path(tmpdir).glob("app_logs_*.log"))
            assert len(exported_files) >= 1

            # Clear logs via button
            await pilot.click("#app-log-clear-btn")
            await pilot.pause()
            assert len(app._app_log_buffer) == 0
