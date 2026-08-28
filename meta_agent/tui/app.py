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
from .screens import ChatOptionsScreen, GenerateScreen
from .widgets import ResourceTab


class MetaAgentTUI(App[None]):
    """TUI application for meta_agent."""

    CSS = """
    /* Toolbar */
    #recipes-toolbar, #agents-toolbar, #tools-toolbar {
        height: 3;
        padding: 0 1;
    }
    #recipes-search, #agents-search, #tools-search {
        width: 1fr;
    }
    #recipes-llm-btn, #agents-llm-btn, #tools-llm-btn {
        width: 14;
    }
    #recipes-sort, #agents-sort, #tools-sort {
        width: 18;
    }

    /* Body */
    #recipes-body, #agents-body, #tools-body {
        height: 1fr;
    }

    /* Sidebar */
    #recipes-sidebar, #agents-sidebar, #tools-sidebar {
        width: 30;
        border-right: solid $primary;
        overflow-y: auto;
    }

    /* Detail pane */
    #recipes-detail, #agents-detail, #tools-detail {
        width: 1fr;
        padding: 1 2;
        overflow-y: auto;
        overflow-x: hidden;
    }

    Markdown {
        height: auto;
    }

    LoadingIndicator {
        height: 3;
    }

    /* Chat button */
    #recipes-chat-btn {
        margin-top: 1;
        display: none;
    }

    /* Generate screen */
    #gen-title {
        margin: 1 2;
        text-style: bold;
        color: $accent;
    }
    #gen-label {
        margin: 0 2;
    }
    #gen-input {
        margin: 0 2 1 2;
    }
    #gen-btn {
        margin: 0 2;
    }
    #gen-status {
        margin: 1 2;
    }

    /* Chat options screen */
    #chat-opts-title {
        margin: 1 2;
        text-style: bold;
        color: $accent;
    }
    .chat-opts-label {
        margin: 1 2 0 2;
    }
    #chat-opts-engine, #chat-opts-model, #chat-opts-agent, #chat-opts-tools {
        margin: 0 2;
    }
    #chat-opts-system {
        margin: 0 2;
        height: 8;
    }
    #chat-opts-cmd {
        margin: 0 2 1 2;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
        overflow-x: auto;
        height: auto;
    }
    #chat-opts-buttons {
        margin: 0 2 1 2;
        height: 3;
    }
    #chat-opts-start {
        margin-right: 1;
    }

    /* Chat screen */
    #chat-screen-layout {
        height: 1fr;
    }
    #chat-info-sidebar {
        width: 32;
        border-right: solid $primary;
        padding: 1 2;
        overflow-y: auto;
    }
    #chat-sidebar-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    .chat-sidebar-item {
        margin-bottom: 1;
    }
    #chat-sidebar-prompt {
        height: 8;
        border: solid $secondary;
        padding: 0 1;
        margin-bottom: 1;
    }
    #chat-back-btn {
        margin-top: 1;
    }
    #chat-main-pane {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    #chat-messages {
        height: 1fr;
        border: solid $primary;
        padding: 1 2;
        margin-bottom: 1;
        overflow-y: auto;
    }
    #chat-loading {
        height: 1;
    }
    #chat-input-bar {
        height: 3;
    }
    #chat-input {
        width: 1fr;
    }
    #chat-send-btn {
        width: 12;
        margin-left: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+c", "handle_ctrl_c", "Quit (×2)", show=True),
        Binding("q", "quit", "Quit"),
        Binding("g", "open_generate", "Generate"),
        Binding("c", "chat_recipe", "Chat", show=True),
    ]

    def __init__(self, engine: str, model: str, recipes_dir: str) -> None:
        """Initialize the TUI with LLM settings."""
        super().__init__()
        self._engine = engine
        self._model = model
        self._recipes_dir = recipes_dir
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

    def _render_recipes(self) -> None:
        """Render the current (filtered + sorted) recipe list."""
        sort_key = str(self.query_one("#recipes-sort", Select).value)
        search = self.query_one("#recipes-search", Input).value
        items = filter_items(self._recipes, search)
        items = sort_items(items, sort_key)
        self._displayed_recipes = items
        self._render_list("recipes", items)
        self._selected_recipe = None
        self.query_one("#recipes-chat-btn", Button).display = False

    def _render_agents(self) -> None:
        """Render the current (filtered + sorted) agent list."""
        sort_key = str(self.query_one("#agents-sort", Select).value)
        search = self.query_one("#agents-search", Input).value
        items = filter_items(self._agents, search)
        items = sort_items(items, sort_key)
        self._displayed_agents = items
        self._render_list("agents", items)

    def _render_tools(self) -> None:
        """Render the current (filtered + sorted) tool list."""
        sort_key = str(self.query_one("#tools-sort", Select).value)
        search = self.query_one("#tools-search", Input).value
        items = filter_items(self._tools, search)
        items = sort_items(items, sort_key)
        self._displayed_tools = items
        self._render_list("tools", items)

    # ------------------------------------------------------------------
    # Search events
    # ------------------------------------------------------------------

    @on(Input.Changed, "#recipes-search")
    def on_recipes_search_changed(self) -> None:
        """Filter recipes on input change."""
        self._render_recipes()

    @on(Input.Changed, "#agents-search")
    def on_agents_search_changed(self) -> None:
        """Filter agents on input change."""
        self._render_agents()

    @on(Input.Changed, "#tools-search")
    def on_tools_search_changed(self) -> None:
        """Filter tools on input change."""
        self._render_tools()

    # ------------------------------------------------------------------
    # LLM Search
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#recipes-llm-btn")
    def on_recipes_llm_search(self) -> None:
        """Trigger LLM-based semantic search for recipes."""
        query = self.query_one("#recipes-search", Input).value.strip()
        if not query:
            return
        self._llm_search("recipes", query, self._recipes)

    @on(Button.Pressed, "#agents-llm-btn")
    def on_agents_llm_search(self) -> None:
        """Trigger LLM-based semantic search for agents."""
        query = self.query_one("#agents-search", Input).value.strip()
        if not query:
            return
        self._llm_search("agents", query, self._agents)

    @on(Button.Pressed, "#tools-llm-btn")
    def on_tools_llm_search(self) -> None:
        """Trigger LLM-based semantic search for tools."""
        query = self.query_one("#tools-search", Input).value.strip()
        if not query:
            return
        self._llm_search("tools", query, self._tools)

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
    def on_recipes_sort_changed(self) -> None:
        """Re-sort and re-render recipes."""
        self._render_recipes()

    @on(Select.Changed, "#agents-sort")
    def on_agents_sort_changed(self) -> None:
        """Re-sort and re-render agents."""
        self._render_agents()

    @on(Select.Changed, "#tools-sort")
    def on_tools_sort_changed(self) -> None:
        """Re-sort and re-render tools."""
        self._render_tools()

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
        self.push_screen(ChatOptionsScreen(self._selected_recipe, self._engine, self._model))

    @on(Button.Pressed, "#recipes-chat-btn")
    def on_chat_btn(self) -> None:
        """Launch chat options screen via button."""
        self._open_chat_options()

    def action_chat_recipe(self) -> None:
        """Launch chat options screen via key binding."""
        self._open_chat_options()

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


def run_tui(engine: str, model: str, recipes_dir: str) -> None:
    """Launch the TUI application."""
    app = MetaAgentTUI(engine=engine, model=model, recipes_dir=recipes_dir)
    app.run()
