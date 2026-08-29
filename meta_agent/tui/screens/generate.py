"""GenerateScreen for interactive recipe generation inside the TUI."""

from pathlib import Path
from typing import Any, ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Markdown, RichLog, Static, TextArea

from ...gen import generate_assistant, GenRequest
from .chat_options import ChatOptionsScreen
from .help import HelpScreen


class GenerateScreen(Screen[bool]):
    """Screen for generating a new assistant recipe with live logs and instant preview."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_screen", "Back", show=True),
        Binding("question_mark", "open_help", "Help (?)", show=True),
        Binding("f1", "open_help", "Help", show=False),
    ]

    def __init__(self, engine: str, model: str, recipes_dir: str, export_dir: str | None = None) -> None:
        """Initialize with LLM settings, target directory, and export directory."""
        super().__init__()
        self._engine = engine
        self._model = model
        self._recipes_dir = recipes_dir
        self._export_dir = export_dir
        self._user_inputs: list[str] = []
        self._history_cursor: int = -1
        self._current_draft: str = ""
        self._generated_recipe_name: str | None = None

    def compose(self) -> ComposeResult:
        """Build the 2-pane generate screen layout."""
        yield Header()
        with Horizontal(id="gen-screen-layout"):
            # Left Sidebar: Config summary & Actions
            with Vertical(id="gen-sidebar"):
                yield Label("Recipe Generator", id="gen-sidebar-title")
                yield Label(f"Engine: {self._engine}", classes="gen-sidebar-item")
                yield Label(f"Model: {self._model}", classes="gen-sidebar-item")
                yield Label(f"Output: {self._recipes_dir}", classes="gen-sidebar-item")
                with Vertical(id="gen-sidebar-actions"):
                    yield Button("Chat with Recipe", id="gen-chat-btn", variant="success")
                    yield Button("Back  [Esc]", id="gen-back-btn", variant="default")

            # Right Main Pane: Recipe Preview + RichLog + Input Bar
            with Vertical(id="gen-main-pane"):
                with VerticalScroll(id="gen-preview-scroll"):
                    yield Markdown(
                        "# Assistant Recipe Generator\n"
                        "Describe the assistant you want to create below.\n"
                        "The meta-agent will inspect available tools/agents and generate a complete TOML recipe.",
                        id="gen-markdown",
                    )
                with Vertical(id="gen-log-pane"):
                    yield Label("Generation / Meta-Agent Activity Logs", id="gen-log-title")
                    yield RichLog(id="gen-rich-log", highlight=True, markup=True)
                yield Static("", id="gen-status-bar")
                with Horizontal(id="gen-input-bar"):
                    yield TextArea(
                        placeholder="Describe the assistant to create... (Enter: newline, Ctrl+J / Send: generate)",
                        show_line_numbers=False,
                        soft_wrap=True,
                        tab_behavior="focus",
                        id="gen-input",
                    )
                    yield Button("Generate  [Ctrl+J]", id="gen-submit-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        """Focus input on mount and initialize button states."""
        self.query_one("#gen-input", TextArea).focus()
        self.query_one("#gen-chat-btn", Button).display = False
        log = self.query_one("#gen-rich-log", RichLog)
        log.write("[green]Meta-agent ready. Enter a prompt below to generate a new assistant recipe.[/green]")

    def action_dismiss_screen(self) -> None:
        """Dismiss screen."""
        self.dismiss(bool(self._generated_recipe_name))

    def action_open_help(self) -> None:
        """Open keyboard shortcuts help modal."""
        self.app.push_screen(HelpScreen())

    @on(Button.Pressed, "#gen-back-btn")
    def on_back_btn(self) -> None:
        """Handle back button."""
        self.dismiss(bool(self._generated_recipe_name))

    @on(Button.Pressed, "#gen-chat-btn")
    def on_chat_btn(self) -> None:
        """Open chat options for newly generated recipe."""
        if not self._generated_recipe_name:
            return
        from ...api import list_recipes

        for r in list_recipes():
            if r.name == self._generated_recipe_name:
                self.dismiss(True)
                self.app.push_screen(ChatOptionsScreen(r, self._engine, self._model, export_dir=self._export_dir))
                return

    # ------------------------------------------------------------------
    # Prompt Input & History Navigation
    # ------------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Handle submission via Ctrl+J/Ctrl+Enter and Up/Down history navigation for generation input."""
        inp = self.query_one("#gen-input", TextArea)
        if not inp.has_focus:
            return

        if event.key in ("ctrl+j", "ctrl+enter", "ctrl+s"):
            event.prevent_default()
            event.stop()
            self.on_submit()
            return

        if not self._user_inputs:
            return

        if event.key == "up" and inp.cursor_location[0] == 0:
            event.prevent_default()
            event.stop()
            if self._history_cursor == -1:
                self._current_draft = inp.text
                self._history_cursor = len(self._user_inputs) - 1
            elif self._history_cursor > 0:
                self._history_cursor -= 1

            inp.load_text(self._user_inputs[self._history_cursor])
            inp.move_cursor((inp.document.line_count - 1, len(inp.document.lines[-1])))

        elif event.key == "down" and inp.cursor_location[0] == inp.document.line_count - 1:
            event.prevent_default()
            event.stop()
            if self._history_cursor != -1:
                if self._history_cursor < len(self._user_inputs) - 1:
                    self._history_cursor += 1
                    inp.load_text(self._user_inputs[self._history_cursor])
                else:
                    self._history_cursor = -1
                    inp.load_text(self._current_draft)
                inp.move_cursor((inp.document.line_count - 1, len(inp.document.lines[-1])))

    @on(Button.Pressed, "#gen-submit-btn")
    def on_submit(self) -> None:
        """Handle generate request submission."""
        inp = self.query_one("#gen-input", TextArea)
        query = inp.text.strip()
        if not query:
            return
        inp.clear()
        self._user_inputs.append(query)
        self._history_cursor = -1
        self._current_draft = ""

        status_msg = "⏳ Generating assistant recipe (you can leave this screen anytime)..."
        self.query_one("#gen-status-bar", Static).update(status_msg)
        self.query_one("#gen-submit-btn", Button).disabled = True
        self.query_one("#gen-chat-btn", Button).display = False

        log = self.query_one("#gen-rich-log", RichLog)
        log.write(f"[cyan]> Generation started: '{query}'[/cyan]")

        # Launch worker on App so it continues even if user navigates back
        app = self.app
        app.run_worker(
            lambda: self._execute_generation(query, app),
            thread=True,
            name=f"recipe_gen_{query[:20]}",
        )

    def _execute_generation(self, query: str, app: Any) -> None:
        """Run recipe generation in background worker."""
        req = GenRequest(engine=self._engine, model=self._model, query=query, recipes_dir=self._recipes_dir)
        r = generate_assistant(req)

        if r.success:
            self._generated_recipe_name = r.name
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
                # If the screen is still mounted, update its widgets
                if self.is_mounted:
                    try:
                        self.query_one("#gen-markdown", Markdown).update(preview_md)
                        self.query_one("#gen-status-bar", Static).update(f"✅ Generated `{r.name}` successfully!")
                        self.query_one("#gen-submit-btn", Button).disabled = False
                        self.query_one("#gen-chat-btn", Button).display = True
                        log = self.query_one("#gen-rich-log", RichLog)
                        log.write(f"[bold green]✓ Successfully generated recipe: {r.name}[/bold green]")
                    except Exception:
                        pass
                app.notify(f"Recipe generated: {r.name}", severity="information")
                # Reload recipes in main app
                if hasattr(app, "_load_recipes"):
                    app._load_recipes()

            app.call_from_thread(_on_success)
        else:

            def _on_failure() -> None:
                if self.is_mounted:
                    try:
                        self.query_one("#gen-status-bar", Static).update(f"❌ Failed: {r.message}")
                        self.query_one("#gen-submit-btn", Button).disabled = False
                        log = self.query_one("#gen-rich-log", RichLog)
                        log.write(f"[bold red]✗ Generation failed: {r.message}[/bold red]")
                    except Exception:
                        pass
                app.notify(f"Generation failed: {r.message}", severity="error")

            app.call_from_thread(_on_failure)
