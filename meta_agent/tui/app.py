"""Main TUI application for meta_agent."""

from pathlib import Path
import time
from typing import Any, ClassVar

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Markdown,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from ..api import find_recipe_files, list_agents, list_recipes, list_tools, Agent, Recipe, Tool
from ..gen import generate_assistant, GenRequest
from ..utils import get_default_export_dir, now_str
from .helpers import (
    CTRL_C_TIMEOUT,
    agent_markdown,
    build_recipe_action_prompt,
    build_semantic_search_prompt,
    filter_items,
    find_matching_recipe,
    InputHistory,
    now_datetime_str,
    parse_recipe_action_intent,
    RecipeActionIntent,
    recipe_markdown,
    tool_markdown,
)
from .screens import ChatOptionsScreen, DeleteRecipeScreen, EditRecipeScreen, HelpScreen, ResumeChatScreen
from .screens.chat import RichLogHandler
from .styles import APP_CSS
from .widgets import GenerateTab, LogTab, ResourceTab


class MetaAgentTUI(App[None]):
    """TUI application for meta_agent."""

    CSS = APP_CSS
    ALLOW_SELECT: ClassVar[bool] = False

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+h", "open_help", "Help (Ctrl+H)", show=True, priority=True),
        Binding("question_mark", "open_help", "Help (?)", show=False, priority=False),
        Binding("f1", "open_help", "Help", show=False, priority=True),
        Binding("ctrl+f", "focus_search", "Search (Ctrl+F)", show=True, priority=True),
        Binding("ctrl+b", "toggle_detail_fullscreen", "Detail Max (Ctrl+B)", show=True, priority=True),
        Binding("ctrl+l", "toggle_log_fullscreen", "Logs Max (Ctrl+L)", show=True, priority=True),
        Binding("escape", "handle_escape", "Back (Esc)", show=False, priority=True),
        Binding("ctrl+c", "chat_recipe", "Chat (Ctrl+C)", show=True, priority=True),
        Binding("ctrl+r", "resume_chat", "Resume (Ctrl+R)", show=True, priority=True),
        Binding("ctrl+e", "edit_recipe", "Edit (Ctrl+E)", show=True, priority=True),
        Binding("ctrl+d", "delete_recipe", "Delete (Ctrl+D)", show=True, priority=True),
        Binding("ctrl+g", "open_generate", "Generate (Ctrl+G)", show=True, priority=True),
        Binding("ctrl+q", "quit", "Quit (Ctrl+Q)", show=True, priority=True),
        Binding("ctrl+p", "toggle_prompt_fullscreen", show=False, priority=True),
    ]

    def __init__(self, engine: str, model: str, recipes_dir: str, export_dir: str | None = None) -> None:
        """Initialize the TUI with LLM settings and export directory."""
        super().__init__()
        self._engine = engine
        self._model = model
        self._recipes_dir = recipes_dir
        self._export_dir = export_dir or get_default_export_dir()
        self._recipes: list[Recipe] = []
        self._agents: list[Agent] = []
        self._tools: list[Tool] = []
        self._displayed_recipes: list[Recipe] = []
        self._displayed_agents: list[Agent] = []
        self._displayed_tools: list[Tool] = []
        self._selected_recipe: Recipe | None = None
        self._last_ctrl_c: float = 0.0
        self._maximized_pane: str | None = None

        # Generate tab history state
        self._gen_input_history = InputHistory()
        self._last_generated_recipe: str | None = None

        # App Log buffer and handler
        self._app_log_buffer: list[str] = []
        self._app_log_handler: RichLogHandler | None = None

    def compose(self) -> ComposeResult:
        """Compose the main TUI layout."""
        yield Header()
        with TabbedContent(initial="tab-recipes"):
            with TabPane("Recipes", id="tab-recipes"):
                yield ResourceTab("recipes", show_chat=True)
            with TabPane("Agents", id="tab-agents"):
                yield ResourceTab("agents")
            with TabPane("Tools", id="tab-tools"):
                yield ResourceTab("tools")
            with TabPane("Generate", id="tab-generate"):
                yield GenerateTab(self._engine, self._model, self._recipes_dir)
            with TabPane("Logs", id="tab-logs"):
                yield LogTab()
        yield Footer()

    def on_mount(self) -> None:
        """Load all resources after mounting and attach app log handler."""
        # Attach RichLogHandler to app logger and root logger
        try:
            log_widget = self.query_one("#app-rich-log", RichLog)
            self._app_log_handler = RichLogHandler(log_widget, self._app_log_buffer)
            import logging

            logging.getLogger().addHandler(self._app_log_handler)
            init_msg = f"Application initialized. Engine='{self._engine}', Model='{self._model}'"
            log_widget.write(f"[green]{init_msg}[/green]")
            for tid in ("recipes", "agents", "tools"):
                try:
                    self.query_one(f"#{tid}-rich-log", RichLog).write(f"[green]{init_msg}[/green]")
                except Exception:
                    pass
            self._app_log_buffer.append(f"[{now_datetime_str()}] INFO: app - {init_msg}")
        except Exception:
            pass

        self._load_recipes()
        self._load_agents()
        self._load_tools()
        try:
            self.query_one("#gen-chat-btn", Button).display = False
        except Exception:
            pass
        try:
            self.query_one("#recipes-search", TextArea).focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Ctrl+C double-press quit
    # ------------------------------------------------------------------

    def action_handle_ctrl_c(self) -> None:
        """Quit on second Ctrl+C within timeout."""
        now = time.monotonic()
        if now - self._last_ctrl_c < CTRL_C_TIMEOUT:
            self.exit()
        else:
            self._last_ctrl_c = now
            self.notify("Press Ctrl+C again to quit", severity="warning", timeout=CTRL_C_TIMEOUT)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @work(thread=True)
    def _load_resource(self, tid: str) -> None:
        """Load resources in a background thread and render."""
        if tid == "recipes":
            self._recipes = list_recipes()
        elif tid == "agents":
            self._agents = list_agents()
        elif tid == "tools":
            self._tools = list_tools()
        self.app.call_from_thread(self._render_tab, tid)

    def _load_recipes(self) -> None:
        """Trigger background loading of recipes."""
        self._load_resource("recipes")

    def _load_agents(self) -> None:
        """Trigger background loading of agents."""
        self._load_resource("agents")

    def _load_tools(self) -> None:
        """Trigger background loading of tools."""
        self._load_resource("tools")

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _render_list(self, tid: str, items: list[Any]) -> None:
        """Populate a ListView and hide the loading indicator."""
        lv = self.query_one(f"#{tid}-list", ListView)
        lv.clear()
        for item in items:
            lv.append(ListItem(Label(item.name)))
        self.query_one(f"#{tid}-loading", LoadingIndicator).display = False

    def _render_tab(self, tid: str) -> None:
        """Render the current filtered resource list for a given tab."""
        items_map: dict[str, list[Any]] = {
            "recipes": self._recipes,
            "agents": self._agents,
            "tools": self._tools,
        }
        all_items = items_map.get(tid, [])
        try:
            search = self.query_one(f"#{tid}-search", TextArea).text
        except Exception:
            return
        items = filter_items(all_items, search)

        if tid == "recipes":
            self._displayed_recipes = items
            self._selected_recipe = None
            try:
                self.query_one("#recipes-chat-btn", Button).display = False
                self.query_one("#recipes-edit-btn", Button).display = False
                self.query_one("#recipes-delete-btn", Button).display = False
            except Exception:
                pass
        elif tid == "agents":
            self._displayed_agents = items
        elif tid == "tools":
            self._displayed_tools = items

        self._render_list(tid, items)

    # ------------------------------------------------------------------
    # Search actions & events
    # ------------------------------------------------------------------

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Check if action is enabled; disables and hides search and fullscreen bindings on sub-screens."""
        if (
            action in ("focus_search", "toggle_detail_fullscreen", "toggle_log_fullscreen")
            and len(self.screen_stack) > 1
        ):
            return False
        return True

    def action_focus_search(self) -> None:
        """Focus the search input or open select overlay if focused on a Select."""
        if isinstance(self.focused, Select):
            self.focused.action_show_overlay()
            return

        if len(self.screen_stack) > 1:
            if hasattr(self.screen, "action_focus_search"):
                self.screen.action_focus_search()
            elif hasattr(self.screen, "action_focus_filter"):
                self.screen.action_focus_filter()
            return

        try:
            tabbed_content = self.query_one(TabbedContent)
            active_tab = tabbed_content.active
            if active_tab == "tab-generate":
                self.query_one("#gen-input", TextArea).focus()
                return
            tid = "recipes"
            if active_tab == "tab-agents":
                tid = "agents"
            elif active_tab == "tab-tools":
                tid = "tools"
            self.query_one(f"#{tid}-search", TextArea).focus()
        except Exception:
            pass

    @on(TextArea.Changed, "#recipes-search")
    @on(TextArea.Changed, "#agents-search")
    @on(TextArea.Changed, "#tools-search")
    def on_search_changed(self, event: TextArea.Changed) -> None:
        """Filter resources on input change."""
        if event.text_area.id:
            tid = event.text_area.id.removesuffix("-search")
            self._render_tab(tid)

    # ------------------------------------------------------------------
    # Ask LLM (Search / Smart Actions / Generate)
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#recipes-llm-btn")
    @on(Button.Pressed, "#agents-llm-btn")
    @on(Button.Pressed, "#tools-llm-btn")
    def on_llm_search_pressed(self, event: Button.Pressed) -> None:
        """Trigger LLM-based action / semantic search on button press."""
        target_id = event.button.id
        if not target_id:
            return
        tid = target_id.removesuffix("-llm-btn")
        self._trigger_llm_search(tid)

    def _trigger_llm_search(self, tid: str) -> None:
        """Trigger Ask LLM search for the given resource tab."""
        query = self.query_one(f"#{tid}-search", TextArea).text.strip()
        if not query:
            return
        self.notify(f"🤖 [Ask LLM] Analyzing: '{query[:30]}...' with LLM", severity="information")
        items_map: dict[str, list[Any]] = {
            "recipes": self._recipes,
            "agents": self._agents,
            "tools": self._tools,
        }
        self._llm_search(tid, query, items_map.get(tid, []))

    @work(thread=True)
    def _llm_search(self, tid: str, query: str, items: list[Any]) -> None:
        """Run LLM semantic action/search in a background thread."""
        from ..api import Script

        catalogue = "\n".join(f"- {x.name}: {getattr(x, 'description', '')}" for x in items)

        if tid == "recipes":
            # Collect brief summaries of exported chat sessions
            chat_summaries: list[str] = []
            exp_dir_p = Path(self._export_dir)
            if exp_dir_p.is_dir():
                for p in sorted(exp_dir_p.glob("chat_*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                    try:
                        content_snip = p.read_text(encoding="utf-8")[:600]
                        # Extract first user message or snippet
                        chat_summaries.append(f"- File '{p.name}': {content_snip[:200].replace(chr(10), ' ')}")
                    except Exception:
                        pass
            chat_cat = "\n".join(chat_summaries) if chat_summaries else "None"
            prompt = build_recipe_action_prompt(query, catalogue, chat_cat)
        else:
            prompt = build_semantic_search_prompt(query, catalogue)

        def _log_app(msg: str, level: str = "INFO", color: str = "white") -> None:
            ts = now_datetime_str()
            formatted_entry = f"[{ts}] {level}: {msg}"
            self._app_log_buffer.append(formatted_entry)
            log_line = f"[dim]{ts}[/dim] [{color}]{msg}[/{color}]"

            def _write_all_logs() -> None:
                for widget_id in ("#app-rich-log", "#recipes-rich-log", "#agents-rich-log", "#tools-rich-log"):
                    try:
                        self.query_one(widget_id, RichLog).write(log_line)
                    except Exception:
                        pass

            self.app.call_from_thread(_write_all_logs)

        _log_app(f"LLM Search triggered for '{tid}' with query: '{query}'", "INFO", "cyan")

        script = Script(agent="native_react", prompt=prompt, tools=[])
        try:
            result = script.run(engine=self._engine, model=self._model)
            _log_app(f"LLM response received for '{tid}':\n{result.strip()}", "DEBUG", "dim")
        except Exception as exc:
            err_msg = str(exc)
            _log_app(f"LLM Search failed for '{tid}': {err_msg}", "ERROR", "bold red")

            def _on_err(err: str = err_msg) -> None:
                self.notify(f"❌ LLM request failed: {err}", severity="error")

            self.app.call_from_thread(_on_err)
            return

        if tid == "recipes":
            intent = parse_recipe_action_intent(result)
            _log_app(
                f"Parsed recipe intent: action='{intent.action}', target='{intent.target}', "
                f"file='{intent.chat_file}', gen='{intent.generate_query}'",
                "INFO",
                "yellow",
            )
            handled = self._handle_recipe_action_intent(intent, query, _log_app)
            if handled:
                return
            ranked_names = intent.ranked_names or []
        else:
            ranked_names = [line.lstrip("- ").strip() for line in result.splitlines() if line.strip()]

        _log_app(f"LLM Search returned {len(ranked_names)} matching candidates for '{tid}'.", "INFO", "green")

        name_to_item = {x.name: x for x in items}
        ranked: list[Any] = []
        for name in ranked_names:
            if name in name_to_item:
                ranked.append(name_to_item[name])

        def _update() -> None:
            self.clear_notifications()
            if tid == "recipes":
                self._displayed_recipes = ranked
            elif tid == "agents":
                self._displayed_agents = ranked
            else:
                self._displayed_tools = ranked
            self._render_list(tid, ranked)

        self.app.call_from_thread(_update)

    def _handle_recipe_action_intent(
        self,
        intent: RecipeActionIntent,
        query: str,
        log_fn: Any,
    ) -> bool:
        """Handle matched recipe action intent (generate, resume, delete, edit). Returns True if handled."""
        match intent.action:
            case "generate":
                return self._handle_intent_generate(intent.generate_query or query, log_fn)
            case "resume":
                return self._handle_intent_resume(intent.chat_file or intent.target or query, log_fn)
            case "delete" | "edit" if intent.target:
                return self._handle_intent_recipe_mutation(intent.action, intent.target, log_fn)
            case _:
                return False

    def _handle_intent_generate(self, gen_req: str, log_fn: Any) -> bool:
        """Switch to generate tab and start recipe generation worker."""
        log_fn(
            f"Intent matched recipe generation: '{gen_req}'. "
            "Switching to Generate tab and starting background generation.",
            "INFO",
            "green",
        )

        def _start_gen() -> None:
            self.clear_notifications()
            try:
                self.query_one(TabbedContent).active = "tab-generate"
                self.query_one("#gen-input", TextArea).focus()
            except Exception:
                pass

            self._gen_input_history.append(gen_req)

            status_msg = "⏳ Generating assistant recipe (you can switch tabs anytime)..."
            self.query_one("#gen-status-bar", Static).update(status_msg)
            self.query_one("#gen-submit-btn", Button).disabled = True
            self.query_one("#gen-chat-btn", Button).display = False

            ts_now = now_datetime_str()
            gen_log = self.query_one("#gen-rich-log", RichLog)
            gen_log.write(f"[dim]{ts_now}[/dim] [cyan]> Generation started from Ask LLM: '{gen_req}'[/cyan]")

            self.run_worker(
                lambda: self._execute_recipe_generation(gen_req),
                thread=True,
                name=f"recipe_gen_{gen_req[:20]}",
            )

        self.app.call_from_thread(_start_gen)
        return True

    def _handle_intent_resume(self, search_term: str, log_fn: Any) -> bool:
        """Open chat resume modal with the requested search filter."""
        log_fn(
            f"Intent matched resume chat with term: '{search_term}'. Opening session picker.",
            "INFO",
            "green",
        )

        def _open_resume() -> None:
            self.clear_notifications()
            self.push_screen(ResumeChatScreen(self._export_dir, initial_filter=search_term))

        self.app.call_from_thread(_open_resume)
        return True

    def _handle_intent_recipe_mutation(self, action: str, target: str, log_fn: Any) -> bool:
        """Find target recipe and open delete or edit screen."""
        matched_recipe = find_matching_recipe(self._recipes, target)
        if matched_recipe is not None:
            target_rec = matched_recipe
            log_fn(
                f"Intent matched {action} target: '{target_rec.name}'. Opening screen.",
                "INFO",
                "green",
            )

            def _open_action(rec: Recipe = target_rec, act: str = action) -> None:
                self.clear_notifications()
                self._selected_recipe = rec
                if act == "delete":
                    self.action_delete_recipe()
                else:
                    self.action_edit_recipe()

            self.app.call_from_thread(_open_action)
            return True

        log_fn(f"{action.capitalize()} target '{target}' not found.", "WARNING", "yellow")

        def _target_not_found(tgt: str = target, act: str = action) -> None:
            self.clear_notifications()
            self.notify(
                f"⚠️ Target recipe '{tgt}' to {act} was not found",
                severity="warning",
                timeout=6.0,
            )

        self.app.call_from_thread(_target_not_found)
        return False

    # ------------------------------------------------------------------
    # Selection & Focus events
    # ------------------------------------------------------------------

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        """Auto-select the first item if list gains focus and no item is selected yet."""
        if isinstance(event.widget, ListView):
            lv = event.widget
            if lv.id == "recipes-list" and lv.index is None and len(self._displayed_recipes) > 0:
                lv.index = 0
                self._select_recipe_by_index(0)
            elif lv.id == "agents-list" and lv.index is None and len(self._displayed_agents) > 0:
                lv.index = 0
                self._select_agent_by_index(0)
            elif lv.id == "tools-list" and lv.index is None and len(self._displayed_tools) > 0:
                lv.index = 0
                self._select_tool_by_index(0)

    def _select_recipe_by_index(self, idx: int) -> None:
        """Select recipe at index and update detail and action buttons."""
        if idx >= len(self._displayed_recipes):
            return
        r = self._displayed_recipes[idx]
        self._selected_recipe = r
        md = recipe_markdown(r)
        self.query_one("#recipes-markdown", Markdown).update(md)
        try:
            self.query_one("#recipes-chat-btn", Button).display = True
            self.query_one("#recipes-edit-btn", Button).display = True
            self.query_one("#recipes-delete-btn", Button).display = True
        except Exception:
            pass

    def _select_agent_by_index(self, idx: int) -> None:
        """Select agent at index and update detail."""
        if idx >= len(self._displayed_agents):
            return
        a = self._displayed_agents[idx]
        md = agent_markdown(a)
        self.query_one("#agents-markdown", Markdown).update(md)

    def _select_tool_by_index(self, idx: int) -> None:
        """Select tool at index and update detail."""
        if idx >= len(self._displayed_tools):
            return
        t = self._displayed_tools[idx]
        md = tool_markdown(t)
        self.query_one("#tools-markdown", Markdown).update(md)

    @on(ListView.Selected, "#recipes-list")
    @on(ListView.Highlighted, "#recipes-list")
    def on_recipe_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        """Show recipe detail on selection or highlight."""
        if event.list_view.index is not None:
            self._select_recipe_by_index(event.list_view.index)

    @on(ListView.Selected, "#agents-list")
    @on(ListView.Highlighted, "#agents-list")
    def on_agent_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        """Show agent detail on selection or highlight."""
        if event.list_view.index is not None:
            self._select_agent_by_index(event.list_view.index)

    @on(ListView.Selected, "#tools-list")
    @on(ListView.Highlighted, "#tools-list")
    def on_tool_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        """Show tool detail on selection or highlight."""
        if event.list_view.index is not None:
            self._select_tool_by_index(event.list_view.index)

    # ------------------------------------------------------------------
    # Chat Options & Launch
    # ------------------------------------------------------------------

    def _open_chat_options(self) -> None:
        """Open the chat options screen for the selected recipe."""
        if self._selected_recipe is None:
            self.notify("No recipe selected", severity="warning")
            return
        self.push_screen(
            ChatOptionsScreen(self._selected_recipe, self._engine, self._model, export_dir=self._export_dir)
        )

    @on(Button.Pressed, "#recipes-chat-btn")
    def on_chat_btn(self) -> None:
        """Launch chat options screen via button."""
        self._open_chat_options()

    def action_chat_recipe(self) -> None:
        """Launch chat options screen or start chat if already on ChatOptionsScreen."""
        if len(self.screen_stack) > 1:
            if hasattr(self.screen, "action_start_chat"):
                self.screen.action_start_chat()
            return
        self._open_chat_options()

    def action_resume_chat(self) -> None:
        """Open the resume chat session modal."""
        self.push_screen(ResumeChatScreen(self._export_dir))

    # ------------------------------------------------------------------
    # Recipe Editing & Deletion
    # ------------------------------------------------------------------

    def action_edit_recipe(self) -> None:
        """Prompt to edit selected recipe via key binding or button."""
        if self._selected_recipe is None:
            self.notify("No recipe selected to edit", severity="warning")
            return

        recipe_name = self._selected_recipe.name
        matched_files = find_recipe_files(recipe_name, self._recipes_dir)

        if not matched_files:
            self.notify(
                f"No recipe file found in '{self._recipes_dir}' for '{recipe_name}'",
                severity="warning",
            )
            return

        def _on_edit_done(saved: bool | None) -> None:
            if saved:
                self.notify(f"Recipe '{recipe_name}' updated successfully", severity="information")
                self._load_recipes()

        self.push_screen(
            EditRecipeScreen(recipe_name, matched_files),
            _on_edit_done,
        )

    @on(Button.Pressed, "#recipes-edit-btn")
    def on_edit_btn(self) -> None:
        """Handle edit button in recipes tab."""
        self.action_edit_recipe()

    def action_delete_recipe(self) -> None:
        """Prompt to delete selected recipe via key binding or button."""
        if self._selected_recipe is None:
            self.notify("No recipe selected to delete", severity="warning")
            return

        recipe_name = self._selected_recipe.name
        matched_files = find_recipe_files(recipe_name, self._recipes_dir)

        if not matched_files:
            self.notify(
                f"No recipe file found in '{self._recipes_dir}' for '{recipe_name}'",
                severity="warning",
            )
            return

        def _on_delete_done(deleted: bool | None) -> None:
            if deleted:
                self.notify(f"Deleted recipe: {recipe_name}", severity="information")
                self._load_recipes()

        self.push_screen(
            DeleteRecipeScreen(recipe_name, matched_files),
            _on_delete_done,
        )

    @on(Button.Pressed, "#recipes-delete-btn")
    def on_delete_btn(self) -> None:
        """Handle delete button in recipes tab."""
        self.action_delete_recipe()

    # ------------------------------------------------------------------
    # Help Modal
    # ------------------------------------------------------------------

    def action_open_help(self) -> None:
        """Open the comprehensive keyboard shortcuts help modal."""
        self.push_screen(HelpScreen())

    # ------------------------------------------------------------------
    # Generate Tab Events & Execution
    # ------------------------------------------------------------------

    def action_open_generate(self) -> None:
        """Switch to the Generate tab and focus the input field."""
        try:
            self.query_one(TabbedContent).active = "tab-generate"
            self.query_one("#gen-input", TextArea).focus()
        except Exception:
            pass

    def on_key(self, event: events.Key) -> None:
        """Handle key events for Generate tab and search input (submission & history)."""
        # Handle search bar submission via Ctrl+J / Ctrl+Enter / Ctrl+S
        for tid in ("recipes", "agents", "tools"):
            try:
                search_ta = self.query_one(f"#{tid}-search", TextArea)
                if search_ta.has_focus and event.key in ("ctrl+j", "ctrl+enter", "ctrl+s"):
                    event.prevent_default()
                    event.stop()
                    self._trigger_llm_search(tid)
                    return
            except Exception:
                pass

        # Handle Generate tab input
        try:
            inp = self.query_one("#gen-input", TextArea)
        except Exception:
            return

        if not inp.has_focus:
            return

        if event.key in ("ctrl+j", "ctrl+enter", "ctrl+s"):
            event.prevent_default()
            event.stop()
            self.on_gen_submit()
            return

        if not self._gen_input_history.entries:
            return

        if event.key == "up" and inp.cursor_location[0] == 0:
            val = self._gen_input_history.previous(inp.text)
            if val is not None:
                event.prevent_default()
                event.stop()
                inp.load_text(val)
                inp.move_cursor((inp.document.line_count - 1, len(inp.document.lines[-1])))

        elif event.key == "down" and inp.cursor_location[0] == inp.document.line_count - 1:
            val = self._gen_input_history.next()
            if val is not None:
                event.prevent_default()
                event.stop()
                inp.load_text(val)
                inp.move_cursor((inp.document.line_count - 1, len(inp.document.lines[-1])))

    @on(Button.Pressed, "#gen-submit-btn")
    def on_gen_submit(self) -> None:
        """Start recipe generation in a background worker."""
        inp = self.query_one("#gen-input", TextArea)
        query = inp.text.strip()
        if not query:
            return
        inp.clear()
        self._gen_input_history.append(query)

        status_msg = "⏳ Generating assistant recipe (you can switch tabs anytime)..."
        self.query_one("#gen-status-bar", Static).update(status_msg)
        self.query_one("#gen-submit-btn", Button).disabled = True
        self.query_one("#gen-chat-btn", Button).display = False

        ts = now_datetime_str()
        log = self.query_one("#gen-rich-log", RichLog)
        log.write(f"[dim]{ts}[/dim] [cyan]> Generation started: '{query}'[/cyan]")

        self.run_worker(
            lambda: self._execute_recipe_generation(query),
            thread=True,
            name=f"recipe_gen_{query[:20]}",
        )

    def _execute_recipe_generation(self, query: str) -> None:
        """Run recipe generation in background worker."""
        log = self.query_one("#gen-rich-log", RichLog)
        req = GenRequest(engine=self._engine, model=self._model, query=query, recipes_dir=self._recipes_dir)
        try:
            r = generate_assistant(req)
        except Exception as e:
            err_msg = str(e)

            def _on_exc() -> None:
                ts_err = now_datetime_str()
                try:
                    self.query_one("#gen-status-bar", Static).update(f"❌ Error: {err_msg}")
                    self.query_one("#gen-submit-btn", Button).disabled = False
                    log.write(f"[dim]{ts_err}[/dim] [bold red]✗ Generation error: {err_msg}[/bold red]")
                except Exception:
                    pass
                self.notify(f"Generation error: {err_msg}", severity="error")

            self.call_from_thread(_on_exc)
            return

        if r.success:
            self._last_generated_recipe = r.name
            preview_md = (
                f"# ✅ Recipe Generated: `{r.name}`\n\n"
                f"- **Saved to**: `{r.path}`\n\n"
                "### Recipe TOML Content:\n"
                "```toml\n"
            )
            try:
                content = Path(r.path).read_text(encoding="utf-8")
                preview_md += content
            except Exception:
                preview_md += "# (Could not read generated file content)"
            preview_md += "\n```\n"

            def _on_success() -> None:
                ts_ok = now_datetime_str()
                try:
                    self.query_one("#gen-markdown", Markdown).update(preview_md)
                    self.query_one("#gen-status-bar", Static).update(f"✅ Generated `{r.name}` successfully!")
                    self.query_one("#gen-submit-btn", Button).disabled = False
                    self.query_one("#gen-chat-btn", Button).display = True
                    log.write(f"[dim]{ts_ok}[/dim] [bold green]✓ Successfully generated recipe: {r.name}[/bold green]")
                except Exception:
                    pass
                self.notify(f"Recipe generated: {r.name}", severity="information")
                self._load_recipes()

            self.call_from_thread(_on_success)
        else:

            def _on_failure() -> None:
                ts_fail = now_datetime_str()
                try:
                    self.query_one("#gen-status-bar", Static).update(f"❌ Failed: {r.message}")
                    self.query_one("#gen-submit-btn", Button).disabled = False
                    log.write(f"[dim]{ts_fail}[/dim] [bold red]✗ Generation failed: {r.message}[/bold red]")
                except Exception:
                    pass
                self.notify(f"Generation failed: {r.message}", severity="error")

            self.call_from_thread(_on_failure)

    @on(Button.Pressed, "#gen-chat-btn")
    def on_gen_chat_btn(self) -> None:
        """Launch chat options with the newly generated recipe."""
        if not self._last_generated_recipe:
            return
        for r in self._recipes:
            if r.name == self._last_generated_recipe:
                self.push_screen(ChatOptionsScreen(r, self._engine, self._model, export_dir=self._export_dir))
                return

        # Fallback: discover from recipes_dir
        matched_files = find_recipe_files(self._last_generated_recipe, self._recipes_dir)
        if matched_files:
            try:
                import tomllib

                with open(matched_files[0], "rb") as f:
                    data = tomllib.load(f)
                r_dict = data.get("recipe", {})
                rec = Recipe(
                    name=r_dict.get("name", self._last_generated_recipe),
                    description=r_dict.get("description", ""),
                    system_prompt=r_dict.get("system", ""),
                    engine_key=r_dict.get("engine", self._engine),
                    model=r_dict.get("model", self._model),
                    agent_type=r_dict.get("agent", "native_react"),
                    tools=r_dict.get("tools", []),
                )
                self.push_screen(ChatOptionsScreen(rec, self._engine, self._model, export_dir=self._export_dir))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # App Log Tab Actions
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#app-log-clear-btn")
    def on_clear_app_logs(self) -> None:
        """Clear the application log buffer and all log widgets."""
        self._app_log_buffer.clear()
        for widget_id in ("#app-rich-log", "#recipes-rich-log", "#agents-rich-log", "#tools-rich-log"):
            try:
                self.query_one(widget_id, RichLog).clear()
            except Exception:
                pass
        self.notify("Application logs cleared", severity="information")

    @on(Button.Pressed, "#app-log-export-btn")
    def on_export_app_logs(self) -> None:
        """Export application logs to a file."""
        if not self._app_log_buffer:
            self.notify("Application log buffer is empty", severity="warning")
            return

        out_dir = Path(self._export_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"app_logs_{now_str()}.log"
            filepath = out_dir / filename
            filepath.write_text("\n".join(self._app_log_buffer), encoding="utf-8")
            self.notify(f"App logs exported to: {filepath}", severity="information")
        except Exception as e:
            self.notify(f"Failed to export app logs: {e}", severity="error")

    # ------------------------------------------------------------------
    # Fullscreen / Maximize Actions
    # ------------------------------------------------------------------

    def action_handle_escape(self) -> None:
        """Handle Escape key; delegates to pushed screen or restores fullscreen / unfocuses input."""
        if len(self.screen_stack) > 1:
            active_screen = self.screen
            if hasattr(active_screen, "action_handle_escape"):
                active_screen.action_handle_escape()
            elif hasattr(active_screen, "action_dismiss_screen"):
                active_screen.action_dismiss_screen()
            elif hasattr(active_screen, "action_dismiss_help"):
                active_screen.action_dismiss_help()
            elif hasattr(active_screen, "action_cancel"):
                active_screen.action_cancel()
            elif hasattr(active_screen, "action_dismiss_cancel"):
                active_screen.action_dismiss_cancel()
            elif hasattr(active_screen, "dismiss"):
                active_screen.dismiss()
            return

        if self._maximized_pane is not None:
            self._restore_fullscreen()
            return
        focused = self.focused
        if focused and isinstance(focused, TextArea):
            self.set_focus(None)

    def action_toggle_detail_fullscreen(self) -> None:
        """Toggle fullscreen for detail or preview pane."""
        if len(self.screen_stack) > 1:
            if hasattr(self.screen, "action_toggle_messages_fullscreen"):
                self.screen.action_toggle_messages_fullscreen()
            return

        try:
            tabbed_content = self.query_one(TabbedContent)
            active_tab = tabbed_content.active
        except Exception:
            return

        if active_tab in ("tab-recipes", "tab-agents", "tab-tools"):
            tid = active_tab.removeprefix("tab-")
            if self._maximized_pane == f"{tid}-detail":
                self._restore_fullscreen()
            else:
                self._maximize_resource_detail(tid)

        elif active_tab == "tab-generate":
            if self._maximized_pane == "gen-preview":
                self._restore_fullscreen()
            else:
                self._maximize_gen_preview()

    def action_toggle_log_fullscreen(self) -> None:
        """Toggle fullscreen for logs pane."""
        if len(self.screen_stack) > 1:
            if hasattr(self.screen, "action_toggle_log_fullscreen"):
                self.screen.action_toggle_log_fullscreen()
            return

        try:
            tabbed_content = self.query_one(TabbedContent)
            active_tab = tabbed_content.active
        except Exception:
            return

        if active_tab in ("tab-recipes", "tab-agents", "tab-tools"):
            tid = active_tab.removeprefix("tab-")
            if self._maximized_pane == f"{tid}-log":
                self._restore_fullscreen()
            else:
                self._maximize_resource_log(tid)

        elif active_tab == "tab-generate":
            if self._maximized_pane == "gen-log":
                self._restore_fullscreen()
            else:
                self._maximize_gen_log()

        elif active_tab == "tab-logs":
            if self._maximized_pane == "app-log":
                self._restore_fullscreen()
            else:
                self._maximize_app_log()

    def action_toggle_prompt_fullscreen(self) -> None:
        """Toggle fullscreen for prompt pane on active screen."""
        if len(self.screen_stack) > 1:
            if hasattr(self.screen, "action_toggle_prompt_fullscreen"):
                self.screen.action_toggle_prompt_fullscreen()

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self) -> None:
        """Restore normal layout when switching tabs."""
        if self._maximized_pane is not None:
            self._restore_fullscreen(notify=False)

    def _maximize_resource_detail(self, tid: str) -> None:
        """Maximize detail pane in resource tab."""
        self._restore_fullscreen(notify=False)
        try:
            self.query_one(f"#{tid}-body").add_class("maximized-detail")
            self.query_one(f"#{tid}-toolbar").add_class("pane-hidden")
            self._maximized_pane = f"{tid}-detail"
            self.notify(f"Maximized {tid.capitalize()} Details (press 'm' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def _maximize_resource_log(self, tid: str) -> None:
        """Maximize log pane in resource tab."""
        self._restore_fullscreen(notify=False)
        try:
            self.query_one(f"#{tid}-body").add_class("maximized-log")
            self.query_one(f"#{tid}-toolbar").add_class("pane-hidden")
            self._maximized_pane = f"{tid}-log"
            self.notify(f"Maximized {tid.capitalize()} Logs (press 'l' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def _maximize_gen_preview(self) -> None:
        """Maximize preview pane in generate tab."""
        self._restore_fullscreen(notify=False)
        try:
            self.query_one("#gen-screen-layout").add_class("maximized-preview")
            self._maximized_pane = "gen-preview"
            self.notify("Maximized Recipe Preview (press 'm' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def _maximize_gen_log(self) -> None:
        """Maximize log pane in generate tab."""
        self._restore_fullscreen(notify=False)
        try:
            self.query_one("#gen-screen-layout").add_class("maximized-log")
            self._maximized_pane = "gen-log"
            self.notify("Maximized Generation Logs (press 'l' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def _maximize_app_log(self) -> None:
        """Maximize application log tab."""
        self._restore_fullscreen(notify=False)
        try:
            self.query_one(LogTab).add_class("maximized-log")
            self._maximized_pane = "app-log"
            self.notify("Maximized Application Logs (press 'l' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def _restore_fullscreen(self, notify: bool = True) -> None:
        """Restore all tabs and panes to normal layout."""
        if self._maximized_pane is None:
            return
        for tid in ("recipes", "agents", "tools"):
            try:
                self.query_one(f"#{tid}-body").remove_class("maximized-detail", "maximized-log")
                self.query_one(f"#{tid}-toolbar").remove_class("pane-hidden")
            except Exception:
                pass
        try:
            self.query_one("#gen-screen-layout").remove_class("maximized-preview", "maximized-log")
        except Exception:
            pass
        try:
            self.query_one(LogTab).remove_class("maximized-log")
        except Exception:
            pass
        self._maximized_pane = None
        if notify:
            self.notify("Restored normal view", timeout=2.0)

    @on(Button.Pressed, "#recipes-detail-max-btn")
    @on(Button.Pressed, "#agents-detail-max-btn")
    @on(Button.Pressed, "#tools-detail-max-btn")
    def on_resource_detail_max(self, event: Button.Pressed) -> None:
        """Handle detail pane maximize button."""
        if event.button.id:
            tid = event.button.id.removesuffix("-detail-max-btn")
            if self._maximized_pane == f"{tid}-detail":
                self._restore_fullscreen()
            else:
                self._maximize_resource_detail(tid)

    @on(Button.Pressed, "#recipes-log-max-btn")
    @on(Button.Pressed, "#agents-log-max-btn")
    @on(Button.Pressed, "#tools-log-max-btn")
    def on_resource_log_max(self, event: Button.Pressed) -> None:
        """Handle log pane maximize button."""
        if event.button.id:
            tid = event.button.id.removesuffix("-log-max-btn")
            if self._maximized_pane == f"{tid}-log":
                self._restore_fullscreen()
            else:
                self._maximize_resource_log(tid)

    @on(Button.Pressed, "#gen-preview-max-btn")
    def on_gen_preview_max(self) -> None:
        """Handle generate preview maximize button."""
        if self._maximized_pane == "gen-preview":
            self._restore_fullscreen()
        else:
            self._maximize_gen_preview()

    @on(Button.Pressed, "#gen-log-max-btn")
    def on_gen_log_max(self) -> None:
        """Handle generate log maximize button."""
        if self._maximized_pane == "gen-log":
            self._restore_fullscreen()
        else:
            self._maximize_gen_log()

    @on(Button.Pressed, "#app-log-max-btn")
    def on_app_log_max(self) -> None:
        """Handle application log maximize button."""
        if self._maximized_pane == "app-log":
            self._restore_fullscreen()
        else:
            self._maximize_app_log()


def run_tui(engine: str, model: str, recipes_dir: str, export_dir: str | None = None) -> None:
    """Launch the TUI application."""
    import logging

    # Remove stream handlers to prevent stdout/stderr leakage onto Textual canvas
    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        if isinstance(h, logging.StreamHandler):
            root_logger.removeHandler(h)

    app = MetaAgentTUI(engine=engine, model=model, recipes_dir=recipes_dir, export_dir=export_dir)
    app.run()
