"""RecipeDetailScreen modal for inspecting recipe details."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Markdown

from ...api import Recipe
from ..helpers import recipe_markdown


class RecipeDetailScreen(ModalScreen[None]):
    """Modal dialog to preview full recipe details."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_modal", "Close (Esc)", show=True, priority=True),
        Binding("enter", "dismiss_modal", "Close (Enter)", show=True, priority=True),
    ]

    def __init__(self, recipe: Recipe) -> None:
        """Initialize with recipe."""
        super().__init__()
        self._recipe = recipe

    def compose(self) -> ComposeResult:
        """Build the recipe detail modal layout."""
        with Vertical(id="recipe-detail-modal-container"):
            yield Label(f"📄 Recipe Details: {self._recipe.name}", id="recipe-detail-modal-title")
            with VerticalScroll(id="recipe-detail-modal-scroll"):
                yield Markdown(recipe_markdown(self._recipe), id="recipe-detail-modal-md")
            with Horizontal(id="recipe-detail-modal-buttons"):
                yield Button("Close  [Esc]", id="recipe-detail-close-btn", variant="primary")

    def action_dismiss_modal(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    @on(Button.Pressed, "#recipe-detail-close-btn")
    def on_close(self) -> None:
        """Handle close button press."""
        self.dismiss(None)
