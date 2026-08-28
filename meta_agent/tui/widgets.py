"""Custom Textual widgets for the TUI."""

from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, ListView, LoadingIndicator, Markdown, Select
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
            yield Input(placeholder="Filter by name...", id=f"{tid}-search")
            yield Button("LLM Search", id=f"{tid}-llm-btn", variant="default")
            yield SearchableSelect(
                [(label, val) for label, val in SORT_OPTIONS],
                id=f"{tid}-sort",
                value="alpha_asc",
                allow_blank=False,
            )
        with Horizontal(id=f"{tid}-body"):
            with Vertical(id=f"{tid}-sidebar"):
                yield ListView(id=f"{tid}-list")
            with VerticalScroll(id=f"{tid}-detail"):
                yield LoadingIndicator(id=f"{tid}-loading")
                yield Markdown("", id=f"{tid}-markdown")
                if self._show_chat:
                    yield Button("Chat with this recipe  [c]", id=f"{tid}-chat-btn", variant="success")
