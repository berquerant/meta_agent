"""EditRecipeScreen for editing recipe TOML files inside the TUI."""

from pathlib import Path
from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static, TextArea

from ...api import save_recipe_file


class EditRecipeScreen(ModalScreen[bool]):
    """Modal dialog to view and edit recipe TOML files with syntax validation."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+s", "save_recipe", "Save (Ctrl+S)", show=True),
        Binding("escape", "dismiss_cancel", "Cancel", show=True),
    ]

    def __init__(self, recipe_name: str, file_paths: list[str]) -> None:
        """Initialize with recipe name and matched file paths."""
        super().__init__()
        self._recipe_name = recipe_name
        self._file_paths = file_paths
        self._selected_index: int = 0

    def compose(self) -> ComposeResult:
        """Build the recipe edit modal layout."""
        with Vertical(id="edit-modal-container"):
            yield Label(f"✏️ Edit Recipe: {self._recipe_name}", id="edit-modal-title")

            if len(self._file_paths) == 1:
                path = self._file_paths[0]
                yield Static(f"File: {path}", id="edit-file-path")
                yield TextArea(
                    self._read_file(path),
                    language="toml",
                    id="edit-text-area",
                )
            else:
                yield Label(
                    "Multiple files matched this recipe. Select a file to edit:",
                    id="edit-modal-subtitle",
                )
                with Horizontal(id="edit-multi-body"):
                    with Vertical(id="edit-file-list-pane"):
                        yield Label("Matched Files:", id="edit-list-title")
                        with ListView(id="edit-file-list"):
                            for p in self._file_paths:
                                yield ListItem(Label(Path(p).name))
                    with Vertical(id="edit-editor-pane"):
                        yield Static(f"File: {self._file_paths[0]}", id="edit-file-path")
                        yield TextArea(
                            self._read_file(self._file_paths[0]),
                            language="toml",
                            id="edit-text-area",
                        )

            yield Static("", id="edit-status-bar")
            with Horizontal(id="edit-modal-buttons"):
                yield Button("Save Changes  [Ctrl+S]", id="edit-save-btn", variant="primary")
                yield Button("Cancel", id="edit-cancel-btn", variant="default")

    def on_mount(self) -> None:
        """Set initial focus to editor."""
        try:
            self.query_one("#edit-text-area", TextArea).focus()
        except Exception:
            pass

    def _read_file(self, path: str) -> str:
        """Read recipe file content."""
        p = Path(path)
        if not p.exists():
            return ""
        try:
            return p.read_text(encoding="utf-8")
        except Exception as e:
            return f"# Error reading file: {e}"

    def action_dismiss_cancel(self) -> None:
        """Cancel and close dialog."""
        self.dismiss(False)

    @on(ListView.Selected, "#edit-file-list")
    def on_file_selected(self, event: ListView.Selected) -> None:
        """Switch active file in multi-choice list."""
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self._file_paths):
            self._selected_index = idx
            target_path = self._file_paths[idx]
            self.query_one("#edit-file-path", Static).update(f"File: {target_path}")
            self.query_one("#edit-text-area", TextArea).text = self._read_file(target_path)
            self.query_one("#edit-status-bar", Static).update("")

    def action_save_recipe(self) -> None:
        """Save edited recipe content."""
        if not self._file_paths or not (0 <= self._selected_index < len(self._file_paths)):
            return

        target_path = self._file_paths[self._selected_index]
        editor = self.query_one("#edit-text-area", TextArea)
        new_content = editor.text

        success, err = save_recipe_file(target_path, new_content)
        if success:
            self.dismiss(True)
        else:
            self.query_one("#edit-status-bar", Static).update(f"❌ {err}")

    @on(Button.Pressed, "#edit-save-btn")
    def on_save_btn(self) -> None:
        """Handle save button press."""
        self.action_save_recipe()

    @on(Button.Pressed, "#edit-cancel-btn")
    def on_cancel_btn(self) -> None:
        """Handle cancel button press."""
        self.dismiss(False)
