"""ChatScreen for interactive multi-turn chat inside the TUI."""

import logging
from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Markdown, RichLog, Static

from ...asking import AskingOpts


class RichLogHandler(logging.Handler):
    """Logging handler that redirects logs to a Textual RichLog widget."""

    def __init__(self, rich_log: RichLog) -> None:
        """Initialize with target RichLog widget."""
        super().__init__()
        self._rich_log = rich_log

    def emit(self, record: logging.LogRecord) -> None:
        """Format and write log record to RichLog."""
        try:
            msg = self.format(record)
            color = "white"
            if record.levelno >= logging.ERROR:
                color = "bold red"
            elif record.levelno >= logging.WARNING:
                color = "yellow"
            elif record.levelno >= logging.INFO:
                color = "blue"
            self._rich_log.app.call_from_thread(
                self._rich_log.write,
                f"[{color}]{msg}[/{color}]",
            )
        except Exception:
            self.handleError(record)


class ChatScreen(Screen[None]):
    """Screen for interactive multi-turn chat with dedicated log window inside TUI."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_screen", "Back"),
    ]

    def __init__(self, recipe_name: str, opts: AskingOpts) -> None:
        """Initialize with recipe name and resolved asking options."""
        super().__init__()
        self._recipe_name = recipe_name
        self._opts = opts
        self._history: list[tuple[str, str]] = []  # (role, text)
        self._log_handler: RichLogHandler | None = None

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

            # Right pane: Chat history + Dedicated Log View + Input area
            with Vertical(id="chat-main-pane"):
                with VerticalScroll(id="chat-messages"):
                    yield Markdown("# Chat Session Started\nType a message below to begin.", id="chat-markdown")
                with Vertical(id="chat-log-pane"):
                    yield Label("Activity / Execution Logs", id="chat-log-title")
                    yield RichLog(id="chat-rich-log", highlight=True, markup=True)
                yield Static("", id="chat-status-bar")
                with Horizontal(id="chat-input-bar"):
                    yield Input(placeholder="Type your message here...", id="chat-input")
                    yield Button("Send", id="chat-send-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        """Configure initial widget state and hook logging."""
        self.query_one("#chat-input", Input).focus()
        log = self.query_one("#chat-rich-log", RichLog)
        log.write("[green]System initialized. Ready for chat session.[/green]")

        # Attach logging handler to capture httpx, openjarvis, and root logs
        handler = RichLogHandler(log)
        formatter = logging.Formatter("%(levelname)s: %(name)s - %(message)s")
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)
        self._log_handler = handler

    def on_unmount(self) -> None:
        """Clean up logging handler on exit."""
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler = None

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
        self.query_one("#chat-status-bar", Static).update("⏳ Generating assistant response...")
        self.query_one("#chat-send-btn", Button).disabled = True

        log = self.query_one("#chat-rich-log", RichLog)
        log.write(f"[cyan]> User prompt sent ({len(text)} chars)[/cyan]")
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
        scroll = self.query_one("#chat-messages", VerticalScroll)
        scroll.scroll_end(animate=False)

    @work(thread=True)
    def _ask_agent(self, query: str) -> None:
        """Query Jarvis agent in a background thread."""
        from openjarvis import Jarvis

        log = self.query_one("#chat-rich-log", RichLog)
        tools_list = [t.strip() for t in self._opts.tools.split(",") if t.strip()]

        self.app.call_from_thread(
            log.write,
            f"[yellow]Calling agent '{self._opts.agent}' with '{self._opts.model}' "
            f"(tools: {len(tools_list)})...[/yellow]",
        )

        full_query = query
        if self._opts.system and len(self._history) <= 1:
            full_query = f"{self._opts.system}\n\n# User Query\n{query}"

        j = Jarvis(model=self._opts.model, engine_key=self._opts.engine)
        try:
            res = j.ask_full(
                full_query,
                agent=self._opts.agent or "orchestrator",
                tools=tools_list,
            )
            content = str(res.get("content", ""))
            tool_results = res.get("tool_results", [])
            for tr in tool_results:
                tool_name = tr.get("tool_name", "unknown")
                success = tr.get("success", True)
                status_color = "green" if success else "red"
                self.app.call_from_thread(
                    log.write,
                    f"[{status_color}]Tool executed: {tool_name} (success={success})[/{status_color}]",
                )
            self.app.call_from_thread(
                log.write,
                "[green]✓ Agent response successfully received.[/green]",
            )
        except Exception as e:
            content = f"⚠️ Error: {e}"
            self.app.call_from_thread(
                log.write,
                f"[bold red]✗ Agent execution failed: {e}[/bold red]",
            )
        finally:
            j.close()

        def _done() -> None:
            self._history.append(("Assistant", content))
            self._render_chat()
            self.query_one("#chat-status-bar", Static).update("")
            self.query_one("#chat-send-btn", Button).disabled = False
            self.query_one("#chat-input", Input).focus()

        self.app.call_from_thread(_done)
