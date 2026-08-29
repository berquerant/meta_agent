"""Fullscreen management for MetaAgentTUI panes and tabs."""

from typing import TYPE_CHECKING

from textual.widgets import TabbedContent

if TYPE_CHECKING:
    from .app import MetaAgentTUI


class FullscreenManager:
    """Manages pane maximization and restoration across tabs in MetaAgentTUI."""

    def __init__(self, app: "MetaAgentTUI") -> None:
        """Initialize with app reference."""
        self._app = app
        self._maximized_pane: str | None = None

    @property
    def maximized_pane(self) -> str | None:
        """Return the ID of the currently maximized pane, or None."""
        return self._maximized_pane

    @maximized_pane.setter
    def maximized_pane(self, value: str | None) -> None:
        """Set the currently maximized pane ID."""
        self._maximized_pane = value

    def toggle_detail_fullscreen(self) -> None:
        """Toggle fullscreen for detail or preview pane."""
        app = self._app
        if len(app.screen_stack) > 1:
            if hasattr(app.screen, "action_toggle_messages_fullscreen"):
                app.screen.action_toggle_messages_fullscreen()
            return

        try:
            tabbed_content = app.query_one(TabbedContent)
            active_tab = tabbed_content.active
        except Exception:
            return

        if active_tab in ("tab-recipes", "tab-agents", "tab-tools", "tab-engines", "tab-models"):
            tid = active_tab.removeprefix("tab-")
            if self._maximized_pane == f"{tid}-detail":
                self.restore_fullscreen()
            else:
                self.maximize_resource_detail(tid)
        elif active_tab == "tab-generate":
            if self._maximized_pane == "gen-preview":
                self.restore_fullscreen()
            else:
                self.maximize_gen_preview()

    def toggle_log_fullscreen(self) -> None:
        """Toggle fullscreen for logs pane."""
        app = self._app
        if len(app.screen_stack) > 1:
            if hasattr(app.screen, "action_toggle_log_fullscreen"):
                app.screen.action_toggle_log_fullscreen()
            return

        try:
            tabbed_content = app.query_one(TabbedContent)
            active_tab = tabbed_content.active
        except Exception:
            return

        if active_tab in ("tab-recipes", "tab-agents", "tab-tools", "tab-engines", "tab-models"):
            tid = active_tab.removeprefix("tab-")
            if self._maximized_pane == f"{tid}-log":
                self.restore_fullscreen()
            else:
                self.maximize_resource_log(tid)
        elif active_tab == "tab-generate":
            if self._maximized_pane == "gen-log":
                self.restore_fullscreen()
            else:
                self.maximize_gen_log()
        elif active_tab == "tab-logs":
            if self._maximized_pane == "app-log":
                self.restore_fullscreen()
            else:
                self.maximize_app_log()

    def maximize_resource_detail(self, tid: str) -> None:
        """Maximize detail pane in resource tab."""
        self.restore_fullscreen(notify=False)
        try:
            self._app.query_one(f"#{tid}-body").add_class("maximized-detail")
            self._app.query_one(f"#{tid}-toolbar").add_class("pane-hidden")
            self._maximized_pane = f"{tid}-detail"
            self._app.notify(f"Maximized {tid.capitalize()} Details (press '^b' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def maximize_resource_log(self, tid: str) -> None:
        """Maximize log pane in resource tab."""
        self.restore_fullscreen(notify=False)
        try:
            self._app.query_one(f"#{tid}-body").add_class("maximized-log")
            self._app.query_one(f"#{tid}-toolbar").add_class("pane-hidden")
            self._maximized_pane = f"{tid}-log"
            self._app.notify(f"Maximized {tid.capitalize()} Logs (press '^l' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def maximize_gen_preview(self) -> None:
        """Maximize preview pane in generate tab."""
        self.restore_fullscreen(notify=False)
        try:
            self._app.query_one("#gen-screen-layout").add_class("maximized-preview")
            self._maximized_pane = "gen-preview"
            self._app.notify("Maximized Recipe Preview (press '^b' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def maximize_gen_log(self) -> None:
        """Maximize log pane in generate tab."""
        self.restore_fullscreen(notify=False)
        try:
            self._app.query_one("#gen-screen-layout").add_class("maximized-log")
            self._maximized_pane = "gen-log"
            self._app.notify("Maximized Generation Logs (press '^l' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def maximize_app_log(self) -> None:
        """Maximize application log tab."""
        self.restore_fullscreen(notify=False)
        from .widgets import LogTab

        try:
            self._app.query_one(LogTab).add_class("maximized-log")
            self._maximized_pane = "app-log"
            self._app.notify("Maximized Application Logs (press '^l' or Esc to restore)", timeout=3.0)
        except Exception:
            pass

    def restore_fullscreen(self, notify: bool = True) -> None:
        """Restore all tabs and panes to normal layout."""
        if self._maximized_pane is None:
            return
        for tid in ("recipes", "agents", "tools", "engines", "models"):
            try:
                self._app.query_one(f"#{tid}-body").remove_class("maximized-detail", "maximized-log")
                self._app.query_one(f"#{tid}-toolbar").remove_class("pane-hidden")
            except Exception:
                pass
        try:
            self._app.query_one("#gen-screen-layout").remove_class("maximized-preview", "maximized-log")
        except Exception:
            pass
        from .widgets import LogTab

        try:
            self._app.query_one(LogTab).remove_class("maximized-log")
        except Exception:
            pass
        self._maximized_pane = None
        if notify:
            self._app.notify("Restored normal view", timeout=2.0)
