"""ChatOptionsScreen for the TUI."""

import shlex
from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static, TextArea

from ...api import list_agents, list_tools, Recipe
from ...asking import AskingOpts
from ...utils import copy_to_system_clipboard
from ..widgets import SearchableSelect
from .chat import ChatScreen


class ChatOptionsScreen(Screen[None]):
    """Screen to review and override recipe settings before starting chat."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "start_chat", "Start Chat"),
    ]

    def __init__(self, recipe: Recipe, default_engine: str, default_model: str, export_dir: str | None = None) -> None:
        """Initialize with recipe, TUI-level defaults, and export directory."""
        super().__init__()
        self._recipe = recipe
        self._default_engine = default_engine
        self._default_model = default_model
        self._export_dir = export_dir

        # Available options for dropdowns
        from openjarvis import Jarvis

        try:
            j = Jarvis(engine_key=self._default_engine)
            self._engine_options = [(e, e) for e in j.list_engines()]
            self._model_options = [(m, m) for m in j.list_models()]
            j.close()
        except Exception:
            self._engine_options = [
                ("ollama", "ollama"),
                ("vllm", "vllm"),
                ("cloud", "cloud"),
                ("litellm", "litellm"),
                ("llamacpp", "llamacpp"),
            ]
            self._model_options = [(default_model, default_model)]

        try:
            self._agent_options = [(a.name, a.name) for a in list_agents()]
        except Exception:
            self._agent_options = [
                ("orchestrator", "orchestrator"),
                ("native_react", "native_react"),
                ("simple", "simple"),
            ]

        try:
            self._all_tools = [t.name for t in list_tools()]
        except Exception:
            self._all_tools = ["file_read", "file_write", "bash", "calculator", "think", "web_search"]

    def compose(self) -> ComposeResult:
        """Build the chat options layout with quick selects."""
        r = self._recipe
        engine = r.engine_key or self._default_engine
        model = r.model or self._default_model
        agent = r.agent_type or "orchestrator"
        tools = ", ".join(r.tools) if r.tools else ""
        system = r.system_prompt or ""

        # Ensure active values are represented in options list
        engine_opts = list(self._engine_options)
        if engine and not any(opt[1] == engine for opt in engine_opts):
            engine_opts.insert(0, (engine, engine))

        model_opts = list(self._model_options)
        if model and not any(opt[1] == model for opt in model_opts):
            model_opts.insert(0, (model, model))

        agent_opts = list(self._agent_options)
        if agent and not any(opt[1] == agent for opt in agent_opts):
            agent_opts.insert(0, (agent, agent))

        yield Header()
        with VerticalScroll():
            yield Label(f"Chat with recipe: {r.name}", id="chat-opts-title")

            yield Label("Engine (Select preset or type custom):", classes="chat-opts-label")
            with Horizontal(classes="chat-opts-row"):
                yield SearchableSelect(engine_opts, value=engine, id="chat-opts-engine-select", allow_blank=True)
                yield Input(value=engine, id="chat-opts-engine", placeholder="Engine name")

            yield Label("Model (Select preset or type custom):", classes="chat-opts-label")
            with Horizontal(classes="chat-opts-row"):
                yield SearchableSelect(model_opts, value=model, id="chat-opts-model-select", allow_blank=True)
                yield Input(value=model, id="chat-opts-model", placeholder="Model name")

            yield Label("Agent type (Select preset or type custom):", classes="chat-opts-label")
            with Horizontal(classes="chat-opts-row"):
                yield SearchableSelect(agent_opts, value=agent, id="chat-opts-agent-select", allow_blank=True)
                yield Input(value=agent, id="chat-opts-agent", placeholder="Agent name")

            yield Label("Tools (Select to append or edit comma-separated):", classes="chat-opts-label")
            with Horizontal(classes="chat-opts-row"):
                yield SearchableSelect(
                    [(t, t) for t in self._all_tools],
                    id="chat-opts-tool-select",
                    prompt="Add tool...",
                    allow_blank=True,
                )
                yield Input(value=tools, id="chat-opts-tools", placeholder="e.g. file_read, think")

            yield Label("System prompt:", classes="chat-opts-label")
            yield TextArea(system, id="chat-opts-system")

            yield Label("Command that will be executed:", classes="chat-opts-label")
            yield Static("", id="chat-opts-cmd")

            with Horizontal(id="chat-opts-buttons"):
                yield Button("Start Chat  [c]", id="chat-opts-start", variant="success")
                yield Button("Copy Command", id="chat-opts-copy", variant="primary")
                yield Button("Cancel  [Esc]", id="chat-opts-cancel", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the command preview after widgets are ready."""
        self._update_cmd_preview()

    def on_key(self, event: events.Key) -> None:
        """Open select overlay if slash key is pressed on a focused Select widget."""
        if event.character == "/" and isinstance(self.focused, Select):
            event.prevent_default()
            event.stop()
            self.focused.action_show_overlay()

    # ------------------------------------------------------------------
    # Select <-> Input Synchronization
    # ------------------------------------------------------------------

    @on(Select.Changed, "#chat-opts-engine-select")
    def on_engine_select_changed(self, event: Select.Changed) -> None:
        """Update engine input when select changed."""
        if event.value is not Select.BLANK and event.value:
            self.query_one("#chat-opts-engine", Input).value = str(event.value)

    @on(Select.Changed, "#chat-opts-model-select")
    def on_model_select_changed(self, event: Select.Changed) -> None:
        """Update model input when select changed."""
        if event.value is not Select.BLANK and event.value:
            self.query_one("#chat-opts-model", Input).value = str(event.value)

    @on(Select.Changed, "#chat-opts-agent-select")
    def on_agent_select_changed(self, event: Select.Changed) -> None:
        """Update agent input when select changed."""
        if event.value is not Select.BLANK and event.value:
            self.query_one("#chat-opts-agent", Input).value = str(event.value)

    @on(Select.Changed, "#chat-opts-tool-select")
    def on_tool_select_changed(self, event: Select.Changed) -> None:
        """Append chosen tool to tools input."""
        if event.value is not Select.BLANK and event.value:
            tool_name = str(event.value)
            tools_inp = self.query_one("#chat-opts-tools", Input)
            current_tools = [t.strip() for t in tools_inp.value.split(",") if t.strip()]
            if tool_name not in current_tools:
                current_tools.append(tool_name)
                tools_inp.value = ", ".join(current_tools)

    # ------------------------------------------------------------------
    # Command preview & full command builder
    # ------------------------------------------------------------------

    def _build_cmd_parts(self, truncate_system: bool) -> list[str]:
        """Build the command parts list."""
        r = self._recipe
        try:
            engine = self.query_one("#chat-opts-engine", Input).value.strip()
            model = self.query_one("#chat-opts-model", Input).value.strip()
            agent = self.query_one("#chat-opts-agent", Input).value.strip()
            tools = self.query_one("#chat-opts-tools", Input).value.strip()
            system = self.query_one("#chat-opts-system", TextArea).text.strip()
        except Exception:
            return []

        parts: list[str] = ["meta_agent", "chat", "--recipe", shlex.quote(r.name)]

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
            if truncate_system and len(norm_system) > 60:
                display_system = norm_system[:60] + "..."
            else:
                display_system = norm_system
            parts.extend(["--system", shlex.quote(display_system)])

        return parts

    def _build_cmd_preview(self) -> str:
        """Build the meta_agent chat command string for display (truncated system)."""
        parts = self._build_cmd_parts(truncate_system=True)
        if not parts:
            return ""

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

    def _build_full_cmd(self) -> str:
        """Build the full meta_agent chat command string for clipboard without truncation."""
        parts = self._build_cmd_parts(truncate_system=False)
        return " ".join(parts)

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

    @on(Button.Pressed, "#chat-opts-copy")
    def on_copy_btn(self) -> None:
        """Handle copy button."""
        self._copy_command()

    def _copy_command(self) -> None:
        """Copy full command to clipboard and notify."""
        full_cmd = self._build_full_cmd()
        copied = copy_to_system_clipboard(full_cmd)
        if not copied:
            self.app.copy_to_clipboard(full_cmd)
        self.notify("Command copied to clipboard (untruncated system prompt)", severity="information")

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
        self.app.push_screen(ChatScreen(self._recipe.name, opts, export_dir=self._export_dir))
