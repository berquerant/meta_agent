"""ChatScreen for interactive multi-turn chat inside the TUI."""

import logging
from pathlib import Path
from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Markdown, RichLog, Static

from ...asking import AskingOpts
from ...utils import get_default_export_dir, now_str


class RichLogHandler(logging.Handler):
    """Logging handler that redirects logs to a Textual RichLog widget and an in-memory buffer."""

    def __init__(self, rich_log: RichLog, buffer: list[str]) -> None:
        """Initialize with target RichLog widget and log buffer."""
        super().__init__()
        self._rich_log = rich_log
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        """Format and write log record to RichLog and buffer."""
        try:
            msg = self.format(record)
            self._buffer.append(f"{record.levelname}: {record.name} - {record.getMessage()}")
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
    """Screen for interactive multi-turn chat with dedicated log window and export inside TUI."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_screen", "Back"),
        Binding("ctrl+e", "export_chat", "Export Chat"),
        Binding("ctrl+l", "export_logs", "Export Logs"),
    ]

    def __init__(self, recipe_name: str, opts: AskingOpts, export_dir: str | None = None) -> None:
        """Initialize with recipe name, resolved asking options, and export dir."""
        super().__init__()
        self._recipe_name = recipe_name
        self._opts = opts
        self._export_dir = export_dir or get_default_export_dir()
        self._history: list[tuple[str, str]] = []  # (role, text)
        self._log_buffer: list[str] = []
        self._log_handler: RichLogHandler | None = None

    def compose(self) -> ComposeResult:
        """Build the chat screen layout with draggable splitter and export buttons."""
        yield Header()
        with Horizontal(id="chat-screen-layout"):
            # Left pane: Recipe/agent info summary + Actions
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
                with Vertical(id="chat-sidebar-actions"):
                    yield Button("Export Chat", id="chat-export-btn", variant="primary")
                    yield Button("Export Logs", id="chat-export-logs-btn", variant="default")
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
        init_msg = "System initialized. Ready for chat session."
        log.write(f"[green]{init_msg}[/green]")
        self._log_buffer.append(f"INFO: system - {init_msg}")

        # Attach logging handler to capture httpx, openjarvis, and root logs
        handler = RichLogHandler(log, self._log_buffer)
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

    # ------------------------------------------------------------------
    # Export Chat & Logs
    # ------------------------------------------------------------------

    def action_export_chat(self) -> None:
        """Export chat conversation to markdown file."""
        self._do_export_chat()

    @on(Button.Pressed, "#chat-export-btn")
    def on_export_chat_btn(self) -> None:
        """Handle export chat button."""
        self._do_export_chat()

    def _do_export_chat(self) -> None:
        """Save chat conversation history to file."""
        if not self._history:
            self.notify("Chat history is empty", severity="warning")
            return

        out_dir = Path(self._export_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"chat_{self._recipe_name}_{now_str()}.md"
            filepath = out_dir / filename

            lines: list[str] = [
                f"# Chat Session: {self._recipe_name}\n",
                f"- **Engine**: {self._opts.engine}",
                f"- **Model**: {self._opts.model}",
                f"- **Agent**: {self._opts.agent}",
                f"- **Tools**: {self._opts.tools or 'none'}\n",
                "---\n",
            ]
            for role, text in self._history:
                lines.append(f"## 👤 {role}\n{text}\n")

            filepath.write_text("\n".join(lines), encoding="utf-8")
            self.notify(f"Chat exported to: {filepath}", severity="information")
        except Exception as e:
            self.notify(f"Failed to export chat: {e}", severity="error")

    def action_export_logs(self) -> None:
        """Export logs to log file."""
        self._do_export_logs()

    @on(Button.Pressed, "#chat-export-logs-btn")
    def on_export_logs_btn(self) -> None:
        """Handle export logs button."""
        self._do_export_logs()

    def _do_export_logs(self) -> None:
        """Save log buffer to file."""
        if not self._log_buffer:
            self.notify("Log buffer is empty", severity="warning")
            return

        out_dir = Path(self._export_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"logs_{self._recipe_name}_{now_str()}.log"
            filepath = out_dir / filename
            filepath.write_text("\n".join(self._log_buffer), encoding="utf-8")
            self.notify(f"Logs exported to: {filepath}", severity="information")
        except Exception as e:
            self.notify(f"Failed to export logs: {e}", severity="error")

    # ------------------------------------------------------------------
    # Message Submission & Agent Interaction
    # ------------------------------------------------------------------

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
        self._log_buffer.append(f"USER: {text}")
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

        # Build query including system prompt and prior conversation history
        prompt_parts: list[str] = []
        if self._opts.system:
            prompt_parts.append(f"# System Prompt\n{self._opts.system}\n")

        # Include past turns (excluding the current latest user query which was just added)
        prior_turns = self._history[:-1]
        if prior_turns:
            prompt_parts.append("# Conversation History")
            for role, text in prior_turns:
                prompt_parts.append(f"<{role}>\n{text}\n</{role}>")
            prompt_parts.append(f"\n# Current User Query\n{query}")
        else:
            if not self._opts.system:
                prompt_parts.append(query)
            else:
                prompt_parts.append(f"# User Query\n{query}")

        full_query = "\n\n".join(prompt_parts)

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
