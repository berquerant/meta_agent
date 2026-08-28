"""ChatOptionsScreen for the TUI."""

import shlex
from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static, TextArea

from ...api import Recipe
from ...asking import AskingOpts
from .chat import ChatScreen


class ChatOptionsScreen(Screen[None]):
    """Screen to review and override recipe settings before starting chat."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "start_chat", "Start Chat"),
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
                yield Button("Start Chat  [c]", id="chat-opts-start", variant="success")
                yield Button("Cancel  [Esc]", id="chat-opts-cancel", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the command preview after widgets are ready."""
        self._update_cmd_preview()

    # ------------------------------------------------------------------
    # Command preview
    # ------------------------------------------------------------------

    def _build_cmd_preview(self) -> str:
        """Build the meta_agent chat command string for display."""
        r = self._recipe
        try:
            engine = self.query_one("#chat-opts-engine", Input).value.strip()
            model = self.query_one("#chat-opts-model", Input).value.strip()
            agent = self.query_one("#chat-opts-agent", Input).value.strip()
            tools = self.query_one("#chat-opts-tools", Input).value.strip()
            system = self.query_one("#chat-opts-system", TextArea).text.strip()
        except Exception:
            return ""

        parts: list[str] = ["meta_agent", "chat", "--recipe", shlex.quote(r.name)]

        # Compare with recipe defaults and add option only if overridden
        rec_engine = r.engine_key or self._default_engine
        if engine and engine != rec_engine:
            parts.extend(["--engine", shlex.quote(engine)])

        rec_model = r.model or self._default_model
        if model and model != rec_model:
            parts.extend(["--model", shlex.quote(model)])

        rec_agent = r.agent_type or ""
        if agent and agent != rec_agent:
            parts.extend(["--agent", shlex.quote(agent)])

        rec_tools = ", ".join(r.tools) if r.tools else ""
        norm_tools = ",".join(t.strip() for t in tools.split(",") if t.strip())
        norm_rec_tools = ",".join(t.strip() for t in rec_tools.split(",") if t.strip())
        if tools and norm_tools != norm_rec_tools:
            parts.extend(["--tools", shlex.quote(norm_tools)])

        rec_system = (r.system_prompt or "").strip().replace("\r\n", "\n")
        norm_system = system.strip().replace("\r\n", "\n")
        if norm_system and norm_system != rec_system:
            display_system = norm_system if len(norm_system) <= 60 else norm_system[:60] + "..."
            parts.extend(["--system", shlex.quote(display_system)])

        head = " ".join(parts[:4])
        tail_items: list[str] = []
        i = 4
        while i < len(parts):
            if i + 1 < len(parts):
                tail_items.append(f"{parts[i]} {parts[i+1]}")
                i += 2
            else:
                tail_items.append(parts[i])
                i += 1

        tail = " \\\n  ".join(tail_items)
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
        """Collect inputs and launch in-TUI chat screen."""
        self._launch_chat()

    @on(Button.Pressed, "#chat-opts-start")
    def on_start_btn(self) -> None:
        """Handle start chat button."""
        self._launch_chat()

    def _launch_chat(self) -> None:
        """Build AskingOpts and transition to ChatScreen."""
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
        self.dismiss()
        self.app.push_screen(ChatScreen(self._recipe.name, opts))
