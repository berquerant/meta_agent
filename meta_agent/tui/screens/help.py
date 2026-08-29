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
| `Ctrl+H` / `?` / `F1` | **Help** | Open this keyboard shortcuts help modal |
| `Ctrl+F` | **Search** | Focus the search input for active tab |
| `Ctrl+B` | **Maximize Detail** | Toggle fullscreen for details or preview pane (`Esc` to restore) |
| `Ctrl+L` | **Maximize Logs** | Toggle fullscreen for activity / execution logs (`Esc` to restore) |
| `Ctrl+C` | **Chat** | Open chat setup options for the selected recipe |
| `Ctrl+R` | **Resume Chat** | Browse and restore previous chat session from exported markdown |
| `Ctrl+E` | **Edit** | Edit selected recipe TOML file in interactive editor (`Ctrl+S` to save) |
| `Ctrl+D` | **Delete** | Prompt to delete selected recipe file with preview/multi-choice selection |
| `Ctrl+G` | **Generate** | Switch to the Generate tab to create a new assistant |
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
| `Ctrl+B` / `Ctrl+L` | **Maximize** | Expand details (`Ctrl+B`) or logs (`Ctrl+L`) to fullscreen (`Esc` to restore) |

---

## ⚙️ Chat Options Screen (`ChatOptionsScreen`)
| Key | Action | Description |
|:---|:---|:---|
| `Ctrl+C` | **Start Chat** | Start multi-turn chat session with current settings |
| `Esc` | **Cancel / Back** | Discard changes and return to main screen |
| *Buttons* | **Copy Command** | Copy untruncated `meta_agent chat ...` command to system clipboard |

---

## 📂 Resume Chat Session Modal (`ResumeChatScreen`)
| Key | Action | Description |
|:---|:---|:---|
| `Ctrl+F` | **Search Files** | Focus the filter input to quickly search exported sessions by name |
| `Up` / `Down` | **Select File** | Navigate through exported sessions with real-time preview |
| `Enter` | **Resume** | Restore session settings and messages to continue chat |
| `Esc` | **Cancel** | Close modal and return to main screen |

---

## 💬 Interactive Chat Screen (`ChatScreen`)
| Key | Action | Description |
|:---|:---|:---|
| `Enter` | **Newline** | Insert a new line in the chat message input box |
| `Ctrl+J` | **Send Message** | Send the multi-line message in the input box to the assistant |
| `Ctrl+B` | **Maximize Messages**| Toggle fullscreen for conversation history (`Esc` to restore) |
| `Ctrl+L` | **Maximize Logs** | Toggle fullscreen for execution logs (`Esc` to restore) |
| `Ctrl+P` | **Maximize Prompt**| Toggle fullscreen for system prompt in left sidebar (`Esc` to restore) |
| `Up` / `Down` | **Input History** | Navigate through past messages when cursor is at top/bottom |
| `Ctrl+S` | **Export Chat** | Save the entire markdown chat history to a file |
| `Esc` | **Back** | Restore normal view if maximized, or return to recipe list |

---

## 🛠️ Recipe Generator Tab (`GenerateTab`)
| Key | Action | Description |
|:---|:---|:---|
| `Enter` | **Newline** | Insert a new line in the generation description box |
| `Ctrl+J` | **Generate** | Submit multi-line generation query in background worker |
| `Up` / `Down` | **Input History** | Navigate through your past generation prompts |
| *Button* | **Chat with Generated Recipe** | Start chat immediately with the generated recipe |

---

## 📜 Application Logs Tab (`LogTab`)
| Key | Action | Description |
|:---|:---|:---|
| *Clear Logs* | **Clear** | Clear current application log buffer and view |
| *Export Logs* | **Export** | Save complete application logs (including LLM Search actions) to file |
"""


class HelpScreen(ModalScreen[None]):
    """Modal screen that shows a comprehensive list of all keyboard shortcuts."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "dismiss_help", "Close Help (Esc)", priority=True),
        Binding("ctrl+h", "dismiss_help", "Close Help", show=False, priority=True),
        Binding("question_mark", "dismiss_help", "Close Help", show=False, priority=True),
        Binding("f1", "dismiss_help", "Close Help", show=False, priority=True),
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
