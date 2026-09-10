"""ConfirmRefactorScreen for previewing and confirming refactoring settings before starting."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Markdown


class ConfirmRefactorScreen(ModalScreen[bool]):
    """Modal dialog to preview and confirm refactoring configuration."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_cancel", "Cancel (Esc)", show=True, priority=True),
        Binding("enter", "confirm_refactor", "Start Refactor (Enter)", show=True, priority=True),
    ]

    def __init__(
        self,
        recipes: list[str],
        target: str,
        query: str,
        engine: str,
        model: str,
    ) -> None:
        """Initialize with refactor parameters."""
        super().__init__()
        self._recipes = recipes
        self._target = target
        self._query = query
        self._engine = engine
        self._model = model

    def compose(self) -> ComposeResult:
        """Build the confirm refactor modal layout."""
        with Vertical(id="confirm-refactor-modal-container"):
            yield Label("🔧 Confirm Recipe Refactoring", id="confirm-refactor-modal-title")
            yield Label(
                f"Are you ready to refactor {len(self._recipes)} recipe(s) with the following settings?",
                id="confirm-refactor-modal-subtitle",
            )

            rec_list_md = "\n".join(f"- `{r}`" for r in self._recipes)
            instruction_md = f"```text\n{self._query}\n```" if self._query else "*(None - automatic evaluation)*"

            content = f"""### 📋 Target Recipes ({len(self._recipes)}):
{rec_list_md}

### 🎯 Refactoring Target:
- Component: **`{self._target}`**

### 🧠 LLM Engine & Model:
- Engine: **`{self._engine}`**
- Model: **`{self._model}`**

### 📝 Instructions:
{instruction_md}"""
            with VerticalScroll(id="confirm-refactor-preview-box"):
                yield Markdown(content, id="confirm-refactor-preview-md")

            with Horizontal(id="confirm-refactor-modal-buttons"):
                yield Button("Start Refactor  [Enter]", id="confirm-refactor-btn", variant="primary")
                yield Button("Cancel  [Esc]", id="confirm-refactor-cancel-btn", variant="default")

    def action_dismiss_cancel(self) -> None:
        """Dismiss without starting."""
        self.dismiss(False)

    def action_confirm_refactor(self) -> None:
        """Confirm and start."""
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-refactor-btn")
    def on_confirm(self) -> None:
        """Handle confirm button press."""
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-refactor-cancel-btn")
    def on_cancel(self) -> None:
        """Handle cancel button press."""
        self.dismiss(False)
