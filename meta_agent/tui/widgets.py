"""Custom Textual widgets for the TUI."""

from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, ListView, LoadingIndicator, Markdown, RichLog, Select, Static
from textual.widgets._select import SelectOverlay

from .helpers import SORT_OPTIONS


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
            yield Input(placeholder="Search or ask LLM...", id=f"{tid}-search")
            yield Button("Ask LLM", id=f"{tid}-llm-btn", variant="default")
            yield SearchableSelect(
                [(label, val) for label, val in SORT_OPTIONS],
                id=f"{tid}-sort",
                value="alpha_asc",
                allow_blank=False,
            )
        with Horizontal(id=f"{tid}-body"):
            with Vertical(id=f"{tid}-sidebar"):
                yield ListView(id=f"{tid}-list")
            with Vertical(id=f"{tid}-main-pane"):
                with VerticalScroll(id=f"{tid}-detail"):
                    yield LoadingIndicator(id=f"{tid}-loading")
                    yield Markdown("", id=f"{tid}-markdown")
                    if self._show_chat:
                        with Horizontal(id=f"{tid}-actions"):
                            yield Button("Chat with this recipe  [c]", id=f"{tid}-chat-btn", variant="success")
                            yield Button("Edit  [e]", id=f"{tid}-edit-btn", variant="default")
                            yield Button("Delete  [d]", id=f"{tid}-delete-btn", variant="error")
                with Vertical(id=f"{tid}-log-pane"):
                    yield Label("Activity / Event Logs", classes="resource-log-title")
                    yield RichLog(id=f"{tid}-rich-log", highlight=True, markup=True)


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
                    yield Input(
                        placeholder="e.g. A Python testing specialist that runs pytest and explains errors",
                        id="gen-input",
                    )
                    yield Button("Generate", id="gen-submit-btn", variant="primary")


class LogTab(Vertical):
    """A tab panel displaying application logs, search activity, and execution events."""

    def compose(self) -> ComposeResult:
        """Build the application log tab layout."""
        with Horizontal(id="app-log-toolbar"):
            yield Label("Application Activity & Event Logs", id="app-log-title")
            yield Button("Clear Logs", id="app-log-clear-btn", variant="default")
            yield Button("Export Logs", id="app-log-export-btn", variant="primary")
        with Vertical(id="app-log-container"):
            yield RichLog(id="app-rich-log", highlight=True, markup=True)
