from pathlib import Path
import tempfile

import pytest
from textual.widgets import Button, ListView, TabbedContent, TextArea

from meta_agent.api import Recipe
from meta_agent.tui.app import MetaAgentTUI
from meta_agent.tui.screens.chat_options import ChatOptionsScreen
from meta_agent.tui.screens.delete_recipe import DeleteRecipeScreen
from meta_agent.tui.screens.edit_recipe import EditRecipeScreen
from meta_agent.tui.screens.resume_chat import ResumeChatScreen


@pytest.mark.anyio
async def test_tui_app_tabs_and_search_focus() -> None:
    """Test switching tabs and focusing search via slash key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            tabs = app.query_one(TabbedContent)
            assert tabs.active == "tab-recipes"
            assert app.query_one("#recipes-search", TextArea).has_focus

            # Switch to agents tab
            await pilot.click(tabs.get_tab("tab-agents"))
            assert tabs.active == "tab-agents"

            # Press 'ctrl+f' to focus search TextArea in agents tab
            await pilot.press("ctrl+f")
            assert app.query_one("#agents-search", TextArea).has_focus

            # Switch to engines tab
            await pilot.click(tabs.get_tab("tab-engines"))
            assert tabs.active == "tab-engines"

            # Press 'ctrl+f' to focus search TextArea in engines tab
            await pilot.press("ctrl+f")
            assert app.query_one("#engines-search", TextArea).has_focus

            # Switch to models tab
            await pilot.click(tabs.get_tab("tab-models"))
            assert tabs.active == "tab-models"

            # Press 'ctrl+f' to focus search TextArea in models tab
            await pilot.press("ctrl+f")
            assert app.query_one("#models-search", TextArea).has_focus

            # Switch to Generate tab via action
            app.action_open_generate()
            await pilot.pause()
            assert tabs.active == "tab-generate"
            assert app.query_one("#gen-input", TextArea).has_focus

            # Test Next Tab and Prev Tab keyboard shortcuts from within focused inputs
            await pilot.press("ctrl+right")
            await pilot.pause()
            assert tabs.active == "tab-logs"

            await pilot.press("ctrl+right")
            await pilot.pause()
            assert tabs.active == "tab-recipes"

            await pilot.press("ctrl+left")
            await pilot.pause()
            assert tabs.active == "tab-logs"


@pytest.mark.anyio
async def test_tui_fullscreen_maximize_and_restore() -> None:
    """Test maximizing detail and log panes via shortcuts, mouse clicks, and restoring with Esc."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            # Default state: not maximized
            assert app._maximized_pane is None

            # Toggle detail fullscreen via 'ctrl+o' key on recipes tab
            await pilot.press("ctrl+o")
            assert app._maximized_pane == "recipes-detail"

            # Press 'ctrl+o' again to restore
            await pilot.press("ctrl+o")
            assert app._maximized_pane is None

            # Toggle log fullscreen via 'ctrl+l' key
            await pilot.press("ctrl+l")
            assert app._maximized_pane == "recipes-log"

            # Restore via escape key
            await pilot.press("escape")
            assert app._maximized_pane is None

            # Click log maximize button
            await pilot.click("#recipes-log-max-btn")
            assert app._maximized_pane == "recipes-log"

            # Switch to detail via 'ctrl+o' key directly
            await pilot.press("ctrl+o")
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
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            # Switch to Generate tab
            app.action_open_generate()
            gen_ta = app.query_one("#gen-input", TextArea)
            gen_ta.text = "Create a pytest assistant\nWith coverage analysis"

            # Submit using Ctrl+J
            await pilot.press("ctrl+j")
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

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            app._selected_recipe = rec

            # 'c' opens ChatOptionsScreen
            app.push_screen(ChatOptionsScreen(rec, "ollama", "llama3", export_dir=tmpdir))
            await pilot.pause()
            assert isinstance(app.screen, ChatOptionsScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, ChatOptionsScreen)

            # 'e' opens EditRecipeScreen
            app.push_screen(EditRecipeScreen("alpha_bot", [str(recipe_path)]))
            await pilot.pause()
            assert isinstance(app.screen, EditRecipeScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, EditRecipeScreen)

            # 'd' opens DeleteRecipeScreen
            app.push_screen(DeleteRecipeScreen("alpha_bot", [str(recipe_path)]))
            await pilot.pause()
            assert isinstance(app.screen, DeleteRecipeScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, DeleteRecipeScreen)

            # 'r' opens ResumeChatScreen
            app.push_screen(ResumeChatScreen(tmpdir))
            await pilot.pause()
            assert isinstance(app.screen, ResumeChatScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, ResumeChatScreen)

            # 'g' switches to GenerateTab
            app.action_open_generate()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "tab-generate"
            assert app.query_one("#gen-input", TextArea).has_focus


@pytest.mark.anyio
async def test_tui_log_tab_clear_and_export() -> None:
    """Test clearing and exporting application logs from LogTab."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            # Switch to log tab
            tabs = app.query_one(TabbedContent)
            await pilot.click(tabs.get_tab("tab-logs"))

            # Populate log buffer
            app._app_log_buffer.append("INFO: test log message 1")
            app._app_log_buffer.append("INFO: test log message 2")

            # Maximize log tab via 'ctrl+l' key
            await pilot.press("ctrl+l")
            assert app._maximized_pane == "app-log"

            # Restore via escape
            await pilot.press("escape")
            assert app._maximized_pane is None

            # Export logs via Ctrl+S
            await pilot.press("ctrl+s")
            exported_files = list(Path(tmpdir).glob("app_logs_*.log"))
            assert len(exported_files) >= 1

            # Clear logs via Ctrl+K
            await pilot.press("ctrl+k")
            assert len(app._app_log_buffer) == 0


@pytest.mark.anyio
async def test_tui_shortcuts_and_escape_while_input_focused() -> None:
    """Test global shortcuts (Ctrl+G, Ctrl+H, Escape) trigger directly even when TextArea is focused."""
    from meta_agent.tui.screens.help import HelpScreen

    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            search_ta = app.query_one("#recipes-search", TextArea)
            search_ta.focus()
            assert search_ta.has_focus

            # Press Escape while focused: unfocuses TextArea
            await pilot.press("escape")
            assert not search_ta.has_focus

            # Focus search again and press Ctrl+G (switches to GenerateTab directly)
            search_ta.focus()
            await pilot.press("ctrl+g")
            tabs = app.query_one(TabbedContent)
            assert tabs.active == "tab-generate"

            # Focus gen-input and press Ctrl+H (opens HelpScreen directly)
            gen_input = app.query_one("#gen-input", TextArea)
            gen_input.focus()
            await pilot.press("ctrl+h")
            assert isinstance(app.screen, HelpScreen)

            # Press Escape from HelpScreen (closes HelpScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, HelpScreen)


@pytest.mark.anyio
async def test_tui_resource_selection_updates_detail() -> None:
    """Test selecting items in recipes, agents, and tools lists updates their detail panes."""
    from meta_agent.api import Agent, Tool
    from meta_agent.tui.widgets import Markdown

    with tempfile.TemporaryDirectory() as tmpdir:
        rec_file = Path(tmpdir) / "demo_bot_2026.toml"
        content = (
            '[recipe]\nname = "demo_bot"\nengine = "ollama"\nmodel = "llama3"\n'
            'agent = "native_react"\ntools = ["file_read"]\nsystem = "Demo prompt"\n'
        )
        rec_file.write_text(content, encoding="utf-8")
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test():
            test_rec = Recipe(
                name="demo_bot",
                description="Demo description",
                system_prompt="Demo prompt",
                engine_key="ollama",
                model="llama3",
                agent_type="native_react",
                tools=["file_read"],
            )
            app._recipes = [test_rec]
            app._displayed_recipes = [test_rec]
            app._selected_recipe = test_rec
            assert app._selected_recipe is not None
            assert app._selected_recipe.name == "demo_bot"

            # Test Agent detail
            test_agent = Agent(name="demo_agent", description="Demo agent description")
            app._agents = [test_agent]
            app._displayed_agents = [test_agent]
            app._selected_agent = test_agent
            agent_md = app.query_one("#agents-markdown", Markdown)
            agent_md.update("demo_agent")
            assert app._selected_agent.name == "demo_agent"

            # Test Tool detail
            test_tool = Tool(name="demo_tool", description="Demo tool description", category="general")
            app._tools = [test_tool]
            app._displayed_tools = [test_tool]
            app._selected_tool = test_tool
            tool_md = app.query_one("#tools-markdown", Markdown)
            tool_md.update("demo_tool")
            assert app._selected_tool.name == "demo_tool"


@pytest.mark.anyio
async def test_tui_ask_llm_button_trigger() -> None:
    """Test clicking Ask LLM button on search input triggers query logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            # Set search query in recipes tab
            search_ta = app.query_one("#recipes-search", TextArea)
            search_ta.text = "find a code refactoring assistant"

            # Click Ask LLM button
            await pilot.click("#recipes-llm-btn")

            # Log buffer should record user query
            assert any("find a code refactoring assistant" in log for log in app._app_log_buffer)


@pytest.mark.anyio
async def test_tui_ctrl_c_double_press_logic() -> None:
    """Test single Ctrl+C shows warning and double Ctrl+C calls exit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test():
            # First Ctrl+C: notifies to press again
            app.action_handle_ctrl_c()
            assert app._last_ctrl_c > 0

            # Second Ctrl+C immediately: triggers exit
            app.action_handle_ctrl_c()


@pytest.mark.anyio
async def test_tui_list_focus_auto_selects_first_item() -> None:
    """Test focusing on recipes list automatically selects first element when elements exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            lv = app.query_one("#recipes-list", ListView)
            assert app._selected_recipe is None

            # Focus the list view (as if navigated via Tab)
            lv.focus()
            await pilot.pause()

            # First element should be auto-selected and index set to 0
            assert lv.index == 0
            assert app._selected_recipe is not None
            assert app.query_one("#recipes-chat-btn", Button).display

            # Navigating down updates selection in real time
            if len(app._displayed_recipes) > 1:
                await pilot.press("down")
                await pilot.pause()
                assert lv.index == 1
                assert app._selected_recipe == app._displayed_recipes[1]


@pytest.mark.anyio
async def test_tui_textarea_focus_ignores_recipe_shortcuts() -> None:
    """Test that focusing a TextArea disables global shortcuts like Ctrl+D, Ctrl+A, Ctrl+E, Ctrl+B."""
    from meta_agent.api import Recipe
    from meta_agent.tui.screens.delete_recipe import DeleteRecipeScreen
    from meta_agent.tui.screens.edit_recipe import EditRecipeScreen

    rec = Recipe(
        name="sample_bot",
        description="A bot for testing",
        system_prompt="You are a test assistant.",
        engine_key="ollama",
        model="llama3",
        agent_type="native_react",
        tools=["file_read"],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        recipe_file = Path(tmpdir) / "sample_bot.toml"
        recipe_file.write_text('[recipe]\nname = "sample_bot"\n', encoding="utf-8")

        app = MetaAgentTUI(engine="ollama", model="llama3", recipes_dir=tmpdir, export_dir=tmpdir, auto_load=False)
        async with app.run_test() as pilot:
            app._selected_recipe = rec
            assert app._selected_recipe is not None

            # Now focus the search TextArea
            search_ta = app.query_one("#recipes-search", TextArea)
            search_ta.focus()
            assert search_ta.has_focus

            # Type some text
            search_ta.load_text("hello world")

            # Press Ctrl+D while TextArea is focused: should NOT trigger DeleteRecipeScreen
            await pilot.press("ctrl+d")
            assert not isinstance(app.screen, DeleteRecipeScreen)
            assert search_ta.has_focus

            # Press Ctrl+E while TextArea is focused: should NOT trigger EditRecipeScreen
            await pilot.press("ctrl+e")
            assert not isinstance(app.screen, EditRecipeScreen)
            assert search_ta.has_focus

            # Press Ctrl+A while TextArea is focused:
            # should select text or move cursor in TextArea, not trigger app actions
            await pilot.press("ctrl+a")
            assert search_ta.has_focus

            # Press Ctrl+B while TextArea is focused: should NOT toggle fullscreen (Ctrl+B is removed/unbound)
            await pilot.press("ctrl+b")
            assert app._maximized_pane is None
            assert search_ta.has_focus
