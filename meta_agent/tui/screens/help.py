"""HelpScreen for explaining all keybindings and usage in the TUI."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Markdown

from ..widgets import OrderedFooter

HELP_MARKDOWN = """
# 📖 Meta Agent TUI Keyboard Shortcuts & Help

## 🌐 Global & Main Screen Shortcuts
| Key | Action | Description |
|:---|:---|:---|
| `Ctrl+H` / `?` / `F1` | **Help** | Open this keyboard shortcuts help modal |
| `Ctrl+F` | **Search** | Focus the search input for active tab |
| `Ctrl+O` | **Maximize Detail** | Toggle fullscreen for details or preview pane (`Esc` to restore) |
| `Ctrl+L` | **Maximize Logs** | Toggle fullscreen for activity / execution logs (`Esc` to restore) |
| `Ctrl+C` | **Chat** | Open chat setup options for the selected recipe |
| `Ctrl+R` | **Resume Chat** | Browse and restore previous chat session from exported markdown |
| `Ctrl+E` | **Edit** | Edit selected recipe TOML file in interactive editor (`Ctrl+S` to save) |
| `Ctrl+D` | **Delete** | Prompt to delete selected recipe file with preview/multi-choice selection |
| `Ctrl+G` | **Generate** | Switch to the Generate tab to create a new assistant |
| `Ctrl+Left` / `Ctrl+[` | **Previous Tab** | Switch to the previous tab (wraps around) |
| `Ctrl+Right` / `Ctrl+]` | **Next Tab** | Switch to the next tab (wraps around) |
| `Ctrl+Q` | **Quit** | Exit the TUI application directly |
| `Esc` | **Back / Blur** | Exit fullscreen, defocus search input, or return to list navigation |

---

## 📋 Resource Lists & Navigation
| Key | Action | Description |
|:---|:---|:---|
| `Tab` / `Shift+Tab` | **Navigate** | Move focus between tabs, inputs, selects, and buttons |
| `Up` / `Down` | **Select Item** | Move up/down through the items list; details update on selection |
| `Ctrl+J` / *Button* | **Ask LLM** | In search bar: submit multi-line query to Ask LLM |
| *Ask LLM* | **Smart Action** | Natural language search, generate (e.g. "create pytest bot"), edit, delete, or resume |
| `Ctrl+O` / `Ctrl+L` | **Maximize** | Expand details (`Ctrl+O`) or logs (`Ctrl+L`) to fullscreen (`Esc` to restore) |

---

## ⚙️ Chat Options Screen (`ChatOptionsScreen`)
| Key | Action | Description |
|:---|:---|:---|
| `Ctrl+C` | **Start Chat** | Start multi-turn chat session with current settings |
| `Esc` | **Cancel / Back** | Discard changes and return to main screen |
| *Buttons* | **Copy Command** | Copy untruncated `meta_agent chat ...` command to system clipboard |

---

## 📜 Logs Tab (`LogTab`)
| Key | Action | Description |
|:---|:---|:---|
| `Ctrl+K` | **Clear Logs** | Clear application execution logs buffer |
| `Ctrl+S` | **Export Logs** | Export full activity and event logs to file |
| `Ctrl+L` | **Maximize Logs** | Toggle fullscreen for application logs (`Esc` to restore) |

## 💬 Chat Screen (`ChatScreen`) Shortcuts
| Key | Action | Description |
|:---|:---|:---|
| `Enter` | **Newline** | Insert a newline in multiline input |
| `Ctrl+J` / `Ctrl+Enter` | **Send Message** | Submit input to LLM agent |
| `Ctrl+O` | **Maximize Messages** | Expand chat messages pane to fullscreen (`Esc` to restore) |
| `Ctrl+L` | **Maximize Logs** | Expand streaming debug logs pane to fullscreen (`Esc` to restore) |
| `Ctrl+P` | **Maximize Prompt** | Expand input prompt area to fullscreen (`Esc` to restore) |
| `Ctrl+S` | **Export Session** | Save chat history to Markdown file |
| `Ctrl+Shift+L` | **Export Logs** | Save raw session activity log to `.log` file |
| `Up` / `Down` | **Input History** | Cycle through previously sent prompts or restore draft |
| `Esc` | **Back / Restore** | Restore fullscreen pane, or close chat session |

---

## 🛠 Modal Dialogs & Editors
| Modal Screen | Key | Action |
|:---|:---|:---|
| **Chat Options** | `Ctrl+C` | Start chat session with configured options |
| **Edit Recipe** | `Ctrl+S` | Validate and save recipe changes |
| **Search Dropdown** | `Ctrl+F` / `/` | Open live typeahead search filter overlay |
| **All Modals** | `Esc` | Cancel / Dismiss modal without saving |
"""


class HelpScreen(ModalScreen[None]):
    """Modal screen that shows a comprehensive list of all keyboard shortcuts."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_help", "Close Help (Esc)", show=True, priority=True),
        Binding("ctrl+h", "dismiss_help", "Close Help", show=False, priority=True),
        Binding("question_mark", "dismiss_help", "Close Help", show=False, priority=True),
        Binding("f1", "dismiss_help", "Close Help", show=False, priority=True),
        Binding("ctrl+c", "dismiss_help", show=False, priority=True),
        Binding("ctrl+g", "dismiss_help", show=False, priority=True),
        Binding("ctrl+q", "dismiss_help", show=False, priority=True),
        Binding("ctrl+f", "dismiss_help", show=False, priority=True),
    ]

    def compose(self) -> ComposeResult:
        """Build the help screen layout."""
        yield Header()
        with Vertical(id="help-modal-container"):
            with VerticalScroll(id="help-markdown-container"):
                yield Markdown(HELP_MARKDOWN)
            yield Button("Close Help  [Esc]", id="help-close-btn", variant="primary")
        yield OrderedFooter()

    def action_dismiss_help(self) -> None:
        """Close the help screen."""
        self.dismiss()

    @on(Button.Pressed, "#help-close-btn")
    def on_close_btn(self) -> None:
        """Handle close button."""
        self.dismiss()
