"""Textual screens for the TUI: GenerateScreen and ChatOptionsScreen."""

import os
import shlex
import subprocess
from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static, TextArea

from ..api import Recipe
from ..asking import AskingOpts

# ---------------------------------------------------------------------------
# ChatOptionsScreen
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
            yield Label("Command that will be executed:", classes="chat-opts-label")
            yield Static("", id="chat-opts-cmd")
            with Horizontal(id="chat-opts-buttons"):
                yield Button("Start Chat  [Ctrl+S]", id="chat-opts-start", variant="success")
                yield Button("Cancel  [Esc]", id="chat-opts-cancel", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the command preview after widgets are ready."""
        self._update_cmd_preview()

    # ------------------------------------------------------------------
    # Command preview
    # ------------------------------------------------------------------

    def _build_cmd_preview(self) -> str:
        """Build the jarvis chat command string for display."""
        try:
            engine = self.query_one("#chat-opts-engine", Input).value.strip() or self._default_engine
            model = self.query_one("#chat-opts-model", Input).value.strip() or self._default_model
            agent = self.query_one("#chat-opts-agent", Input).value.strip() or "orchestrator"
            tools = self.query_one("#chat-opts-tools", Input).value.strip()
            system = self.query_one("#chat-opts-system", TextArea).text.strip()
        except Exception:
            return ""

        opts = AskingOpts(engine=engine, model=model, agent=agent, tools=tools, system=system, jarvis=None)
        base = ["uv", "run", "jarvis", "chat"]
        cli_opts = opts.as_cli_chat_opts()

        # Format as multi-line command for readability
        parts: list[str] = [shlex.quote(x) for x in base]
        i = 0
        while i < len(cli_opts):
            if cli_opts[i].startswith("--") and i + 1 < len(cli_opts):
                key = cli_opts[i]
                val = cli_opts[i + 1]
                display_val = val if len(val) <= 60 else val[:60] + "..."
                parts.append(f"{key} {shlex.quote(display_val)}")
                i += 2
            else:
                parts.append(shlex.quote(cli_opts[i]))
                i += 1

        head = " ".join(parts[:4])  # uv run jarvis chat
        tail = " \\\n  ".join(parts[4:])
        return f"{head} \\\n  {tail}" if tail else head

    def _update_cmd_preview(self) -> None:
        """Update the command preview Static widget."""
        try:
            preview = self._build_cmd_preview()
            self.query_one("#chat-opts-cmd", Static).update(preview)
        except Exception:
            pass

    @on(Input.Changed, "#chat-opts-engine")
    @on(Input.Changed, "#chat-opts-model")
    @on(Input.Changed, "#chat-opts-agent")
    @on(Input.Changed, "#chat-opts-tools")
    def on_input_changed(self) -> None:
        """Refresh command preview when any input changes."""
        self._update_cmd_preview()

    @on(TextArea.Changed, "#chat-opts-system")
    def on_system_changed(self) -> None:
        """Refresh command preview when system prompt changes."""
        self._update_cmd_preview()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

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
        cmd = ["uv", "run", "jarvis", "chat"] + opts.as_cli_chat_opts()
        env = os.environ.copy()
        self.dismiss()
        with self.app.suspend():
            subprocess.run(cmd, env=env)


# ---------------------------------------------------------------------------
# GenerateScreen
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
        from ..gen import generate_assistant, GenRequest

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
