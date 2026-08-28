"""HelpScreen for explaining all keybindings and usage in the TUI."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Markdown

HELP_MARKDOWN = """
# 📖 Meta Agent TUI Keyboard Shortcuts & Help

## 🌐 Global & Main Screen Shortcuts
| Key | Action | Description |
|:---|:---|:---|
| `?` / `F1` | **Help** | Open this keyboard shortcuts help modal |
| `/` | **Search** | Focus the filter input for the currently active tab (Recipes / Agents / Tools) |
| `c` | **Chat** | Open chat setup options for the selected recipe |
| `g` | **Generate** | Open recipe generator modal to create a new assistant |
| `q` | **Quit** | Exit the TUI application |
| `Ctrl+C` (×2) | **Quit (force)** | Double-press Ctrl+C within 2 seconds to quit anytime |

---

## 📋 Resource Lists & Navigation
| Key | Action | Description |
|:---|:---|:---|
| `Tab` / `Shift+Tab` | **Navigate** | Move focus between Search input, Sort select, Resource list, and Chat button |
| `Up` / `Down` | **Select Item** | Move up/down through the items list; details update on selection |
| `Enter` / `Space` | **Open / Focus** | Open dropdowns or trigger action buttons |

---

## ⚙️ Chat Options Screen (`ChatOptionsScreen`)
| Key | Action | Description |
|:---|:---|:---|
| `c` | **Start Chat** | Start multi-turn chat session with current settings |
| `/` | **Search Presets** | When focused on a dropdown (Engine/Model/Agent/Tools), open search popup |
| `Esc` | **Cancel / Back** | Discard changes and return to main screen |
| *Buttons* | **Copy Command** | Copy untruncated `meta_agent chat ...` command to system clipboard |

---

## 💬 Interactive Chat Screen (`ChatScreen`)
| Key | Action | Description |
|:---|:---|:---|
| `Up` / `Down` | **Input History** | Navigate through your past sent messages in the chat input field |
| `Enter` | **Send Message** | Send the message in input field to the assistant |
| `Ctrl+E` | **Export Chat** | Save the entire markdown chat history to a file |
| `Ctrl+L` | **Export Logs** | Save all activity & engine execution logs to a file |
| `Esc` | **Back** | Return to recipe list |

---

## 🛠️ Recipe Generator Screen (`GenerateScreen`)
| Key | Action | Description |
|:---|:---|:---|
| `Enter` | **Generate** | Submit generation query |
| `Esc` | **Back** | Return to recipe list without saving |
"""


class HelpScreen(ModalScreen[None]):
    """Modal screen that shows a comprehensive list of all keyboard shortcuts."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_help", "Close Help"),
        Binding("question_mark", "dismiss_help", "Close Help", show=False),
        Binding("f1", "dismiss_help", "Close Help", show=False),
    ]

    def compose(self) -> ComposeResult:
        """Build the help screen layout."""
        yield Header()
        with Vertical(id="help-modal-container"):
            with VerticalScroll(id="help-markdown-container"):
                yield Markdown(HELP_MARKDOWN)
            yield Button("Close Help  [Esc]", id="help-close-btn", variant="primary")
        yield Footer()

    def action_dismiss_help(self) -> None:
        """Close the help screen."""
        self.dismiss()

    @on(Button.Pressed, "#help-close-btn")
    def on_close_btn(self) -> None:
        """Handle close button."""
        self.dismiss()
