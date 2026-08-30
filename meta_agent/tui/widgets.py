"""Custom Textual widgets for the TUI."""

from typing import Any, ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Label,
    ListView,
    LoadingIndicator,
    Markdown,
    RichLog,
    Select,
    Static,
    TextArea,
)
from textual.widgets._footer import FooterKey
from textual.widgets._select import SelectOverlay


class OrderedFooter(Footer):
    """Custom Footer ensuring Help is always positioned on the far left."""

    def compose(self) -> ComposeResult:
        """Compose footer keys with Help always on the far left."""
        if not self._bindings_ready:
            return
        items = list(super().compose())

        def _sort_order(w: Any) -> int:
            if isinstance(w, FooterKey):
                if w.key in ("ctrl+h", "question_mark", "f1"):
                    return 0
                if w.key in ("escape", "back"):
                    return 1
                if w.key == "ctrl+f":
                    return 2
                if w.key == "ctrl+c":
                    return 3
                if w.key == "ctrl+s":
                    return 4
                if w.key == "ctrl+k":
                    return 5
                if w.key == "ctrl+g":
                    return 6
                if w.key == "ctrl+q":
                    return 7
            return 10

        yield from sorted(items, key=_sort_order)


class SearchableSelectOverlay(SelectOverlay):
    """Select overlay that displays the current search query in its border title."""

    def on_mount(self) -> None:
        """Initialize and set border title."""
        super().on_mount()
        self.border_title = "Type to search..."

    def watch_has_focus(self, value: bool) -> None:
        """Reset search query and update border title on focus change."""
        super().watch_has_focus(value)
        self.border_title = "Type to search..."

    async def _on_key(self, event: events.Key) -> None:
        """Handle key press, update search query display, and filter."""
        await super()._on_key(event)
        if self._search_query:
            self.border_title = f"Search: '{self._search_query}'"
        else:
            self.border_title = "Type to search..."


class SearchableSelect(Select[Any]):
    """Select widget with live search query display in its overlay."""

    def compose(self) -> ComposeResult:
        """Compose select with SearchableSelectOverlay."""
        from textual.widgets._select import SelectCurrent

        yield SelectCurrent(self.prompt)
        yield SearchableSelectOverlay(type_to_search=self._type_to_search).data_bind(compact=Select.compact)


class PromptTextArea(TextArea):
    """Custom TextArea allowing App-level navigation bindings (Ctrl+[, Ctrl+]) to pass through."""

    BINDINGS = [
        *TextArea.BINDINGS,
        ("ctrl+left_square_bracket", "app.previous_tab", "Previous Tab"),
        ("ctrl+right_square_bracket", "app.next_tab", "Next Tab"),
    ]

    async def _on_key(self, event: events.Key) -> None:
        """Forward tab navigation shortcuts to app navigation actions."""
        if event.key in ("ctrl+left", "ctrl+left_square_bracket", "ctrl+[", "ctrl__"):
            event.stop()
            event.prevent_default()
            await self.app.run_action("previous_tab")
            return
        elif event.key in ("ctrl+right", "ctrl+right_square_bracket", "ctrl+]"):
            event.stop()
            event.prevent_default()
            await self.app.run_action("next_tab")
            return
        await super()._on_key(event)


class ResourceTab(Vertical):
    """A tab panel with search, sort, list, and detail area."""

    def __init__(self, tab_id: str, show_chat: bool = False) -> None:
        """Initialize the resource tab."""
        super().__init__()
        self._tab_id = tab_id
        self._show_chat = show_chat

    def compose(self) -> ComposeResult:
        """Build the resource tab layout."""
        tid = self._tab_id
        with Horizontal(id=f"{tid}-toolbar"):
            yield PromptTextArea(
                placeholder="Search or ask LLM...  [Ctrl+J to ask]",
                show_line_numbers=False,
                soft_wrap=True,
                tab_behavior="focus",
                id=f"{tid}-search",
            )
            yield Button("Ask LLM", id=f"{tid}-llm-btn", variant="default")
        with Horizontal(id=f"{tid}-body"):
            with Vertical(id=f"{tid}-sidebar"):
                yield ListView(id=f"{tid}-list")
            with Vertical(id=f"{tid}-main-pane"):
                with VerticalScroll(id=f"{tid}-detail"):
                    with Horizontal(classes="pane-header"):
                        yield Label("Description & Details", classes="pane-title")
                        yield Button(
                            "^o",
                            id=f"{tid}-detail-max-btn",
                            classes="pane-max-btn",
                            tooltip="Toggle Fullscreen (Ctrl+O)",
                        )
                    yield LoadingIndicator(id=f"{tid}-loading")
                    yield Markdown("", id=f"{tid}-markdown")
                    if self._show_chat:
                        with Horizontal(id=f"{tid}-actions"):
                            yield Button("Chat with this recipe  [Ctrl+C]", id=f"{tid}-chat-btn", variant="success")
                            yield Button("Edit  [Ctrl+E]", id=f"{tid}-edit-btn", variant="default")
                            yield Button("Delete  [Ctrl+D]", id=f"{tid}-delete-btn", variant="error")
                with Vertical(id=f"{tid}-log-pane"):
                    with Horizontal(classes="pane-header"):
                        yield Label("Activity / Event Logs", classes="pane-title")
                        yield Button(
                            "^l", id=f"{tid}-log-max-btn", classes="pane-max-btn", tooltip="Toggle Fullscreen (Ctrl+L)"
                        )
                    yield RichLog(id=f"{tid}-rich-log", highlight=True, markup=True, wrap=True)


class GenerateTab(Vertical):
    """A tab panel for recipe generation with live logs, status, preview, and chat transition."""

    def __init__(self, engine: str, model: str, recipes_dir: str) -> None:
        """Initialize the generate tab."""
        super().__init__()
        self._engine = engine
        self._model = model
        self._recipes_dir = recipes_dir

    def compose(self) -> ComposeResult:
        """Build the 2-pane generate tab layout."""
        with Horizontal(id="gen-screen-layout"):
            # Left Sidebar: Config summary & Actions
            with Vertical(id="gen-sidebar"):
                yield Label("Recipe Generator", id="gen-sidebar-title")
                yield Label(f"Engine: {self._engine}", classes="gen-sidebar-item")
                yield Label(f"Model: {self._model}", classes="gen-sidebar-item")
                yield Label(f"Output: {self._recipes_dir}", classes="gen-sidebar-item")
                with Vertical(id="gen-sidebar-actions"):
                    yield Button("Chat with Generated Recipe", id="gen-chat-btn", variant="success")

            # Right Main Pane: Recipe Preview + RichLog + Input Bar
            with Vertical(id="gen-main-pane"):
                with VerticalScroll(id="gen-preview-scroll"):
                    with Horizontal(classes="pane-header"):
                        yield Label("Recipe Preview", classes="pane-title")
                        yield Button(
                            "^o", id="gen-preview-max-btn", classes="pane-max-btn", tooltip="Toggle Fullscreen (Ctrl+O)"
                        )
                    yield Markdown(
                        "# Assistant Recipe Generator\n"
                        "Describe the assistant you want to create below.\n"
                        "The meta-agent will inspect available tools/agents and generate a complete TOML recipe.",
                        id="gen-markdown",
                    )
                with Vertical(id="gen-log-pane"):
                    with Horizontal(classes="pane-header"):
                        yield Label("Generation / Meta-Agent Activity Logs", classes="pane-title")
                        yield Button(
                            "^l", id="gen-log-max-btn", classes="pane-max-btn", tooltip="Toggle Fullscreen (Ctrl+L)"
                        )
                    yield RichLog(id="gen-rich-log", highlight=True, markup=True, wrap=True)
                yield Static("", id="gen-status-bar")
                with Horizontal(id="gen-input-bar"):
                    yield PromptTextArea(
                        placeholder="Describe the assistant to create... (Enter: newline, Ctrl+J / Send: generate)",
                        show_line_numbers=False,
                        soft_wrap=True,
                        tab_behavior="focus",
                        id="gen-input",
                    )
                    yield Button("Generate  [Ctrl+J]", id="gen-submit-btn", variant="primary")


class LogTab(Vertical):
    """A tab panel displaying application logs, search activity, and execution events."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+k", "clear_logs", "Clear Logs (Ctrl+K)", show=True, priority=True),
        Binding("ctrl+s", "export_logs", "Export Logs (Ctrl+S)", show=True, priority=True),
    ]

    def compose(self) -> ComposeResult:
        """Build the application log tab layout."""
        with Horizontal(id="app-log-toolbar"):
            yield Label("Application Activity & Event Logs", id="app-log-title")
        with Vertical(id="app-log-container"):
            yield RichLog(id="app-rich-log", highlight=True, markup=True, wrap=True)

    def action_clear_logs(self) -> None:
        """Clear application logs via app action."""
        if hasattr(self.app, "action_clear_logs"):
            self.app.action_clear_logs()

    def action_export_logs(self) -> None:
        """Export application logs via app action."""
        if hasattr(self.app, "action_export_logs"):
            self.app.action_export_logs()
