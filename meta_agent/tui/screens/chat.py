"""ChatScreen for interactive multi-turn chat sessions inside the TUI with streaming and log capture."""

import asyncio
import logging
from pathlib import Path
from typing import ClassVar

from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Markdown, RichLog, Static

from ...asking import AskingOpts
from ...utils import get_default_export_dir, now_str
from ..helpers import build_chat_prompt, now_datetime_str
from .help import HelpScreen


class RichLogHandler(logging.Handler):
    """Logging handler that redirects logs to a Textual RichLog widget and an in-memory buffer."""

    def __init__(self, rich_log: RichLog, buffer: list[str]) -> None:
        """Initialize with target RichLog widget and log buffer."""
        super().__init__()
        self._rich_log = rich_log
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        """Format and write log record to RichLog and buffer with colored level tags and timestamp."""
        try:
            msg = self.format(record)
            ts = now_datetime_str()
            self._buffer.append(f"[{ts}] {record.levelname}: {record.name} - {record.getMessage()}")
            color = "white"
            if record.levelno >= logging.ERROR:
                color = "bold red"
            elif record.levelno >= logging.WARNING:
                color = "yellow"
            elif record.levelno >= logging.INFO:
                color = "blue"
            self._rich_log.app.call_from_thread(
                self._rich_log.write,
                f"[dim]{ts}[/dim] [{color}]{msg}[/{color}]",
            )
        except Exception:
            self.handleError(record)


class ChatScreen(Screen[None]):
    """Screen for interactive multi-turn chat with dedicated log window and export inside TUI."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_screen", "Back", show=True),
        Binding("ctrl+e", "export_chat", "Export Chat", show=True),
        Binding("ctrl+l", "export_logs", "Export Logs", show=True),
        Binding("question_mark", "open_help", "Help (?)", show=True),
        Binding("f1", "open_help", "Help", show=False),
    ]

    def __init__(
        self,
        recipe_name: str,
        opts: AskingOpts,
        export_dir: str | None = None,
        initial_history: list[tuple[str, str, str]] | None = None,
    ) -> None:
        """Initialize with recipe name, resolved asking options, and export dir."""
        super().__init__()
        self._recipe_name = recipe_name
        self._opts = opts
        self._export_dir = export_dir or get_default_export_dir()
        self._history: list[tuple[str, str, str]] = list(initial_history) if initial_history else []
        self._user_inputs: list[str] = [text for role, text, _ts in self._history if role == "User"]
        self._history_cursor: int = -1  # -1 indicates active/draft editing state
        self._current_draft: str = ""
        self._log_buffer: list[str] = []
        self._log_handler: RichLogHandler | None = None

    def compose(self) -> ComposeResult:
        """Build the chat screen layout with action buttons."""
        yield Header()
        with Horizontal(id="chat-screen-layout"):
            # Left pane: Recipe/agent info summary + Actions
            with Vertical(id="chat-info-sidebar"):
                yield Label(f"Recipe: {self._recipe_name}", id="chat-sidebar-title")
                yield Label(f"Engine: {self._opts.engine}", classes="chat-sidebar-item")
                yield Label(f"Model: {self._opts.model}", classes="chat-sidebar-item")
                yield Label(f"Agent: {self._opts.agent or 'direct engine'}", classes="chat-sidebar-item")
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
        if self._history:
            init_msg = f"System initialized. Resumed previous session with {len(self._history)} messages."
            self._render_chat()
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

    def action_open_help(self) -> None:
        """Open the keyboard shortcuts help modal."""
        self.app.push_screen(HelpScreen())

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
                f"- **Agent**: {self._opts.agent or 'direct engine'}",
                f"- **Tools**: {self._opts.tools or 'none'}",
            ]
            if self._opts.system:
                lines.append(f"- **System**: {self._opts.system}")
            lines.append("\n---\n")
            for role, text, ts in self._history:
                lines.append(f"## 👤 {role} [{ts}]\n{text}\n")

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
    # Message Submission, History Navigation & Agent Execution
    # ------------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Handle Up/Down arrow navigation for chat input history."""
        inp = self.query_one("#chat-input", Input)
        if not inp.has_focus or not self._user_inputs:
            return

        if event.key == "up":
            event.prevent_default()
            event.stop()
            if self._history_cursor == -1:
                self._current_draft = inp.value
                self._history_cursor = len(self._user_inputs) - 1
            elif self._history_cursor > 0:
                self._history_cursor -= 1

            inp.value = self._user_inputs[self._history_cursor]
            inp.cursor_position = len(inp.value)

        elif event.key == "down":
            event.prevent_default()
            event.stop()
            if self._history_cursor != -1:
                if self._history_cursor < len(self._user_inputs) - 1:
                    self._history_cursor += 1
                    inp.value = self._user_inputs[self._history_cursor]
                else:
                    self._history_cursor = -1
                    inp.value = self._current_draft
                inp.cursor_position = len(inp.value)

    @on(Button.Pressed, "#chat-send-btn")
    @on(Input.Submitted, "#chat-input")
    def on_submit(self) -> None:
        """Handle user message submission."""
        inp = self.query_one("#chat-input", Input)
        text = inp.value.strip()
        if not text:
            return
        inp.value = ""
        self._user_inputs.append(text)
        self._history_cursor = -1
        self._current_draft = ""

        ts = now_datetime_str()
        self._history.append(("User", text, ts))
        self._render_chat()
        self.query_one("#chat-status-bar", Static).update("⏳ Generating assistant response...")
        self.query_one("#chat-send-btn", Button).disabled = True

        log = self.query_one("#chat-rich-log", RichLog)
        log.write(f"[dim]{ts}[/dim] [cyan]> User prompt sent ({len(text)} chars)[/cyan]")
        self._log_buffer.append(f"[{ts}] USER: {text}")
        self._ask_agent(text)

    def _render_chat(self, streaming_response: str | None = None) -> None:
        """Render all messages in markdown, optionally including streaming response."""
        md_lines: list[str] = ["# Chat Session\n"]
        for role, text, ts in self._history:
            if role == "User":
                md_lines.append(f"### 👤 User <small style='color:gray;'>({ts})</small>\n{text}\n")
            else:
                md_lines.append(f"### 🤖 Assistant <small style='color:gray;'>({ts})</small>\n{text}\n")
        if streaming_response is not None:
            curr_ts = now_datetime_str()
            prefix = f"### 🤖 Assistant <small style='color:gray;'>({curr_ts})</small>\n"
            md_lines.append(f"{prefix}{streaming_response} ▌\n")

        self.query_one("#chat-markdown", Markdown).update("\n".join(md_lines))
        scroll = self.query_one("#chat-messages", VerticalScroll)
        scroll.scroll_end(animate=False)

    @work(thread=True)
    def _ask_agent(self, query: str) -> None:
        """Query Jarvis agent in a background thread with progressive/streaming updates."""
        from openjarvis import Jarvis

        log = self.query_one("#chat-rich-log", RichLog)
        tools_list = [t.strip() for t in self._opts.tools.split(",") if t.strip()]

        agent_mode = bool(self._opts.agent and self._opts.agent not in ("simple", "none", "direct"))
        agent_label = self._opts.agent if agent_mode else "direct engine"

        ts_start = now_datetime_str()
        log_msg = (
            f"[dim]{ts_start}[/dim] [yellow]Calling {agent_label} with '{self._opts.model}' "
            f"(tools: {len(tools_list)})...[/yellow]"
        )
        self.app.call_from_thread(log.write, log_msg)

        full_query = build_chat_prompt(self._opts.system, self._history, query)
        j = Jarvis(model=self._opts.model, engine_key=self._opts.engine)

        content = ""
        try:
            if not agent_mode:
                # Direct engine mode: streaming token response
                async def _run_stream() -> str:
                    parts: list[str] = []
                    async for token in j.ask_stream(full_query):
                        parts.append(token)
                        curr_text = "".join(parts)
                        self.app.call_from_thread(self._render_chat, curr_text)
                    return "".join(parts)

                content = asyncio.run(_run_stream())
                ts_done = now_datetime_str()
                self.app.call_from_thread(
                    log.write,
                    f"[dim]{ts_done}[/dim] [green]✓ Direct engine streaming response completed.[/green]",
                )
            else:
                # Agent mode: run agent and report tools execution
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
                    ts_tr = now_datetime_str()
                    tr_msg = (
                        f"[dim]{ts_tr}[/dim] [{status_color}]Tool executed: "
                        f"{tool_name} (success={success})[/{status_color}]"
                    )
                    self.app.call_from_thread(log.write, tr_msg)
                ts_done = now_datetime_str()
                self.app.call_from_thread(
                    log.write,
                    f"[dim]{ts_done}[/dim] [green]✓ Agent execution completed.[/green]",
                )
        except Exception as e:
            content = f"⚠️ Error: {e}"
            ts_err = now_datetime_str()
            self.app.call_from_thread(
                log.write,
                f"[dim]{ts_err}[/dim] [bold red]✗ Execution failed: {e}[/bold red]",
            )
        finally:
            j.close()

        def _done() -> None:
            ts_resp = now_datetime_str()
            self._history.append(("Assistant", content, ts_resp))
            self._render_chat()
            self.query_one("#chat-status-bar", Static).update("")
            self.query_one("#chat-send-btn", Button).disabled = False
            self.query_one("#chat-input", Input).focus()

        self.app.call_from_thread(_done)
