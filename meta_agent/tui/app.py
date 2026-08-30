"""MetaAgentTUI application and main event loop."""

import logging
from pathlib import Path
from typing import Any, ClassVar

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    Button,
    Header,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Markdown,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from ..api import (
    Agent,
    Engine,
    find_recipe_files,
    list_agents,
    list_engines,
    list_models,
    list_recipes,
    list_tools,
    Model,
    Recipe,
    Script,
    Tool,
)
from ..utils import get_default_export_dir, now_str
from .fullscreen import FullscreenManager
from .generation import RecipeGenerator
from .helpers import (
    agent_markdown,
    engine_markdown,
    filter_items,
    InputHistory,
    model_markdown,
    now_datetime_str,
    recipe_markdown,
    tool_markdown,
)
from .intent import (
    build_recipe_action_prompt,
    build_semantic_search_prompt,
    IntentDispatcher,
    parse_recipe_action_intent,
    RecipeActionIntent,
)
from .screens import ChatOptionsScreen, DeleteRecipeScreen, EditRecipeScreen, HelpScreen, ResumeChatScreen
from .screens.chat import RichLogHandler
from .styles import APP_CSS
from .widgets import GenerateTab, LogTab, OrderedFooter, ResourceTab


class MetaAgentTUI(App[None]):
    """TUI application for meta_agent."""

    CSS = APP_CSS
    ALLOW_SELECT: ClassVar[bool] = False

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+h", "open_help", "Help (Ctrl+H)", show=True, priority=True),
        Binding("question_mark", "open_help", "Help (?)", show=False, priority=False),
        Binding("f1", "open_help", "Help", show=False, priority=True),
        Binding("ctrl+f", "focus_search", "Search (Ctrl+F)", show=True, priority=False),
        Binding("ctrl+c", "chat_recipe", "Chat (Ctrl+C)", show=True, priority=False),
        Binding("ctrl+g", "open_generate", "Generate (Ctrl+G)", show=True, priority=True),
        Binding("ctrl+left", "previous_tab", "Prev Tab (Ctrl+Left)", show=False, priority=True),
        Binding("ctrl+right", "next_tab", "Next Tab (Ctrl+Right)", show=False, priority=True),
        Binding("ctrl+left_square_bracket", "previous_tab", "Prev Tab (Ctrl+[)", show=False, priority=True),
        Binding("ctrl+right_square_bracket", "next_tab", "Next Tab (Ctrl+])", show=False, priority=True),
        Binding("ctrl+q", "quit", "Quit (Ctrl+Q)", show=True, priority=True),
        Binding("ctrl+o", "toggle_detail_fullscreen", "Detail Max (Ctrl+O)", show=False, priority=True),
        Binding("ctrl+l", "toggle_log_fullscreen", "Logs Max (Ctrl+L)", show=False, priority=True),
        Binding("ctrl+r", "resume_chat", "Resume (Ctrl+R)", show=False, priority=True),
        Binding("ctrl+e", "edit_recipe", "Edit (Ctrl+E)", show=False, priority=False),
        Binding("ctrl+d", "delete_recipe", "Delete (Ctrl+D)", show=False, priority=False),
        Binding("ctrl+p", "toggle_prompt_fullscreen", show=False, priority=True),
        Binding("escape", "handle_escape", "Back (Esc)", show=False, priority=False),
    ]

    def __init__(
        self,
        engine: str,
        model: str,
        recipes_dir: str,
        export_dir: str | None = None,
        auto_load: bool = True,
        initial_tab: str = "tab-recipes",
    ) -> None:
        """Initialize the TUI with LLM settings and export directory."""
        super().__init__()
        self._engine = engine
        self._model = model
        self._recipes_dir = recipes_dir
        self._export_dir = export_dir or get_default_export_dir()
        self._auto_load = auto_load
        self._initial_tab = initial_tab
        self._recipes: list[Recipe] = []
        self._agents: list[Agent] = []
        self._tools: list[Tool] = []
        self._engines: list[Engine] = []
        self._models: list[Model] = []
        self._selected_recipe: Recipe | None = None
        self._selected_agent: Agent | None = None
        self._selected_tool: Tool | None = None
        self._selected_engine: Engine | None = None
        self._selected_model: Model | None = None
        self._last_generated_recipe: str | None = None
        self._app_log_buffer: list[str] = []
        self._app_log_handler: RichLogHandler | None = None
        self._gen_input_history = InputHistory()
        self._last_ctrl_c: float = 0.0
        self._displayed_recipes: list[Recipe] = []
        self._displayed_agents: list[Agent] = []
        self._displayed_tools: list[Tool] = []
        self._displayed_engines: list[Engine] = []
        self._displayed_models: list[Model] = []

        # Sub-managers
        self._fullscreen = FullscreenManager(self)
        self._intent_dispatcher = IntentDispatcher(self)
        self._recipe_generator = RecipeGenerator(self)

    @property
    def _maximized_pane(self) -> str | None:
        """Return the currently maximized pane ID."""
        return self._fullscreen.maximized_pane

    @_maximized_pane.setter
    def _maximized_pane(self, value: str | None) -> None:
        """Set the currently maximized pane ID."""
        self._fullscreen.maximized_pane = value

    def compose(self) -> ComposeResult:
        """Build the main TUI layout."""
        yield Header()
        with TabbedContent(initial=self._initial_tab):
            with TabPane("Recipes", id="tab-recipes"):
                yield ResourceTab("recipes", show_chat=True)
            with TabPane("Agents", id="tab-agents"):
                yield ResourceTab("agents")
            with TabPane("Tools", id="tab-tools"):
                yield ResourceTab("tools")
            with TabPane("Engines", id="tab-engines"):
                yield ResourceTab("engines")
            with TabPane("Models", id="tab-models"):
                yield ResourceTab("models")
            with TabPane("Generate", id="tab-generate"):
                yield GenerateTab(self._engine, self._model, self._recipes_dir)
            with TabPane("Logs", id="tab-logs"):
                yield LogTab()
        yield OrderedFooter()

    def on_mount(self) -> None:
        """Load all resources after mounting and attach app log handler."""
        try:
            log_widget = self.query_one("#app-rich-log", RichLog)
            self._app_log_handler = RichLogHandler(log_widget, self._app_log_buffer)
            # Scope to "meta_agent" logger to avoid deadlock and intercepting pytest/asyncio root logs
            logging.getLogger("meta_agent").addHandler(self._app_log_handler)
            init_msg = f"Application initialized. Engine='{self._engine}', Model='{self._model}'"
            log_widget.write(f"[green]{init_msg}[/green]")
            for tid in ("recipes", "agents", "tools", "engines", "models"):
                try:
                    self.query_one(f"#{tid}-rich-log", RichLog).write(f"[green]{init_msg}[/green]")
                except Exception:
                    pass
            self._app_log_buffer.append(f"[{now_datetime_str()}] INFO: app - {init_msg}")
        except Exception:
            pass

        if self._auto_load:
            self._load_recipes()
            self._load_agents()
            self._load_tools()
            self._load_engines()
            self._load_models()
        else:
            for tid in ("recipes", "agents", "tools", "engines", "models"):
                try:
                    self.query_one(f"#{tid}-loading", LoadingIndicator).display = False
                except Exception:
                    pass
        try:
            self.query_one("#gen-chat-btn", Button).display = False
        except Exception:
            pass
        try:
            self.query_one("#recipes-search", TextArea).focus()
        except Exception:
            pass

    def on_unmount(self) -> None:
        """Clean up app logging handler on exit."""
        if hasattr(self, "_app_log_handler") and self._app_log_handler is not None:
            logging.getLogger("meta_agent").removeHandler(self._app_log_handler)
            self._app_log_handler = None

    # ------------------------------------------------------------------
    # Resource Loading & Rendering
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
        elif tid == "engines":
            self._engines = list_engines(default_engine=self._engine)
        elif tid == "models":
            self._models = list_models(engine=self._engine)
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

    def _load_engines(self) -> None:
        """Trigger background loading of engines."""
        self._load_resource("engines")

    def _load_models(self) -> None:
        """Trigger background loading of models."""
        self._load_resource("models")

    def _render_list(self, tid: str, items: list[Any]) -> None:
        """Populate ListView with resource items."""
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
            "engines": self._engines,
            "models": self._models,
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
        elif tid == "engines":
            self._displayed_engines = items
        elif tid == "models":
            self._displayed_models = items

        self._render_list(tid, items)

    # ------------------------------------------------------------------
    # Search & LLM Intent Handler
    # ------------------------------------------------------------------

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Enable focus_search action for key binding routing."""
        if action == "focus_search":
            return True
        return super().check_action(action, parameters)

    def action_focus_search(self) -> None:
        """Focus the search input on the currently active tab."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            active_tab = tabbed_content.active
        except Exception:
            return

        if active_tab == "tab-recipes":
            self.query_one("#recipes-search", TextArea).focus()
        elif active_tab == "tab-agents":
            self.query_one("#agents-search", TextArea).focus()
        elif active_tab == "tab-tools":
            self.query_one("#tools-search", TextArea).focus()
        elif active_tab == "tab-engines":
            self.query_one("#engines-search", TextArea).focus()
        elif active_tab == "tab-models":
            self.query_one("#models-search", TextArea).focus()
        elif active_tab == "tab-generate":
            self.query_one("#gen-input", TextArea).focus()

    @on(TextArea.Changed, "#recipes-search")
    @on(TextArea.Changed, "#agents-search")
    @on(TextArea.Changed, "#tools-search")
    @on(TextArea.Changed, "#engines-search")
    @on(TextArea.Changed, "#models-search")
    def on_search_changed(self, event: TextArea.Changed) -> None:
        """Live-filter resource list as user types in search TextArea."""
        if event.text_area.id:
            tid = event.text_area.id.removesuffix("-search")
            self._render_tab(tid)

    @on(Button.Pressed, "#recipes-llm-btn")
    @on(Button.Pressed, "#agents-llm-btn")
    @on(Button.Pressed, "#tools-llm-btn")
    @on(Button.Pressed, "#engines-llm-btn")
    @on(Button.Pressed, "#models-llm-btn")
    def on_llm_search_pressed(self, event: Button.Pressed) -> None:
        """Trigger Ask LLM semantic search."""
        if event.button.id:
            tid = event.button.id.removesuffix("-llm-btn")
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
            "engines": self._engines,
            "models": self._models,
        }
        self._llm_search(tid, query, items_map.get(tid, []))

    @work(thread=True)
    def _llm_search(self, tid: str, query: str, items: list[Any]) -> None:
        """Run LLM semantic action/search in a background thread."""
        catalogue = "\n".join(f"- {x.name}: {getattr(x, 'description', '')}" for x in items)

        if tid == "recipes":
            chat_summaries: list[str] = []
            exp_dir_p = Path(self._export_dir)
            if exp_dir_p.is_dir():
                for p in sorted(exp_dir_p.glob("chat_*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                    try:
                        content_snip = p.read_text(encoding="utf-8")[:600]
                        chat_summaries.append(f"- File '{p.name}': {content_snip[:200].replace(chr(10), ' ')}")
                    except Exception:
                        pass
            chat_cat = "\n".join(chat_summaries) if chat_summaries else "None"
            prompt = build_recipe_action_prompt(query, catalogue, chat_cat)
        else:
            prompt = build_semantic_search_prompt(query, catalogue)

        def _log_app(msg: str, level: str = "INFO", color: str = "white") -> None:
            ts = now_datetime_str()
            self._app_log_buffer.append(f"[{ts}] {level}: {msg}")
            log_line = f"[dim]{ts}[/dim] [{color}]{msg}[/{color}]"

            def _write_all_logs() -> None:
                for widget_id in (
                    "#app-rich-log",
                    "#recipes-rich-log",
                    "#agents-rich-log",
                    "#tools-rich-log",
                    "#engines-rich-log",
                    "#models-rich-log",
                ):
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
            self.app.call_from_thread(lambda: self.notify(f"❌ LLM request failed: {err_msg}", severity="error"))
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
        ranked: list[Any] = [name_to_item[name] for name in ranked_names if name in name_to_item]

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

    def _handle_recipe_action_intent(self, intent: RecipeActionIntent, query: str, log_fn: Any) -> bool:
        """Handle matched recipe action intent."""
        return self._intent_dispatcher.handle_recipe_action_intent(intent, query, log_fn)

    def _handle_intent_generate(self, gen_req: str, log_fn: Any) -> bool:
        """Switch to generate tab and start recipe generation."""
        return self._intent_dispatcher.handle_intent_generate(gen_req, log_fn)

    def _handle_intent_resume(self, search_term: str, log_fn: Any) -> bool:
        """Open chat resume modal."""
        return self._intent_dispatcher.handle_intent_resume(search_term, log_fn)

    def _handle_intent_recipe_mutation(self, action: str, target: str, log_fn: Any) -> bool:
        """Find target recipe and open delete or edit screen."""
        return self._intent_dispatcher.handle_intent_recipe_mutation(action, target, log_fn)

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
            elif lv.id == "engines-list" and lv.index is None and len(self._displayed_engines) > 0:
                lv.index = 0
                self._select_engine_by_index(0)
            elif lv.id == "models-list" and lv.index is None and len(self._displayed_models) > 0:
                lv.index = 0
                self._select_model_by_index(0)

    def _select_recipe_by_index(self, index: int) -> None:
        if 0 <= index < len(self._displayed_recipes):
            self._selected_recipe = self._displayed_recipes[index]
            md = recipe_markdown(self._selected_recipe)
            self.query_one("#recipes-markdown", Markdown).update(md)
            self.query_one("#recipes-chat-btn", Button).display = True
            self.query_one("#recipes-edit-btn", Button).display = True
            self.query_one("#recipes-delete-btn", Button).display = True

    def _select_agent_by_index(self, index: int) -> None:
        if 0 <= index < len(self._displayed_agents):
            self._selected_agent = self._displayed_agents[index]
            md = agent_markdown(self._selected_agent)
            self.query_one("#agents-markdown", Markdown).update(md)

    def _select_tool_by_index(self, index: int) -> None:
        if 0 <= index < len(self._displayed_tools):
            self._selected_tool = self._displayed_tools[index]
            md = tool_markdown(self._selected_tool)
            self.query_one("#tools-markdown", Markdown).update(md)

    def _select_engine_by_index(self, index: int) -> None:
        if 0 <= index < len(self._displayed_engines):
            self._selected_engine = self._displayed_engines[index]
            md = engine_markdown(self._selected_engine)
            self.query_one("#engines-markdown", Markdown).update(md)

    def _select_model_by_index(self, index: int) -> None:
        if 0 <= index < len(self._displayed_models):
            self._selected_model = self._displayed_models[index]
            md = model_markdown(self._selected_model)
            self.query_one("#models-markdown", Markdown).update(md)

    @on(ListView.Selected, "#recipes-list")
    @on(ListView.Highlighted, "#recipes-list")
    def on_recipe_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        """Render markdown details and show action buttons for selected recipe."""
        if event.list_view.index is not None:
            self._select_recipe_by_index(event.list_view.index)

    @on(ListView.Selected, "#agents-list")
    @on(ListView.Highlighted, "#agents-list")
    def on_agent_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        """Render markdown details for selected agent."""
        if event.list_view.index is not None:
            self._select_agent_by_index(event.list_view.index)

    @on(ListView.Selected, "#tools-list")
    @on(ListView.Highlighted, "#tools-list")
    def on_tool_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        """Render markdown details for selected tool."""
        if event.list_view.index is not None:
            self._select_tool_by_index(event.list_view.index)

    @on(ListView.Selected, "#engines-list")
    @on(ListView.Highlighted, "#engines-list")
    def on_engine_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        """Render markdown details for selected engine."""
        if event.list_view.index is not None:
            self._select_engine_by_index(event.list_view.index)

    @on(ListView.Selected, "#models-list")
    @on(ListView.Highlighted, "#models-list")
    def on_model_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        """Render markdown details for selected model."""
        if event.list_view.index is not None:
            self._select_model_by_index(event.list_view.index)

    # ------------------------------------------------------------------
    # Recipe Actions & Modals
    # ------------------------------------------------------------------

    def _open_chat_options(self, recipe: Recipe) -> None:
        """Push ChatOptionsScreen to review and start chat."""
        self.push_screen(
            ChatOptionsScreen(
                recipe,
                self._engine,
                self._model,
                export_dir=self._export_dir,
            )
        )

    @on(Button.Pressed, "#recipes-chat-btn")
    def on_chat_btn(self) -> None:
        """Handle chat button on recipes tab."""
        self.action_chat_recipe()

    def action_chat_recipe(self) -> None:
        """Open chat options for the currently selected recipe."""
        if self._selected_recipe is not None:
            self._open_chat_options(self._selected_recipe)
        else:
            self.notify("Please select a recipe first", severity="warning")

    def action_handle_ctrl_c(self) -> None:
        """Handle Ctrl+C: first press warns, second press within timeout quits."""
        import time

        now = time.monotonic()
        if now - self._last_ctrl_c < 2.0:
            self.exit()
        else:
            self._last_ctrl_c = now
            self.notify("Press Ctrl+C again to quit", severity="warning", timeout=2.0)

    def action_resume_chat(self) -> None:
        """Open session picker modal to resume previous chat session."""
        self.push_screen(ResumeChatScreen(self._export_dir))

    def action_edit_recipe(self) -> None:
        """Open editor screen for currently selected recipe."""
        if self._selected_recipe is None:
            self.notify("Please select a recipe first", severity="warning")
            return

        recipe_name = self._selected_recipe.name
        matched_files = find_recipe_files(recipe_name, self._recipes_dir)

        def _on_edit_done(saved: bool | None) -> None:
            if saved:
                self.notify(f"Recipe '{recipe_name}' updated", severity="information")
                self._load_recipes()

        self.push_screen(
            EditRecipeScreen(recipe_name, matched_files),
            _on_edit_done,
        )

    @on(Button.Pressed, "#recipes-edit-btn")
    def on_edit_btn(self) -> None:
        """Handle edit button on recipes tab."""
        self.action_edit_recipe()

    def action_delete_recipe(self) -> None:
        """Prompt to delete selected recipe via key binding or button."""
        if self._selected_recipe is None:
            self.notify("Please select a recipe first", severity="warning")
            return

        recipe_name = self._selected_recipe.name
        matched_files = find_recipe_files(recipe_name, self._recipes_dir)

        def _on_delete_done(deleted: bool | None) -> None:
            if deleted:
                self.notify(f"Recipe '{recipe_name}' deleted", severity="information")
                self._load_recipes()

        self.push_screen(
            DeleteRecipeScreen(recipe_name, matched_files),
            _on_delete_done,
        )

    @on(Button.Pressed, "#recipes-delete-btn")
    def on_delete_btn(self) -> None:
        """Handle delete button on recipes tab."""
        self.action_delete_recipe()

    def action_open_help(self) -> None:
        """Display the help and keyboard shortcuts modal."""
        self.push_screen(HelpScreen())

    def action_open_generate(self) -> None:
        """Switch to GenerateTab and focus input prompt."""
        try:
            self._fullscreen.restore_fullscreen()
            self.query_one(TabbedContent).active = "tab-generate"
            self.query_one("#gen-input", TextArea).focus()
        except Exception:
            pass

    def action_previous_tab(self) -> None:
        """Switch to previous tab (wraps around)."""
        tabs_order = [
            "tab-recipes",
            "tab-agents",
            "tab-tools",
            "tab-engines",
            "tab-models",
            "tab-generate",
            "tab-logs",
        ]
        try:
            tabbed_content = self.query_one(TabbedContent)
            current = tabbed_content.active
            if current in tabs_order:
                idx = tabs_order.index(current)
                prev_idx = (idx - 1) % len(tabs_order)
                target_tab = tabs_order[prev_idx]
                self.set_focus(None)
                tabbed_content.active = target_tab
                self._focus_tab_search(target_tab)
        except Exception:
            pass

    def action_next_tab(self) -> None:
        """Switch to next tab (wraps around)."""
        tabs_order = [
            "tab-recipes",
            "tab-agents",
            "tab-tools",
            "tab-engines",
            "tab-models",
            "tab-generate",
            "tab-logs",
        ]
        try:
            tabbed_content = self.query_one(TabbedContent)
            current = tabbed_content.active
            if current in tabs_order:
                idx = tabs_order.index(current)
                next_idx = (idx + 1) % len(tabs_order)
                target_tab = tabs_order[next_idx]
                self.set_focus(None)
                tabbed_content.active = target_tab
                self._focus_tab_search(target_tab)
        except Exception:
            pass

    def _focus_tab_search(self, target_tab: str) -> None:
        """Focus the search/input widget for the specified tab."""
        if target_tab == "tab-recipes":
            self.query_one("#recipes-search", TextArea).focus()
        elif target_tab == "tab-agents":
            self.query_one("#agents-search", TextArea).focus()
        elif target_tab == "tab-tools":
            self.query_one("#tools-search", TextArea).focus()
        elif target_tab == "tab-engines":
            self.query_one("#engines-search", TextArea).focus()
        elif target_tab == "tab-models":
            self.query_one("#models-search", TextArea).focus()
        elif target_tab == "tab-generate":
            self.query_one("#gen-input", TextArea).focus()

    # ------------------------------------------------------------------
    # Keyboard & Key Navigation
    # ------------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Handle Ctrl+J submission, tab navigation, and Up/Down prompt history cycling."""
        if event.key in ("ctrl+left", "ctrl+left_square_bracket", "ctrl+[", "ctrl__"):
            event.prevent_default()
            event.stop()
            self.action_previous_tab()
            return
        elif event.key in ("ctrl+right", "ctrl+right_square_bracket", "ctrl+]"):
            event.prevent_default()
            event.stop()
            self.action_next_tab()
            return

        if event.key == "ctrl+s":
            try:
                tabs = self.query_one(TabbedContent)
                if tabs.active == "tab-logs":
                    event.prevent_default()
                    event.stop()
                    self.action_export_logs()
                    return
            except Exception:
                pass

        if event.key == "ctrl+k":
            try:
                tabs = self.query_one(TabbedContent)
                if tabs.active == "tab-logs":
                    event.prevent_default()
                    event.stop()
                    self.action_clear_logs()
                    return
            except Exception:
                pass

        if event.key in ("ctrl+j", "ctrl+m"):
            focused = self.focused
            if isinstance(focused, TextArea) and focused.id in (
                "recipes-search",
                "agents-search",
                "tools-search",
                "engines-search",
                "models-search",
            ):
                tid = focused.id.removesuffix("-search")
                event.prevent_default()
                event.stop()
                self._trigger_llm_search(tid)
                return
            elif isinstance(focused, TextArea) and focused.id == "gen-input":
                event.prevent_default()
                event.stop()
                self.on_gen_submit()
                return

        if event.key in ("up", "down"):
            focused = self.focused
            if isinstance(focused, TextArea) and focused.id == "gen-input":
                inp = focused
                cursor_row, _ = inp.cursor_location
                total_lines = inp.document.line_count

                if event.key == "up" and cursor_row == 0:
                    val = self._gen_input_history.previous(inp.text)
                    if val is not None:
                        event.prevent_default()
                        event.stop()
                        inp.load_text(val)
                        inp.move_cursor((0, 0))
                        return
                elif event.key == "down" and cursor_row >= total_lines - 1:
                    val = self._gen_input_history.next()
                    if val is not None:
                        event.prevent_default()
                        event.stop()
                        inp.load_text(val)
                        inp.move_cursor((inp.document.line_count - 1, len(inp.document.lines[-1])))
                        return

    # ------------------------------------------------------------------
    # Generation Tab Actions
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#gen-submit-btn")
    def on_gen_submit(self) -> None:
        """Start recipe generation in a background worker."""
        inp = self.query_one("#gen-input", TextArea)
        query = inp.text.strip()
        if not query:
            return
        inp.clear()
        self._gen_input_history.append(query)

        self.query_one("#gen-status-bar", Static).update(
            "⏳ Generating assistant recipe (you can switch tabs anytime)..."
        )
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
        self._recipe_generator.execute_generation(query)

    @on(Button.Pressed, "#gen-chat-btn")
    def on_gen_chat_btn(self) -> None:
        """Launch chat options with the newly generated recipe."""
        self._recipe_generator.launch_chat_for_generated()

    # ------------------------------------------------------------------
    # Log Tab Actions
    # ------------------------------------------------------------------

    def action_clear_logs(self) -> None:
        """Clear application rich log and internal log buffer."""
        try:
            self.query_one("#app-rich-log", RichLog).clear()
            self._app_log_buffer.clear()
            self.notify("Application logs cleared", severity="information")
        except Exception:
            pass

    def action_export_logs(self) -> None:
        """Save application execution log buffer to file."""
        if not self._app_log_buffer:
            self.notify("No logs to export", severity="warning")
            return
        out_dir = Path(self._export_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"app_logs_{now_str()}.log"
        out_path = out_dir / filename
        try:
            out_path.write_text("\n".join(self._app_log_buffer), encoding="utf-8")
            self.notify(f"Exported app logs to {out_path}", severity="information")
        except Exception as e:
            self.notify(f"Failed to export logs: {e}", severity="error")

    @on(Button.Pressed, "#app-log-clear-btn")
    def on_clear_app_logs(self) -> None:
        """Clear application rich log and internal log buffer."""
        self.action_clear_logs()

    @on(Button.Pressed, "#app-log-export-btn")
    def on_export_app_logs(self) -> None:
        """Save application execution log buffer to file."""
        self.action_export_logs()

    # ------------------------------------------------------------------
    # Escape & Fullscreen Layout Actions
    # ------------------------------------------------------------------

    def action_handle_escape(self) -> None:
        """Hierarchical back/escape action."""
        if len(self.screen_stack) > 1:
            self.pop_screen()
            return
        if self._fullscreen.maximized_pane is not None:
            self._fullscreen.restore_fullscreen()
            return
        focused = self.focused
        if isinstance(focused, TextArea):
            try:
                tabbed_content = self.query_one(TabbedContent)
                active_tab = tabbed_content.active
                if active_tab == "tab-recipes":
                    self.query_one("#recipes-list", ListView).focus()
                elif active_tab == "tab-agents":
                    self.query_one("#agents-list", ListView).focus()
                elif active_tab == "tab-tools":
                    self.query_one("#tools-list", ListView).focus()
                else:
                    self.set_focus(None)
            except Exception:
                self.set_focus(None)
            return
        self.set_focus(None)

    def action_toggle_detail_fullscreen(self) -> None:
        """Toggle fullscreen for detail or preview pane."""
        self._fullscreen.toggle_detail_fullscreen()

    def action_toggle_log_fullscreen(self) -> None:
        """Toggle fullscreen for logs pane."""
        self._fullscreen.toggle_log_fullscreen()

    def action_toggle_prompt_fullscreen(self) -> None:
        """Toggle fullscreen for prompt pane on active screen."""
        if len(self.screen_stack) > 1 and hasattr(self.screen, "action_toggle_prompt_fullscreen"):
            self.screen.action_toggle_prompt_fullscreen()

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self) -> None:
        """Restore normal layout when switching tabs."""
        if self._fullscreen.maximized_pane is not None:
            self._fullscreen.restore_fullscreen(notify=False)

    def _maximize_resource_detail(self, tid: str) -> None:
        self._fullscreen.maximize_resource_detail(tid)

    def _maximize_resource_log(self, tid: str) -> None:
        self._fullscreen.maximize_resource_log(tid)

    def _maximize_gen_preview(self) -> None:
        self._fullscreen.maximize_gen_preview()

    def _maximize_gen_log(self) -> None:
        self._fullscreen.maximize_gen_log()

    def _maximize_app_log(self) -> None:
        self._fullscreen.maximize_app_log()

    def _restore_fullscreen(self, notify: bool = True) -> None:
        self._fullscreen.restore_fullscreen(notify=notify)

    @on(Button.Pressed, "#recipes-detail-max-btn")
    @on(Button.Pressed, "#agents-detail-max-btn")
    @on(Button.Pressed, "#tools-detail-max-btn")
    def on_resource_detail_max(self, event: Button.Pressed) -> None:
        """Handle detail pane maximize button."""
        if event.button.id:
            tid = event.button.id.removesuffix("-detail-max-btn")
            if self._fullscreen.maximized_pane == f"{tid}-detail":
                self._fullscreen.restore_fullscreen()
            else:
                self._fullscreen.maximize_resource_detail(tid)

    @on(Button.Pressed, "#recipes-log-max-btn")
    @on(Button.Pressed, "#agents-log-max-btn")
    @on(Button.Pressed, "#tools-log-max-btn")
    def on_resource_log_max(self, event: Button.Pressed) -> None:
        """Handle log pane maximize button."""
        if event.button.id:
            tid = event.button.id.removesuffix("-log-max-btn")
            if self._fullscreen.maximized_pane == f"{tid}-log":
                self._fullscreen.restore_fullscreen()
            else:
                self._fullscreen.maximize_resource_log(tid)

    @on(Button.Pressed, "#gen-preview-max-btn")
    def on_gen_preview_max(self) -> None:
        """Handle generate preview maximize button."""
        if self._fullscreen.maximized_pane == "gen-preview":
            self._fullscreen.restore_fullscreen()
        else:
            self._fullscreen.maximize_gen_preview()

    @on(Button.Pressed, "#gen-log-max-btn")
    def on_gen_log_max(self) -> None:
        """Handle generate log maximize button."""
        if self._fullscreen.maximized_pane == "gen-log":
            self._fullscreen.restore_fullscreen()
        else:
            self._fullscreen.maximize_gen_log()

    @on(Button.Pressed, "#app-log-max-btn")
    def on_app_log_max(self) -> None:
        """Handle application log maximize button."""
        if self._fullscreen.maximized_pane == "app-log":
            self._fullscreen.restore_fullscreen()
        else:
            self._fullscreen.maximize_app_log()


def run_tui(engine: str, model: str, recipes_dir: str, export_dir: str | None = None) -> None:
    """Launch the TUI application."""
    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        if isinstance(h, logging.StreamHandler):
            root_logger.removeHandler(h)

    app = MetaAgentTUI(engine=engine, model=model, recipes_dir=recipes_dir, export_dir=export_dir)
    app.run()
