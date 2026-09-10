"""Keyboard navigation, shortcut routing, and history cycling coordinator for MetaAgentTUI."""

import time
from typing import TYPE_CHECKING

from textual import events
from textual.widgets import TabbedContent, TextArea

if TYPE_CHECKING:
    from .app import MetaAgentTUI


class KeyNavigator:
    """Coordinates key events, prompt history cycling, and tab navigation."""

    TABS_ORDER: list[str] = [
        "tab-recipes",
        "tab-agents",
        "tab-tools",
        "tab-engines",
        "tab-models",
        "tab-generate",
        "tab-refactor",
        "tab-logs",
    ]

    def __init__(self, app: "MetaAgentTUI") -> None:
        """Initialize with app reference."""
        self._app = app
        self._last_ctrl_c: float = 0.0

    def focus_search(self) -> None:
        """Focus the search or primary input on the currently active tab."""
        try:
            tabbed_content = self._app.query_one(TabbedContent)
            active_tab = tabbed_content.active
        except Exception:
            return

        if active_tab == "tab-recipes":
            self._app.query_one("#recipes-search", TextArea).focus()
        elif active_tab == "tab-agents":
            self._app.query_one("#agents-search", TextArea).focus()
        elif active_tab == "tab-tools":
            self._app.query_one("#tools-search", TextArea).focus()
        elif active_tab == "tab-engines":
            self._app.query_one("#engines-search", TextArea).focus()
        elif active_tab == "tab-models":
            self._app.query_one("#models-search", TextArea).focus()
        elif active_tab == "tab-generate":
            self._app.query_one("#gen-input", TextArea).focus()
        elif active_tab == "tab-refactor":
            self._app.query_one("#refactor-search", TextArea).focus()

    def focus_tab_search(self, target_tab: str) -> None:
        """Focus the search/input widget for the specified tab."""
        if target_tab == "tab-recipes":
            self._app.query_one("#recipes-search", TextArea).focus()
        elif target_tab == "tab-agents":
            self._app.query_one("#agents-search", TextArea).focus()
        elif target_tab == "tab-tools":
            self._app.query_one("#tools-search", TextArea).focus()
        elif target_tab == "tab-engines":
            self._app.query_one("#engines-search", TextArea).focus()
        elif target_tab == "tab-models":
            self._app.query_one("#models-search", TextArea).focus()
        elif target_tab == "tab-generate":
            self._app.query_one("#gen-input", TextArea).focus()
        elif target_tab == "tab-refactor":
            self._app.query_one("#refactor-input", TextArea).focus()

    def switch_tab_relative(self, delta: int) -> None:
        """Switch active tab by offset delta (-1 or +1) with wrapping."""
        try:
            tabbed_content = self._app.query_one(TabbedContent)
            current = tabbed_content.active
            if current in self.TABS_ORDER:
                idx = self.TABS_ORDER.index(current)
                target_idx = (idx + delta) % len(self.TABS_ORDER)
                target_tab = self.TABS_ORDER[target_idx]
                self._app.set_focus(None)
                tabbed_content.active = target_tab
                self.focus_tab_search(target_tab)
        except Exception:
            pass

    def handle_ctrl_c(self) -> None:
        """Handle Ctrl+C: first press warns, second press within timeout quits."""
        now = time.monotonic()
        if now - self._last_ctrl_c < 2.0:
            self._app.exit()
        else:
            self._last_ctrl_c = now
            self._app._last_ctrl_c = now
            self._app.notify("Press Ctrl+C again to quit", severity="warning", timeout=2.0)

    def handle_tab_nav_key(self, event: events.Key) -> bool:
        """Handle tab navigation keys. Returns True if handled."""
        if event.key in ("ctrl+left", "ctrl+left_square_bracket", "ctrl+[", "ctrl__"):
            event.prevent_default()
            event.stop()
            self.switch_tab_relative(-1)
            return True
        if event.key in ("ctrl+right", "ctrl+right_square_bracket", "ctrl+]"):
            event.prevent_default()
            event.stop()
            self.switch_tab_relative(1)
            return True
        return False

    def handle_log_tab_key(self, event: events.Key) -> bool:
        """Handle log tab specific shortcuts. Returns True if handled."""
        try:
            tabs = self._app.query_one(TabbedContent)
            if tabs.active != "tab-logs":
                return False
        except Exception:
            return False

        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self._app.action_export_logs()
            return True
        if event.key == "ctrl+k":
            event.prevent_default()
            event.stop()
            self._app.action_clear_logs()
            return True
        return False

    def handle_submit_key(self, event: events.Key) -> bool:
        """Handle Ctrl+J / Ctrl+M submission across focused TextAreas. Returns True if handled."""
        if event.key not in ("ctrl+j", "ctrl+m"):
            return False

        focused = self._app.focused
        if not isinstance(focused, TextArea):
            return False

        if focused.id in (
            "recipes-search",
            "agents-search",
            "tools-search",
            "engines-search",
            "models-search",
        ):
            tid = (focused.id or "").removesuffix("-search")
            event.prevent_default()
            event.stop()
            self._app._trigger_llm_search(tid)
            return True
        if focused.id == "gen-input":
            event.prevent_default()
            event.stop()
            self._app.on_gen_submit()
            return True
        if focused.id == "refactor-input":
            event.prevent_default()
            event.stop()
            self._app.on_refactor_submit()
            return True
        return False

    def handle_history_nav_key(self, event: events.Key) -> bool:
        """Handle Up/Down prompt history navigation in input boxes. Returns True if handled."""
        if event.key not in ("up", "down"):
            return False

        focused = self._app.focused
        if not isinstance(focused, TextArea) or focused.id not in ("gen-input", "refactor-input"):
            return False

        inp = focused
        history = self._app._refactor_input_history if focused.id == "refactor-input" else self._app._gen_input_history
        cursor_row, _ = inp.cursor_location
        total_lines = inp.document.line_count

        if event.key == "up" and cursor_row == 0:
            val = history.previous(inp.text)
            if val is not None:
                event.prevent_default()
                event.stop()
                inp.load_text(val)
                inp.move_cursor((0, 0))
                return True
        elif event.key == "down" and cursor_row >= total_lines - 1:
            val = history.next()
            if val is not None:
                event.prevent_default()
                event.stop()
                inp.load_text(val)
                inp.move_cursor((inp.document.line_count - 1, len(inp.document.lines[-1])))
                return True
        return False

    def handle_key(self, event: events.Key) -> None:
        """Dispatch key navigation, shortcuts, submit, and history cycling."""
        if self.handle_tab_nav_key(event):
            return
        if self.handle_log_tab_key(event):
            return
        if self.handle_submit_key(event):
            return
        self.handle_history_nav_key(event)
