"""ChatOptionsScreen for reviewing and customizing recipe parameters before starting a chat session."""

from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static, TextArea

from ...api import Recipe
from ...asking import AskingOpts
from ...utils import copy_to_system_clipboard
from ..helpers import build_chat_command_parts, fetch_runtime_options, format_command_preview
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
        self._runtime_options = fetch_runtime_options(default_engine, default_model)

    def compose(self) -> ComposeResult:
        """Build the chat options layout with quick selects."""
        r = self._recipe
        engine = r.engine_key or self._default_engine
        model = r.model or self._default_model
        agent = r.agent_type or "orchestrator"
        tools = ", ".join(r.tools) if r.tools else ""
        system = r.system_prompt or ""

        # Ensure active recipe values exist in dropdown options
        engine_opts = list(self._runtime_options.engines)
        if engine and not any(opt[1] == engine for opt in engine_opts):
            engine_opts.insert(0, (engine, engine))

        model_opts = list(self._runtime_options.models)
        if model and not any(opt[1] == model for opt in model_opts):
            model_opts.insert(0, (model, model))

        agent_opts = list(self._runtime_options.agents)
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
                    [(t, t) for t in self._runtime_options.tools],
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
    # Command Preview & Execution Helpers
    # ------------------------------------------------------------------

    def _get_current_inputs(self) -> tuple[str, str, str, str, str]:
        """Read current user values from input widgets."""
        return (
            self.query_one("#chat-opts-engine", Input).value.strip(),
            self.query_one("#chat-opts-model", Input).value.strip(),
            self.query_one("#chat-opts-agent", Input).value.strip(),
            self.query_one("#chat-opts-tools", Input).value.strip(),
            self.query_one("#chat-opts-system", TextArea).text.strip(),
        )

    def _update_cmd_preview(self) -> None:
        """Update the command preview Static widget."""
        try:
            engine, model, agent, tools, system = self._get_current_inputs()
            parts = build_chat_command_parts(
                recipe=self._recipe,
                engine=engine,
                model=model,
                agent=agent,
                tools=tools,
                system=system,
                default_engine=self._default_engine,
                default_model=self._default_model,
                truncate_system=True,
            )
            preview = format_command_preview(parts)
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
    # Screen Actions
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
        """Copy full command (untruncated) to system clipboard and notify."""
        engine, model, agent, tools, system = self._get_current_inputs()
        parts = build_chat_command_parts(
            recipe=self._recipe,
            engine=engine,
            model=model,
            agent=agent,
            tools=tools,
            system=system,
            default_engine=self._default_engine,
            default_model=self._default_model,
            truncate_system=False,
        )
        full_cmd = " ".join(parts)
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
        engine, model, agent, tools, system = self._get_current_inputs()
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
