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
    Input,
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
    now_datetime_str,
    parse_recipe_action_intent,
    RecipeActionIntent,
    recipe_markdown,
    sort_items,
    tool_markdown,
)
from .screens import ChatOptionsScreen, DeleteRecipeScreen, EditRecipeScreen, HelpScreen, ResumeChatScreen
from .screens.chat import RichLogHandler
from .styles import APP_CSS
from .widgets import GenerateTab, LogTab, ResourceTab


class MetaAgentTUI(App[None]):
    """TUI application for meta_agent."""

    CSS = APP_CSS

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("question_mark", "open_help", "Help (?)", show=True),
        Binding("f1", "open_help", "Help", show=False),
        Binding("slash", "focus_search", "Search (/)", show=True),
        Binding("c", "chat_recipe", "Chat", show=True),
        Binding("r", "resume_chat", "Resume Chat (r)", show=True),
        Binding("e", "edit_recipe", "Edit (e)", show=True),
        Binding("d", "delete_recipe", "Delete (d)", show=True),
        Binding("g", "open_generate", "Generate (g)", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "handle_ctrl_c", "Quit (×2)", show=True),
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

        # Generate tab history state
        self._gen_user_inputs: list[str] = []
        self._gen_history_cursor: int = -1
        self._gen_current_draft: str = ""
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
        """Render the current (filtered + sorted) resource list for a given tab."""
        items_map: dict[str, list[Any]] = {
            "recipes": self._recipes,
            "agents": self._agents,
            "tools": self._tools,
        }
        all_items = items_map.get(tid, [])
        try:
            sort_key = str(self.query_one(f"#{tid}-sort", Select).value)
            search = self.query_one(f"#{tid}-search", Input).value
        except Exception:
            return
        items = filter_items(all_items, search)
        items = sort_items(items, sort_key)

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
        """Check if action is enabled; disables and hides search binding on sub-screens."""
        if action == "focus_search" and len(self.screen_stack) > 1:
            return False
        return True

    def action_focus_search(self) -> None:
        """Focus the search input or open select overlay if focused on a Select."""
        if len(self.screen_stack) > 1:
            return

        if isinstance(self.focused, Select):
            self.focused.action_show_overlay()
            return

        try:
            tabbed_content = self.query_one(TabbedContent)
            active_tab = tabbed_content.active
            if active_tab == "tab-generate":
                self.query_one("#gen-input", Input).focus()
                return
            tid = "recipes"
            if active_tab == "tab-agents":
                tid = "agents"
            elif active_tab == "tab-tools":
                tid = "tools"
            self.query_one(f"#{tid}-search", Input).focus()
        except Exception:
            pass

    @on(Input.Changed, "#recipes-search")
    @on(Input.Changed, "#agents-search")
    @on(Input.Changed, "#tools-search")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Filter resources on input change."""
        if event.input.id:
            tid = event.input.id.removesuffix("-search")
            self._render_tab(tid)

    # ------------------------------------------------------------------
    # Ask LLM (Search / Smart Actions / Generate)
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#recipes-llm-btn")
    @on(Button.Pressed, "#agents-llm-btn")
    @on(Button.Pressed, "#tools-llm-btn")
    @on(Input.Submitted, "#recipes-search")
    @on(Input.Submitted, "#agents-search")
    @on(Input.Submitted, "#tools-search")
    def on_llm_search_pressed(self, event: Button.Pressed | Input.Submitted) -> None:
        """Trigger LLM-based action / semantic search on button press or enter key."""
        target_id = event.button.id if isinstance(event, Button.Pressed) else event.input.id
        if not target_id:
            return
        tid = target_id.removesuffix("-llm-btn").removesuffix("-search")
        query = self.query_one(f"#{tid}-search", Input).value.strip()
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
        if intent.action == "generate":
            gen_req = intent.generate_query or query
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
                except Exception:
                    pass

                self._gen_user_inputs.append(gen_req)
                self._gen_history_cursor = -1
                self._gen_current_draft = ""

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

        if intent.action == "resume":
            search_term = intent.chat_file or intent.target or query
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

        if intent.action in ("delete", "edit") and intent.target:
            matched_recipe = next((r for r in self._recipes if r.name == intent.target), None)
            if not matched_recipe:
                matched_recipe = next((r for r in self._recipes if intent.target.lower() in r.name.lower()), None)

            if matched_recipe is not None:
                target_rec = matched_recipe
                action_name = intent.action
                log_fn(
                    f"Intent matched {action_name} target: '{target_rec.name}'. Opening screen.",
                    "INFO",
                    "green",
                )

                def _open_action(rec: Recipe = target_rec, act: str = action_name) -> None:
                    self.clear_notifications()
                    self._selected_recipe = rec
                    if act == "delete":
                        self.action_delete_recipe()
                    else:
                        self.action_edit_recipe()

                self.app.call_from_thread(_open_action)
                return True
            else:
                log_fn(f"{intent.action.capitalize()} target '{intent.target}' not found.", "WARNING", "yellow")

                def _target_not_found(tgt: str = str(intent.target), act: str = intent.action) -> None:
                    self.clear_notifications()
                    self.notify(
                        f"⚠️ Target recipe '{tgt}' to {act} was not found",
                        severity="warning",
                        timeout=6.0,
                    )

                self.app.call_from_thread(_target_not_found)
                return False

        return False

    # ------------------------------------------------------------------
    # Sort events
    # ------------------------------------------------------------------

    @on(Select.Changed, "#recipes-sort")
    @on(Select.Changed, "#agents-sort")
    @on(Select.Changed, "#tools-sort")
    def on_sort_changed(self, event: Select.Changed) -> None:
        """Re-sort and re-render resources for active select widget."""
        if event.select.id:
            tid = event.select.id.removesuffix("-sort")
            self._render_tab(tid)

    # ------------------------------------------------------------------
    # Selection events
    # ------------------------------------------------------------------

    @on(ListView.Selected, "#recipes-list")
    def on_recipe_selected(self, event: ListView.Selected) -> None:
        """Show recipe detail on selection."""
        idx = event.list_view.index
        if idx is None or idx >= len(self._displayed_recipes):
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

    @on(ListView.Selected, "#agents-list")
    def on_agent_selected(self, event: ListView.Selected) -> None:
        """Show agent detail on selection."""
        idx = event.list_view.index
        if idx is None or idx >= len(self._displayed_agents):
            return
        a = self._displayed_agents[idx]
        md = agent_markdown(a)
        self.query_one("#agents-markdown", Markdown).update(md)

    @on(ListView.Selected, "#tools-list")
    def on_tool_selected(self, event: ListView.Selected) -> None:
        """Show tool detail on selection."""
        idx = event.list_view.index
        if idx is None or idx >= len(self._displayed_tools):
            return
        t = self._displayed_tools[idx]
        md = tool_markdown(t)
        self.query_one("#tools-markdown", Markdown).update(md)

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
        """Launch chat options screen via key binding."""
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
            self.query_one("#gen-input", Input).focus()
        except Exception:
            pass

    def on_key(self, event: events.Key) -> None:
        """Handle Up/Down arrow history navigation for the Generate tab input."""
        try:
            inp = self.query_one("#gen-input", Input)
        except Exception:
            return

        if not inp.has_focus or not self._gen_user_inputs:
            return

        if event.key == "up":
            event.prevent_default()
            event.stop()
            if self._gen_history_cursor == -1:
                self._gen_current_draft = inp.value
                self._gen_history_cursor = len(self._gen_user_inputs) - 1
            elif self._gen_history_cursor > 0:
                self._gen_history_cursor -= 1

            inp.value = self._gen_user_inputs[self._gen_history_cursor]
            inp.cursor_position = len(inp.value)

        elif event.key == "down":
            event.prevent_default()
            event.stop()
            if self._gen_history_cursor != -1:
                if self._gen_history_cursor < len(self._gen_user_inputs) - 1:
                    self._gen_history_cursor += 1
                    inp.value = self._gen_user_inputs[self._gen_history_cursor]
                else:
                    self._gen_history_cursor = -1
                    inp.value = self._gen_current_draft
                inp.cursor_position = len(inp.value)

    @on(Button.Pressed, "#gen-submit-btn")
    @on(Input.Submitted, "#gen-input")
    def on_gen_submit(self) -> None:
        """Start recipe generation in a background worker."""
        inp = self.query_one("#gen-input", Input)
        query = inp.value.strip()
        if not query:
            return
        inp.value = ""
        self._gen_user_inputs.append(query)
        self._gen_history_cursor = -1
        self._gen_current_draft = ""

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
        r = generate_assistant(req)

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
