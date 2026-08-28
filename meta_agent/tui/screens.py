"""Textual screens for the TUI: GenerateScreen, ChatOptionsScreen, and ChatScreen."""

import shlex
from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, LoadingIndicator, Markdown, Static, TextArea

from ..api import Recipe
from ..asking import AskingOpts

# ---------------------------------------------------------------------------
# ChatScreen (Interactive In-TUI multi-turn chat)
# ---------------------------------------------------------------------------


class ChatScreen(Screen[None]):
    """Screen for interactive multi-turn chat inside the TUI."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_screen", "Back"),
    ]

    def __init__(self, recipe_name: str, opts: AskingOpts) -> None:
        """Initialize with recipe name and resolved asking options."""
        super().__init__()
        self._recipe_name = recipe_name
        self._opts = opts
        self._history: list[tuple[str, str]] = []  # (role, text)

    def compose(self) -> ComposeResult:
        """Build the chat screen layout."""
        yield Header()
        with Horizontal(id="chat-screen-layout"):
            # Left pane: Recipe/agent info summary
            with Vertical(id="chat-info-sidebar"):
                yield Label(f"Recipe: {self._recipe_name}", id="chat-sidebar-title")
                yield Label(f"Engine: {self._opts.engine}", classes="chat-sidebar-item")
                yield Label(f"Model: {self._opts.model}", classes="chat-sidebar-item")
                yield Label(f"Agent: {self._opts.agent}", classes="chat-sidebar-item")
                if self._opts.tools:
                    yield Label(f"Tools: {self._opts.tools}", classes="chat-sidebar-item")
                if self._opts.system:
                    yield Label("System Prompt:", classes="chat-sidebar-item")
                    yield VerticalScroll(Markdown(self._opts.system), id="chat-sidebar-prompt")
                yield Button("Back  [Esc]", id="chat-back-btn", variant="default")

            # Right pane: Chat history + Input area
            with Vertical(id="chat-main-pane"):
                with VerticalScroll(id="chat-messages"):
                    yield Markdown("# Chat Session Started\nType a message below to begin.", id="chat-markdown")
                yield LoadingIndicator(id="chat-loading")
                with Horizontal(id="chat-input-bar"):
                    yield Input(placeholder="Type your message here...", id="chat-input")
                    yield Button("Send", id="chat-send-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        """Configure initial widget state."""
        self.query_one("#chat-loading", LoadingIndicator).display = False
        self.query_one("#chat-input", Input).focus()

    def action_dismiss_screen(self) -> None:
        """Dismiss chat screen."""
        self.dismiss()

    @on(Button.Pressed, "#chat-back-btn")
    def on_back_btn(self) -> None:
        """Handle back button."""
        self.dismiss()

    @on(Button.Pressed, "#chat-send-btn")
    @on(Input.Submitted, "#chat-input")
    def on_submit(self) -> None:
        """Handle user message submission."""
        inp = self.query_one("#chat-input", Input)
        text = inp.value.strip()
        if not text:
            return
        inp.value = ""
        self._history.append(("User", text))
        self._render_chat()
        self.query_one("#chat-loading", LoadingIndicator).display = True
        self.query_one("#chat-send-btn", Button).disabled = True
        self._ask_agent(text)

    def _render_chat(self) -> None:
        """Render all messages in markdown."""
        md_lines: list[str] = ["# Chat Session\n"]
        for role, text in self._history:
            if role == "User":
                md_lines.append(f"### 👤 User\n{text}\n")
            else:
                md_lines.append(f"### 🤖 Assistant\n{text}\n")
        self.query_one("#chat-markdown", Markdown).update("\n".join(md_lines))
        # Scroll to bottom
        scroll = self.query_one("#chat-messages", VerticalScroll)
        scroll.scroll_end(animate=False)

    @work(thread=True)
    def _ask_agent(self, query: str) -> None:
        """Query Jarvis agent in a background thread."""
        from openjarvis import Jarvis

        tools_list = [t.strip() for t in self._opts.tools.split(",") if t.strip()]
        full_query = query
        if self._opts.system and not self._history[:-1]:
            # First turn: prepend system prompt instruction
            full_query = f"{self._opts.system}\n\n# User Query\n{query}"

        j = Jarvis(model=self._opts.model, engine_key=self._opts.engine)
        try:
            res = j.ask_full(
                full_query,
                agent=self._opts.agent or "orchestrator",
                tools=tools_list,
            )
            content = str(res.get("content", ""))
        except Exception as e:
            content = f"⚠️ Error: {e}"
        finally:
            j.close()

        def _done() -> None:
            self._history.append(("Assistant", content))
            self._render_chat()
            self.query_one("#chat-loading", LoadingIndicator).display = False
            self.query_one("#chat-send-btn", Button).disabled = False
            self.query_one("#chat-input", Input).focus()

        self.app.call_from_thread(_done)


# ---------------------------------------------------------------------------
# ChatOptionsScreen
# ---------------------------------------------------------------------------


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
