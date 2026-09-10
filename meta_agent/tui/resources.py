"""Resource management and rendering coordinator for MetaAgentTUI."""

from typing import Any, TYPE_CHECKING

from textual import events
from textual.widgets import Button, Label, ListItem, ListView, LoadingIndicator, Markdown, TextArea

from ..api import (
    list_agents,
    list_engines,
    list_models,
    list_recipes,
    list_tools,
)
from .helpers import (
    agent_markdown,
    engine_markdown,
    filter_items,
    model_markdown,
    recipe_markdown,
    tool_markdown,
)

if TYPE_CHECKING:
    from .app import MetaAgentTUI


class ResourceManager:
    """Manages background loading, live filtering, list rendering, and detail view selection."""

    def __init__(self, app: "MetaAgentTUI") -> None:
        """Initialize with parent app reference."""
        self._app = app

    def load_resource(self, tid: str) -> None:
        """Load resources for a tab in background thread and trigger render."""
        app = self._app
        if tid == "recipes":
            app._recipes = list_recipes()
        elif tid == "agents":
            app._agents = list_agents()
        elif tid == "tools":
            app._tools = list_tools()
        elif tid == "engines":
            app._engines = list_engines(default_engine=app._engine)
        elif tid == "models":
            app._models = list_models(engine=app._engine)
        app.app.call_from_thread(self.render_tab, tid)

    def render_list(self, tid: str, items: list[Any]) -> None:
        """Populate ListView with resource items and hide loading indicator."""
        app = self._app
        lv = app.query_one(f"#{tid}-list", ListView)
        lv.clear()
        for item in items:
            lv.append(ListItem(Label(item.name)))
        app.query_one(f"#{tid}-loading", LoadingIndicator).display = False

    def render_tab(self, tid: str) -> None:
        """Render filtered resource list for a given tab."""
        app = self._app
        items_map: dict[str, list[Any]] = {
            "recipes": app._recipes,
            "agents": app._agents,
            "tools": app._tools,
            "engines": app._engines,
            "models": app._models,
        }
        all_items = items_map.get(tid, [])
        try:
            search = app.query_one(f"#{tid}-search", TextArea).text
        except Exception:
            return
        items = filter_items(all_items, search)

        if tid == "recipes":
            app._displayed_recipes = items
            app._selected_recipe = None
            try:
                app.query_one("#recipes-chat-btn", Button).display = False
                app.query_one("#recipes-refactor-btn", Button).display = False
                app.query_one("#recipes-edit-btn", Button).display = False
                app.query_one("#recipes-delete-btn", Button).display = False
            except Exception:
                pass
            app._update_refactor_selection_list(app._recipes)
        elif tid == "agents":
            app._displayed_agents = items
        elif tid == "tools":
            app._displayed_tools = items
        elif tid == "engines":
            app._displayed_engines = items
        elif tid == "models":
            app._displayed_models = items

        self.render_list(tid, items)

    def handle_descendant_focus(self, event: events.DescendantFocus) -> None:
        """Auto-select the first item if list gains focus and no item is selected yet."""
        app = self._app
        if isinstance(event.widget, ListView):
            lv = event.widget
            if lv.id == "recipes-list" and lv.index is None and len(app._displayed_recipes) > 0:
                lv.index = 0
                self.select_recipe_by_index(0)
            elif lv.id == "agents-list" and lv.index is None and len(app._displayed_agents) > 0:
                lv.index = 0
                self.select_agent_by_index(0)
            elif lv.id == "engines-list" and lv.index is None and len(app._displayed_engines) > 0:
                lv.index = 0
                self.select_engine_by_index(0)
            elif lv.id == "models-list" and lv.index is None and len(app._displayed_models) > 0:
                lv.index = 0
                self.select_model_by_index(0)

    def select_recipe_by_index(self, index: int) -> None:
        """Select recipe at index and render markdown preview with action buttons."""
        app = self._app
        if 0 <= index < len(app._displayed_recipes):
            app._selected_recipe = app._displayed_recipes[index]
            md = recipe_markdown(app._selected_recipe)
            app.query_one("#recipes-markdown", Markdown).update(md)
            app.query_one("#recipes-chat-btn", Button).display = True
            app.query_one("#recipes-refactor-btn", Button).display = True
            app.query_one("#recipes-edit-btn", Button).display = True
            app.query_one("#recipes-delete-btn", Button).display = True

    def select_agent_by_index(self, index: int) -> None:
        """Select agent at index and render markdown preview."""
        app = self._app
        if 0 <= index < len(app._displayed_agents):
            app._selected_agent = app._displayed_agents[index]
            md = agent_markdown(app._selected_agent)
            app.query_one("#agents-markdown", Markdown).update(md)

    def select_tool_by_index(self, index: int) -> None:
        """Select tool at index and render markdown preview."""
        app = self._app
        if 0 <= index < len(app._displayed_tools):
            app._selected_tool = app._displayed_tools[index]
            md = tool_markdown(app._selected_tool)
            app.query_one("#tools-markdown", Markdown).update(md)

    def select_engine_by_index(self, index: int) -> None:
        """Select engine at index and render markdown preview."""
        app = self._app
        if 0 <= index < len(app._displayed_engines):
            app._selected_engine = app._displayed_engines[index]
            md = engine_markdown(app._selected_engine)
            app.query_one("#engines-markdown", Markdown).update(md)

    def select_model_by_index(self, index: int) -> None:
        """Select model at index and render markdown preview."""
        app = self._app
        if 0 <= index < len(app._displayed_models):
            app._selected_model = app._displayed_models[index]
            md = model_markdown(app._selected_model)
            app.query_one("#models-markdown", Markdown).update(md)
