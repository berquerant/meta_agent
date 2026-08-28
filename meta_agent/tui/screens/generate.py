"""GenerateScreen for the TUI."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from .help import HelpScreen


class GenerateScreen(Screen[bool]):
    """Screen for generating a new assistant recipe."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_screen", "Back", show=True),
        Binding("question_mark", "open_help", "Help (?)", show=True),
        Binding("f1", "open_help", "Help", show=False),
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

    def action_open_help(self) -> None:
        """Open the keyboard shortcuts help modal."""
        self.app.push_screen(HelpScreen())

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
        from ...gen import generate_assistant, GenRequest

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
