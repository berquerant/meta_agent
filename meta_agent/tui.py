"""TUI for meta_agent using Textual."""

import os
import subprocess
import time
from dataclasses import asdict
from typing import Any, ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
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
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from .api import list_agents, list_recipes, list_tools, Agent, Recipe, Tool
from .asking import AskingOpts
from .cmd import format_obj

# ---------------------------------------------------------------------------
# Sort helpers
# ---------------------------------------------------------------------------

_SORT_OPTIONS: list[tuple[str, str]] = [
    ("A → Z", "alpha_asc"),
    ("Z → A", "alpha_desc"),
]

SortKey = str  # "alpha_asc" | "alpha_desc"

_CTRL_C_TIMEOUT = 2.0  # seconds


def _sort_items(items: list[Any], sort_key: SortKey) -> list[Any]:
    """Sort a list of dataclass items by name."""
    reverse = sort_key == "alpha_desc"
    return sorted(items, key=lambda x: x.name.lower(), reverse=reverse)


def _filter_items(items: list[Any], query: str) -> list[Any]:
    """Filter items whose name contains query (case-insensitive substring)."""
    q = query.strip().lower()
    if not q:
        return items
    return [x for x in items if q in x.name.lower()]


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------


def _obj_to_markdown(obj: dict[str, Any]) -> str:
    """Convert a dataclass dict to a Markdown string for display."""
    return format_obj(obj, "text")


def _recipe_markdown(r: Recipe) -> str:
    """Format recipe as markdown."""
    return _obj_to_markdown(asdict(r))


def _agent_markdown(a: Agent) -> str:
    """Format agent as markdown."""
    return _obj_to_markdown(asdict(a))


def _tool_markdown(t: Tool) -> str:
    """Format tool as markdown."""
    return _obj_to_markdown(asdict(t))


# ---------------------------------------------------------------------------
# Chat Options Screen (override engine/model/agent/tools/system before chat)
# ---------------------------------------------------------------------------


class ChatOptionsScreen(Screen[None]):
    """Screen to review and override recipe settings before starting chat."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "start_chat", "Start Chat"),
    ]

    def __init__(self, recipe: Recipe, default_engine: str, default_model: str) -> None:
        """Initialize with recipe and TUI-level defaults."""
        super().__init__()
        self._recipe = recipe
        self._default_engine = default_engine
        self._default_model = default_model

    def compose(self) -> ComposeResult:
        """Build the chat options layout."""
        r = self._recipe
        engine = r.engine_key or self._default_engine
        model = r.model or self._default_model
        agent = r.agent_type or ""
        tools = ", ".join(r.tools) if r.tools else ""
        system = r.system_prompt or ""

        yield Header()
        with VerticalScroll():
            yield Label(f"Chat with recipe: {r.name}", id="chat-opts-title")
            yield Label("Engine:", classes="chat-opts-label")
            yield Input(value=engine, id="chat-opts-engine")
            yield Label("Model:", classes="chat-opts-label")
            yield Input(value=model, id="chat-opts-model")
            yield Label("Agent type:", classes="chat-opts-label")
            yield Input(value=agent, id="chat-opts-agent")
            yield Label("Tools (comma-separated):", classes="chat-opts-label")
            yield Input(value=tools, id="chat-opts-tools")
            yield Label("System prompt:", classes="chat-opts-label")
            yield TextArea(system, id="chat-opts-system")
            with Horizontal(id="chat-opts-buttons"):
                yield Button("Start Chat  [Ctrl+S]", id="chat-opts-start", variant="success")
                yield Button("Cancel  [Esc]", id="chat-opts-cancel", variant="default")
            yield Static("", id="chat-opts-status")
        yield Footer()

    def action_cancel(self) -> None:
        """Dismiss without starting chat."""
        self.dismiss()

    @on(Button.Pressed, "#chat-opts-cancel")
    def on_cancel_btn(self) -> None:
        """Handle cancel button."""
        self.dismiss()

    def action_start_chat(self) -> None:
        """Collect inputs and launch jarvis chat."""
        self._launch_chat()

    @on(Button.Pressed, "#chat-opts-start")
    def on_start_btn(self) -> None:
        """Handle start chat button."""
        self._launch_chat()

    def _launch_chat(self) -> None:
        """Build AskingOpts from form inputs and launch chat via app.suspend()."""
        engine = self.query_one("#chat-opts-engine", Input).value.strip()
        model = self.query_one("#chat-opts-model", Input).value.strip()
        agent = self.query_one("#chat-opts-agent", Input).value.strip()
        tools = self.query_one("#chat-opts-tools", Input).value.strip()
        system = self.query_one("#chat-opts-system", TextArea).text.strip()

        opts = AskingOpts(
            engine=engine or self._default_engine,
            model=model or self._default_model,
            agent=agent or "orchestrator",
            tools=tools,
            system=system,
            jarvis=None,
        )
        jarvis_cmd = ["uv", "run", "jarvis"]
        cmd = jarvis_cmd + ["chat"] + opts.as_cli_chat_opts()
        env = os.environ.copy()
        self.dismiss()
        with self.app.suspend():
            subprocess.run(cmd, env=env)


# ---------------------------------------------------------------------------
# Generate Screen
# ---------------------------------------------------------------------------


class GenerateScreen(Screen[bool]):
    """Screen for generating a new assistant recipe."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_screen", "Back"),
    ]

    def __init__(self, engine: str, model: str, recipes_dir: str) -> None:
        """Initialize with LLM settings."""
        super().__init__()
        self._engine = engine
        self._model = model
        self._recipes_dir = recipes_dir

    def compose(self) -> ComposeResult:
        """Build the generate screen layout."""
        yield Header()
        with VerticalScroll():
            yield Label("Generate a new assistant recipe", id="gen-title")
            yield Label("Describe the assistant you want to create:", id="gen-label")
            yield Input(placeholder="e.g. An assistant that reviews code", id="gen-input")
            yield Button("Generate", id="gen-btn", variant="primary")
            yield Static("", id="gen-status")
        yield Footer()

    def action_dismiss_screen(self) -> None:
        """Dismiss screen without refreshing."""
        self.dismiss(False)

    @on(Button.Pressed, "#gen-btn")
    def on_gen_btn(self) -> None:
        """Handle generate button press."""
        query_widget = self.query_one("#gen-input", Input)
        query = query_widget.value.strip()
        if not query:
            self.query_one("#gen-status", Static).update("⚠ Please enter a query")
            return
        self.query_one("#gen-status", Static).update("⏳ Generating...")
        self.query_one("#gen-btn", Button).disabled = True
        self._do_generate(query)

    @work(thread=True)
    def _do_generate(self, query: str) -> None:
        """Run recipe generation in a background thread."""
        from .gen import generate_assistant, GenRequest

        req = GenRequest(engine=self._engine, model=self._model, query=query, recipes_dir=self._recipes_dir)
        r = generate_assistant(req)
        if r.success:
            self.app.call_from_thread(
                self.query_one("#gen-status", Static).update,
                f"✅ Recipe generated: `{r.name}`\nPath: {r.path}",
            )
            self.app.call_from_thread(self.dismiss, True)
        else:
            self.app.call_from_thread(
                self.query_one("#gen-status", Static).update,
                f"❌ Generation failed: {r.message}",
            )
            self.app.call_from_thread(setattr, self.query_one("#gen-btn", Button), "disabled", False)


# ---------------------------------------------------------------------------
# Resource tab (generic panel for Recipes / Agents / Tools)
# ---------------------------------------------------------------------------


class ResourceTab(Vertical):
    """A tab panel with search, sort, list, and detail area."""

    def __init__(self, tab_id: str, show_chat: bool = False) -> None:
        """Initialize the resource tab."""
        super().__init__()
        self._tab_id = tab_id
        self._show_chat = show_chat

    def compose(self) -> ComposeResult:
        """Build the resource tab layout."""
        tid = self._tab_id
        with Horizontal(id=f"{tid}-toolbar"):
            yield Input(placeholder="Filter by name...", id=f"{tid}-search")
            yield Button("LLM Search", id=f"{tid}-llm-btn", variant="default")
            yield Select(
                [(label, val) for label, val in _SORT_OPTIONS],
                id=f"{tid}-sort",
                value="alpha_asc",
                allow_blank=False,
            )
        with Horizontal(id=f"{tid}-body"):
            with Vertical(id=f"{tid}-sidebar"):
                yield ListView(id=f"{tid}-list")
            with VerticalScroll(id=f"{tid}-detail"):
                yield LoadingIndicator(id=f"{tid}-loading")
                yield Markdown("", id=f"{tid}-markdown")
                if self._show_chat:
                    yield Button("Chat with this recipe  [c]", id=f"{tid}-chat-btn", variant="success")


# ---------------------------------------------------------------------------
# Main TUI App
# ---------------------------------------------------------------------------


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

    LoadingIndicator {
        height: 3;
    }

    /* Chat button */
    #recipes-chat-btn {
        margin-top: 1;
        display: none;
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
        height: 10;
    }
    #chat-opts-buttons {
        margin: 1 2;
        height: 3;
    }
    #chat-opts-start {
        margin-right: 1;
    }
    #chat-opts-status {
        margin: 0 2;
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
        if now - self._last_ctrl_c < _CTRL_C_TIMEOUT:
            self.exit()
        else:
            self._last_ctrl_c = now
            self.notify("Press Ctrl+C again to quit", severity="warning", timeout=_CTRL_C_TIMEOUT)

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
        items = _filter_items(self._recipes, search)
        items = _sort_items(items, sort_key)
        self._displayed_recipes = items
        self._render_list("recipes", items)
        self._selected_recipe = None
        self.query_one("#recipes-chat-btn", Button).display = False

    def _render_agents(self) -> None:
        """Render the current (filtered + sorted) agent list."""
        sort_key = str(self.query_one("#agents-sort", Select).value)
        search = self.query_one("#agents-search", Input).value
        items = _filter_items(self._agents, search)
        items = _sort_items(items, sort_key)
        self._displayed_agents = items
        self._render_list("agents", items)

    def _render_tools(self) -> None:
        """Render the current (filtered + sorted) tool list."""
        sort_key = str(self.query_one("#tools-sort", Select).value)
        search = self.query_one("#tools-search", Input).value
        items = _filter_items(self._tools, search)
        items = _sort_items(items, sort_key)
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
        from .api import Script

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
        md = _recipe_markdown(r)
        self.query_one("#recipes-markdown", Markdown).update(md)
        self.query_one("#recipes-chat-btn", Button).display = True

    @on(ListView.Selected, "#agents-list")
    def on_agent_selected(self, event: ListView.Selected) -> None:
        """Show agent detail on selection."""
        idx = event.list_view.index
        if idx is None or idx >= len(self._displayed_agents):
            return
        a = self._displayed_agents[idx]
        md = _agent_markdown(a)
        self.query_one("#agents-markdown", Markdown).update(md)

    @on(ListView.Selected, "#tools-list")
    def on_tool_selected(self, event: ListView.Selected) -> None:
        """Show tool detail on selection."""
        idx = event.list_view.index
        if idx is None or idx >= len(self._displayed_tools):
            return
        t = self._displayed_tools[idx]
        md = _tool_markdown(t)
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
