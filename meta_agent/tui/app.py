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
    ListView,
    LoadingIndicator,
    RichLog,
    SelectionList,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from ..api import (
    Agent,
    Engine,
    Model,
    Recipe,
    Script,
    Tool,
)
from ..utils import get_default_export_dir, now_str
from .fullscreen import FullscreenManager
from .generation import RecipeGenerator
from .helpers import (
    InputHistory,
    now_datetime_str,
)
from .intent import (
    build_recipe_action_prompt,
    build_semantic_search_prompt,
    IntentDispatcher,
    parse_recipe_action_intent,
    RecipeActionIntent,
)
from .nav import KeyNavigator
from .refactoring import RecipeRefactorer
from .resources import ResourceManager
from .screens import ScreenNavigator
from .screens.chat import RichLogHandler
from .styles import APP_CSS
from .widgets import GenerateTab, LogTab, OrderedFooter, RefactorTab, ResourceTab


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
        Binding("ctrl+r", "resume_chat", "Resume (Ctrl+R)", show=True, priority=True),
        Binding("ctrl+x", "refactor_recipe", "Refactor (Ctrl+X)", show=True, priority=False),
        Binding("ctrl+o", "toggle_detail_fullscreen", "Detail Max (Ctrl+O)", show=False, priority=True),
        Binding("ctrl+l", "toggle_log_fullscreen", "Logs Max (Ctrl+L)", show=False, priority=True),
        Binding("ctrl+u", "toggle_sidebar_fullscreen", "Sidebar Max (Ctrl+U)", show=False, priority=True),
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
        self._refactor_input_history = InputHistory()
        self._last_ctrl_c: float = 0.0
        self._displayed_recipes: list[Recipe] = []
        self._displayed_agents: list[Agent] = []
        self._displayed_tools: list[Tool] = []
        self._displayed_engines: list[Engine] = []
        self._displayed_models: list[Model] = []
        self._selected_refactor_recipes: set[str] = set()

        # Sub-managers
        self._fullscreen = FullscreenManager(self)
        self._intent_dispatcher = IntentDispatcher(self)
        self._recipe_generator = RecipeGenerator(self)
        self._recipe_refactorer = RecipeRefactorer(self)
        self._resource_manager = ResourceManager(self)
        self._key_navigator = KeyNavigator(self)
        self._screen_navigator = ScreenNavigator(self)

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
            with TabPane("Refactor", id="tab-refactor"):
                yield RefactorTab(self._engine, self._model)
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
        if self._initial_tab != "tab-recipes":
            try:
                self.query_one(TabbedContent).active = self._initial_tab
            except Exception:
                pass

        try:
            if self._initial_tab == "tab-generate":
                self.query_one("#gen-input", TextArea).focus()
            elif self._initial_tab == "tab-recipes":
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
        self._resource_manager.load_resource(tid)

    def _load_recipes(self) -> None:
        self._load_resource("recipes")

    def _load_agents(self) -> None:
        self._load_resource("agents")

    def _load_tools(self) -> None:
        self._load_resource("tools")

    def _load_engines(self) -> None:
        self._load_resource("engines")

    def _load_models(self) -> None:
        self._load_resource("models")

    def _render_list(self, tid: str, items: list[Any]) -> None:
        self._resource_manager.render_list(tid, items)

    def _render_tab(self, tid: str) -> None:
        self._resource_manager.render_tab(tid)

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
        self._key_navigator.focus_search()

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

    @on(TextArea.Changed, "#refactor-search")
    def on_refactor_search_changed(self, event: TextArea.Changed) -> None:
        """Live-filter refactor recipe selection list as user types."""
        self._recipe_refactorer.filter_recipes(event.text_area.text)

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

    def _build_search_prompt(self, tid: str, query: str, items: list[Any]) -> str:
        """Build prompt for semantic search or recipe action intent."""
        catalogue = "\n".join(f"- {x.name}: {getattr(x, 'description', '')}" for x in items)
        if tid != "recipes":
            return build_semantic_search_prompt(query, catalogue)

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
        return build_recipe_action_prompt(query, catalogue, chat_cat)

    def _broadcast_app_log(self, msg: str, level: str = "INFO", color: str = "white") -> None:
        """Append log message to buffer and broadcast to all tab RichLog widgets."""
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

    @work(thread=True)
    def _llm_search(self, tid: str, query: str, items: list[Any]) -> None:
        """Run LLM semantic action/search in a background thread."""
        prompt = self._build_search_prompt(tid, query, items)
        self._broadcast_app_log(f"LLM Search triggered for '{tid}' with query: '{query}'", "INFO", "cyan")

        script = Script(agent="native_react", prompt=prompt, tools=[])
        try:
            result = script.run(engine=self._engine, model=self._model)
            self._broadcast_app_log(f"LLM response received for '{tid}':\n{result.strip()}", "DEBUG", "dim")
        except Exception as exc:
            err_msg = str(exc)
            self._broadcast_app_log(f"LLM Search failed for '{tid}': {err_msg}", "ERROR", "bold red")
            self.app.call_from_thread(lambda: self.notify(f"❌ LLM request failed: {err_msg}", severity="error"))
            return

        if tid == "recipes":
            intent = parse_recipe_action_intent(result)
            self._broadcast_app_log(
                f"Parsed recipe intent: action='{intent.action}', target='{intent.target}', "
                f"file='{intent.chat_file}', gen='{intent.generate_query}'",
                "INFO",
                "yellow",
            )
            handled = self._handle_recipe_action_intent(intent, query, self._broadcast_app_log)
            if handled:
                return
            ranked_names = intent.ranked_names or []
        else:
            ranked_names = [line.lstrip("- ").strip() for line in result.splitlines() if line.strip()]

        self._broadcast_app_log(
            f"LLM Search returned {len(ranked_names)} matching candidates for '{tid}'.", "INFO", "green"
        )

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
        return self._intent_dispatcher.handle_intent_generate(gen_req, log_fn)

    def _handle_intent_resume(self, search_term: str, log_fn: Any) -> bool:
        return self._intent_dispatcher.handle_intent_resume(search_term, log_fn)

    def _handle_intent_recipe_mutation(self, action: str, target: str, log_fn: Any) -> bool:
        return self._intent_dispatcher.handle_intent_recipe_mutation(action, target, log_fn)

    # ------------------------------------------------------------------
    # Selection & Focus events
    # ------------------------------------------------------------------

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        """Auto-select the first item if list gains focus and no item is selected yet."""
        self._resource_manager.handle_descendant_focus(event)

    def _sync_refactor_selected_box(self, selected_values: list[str]) -> None:
        self._recipe_refactorer.sync_selected_box(selected_values)

    def _filter_refactor_recipes(self, search_query: str) -> None:
        self._recipe_refactorer.filter_recipes(search_query)

    def _update_refactor_selection_list(self, recipes: list[Recipe]) -> None:
        self._recipe_refactorer.update_selection_list(recipes)

    def _select_recipe_by_index(self, index: int) -> None:
        self._resource_manager.select_recipe_by_index(index)

    def _select_agent_by_index(self, index: int) -> None:
        self._resource_manager.select_agent_by_index(index)

    def _select_tool_by_index(self, index: int) -> None:
        self._resource_manager.select_tool_by_index(index)

    def _select_engine_by_index(self, index: int) -> None:
        self._resource_manager.select_engine_by_index(index)

    def _select_model_by_index(self, index: int) -> None:
        self._resource_manager.select_model_by_index(index)

    @on(ListView.Selected, "#recipes-list")
    @on(ListView.Highlighted, "#recipes-list")
    def on_recipe_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self._resource_manager.select_recipe_by_index(event.list_view.index)

    @on(ListView.Selected, "#agents-list")
    @on(ListView.Highlighted, "#agents-list")
    def on_agent_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self._resource_manager.select_agent_by_index(event.list_view.index)

    @on(ListView.Selected, "#tools-list")
    @on(ListView.Highlighted, "#tools-list")
    def on_tool_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self._resource_manager.select_tool_by_index(event.list_view.index)

    @on(ListView.Selected, "#engines-list")
    @on(ListView.Highlighted, "#engines-list")
    def on_engine_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self._resource_manager.select_engine_by_index(event.list_view.index)

    @on(ListView.Selected, "#models-list")
    @on(ListView.Highlighted, "#models-list")
    def on_model_selected(self, event: ListView.Selected | ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self._resource_manager.select_model_by_index(event.list_view.index)

    # ------------------------------------------------------------------
    # Recipe Actions & Screen Navigation
    # ------------------------------------------------------------------

    def _open_chat_options(self, recipe: Recipe) -> None:
        self._screen_navigator.open_chat_options(recipe)

    @on(Button.Pressed, "#recipes-chat-btn")
    def on_chat_btn(self) -> None:
        self.action_chat_recipe()

    def action_chat_recipe(self) -> None:
        self._screen_navigator.chat_recipe()

    def action_handle_ctrl_c(self) -> None:
        self._key_navigator.handle_ctrl_c()

    def action_resume_chat(self) -> None:
        self._screen_navigator.resume_chat()

    def action_refactor_recipe(self) -> None:
        """Switch to Refactor tab with selected recipe pre-selected."""
        if self._selected_recipe is None:
            self.notify("Please select a recipe first", severity="warning")
            return
        rec_name = self._selected_recipe.name
        try:
            self._fullscreen.restore_fullscreen()
            self.query_one(TabbedContent).active = "tab-refactor"
            sl = self.query_one("#refactor-recipe-list", SelectionList)
            sl.deselect_all()
            sl.select(rec_name)
            self._recipe_refactorer.sync_selected_box(list(sl.selected))
            self.query_one("#refactor-input", TextArea).focus()
        except Exception:
            pass

    @on(Button.Pressed, "#recipes-refactor-btn")
    def on_refactor_btn(self) -> None:
        self.action_refactor_recipe()

    def action_edit_recipe(self) -> None:
        self._screen_navigator.edit_recipe()

    @on(Button.Pressed, "#recipes-edit-btn")
    def on_edit_btn(self) -> None:
        self.action_edit_recipe()

    def action_delete_recipe(self) -> None:
        self._screen_navigator.delete_recipe()

    @on(Button.Pressed, "#recipes-delete-btn")
    def on_delete_btn(self) -> None:
        self.action_delete_recipe()

    def action_open_help(self) -> None:
        self._screen_navigator.open_help()

    def action_open_generate(self) -> None:
        """Switch to GenerateTab and focus input prompt."""
        try:
            self._fullscreen.restore_fullscreen()
            self.query_one(TabbedContent).active = "tab-generate"
            self.query_one("#gen-input", TextArea).focus()
        except Exception:
            pass

    def action_previous_tab(self) -> None:
        self._key_navigator.switch_tab_relative(-1)

    def action_next_tab(self) -> None:
        self._key_navigator.switch_tab_relative(1)

    def _focus_tab_search(self, target_tab: str) -> None:
        self._key_navigator.focus_tab_search(target_tab)

    def on_key(self, event: events.Key) -> None:
        """Handle Ctrl+J submission, tab navigation, and Up/Down prompt history cycling."""
        self._key_navigator.handle_key(event)

    # ------------------------------------------------------------------
    # Refactor Tab Actions
    # ------------------------------------------------------------------

    @on(SelectionList.SelectedChanged, "#refactor-recipe-list")
    def on_refactor_selection_changed(self, event: SelectionList.SelectedChanged[Any]) -> None:
        """Update selected box when SelectionList state changes."""
        visible_options = {getattr(opt, "value") for opt in event.selection_list._options}
        current_visible_selected = set(event.selection_list.selected)
        self._selected_refactor_recipes.difference_update(visible_options - current_visible_selected)
        self._selected_refactor_recipes.update(current_visible_selected)
        self._recipe_refactorer.sync_selected_box(sorted(self._selected_refactor_recipes))

    @on(Button.Pressed, "#refactor-select-all-btn")
    def on_refactor_select_all(self) -> None:
        self._recipe_refactorer.select_all()

    @on(Button.Pressed, "#refactor-clear-all-btn")
    def on_refactor_clear_all(self) -> None:
        self._recipe_refactorer.clear_all()

    @on(Button.Pressed, "#refactor-submit-btn")
    def on_refactor_submit(self) -> None:
        self._recipe_refactorer.prompt_and_submit()

    def _execute_recipe_refactor(self, recipes: list[str], query: str, target: str) -> None:
        self._recipe_refactorer.execute_refactor(recipes=recipes, query=query, target=target)

    @on(Button.Pressed, "#refactor-save-inplace-btn")
    def on_refactor_save_inplace(self) -> None:
        self._recipe_refactorer.save_results(in_place=True)

    @on(Button.Pressed, "#refactor-save-new-btn")
    def on_refactor_save_new(self) -> None:
        self._recipe_refactorer.save_results(in_place=False)

    @on(Button.Pressed, "#refactor-discard-btn")
    def on_refactor_discard(self) -> None:
        self._recipe_refactorer.discard_results()

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
        self._recipe_generator.execute_generation(query)

    @on(Button.Pressed, "#gen-chat-btn")
    def on_gen_chat_btn(self) -> None:
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
        self.action_clear_logs()

    @on(Button.Pressed, "#app-log-export-btn")
    def on_export_app_logs(self) -> None:
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
        self._fullscreen.toggle_detail_fullscreen()

    def action_toggle_log_fullscreen(self) -> None:
        self._fullscreen.toggle_log_fullscreen()

    def action_toggle_sidebar_fullscreen(self) -> None:
        self._fullscreen.toggle_sidebar_fullscreen()

    def action_toggle_prompt_fullscreen(self) -> None:
        if len(self.screen_stack) > 1 and hasattr(self.screen, "action_toggle_prompt_fullscreen"):
            self.screen.action_toggle_prompt_fullscreen()

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self) -> None:
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

    @on(Button.Pressed)
    def on_any_button_pressed(self, event: Button.Pressed) -> None:
        """Route maximize buttons to FullscreenManager."""
        if event.button.id and self._fullscreen.handle_button_press(event.button.id):
            event.stop()


def run_tui(engine: str, model: str, recipes_dir: str, export_dir: str | None = None) -> None:
    """Launch the TUI application."""
    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        if isinstance(h, logging.StreamHandler):
            root_logger.removeHandler(h)

    app = MetaAgentTUI(engine=engine, model=model, recipes_dir=recipes_dir, export_dir=export_dir)
    app.run()
