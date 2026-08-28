"""TUI for meta_agent using Textual."""

from dataclasses import asdict
from typing import Any, ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
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
    MarkdownViewer,
    Static,
    TabbedContent,
    TabPane,
)

from .api import list_agents, list_recipes, list_tools, Agent, Recipe, Tool
from .cmd import format_obj
from .gen import generate_assistant, GenRequest

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _obj_to_markdown(title: str, obj: dict[str, Any]) -> str:
    """Convert a dataclass dict to a Markdown string for display."""
    return format_obj(obj, "text")


def _recipe_markdown(r: Recipe) -> str:
    """Format recipe as markdown."""
    return _obj_to_markdown(r.name, asdict(r))


def _agent_markdown(a: Agent) -> str:
    """Format agent as markdown."""
    return _obj_to_markdown(a.name, asdict(a))


def _tool_markdown(t: Tool) -> str:
    """Format tool as markdown."""
    return _obj_to_markdown(t.name, asdict(t))


# ---------------------------------------------------------------------------
# Generate Screen
# ---------------------------------------------------------------------------


class GenerateScreen(Screen[None]):
    """Screen for generating a new assistant recipe."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss", "Back"),
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
        yield Label("Generate a new assistant recipe", id="gen-title")
        yield Label("Describe the assistant you want to create:", id="gen-label")
        yield Input(placeholder="e.g. An assistant that reviews code", id="gen-input")
        yield Button("Generate", id="gen-btn", variant="primary")
        yield Static("", id="gen-status")
        yield Footer()

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
        req = GenRequest(engine=self._engine, model=self._model, query=query, recipes_dir=self._recipes_dir)
        r = generate_assistant(req)
        if r.success:
            self.app.call_from_thread(
                self.query_one("#gen-status", Static).update,
                f"✅ Recipe generated: `{r.name}`\nPath: {r.path}",
            )
        else:
            self.app.call_from_thread(
                self.query_one("#gen-status", Static).update,
                f"❌ Generation failed: {r.message}",
            )
        self.app.call_from_thread(
            setattr,
            self.query_one("#gen-btn", Button),
            "disabled",
            False,
        )


# ---------------------------------------------------------------------------
# Main TUI App
# ---------------------------------------------------------------------------


class MetaAgentTUI(App[None]):
    """TUI application for meta_agent."""

    CSS = """
    #sidebar {
        width: 30;
        border-right: solid $primary;
        overflow-y: auto;
    }

    #detail {
        padding: 1 2;
    }

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
        color: $success;
    }

    LoadingIndicator {
        height: 3;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("q", "quit", "Quit"),
        Binding("g", "open_generate", "Generate Recipe"),
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

    def compose(self) -> ComposeResult:
        """Compose the main TUI layout."""
        yield Header()
        with TabbedContent(initial="tab-recipes"):
            with TabPane("Recipes", id="tab-recipes"):
                with Horizontal():
                    with Vertical(id="sidebar"):
                        yield ListView(id="recipe-list")
                    with Container(id="detail"):
                        yield LoadingIndicator(id="recipe-loading")
                        yield MarkdownViewer("", id="recipe-detail", show_table_of_contents=False)
            with TabPane("Agents", id="tab-agents"):
                with Horizontal():
                    with Vertical(id="sidebar"):
                        yield ListView(id="agent-list")
                    with Container(id="detail"):
                        yield LoadingIndicator(id="agent-loading")
                        yield MarkdownViewer("", id="agent-detail", show_table_of_contents=False)
            with TabPane("Tools", id="tab-tools"):
                with Horizontal():
                    with Vertical(id="sidebar"):
                        yield ListView(id="tool-list")
                    with Container(id="detail"):
                        yield LoadingIndicator(id="tool-loading")
                        yield MarkdownViewer("", id="tool-detail", show_table_of_contents=False)
        yield Footer()

    def on_mount(self) -> None:
        """Load all resources after mounting."""
        self._load_recipes()
        self._load_agents()
        self._load_tools()

    @work(thread=True)
    def _load_recipes(self) -> None:
        """Load recipes in a background thread."""
        recipes = list_recipes()
        self._recipes = recipes

        def _update() -> None:
            lv = self.query_one("#recipe-list", ListView)
            lv.clear()
            for r in recipes:
                lv.append(ListItem(Label(r.name)))
            self.query_one("#recipe-loading", LoadingIndicator).display = False

        self.app.call_from_thread(_update)

    @work(thread=True)
    def _load_agents(self) -> None:
        """Load agents in a background thread."""
        agents = list_agents()
        self._agents = agents

        def _update() -> None:
            lv = self.query_one("#agent-list", ListView)
            lv.clear()
            for a in agents:
                lv.append(ListItem(Label(a.name)))
            self.query_one("#agent-loading", LoadingIndicator).display = False

        self.app.call_from_thread(_update)

    @work(thread=True)
    def _load_tools(self) -> None:
        """Load tools in a background thread."""
        tools = list_tools()
        self._tools = tools

        def _update() -> None:
            lv = self.query_one("#tool-list", ListView)
            lv.clear()
            for t in tools:
                lv.append(ListItem(Label(t.name)))
            self.query_one("#tool-loading", LoadingIndicator).display = False

        self.app.call_from_thread(_update)

    @on(ListView.Selected, "#recipe-list")
    def on_recipe_selected(self, event: ListView.Selected) -> None:
        """Show recipe detail on selection."""
        idx = event.list_view.index
        if idx is None or idx >= len(self._recipes):
            return
        r = self._recipes[idx]
        md = _recipe_markdown(r)
        self.query_one("#recipe-detail", MarkdownViewer).document.update(md)

    @on(ListView.Selected, "#agent-list")
    def on_agent_selected(self, event: ListView.Selected) -> None:
        """Show agent detail on selection."""
        idx = event.list_view.index
        if idx is None or idx >= len(self._agents):
            return
        a = self._agents[idx]
        md = _agent_markdown(a)
        self.query_one("#agent-detail", MarkdownViewer).document.update(md)

    @on(ListView.Selected, "#tool-list")
    def on_tool_selected(self, event: ListView.Selected) -> None:
        """Show tool detail on selection."""
        idx = event.list_view.index
        if idx is None or idx >= len(self._tools):
            return
        t = self._tools[idx]
        md = _tool_markdown(t)
        self.query_one("#tool-detail", MarkdownViewer).document.update(md)

    def action_open_generate(self) -> None:
        """Open the recipe generation screen."""
        self.push_screen(GenerateScreen(self._engine, self._model, self._recipes_dir))


def run_tui(engine: str, model: str, recipes_dir: str) -> None:
    """Launch the TUI application."""
    app = MetaAgentTUI(engine=engine, model=model, recipes_dir=recipes_dir)
    app.run()
