"""ResumeChatScreen for selecting and restoring previous chat sessions from exported markdown files."""

from pathlib import Path
from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Markdown, Static

from ...asking import AskingOpts
from ..helpers import parse_exported_chat_file
from .chat import ChatScreen


class ResumeChatScreen(ModalScreen[bool]):
    """Modal dialog to browse, preview, and resume exported chat sessions."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("slash", "focus_filter", "Search (/)", show=True),
        Binding("escape", "dismiss_cancel", "Cancel", show=True),
    ]

    def __init__(self, export_dir: str) -> None:
        """Initialize with export directory."""
        super().__init__()
        self._export_dir = export_dir
        self._all_files: list[Path] = []
        self._displayed_files: list[Path] = []
        self._selected_index: int = 0

    def compose(self) -> ComposeResult:
        """Build the resume chat modal layout."""
        self._scan_files()
        with Vertical(id="resume-modal-container"):
            yield Label("📂 Resume Chat Session", id="resume-modal-title")
            yield Label("Select an exported chat session file, or enter a file path:", id="resume-modal-subtitle")

            with Horizontal(id="resume-manual-bar"):
                yield Input(placeholder="Path to exported chat markdown file...", id="resume-path-input")
                yield Button("Load File", id="resume-load-btn", variant="default")

            with Horizontal(id="resume-main-body"):
                with Vertical(id="resume-file-list-pane"):
                    yield Label(f"Exported Sessions ({self._export_dir}):", id="resume-list-title")
                    yield Input(placeholder="Filter files by name...  [/]", id="resume-filter-input")
                    with ListView(id="resume-file-list"):
                        for p in self._displayed_files:
                            yield ListItem(Label(p.name))
                with VerticalScroll(id="resume-preview-box"):
                    if self._displayed_files:
                        init_preview = self._load_preview(self._displayed_files[0])
                    else:
                        init_preview = "*(No exported chat files found)*"
                    yield Markdown(init_preview, id="resume-preview-md")

            yield Static("", id="resume-status-bar")
            with Horizontal(id="resume-modal-buttons"):
                yield Button("Resume Chat", id="resume-confirm-btn", variant="primary")
                yield Button("Cancel", id="resume-cancel-btn", variant="default")

    def on_mount(self) -> None:
        """Set initial focus."""
        if self._displayed_files:
            try:
                self.query_one("#resume-file-list", ListView).focus()
            except Exception:
                pass
        else:
            try:
                self.query_one("#resume-path-input", Input).focus()
            except Exception:
                pass

    def action_focus_filter(self) -> None:
        """Focus the search filter input."""
        self.query_one("#resume-filter-input", Input).focus()

    @on(Input.Changed, "#resume-filter-input")
    def on_filter_changed(self, event: Input.Changed) -> None:
        """Filter files list in real-time as user types."""
        q = event.value.strip().lower()
        if q:
            self._displayed_files = [p for p in self._all_files if q in p.name.lower()]
        else:
            self._displayed_files = list(self._all_files)

        lv = self.query_one("#resume-file-list", ListView)
        lv.clear()
        for p in self._displayed_files:
            lv.append(ListItem(Label(p.name)))

        if self._displayed_files:
            self._selected_index = 0
            lv.index = 0
            target_p = self._displayed_files[0]
            self.query_one("#resume-path-input", Input).value = str(target_p)
            md = self._load_preview(target_p)
            self.query_one("#resume-preview-md", Markdown).update(md)
        else:
            self.query_one("#resume-preview-md", Markdown).update("*(No matching files)*")

    def _scan_files(self) -> None:
        """Scan export directory for chat_*.md files."""
        dir_p = Path(self._export_dir)
        if dir_p.is_dir():
            self._all_files = sorted(
                dir_p.glob("chat_*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        else:
            self._all_files = []
        self._displayed_files = list(self._all_files)

    def _load_preview(self, path: Path) -> str:
        """Read and parse file to produce preview markdown."""
        if not path.is_file():
            return f"*(File not found: {path})*"
        try:
            content = path.read_text(encoding="utf-8")
            parsed = parse_exported_chat_file(content)
            if not parsed:
                return f"**File**: `{path}`\n\n*(Could not parse chat header)*\n\n```markdown\n{content[:500]}\n```"

            preview_lines = [
                f"# Session: `{parsed.recipe_name}`\n",
                f"- **File**: `{path}`",
                f"- **Engine**: {parsed.engine}",
                f"- **Model**: {parsed.model}",
                f"- **Agent**: {parsed.agent or 'direct engine'}",
                f"- **Tools**: {parsed.tools or 'none'}",
                f"- **History Turns**: {len(parsed.history)} messages\n",
                "### Last Messages:\n",
            ]
            for role, text, ts in parsed.history[-4:]:
                preview_lines.append(f"**{role}** ({ts}):\n> {text[:150]}...\n")

            return "\n".join(preview_lines)
        except Exception as e:
            return f"*(Error reading file: {e})*"

    def action_dismiss_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(False)

    @on(ListView.Selected, "#resume-file-list")
    def on_file_selected(self, event: ListView.Selected) -> None:
        """Handle file selection in list view."""
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self._displayed_files):
            self._selected_index = idx
            target_p = self._displayed_files[idx]
            self.query_one("#resume-path-input", Input).value = str(target_p)
            md = self._load_preview(target_p)
            self.query_one("#resume-preview-md", Markdown).update(md)
            self.query_one("#resume-status-bar", Static).update("")

    @on(Button.Pressed, "#resume-load-btn")
    def on_load_btn(self) -> None:
        """Load manual path preview."""
        manual_path = self.query_one("#resume-path-input", Input).value.strip()
        if not manual_path:
            return
        p = Path(manual_path)
        md = self._load_preview(p)
        self.query_one("#resume-preview-md", Markdown).update(md)

    @on(Button.Pressed, "#resume-confirm-btn")
    def on_confirm_btn(self) -> None:
        """Parse selected file and resume ChatScreen."""
        target_path_str = self.query_one("#resume-path-input", Input).value.strip()
        target_path: Path | None = None
        if target_path_str:
            target_path = Path(target_path_str)
        elif self._displayed_files and 0 <= self._selected_index < len(self._displayed_files):
            target_path = self._displayed_files[self._selected_index]

        if not target_path or not target_path.is_file():
            self.query_one("#resume-status-bar", Static).update("❌ Please select or enter a valid chat markdown file.")
            return

        try:
            content = target_path.read_text(encoding="utf-8")
            parsed = parse_exported_chat_file(content)
            if not parsed:
                self.query_one("#resume-status-bar", Static).update("❌ Invalid chat file format.")
                return

            opts = AskingOpts(
                engine=parsed.engine,
                model=parsed.model,
                agent=parsed.agent or "",
                tools=parsed.tools or "",
                system=parsed.system or "",
            )
            self.dismiss(True)
            self.app.push_screen(
                ChatScreen(
                    recipe_name=parsed.recipe_name,
                    opts=opts,
                    export_dir=self._export_dir,
                    initial_history=parsed.history,
                )
            )
        except Exception as e:
            self.query_one("#resume-status-bar", Static).update(f"❌ Failed to restore session: {e}")

    @on(Button.Pressed, "#resume-cancel-btn")
    def on_cancel_btn(self) -> None:
        """Handle cancel button."""
        self.dismiss(False)
