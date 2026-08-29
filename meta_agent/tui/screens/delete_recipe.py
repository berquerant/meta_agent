"""DeleteRecipeScreen for confirming and selecting recipe files to delete."""

from pathlib import Path
from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Markdown, Static

from ...api import delete_recipe_file


class DeleteRecipeScreen(ModalScreen[bool]):
    """Modal dialog to preview and select recipe files for deletion."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_cancel", "Cancel (Esc)", show=True, priority=True),
    ]

    def __init__(self, recipe_name: str, file_paths: list[str]) -> None:
        """Initialize with recipe name and matched file paths."""
        super().__init__()
        self._recipe_name = recipe_name
        self._file_paths = file_paths
        self._selected_index: int = 0

    def compose(self) -> ComposeResult:
        """Build the delete confirmation / selection modal layout."""
        with Vertical(id="delete-modal-container"):
            yield Label("🗑️ Confirm Recipe Deletion", id="delete-modal-title")

            if len(self._file_paths) == 1:
                path = self._file_paths[0]
                yield Label(
                    f"Are you sure you want to delete this recipe file for '{self._recipe_name}'?",
                    id="delete-modal-subtitle",
                )
                yield Static(f"File: {path}", id="delete-file-path")
                with VerticalScroll(id="delete-preview-box"):
                    yield Markdown(self._load_file_preview(path), id="delete-preview-md")
                with Horizontal(id="delete-modal-buttons"):
                    yield Button("Delete", id="delete-confirm-btn", variant="error")
                    yield Button("Cancel", id="delete-cancel-btn", variant="default")
            else:
                yield Label(
                    f"Multiple recipe files matched '{self._recipe_name}'.\n"
                    "Select a file to preview and delete, delete all, or cancel:",
                    id="delete-modal-subtitle",
                )
                with Horizontal(id="delete-multi-body"):
                    with Vertical(id="delete-file-list-pane"):
                        yield Label("Matched Files:", id="delete-list-title")
                        with ListView(id="delete-file-list"):
                            for p in self._file_paths:
                                yield ListItem(Label(Path(p).name))
                    with VerticalScroll(id="delete-preview-box"):
                        yield Markdown(self._load_file_preview(self._file_paths[0]), id="delete-preview-md")
                with Horizontal(id="delete-modal-buttons"):
                    yield Button("Delete Selected", id="delete-selected-btn", variant="error")
                    yield Button("Delete All", id="delete-all-btn", variant="error")
                    yield Button("Cancel (Keep All)", id="delete-cancel-btn", variant="default")

    def on_mount(self) -> None:
        """Set initial focus."""
        if len(self._file_paths) > 1:
            try:
                self.query_one("#delete-file-list", ListView).focus()
            except Exception:
                pass
        else:
            try:
                self.query_one("#delete-cancel-btn", Button).focus()
            except Exception:
                pass

    def _load_file_preview(self, path: str) -> str:
        """Load and format file contents into a markdown code block."""
        p = Path(path)
        if not p.exists():
            return f"*(File not found: {path})*"
        try:
            content = p.read_text(encoding="utf-8")
            return f"**File**: `{path}`\n\n```toml\n{content}\n```"
        except Exception as e:
            return f"*(Error reading file: {e})*"

    def action_dismiss_cancel(self) -> None:
        """Cancel and close dialog."""
        self.dismiss(False)

    @on(ListView.Selected, "#delete-file-list")
    def on_file_selected(self, event: ListView.Selected) -> None:
        """Update preview on file selection."""
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self._file_paths):
            self._selected_index = idx
            md = self._load_file_preview(self._file_paths[idx])
            self.query_one("#delete-preview-md", Markdown).update(md)

    @on(Button.Pressed, "#delete-cancel-btn")
    def on_cancel_btn(self) -> None:
        """Handle cancel button."""
        self.dismiss(False)

    @on(Button.Pressed, "#delete-confirm-btn")
    def on_confirm_single_btn(self) -> None:
        """Delete the single matched file."""
        if self._file_paths:
            deleted = delete_recipe_file(self._file_paths[0])
            self.dismiss(deleted)
        else:
            self.dismiss(False)

    @on(Button.Pressed, "#delete-selected-btn")
    def on_delete_selected_btn(self) -> None:
        """Delete currently selected file in multi-choice list."""
        if 0 <= self._selected_index < len(self._file_paths):
            deleted = delete_recipe_file(self._file_paths[self._selected_index])
            self.dismiss(deleted)
        else:
            self.dismiss(False)

    @on(Button.Pressed, "#delete-all-btn")
    def on_delete_all_btn(self) -> None:
        """Delete all matched files."""
        any_deleted = False
        for p in self._file_paths:
            if delete_recipe_file(p):
                any_deleted = True
        self.dismiss(any_deleted)
