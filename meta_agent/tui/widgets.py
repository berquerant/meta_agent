"""Custom Textual widgets for the TUI."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, ListView, LoadingIndicator, Markdown, Select

from .helpers import SORT_OPTIONS


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
            yield Select(
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
