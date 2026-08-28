"""Main TUI application for meta_agent."""

import time
from typing import Any, ClassVar

from textual import on, work
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
    Select,
    TabbedContent,
    TabPane,
)

from ..api import list_agents, list_recipes, list_tools, Agent, Recipe, Tool
from .helpers import (
    CTRL_C_TIMEOUT,
    agent_markdown,
    filter_items,
    recipe_markdown,
    sort_items,
    tool_markdown,
)
from .screens import ChatOptionsScreen, GenerateScreen, HelpScreen
from .styles import APP_CSS
from .widgets import ResourceTab


class MetaAgentTUI(App[None]):
    """TUI application for meta_agent."""

    CSS = APP_CSS

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("question_mark", "open_help", "Help (?)", show=True),
        Binding("f1", "open_help", "Help", show=False),
        Binding("slash", "focus_search", "Search (/)", show=True),
        Binding("c", "chat_recipe", "Chat", show=True),
        Binding("g", "open_generate", "Generate", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "handle_ctrl_c", "Quit (×2)", show=True),
    ]

    def __init__(self, engine: str, model: str, recipes_dir: str, export_dir: str | None = None) -> None:
        """Initialize the TUI with LLM settings and export directory."""
        super().__init__()
        self._engine = engine
        self._model = model
        self._recipes_dir = recipes_dir
        self._export_dir = export_dir
        self._recipes: list[Recipe] = []
        self._agents: list[Agent] = []
        self._tools: list[Tool] = []
        self._displayed_recipes: list[Recipe] = []
        self._displayed_agents: list[Agent] = []
        self._displayed_tools: list[Tool] = []
        self._selected_recipe: Recipe | None = None
        self._last_ctrl_c: float = 0.0

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
        yield Footer()

    def on_mount(self) -> None:
        """Load all resources after mounting."""
        self._load_recipes()
        self._load_agents()
        self._load_tools()

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
    def _load_recipes(self) -> None:
        """Load recipes in a background thread."""
        recipes = list_recipes()
        self._recipes = recipes
        self.app.call_from_thread(self._render_recipes)

    @work(thread=True)
    def _load_agents(self) -> None:
        """Load agents in a background thread."""
        agents = list_agents()
        self._agents = agents
        self.app.call_from_thread(self._render_agents)

    @work(thread=True)
    def _load_tools(self) -> None:
        """Load tools in a background thread."""
        tools = list_tools()
        self._tools = tools
        self.app.call_from_thread(self._render_tools)

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
        sort_key = str(self.query_one(f"#{tid}-sort", Select).value)
        search = self.query_one(f"#{tid}-search", Input).value
        items = filter_items(all_items, search)
        items = sort_items(items, sort_key)

        if tid == "recipes":
            self._displayed_recipes = items
            self._selected_recipe = None
            self.query_one("#recipes-chat-btn", Button).display = False
        elif tid == "agents":
            self._displayed_agents = items
        elif tid == "tools":
            self._displayed_tools = items

        self._render_list(tid, items)

    def _render_recipes(self) -> None:
        """Render recipe list."""
        self._render_tab("recipes")

    def _render_agents(self) -> None:
        """Render agent list."""
        self._render_tab("agents")

    def _render_tools(self) -> None:
        """Render tool list."""
        self._render_tab("tools")

    # ------------------------------------------------------------------
    # Search actions & events
    # ------------------------------------------------------------------

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Check if action is enabled; disables and hides search binding on sub-screens."""
        if action == "focus_search" and len(self.screen_stack) > 1:
            return False
        return True

    def action_focus_search(self) -> None:
        """Focus the search input for the active tab (main screen only)."""
        if len(self.screen_stack) > 1:
            return

        try:
            tabbed_content = self.query_one(TabbedContent)
            active_tab = tabbed_content.active
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
    # LLM Search
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#recipes-llm-btn")
    @on(Button.Pressed, "#agents-llm-btn")
    @on(Button.Pressed, "#tools-llm-btn")
    def on_llm_search_pressed(self, event: Button.Pressed) -> None:
        """Trigger LLM-based semantic search for active button's resource type."""
        if not event.button.id:
            return
        tid = event.button.id.removesuffix("-llm-btn")
        query = self.query_one(f"#{tid}-search", Input).value.strip()
        if not query:
            return
        items_map: dict[str, list[Any]] = {
            "recipes": self._recipes,
            "agents": self._agents,
            "tools": self._tools,
        }
        self._llm_search(tid, query, items_map.get(tid, []))

    @work(thread=True)
    def _llm_search(self, tid: str, query: str, items: list[Any]) -> None:
        """Run LLM semantic search in a background thread and re-render list."""
        from ..api import Script

        catalogue = "\n".join(f"- {x.name}: {getattr(x, 'description', '')}" for x in items)
        prompt = (
            "You are a search assistant. The user is looking for items matching their query.\n"
            f"Query: {query}\n\n"
            f"Available items:\n{catalogue}\n\n"
            "Reply with ONLY a newline-separated list of matching item names, "
            "ordered by relevance (most relevant first). "
            "Include only names that appear in the list above. No explanations."
        )
        script = Script(agent="native_react", prompt=prompt, tools=[])
        try:
            result = script.run(engine=self._engine, model=self._model)
        except Exception:
            return
        ranked_names = [line.lstrip("- ").strip() for line in result.splitlines() if line.strip()]
        name_to_item = {x.name: x for x in items}
        ranked: list[Any] = []
        for name in ranked_names:
            if name in name_to_item:
                ranked.append(name_to_item[name])

        def _update() -> None:
            if tid == "recipes":
                self._displayed_recipes = ranked
            elif tid == "agents":
                self._displayed_agents = ranked
            else:
                self._displayed_tools = ranked
            self._render_list(tid, ranked)

        self.app.call_from_thread(_update)

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
        self.query_one("#recipes-chat-btn", Button).display = True

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
    # Chat
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

    # ------------------------------------------------------------------
    # Help Modal
    # ------------------------------------------------------------------

    def action_open_help(self) -> None:
        """Open the comprehensive keyboard shortcuts help modal."""
        self.push_screen(HelpScreen())

    # ------------------------------------------------------------------
    # Generate Recipe
    # ------------------------------------------------------------------

    def action_open_generate(self) -> None:
        """Open the recipe generation screen."""
        self.push_screen(
            GenerateScreen(self._engine, self._model, self._recipes_dir),
            self._on_generate_done,
        )

    def _on_generate_done(self, success: bool | None) -> None:
        """Reload recipe list if generation succeeded."""
        if success:
            self._load_recipes()


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
